"""Pruebas de errores relevantes: normalización, evaluación, fuga y adaptadores."""
import json
from pathlib import Path
import tempfile
import unittest
from PIL import Image
from lector_facturas.common import FIELDS, gold_empty, money, normalize_date, write_jsonl
from lector_facturas.datasets import sroie, wildreceipt, prepare
from lector_facturas.extraction import extract, validate
from lector_facturas.evaluation import evaluate
from lector_facturas.google_ai import parse_entities
from lector_facturas.cli import compare

ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT/'configs/default.json').read_text())


def ocr_lines(texts):
    words=[]
    for i,text in enumerate(texts):
        x=10
        for word in text.split():
            words.append({'text':word,'box':[x,i*30,x+len(word)*10,i*30+20],'line_id':str(i),'confidence':90})
            x += len(word)*10+10
    return {'words':words}


class NormalizationTests(unittest.TestCase):
    def test_amount_formats(self):
        self.assertEqual(money('1,234.56'), '1234.56')
        self.assertEqual(money('1.234,56'), '1234.56')
        self.assertIsNone(money('1,234'))
        self.assertIsNone(money('12%'))
        self.assertIsNone(money('12,34.56'))
        self.assertEqual(money('(12.00)'), '-12.00')

    def test_dates_not_guessed(self):
        self.assertEqual(normalize_date('2026-09-27'), '2026-09-27')
        self.assertTrue(normalize_date('03/04/2026').startswith('AMBIGUOUS:'))
        self.assertEqual(normalize_date('03/04/2026','dmy'), '2026-04-03')
        self.assertIsNone(normalize_date('31/02/2026'))

    def test_distinguish_total_tax_subtotal(self):
        result=extract(ocr_lines(['SUBTOTAL 100.00','TAX 12% 12.00','TOTAL 112.00','TOTAL ITEMS 2']),CONFIG)
        self.assertEqual(result['fields']['subtotal'],'100.00')
        self.assertEqual(result['fields']['tax'],'12.00')
        self.assertEqual(result['fields']['total'],'112.00')

    def test_percentage_not_partial_amount(self):
        result=extract(ocr_lines(['TAX 12.5%']),CONFIG)
        self.assertIsNone(result['fields']['tax'])

    def test_abstains_conflicting_totals(self):
        result=extract(ocr_lines(['TOTAL 20.00','TOTAL 30.00']),CONFIG)
        self.assertIsNone(result['fields']['total'])
        self.assertIn('total:ambiguous_candidates',result['alerts'])

    def test_tax_id_is_not_tax_amount(self):
        result=extract(ocr_lines(['TAX ID 12345678','INVOICE NO: 001-002-000123']),CONFIG)
        self.assertEqual(result['fields']['tax_id'],'12345678')
        self.assertIsNone(result['fields']['tax'])
        self.assertEqual(result['fields']['document_number'],'001-002-000123')

    def test_balance_opt_in(self):
        from copy import deepcopy
        cfg=deepcopy(CONFIG)
        values={'subtotal':'100','tax':'12','total':'112'}
        self.assertEqual(validate(values,cfg)['amount_balance'],'not_applicable')
        cfg['validation']['check_amount_balance']=True
        self.assertEqual(validate(values,cfg)['amount_balance'],'consistent')
        values['total']='115'
        self.assertEqual(validate(values,cfg)['amount_balance'],'inconsistent_review')


class EvaluationTests(unittest.TestCase):
    def test_bad_value_fp_fn_and_unannotated_excluded(self):
        g=gold_empty();g['total']={'status':'annotated','value':'100.00'}
        r={'id':'s/1','dataset':'s','gold':g,'regions':[],'issues':[]}
        p={'id':'s/1','status':'ok','fields':{'total':'90.00','subtotal':'100'},'elapsed_seconds':1}
        with tempfile.TemporaryDirectory() as td:
            summary=evaluate([r],[p],CONFIG,td)
            import pandas as pd
            m=pd.read_csv(Path(td)/'metrics.csv')
            row=m[(m.dataset=='s')&(m.field=='total')].iloc[0]
            self.assertEqual((row.tp,row.fp,row.fn),(0,1,1))
            self.assertEqual(summary['evaluated_field_instances'],1)
            self.assertEqual(summary['micro_exact_match'],0)

    def test_missing_prediction_counts_failure(self):
        g=gold_empty();g['total']={'status':'annotated','value':'100'}
        r={'id':'s/1','dataset':'s','gold':g,'regions':[],'issues':[]}
        with tempfile.TemporaryDirectory() as td:
            s=evaluate([r],[],CONFIG,td)
            self.assertEqual(s['execution_success_rate'],0)
            self.assertEqual(s['micro_exact_match'],0)

    def test_google_entities_ambiguous(self):
        entities=[{'type_':'total_amount','mention_text':'100'},{'type_':'total_amount','mention_text':'200'}]
        self.assertIsNone(parse_entities(entities,CONFIG)['fields']['total'])

    def test_compare_requires_same_documents(self):
        with tempfile.TemporaryDirectory() as td:
            a,b=Path(td)/'a',Path(td)/'b'
            write_jsonl(a/'evaluation_manifest.jsonl',[{'id':'x','sha256':'a','gold':{}}])
            write_jsonl(b/'evaluation_manifest.jsonl',[{'id':'y','sha256':'a','gold':{}}])
            with self.assertRaises(ValueError):compare(a,b,Path(td)/'out')


class AdapterTests(unittest.TestCase):
    def test_sroie_commas_and_no_company_as_taxid(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            for folder in ['img','box','entities']:(root/'train'/folder).mkdir(parents=True)
            Image.new('RGB',(100,100),'white').save(root/'train/img/a.jpg')
            (root/'train/box/a.txt').write_bytes('0,0,80,0,80,20,0,20,COMPANY, £'.encode('cp1252'))
            (root/'train/entities/a.txt').write_text(json.dumps({'company':'A','date':'2026-09-27','total':'100'}))
            rows=sroie(root)
            self.assertEqual(rows[0]['regions'][0]['text'],'COMPANY, £')
            self.assertIn('encoding_fallback_cp1252', rows[0]['issues'])
            self.assertEqual(rows[0]['gold']['tax_id']['status'],'unannotated')
            self.assertEqual(rows[0]['gold']['total']['value'],'100')

    def test_wild_ambiguous_and_official_test_reserved(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);im=root/'same.png';Image.new('RGB',(100,100),'white').save(im)
            (root/'class_list.txt').write_text('0 Ignore\n7 Date_value\n17 Subtotal_value\n19 Tax_value\n23 Total_value\n')
            item={'file_name':'same.png','width':100,'height':100,'annotations':[
                {'box':[0,0,20,0,20,20,0,20],'label':23,'text':'100'},
                {'box':[0,30,20,30,20,50,0,50],'label':23,'text':'200'}]}
            for split in ['train','test']:(root/(split+'.txt')).write_text(json.dumps(item)+'\n')
            rows=prepare(None,root,root/'out',CONFIG)
            train=next(r for r in rows if r['source_split']=='train')
            test=next(r for r in rows if r['source_split']=='test')
            self.assertEqual(train['split'],'quarantine')
            self.assertEqual(test['split'],'test')
            self.assertEqual(train['gold']['total']['status'],'ambiguous')

    def test_path_escape_rejected(self):
        from lector_facturas.common import inside
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(ValueError):inside(td,'../outside.jpg')

if __name__=='__main__':unittest.main()
