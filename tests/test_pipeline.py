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

ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT/'configs/definitivo.json').read_text())


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
        self.assertIn('total:ambiguous_consensus',result['alerts'])

    def test_tax_id_is_not_tax_amount(self):
        result=extract(ocr_lines(['TAX ID 12345678','INVOICE NO: 001-002-000123']),CONFIG)
        self.assertEqual(result['fields']['tax_id'],'12345678')
        self.assertIsNone(result['fields']['tax'])
        self.assertEqual(result['fields']['document_number'],'001-002-000123')

    def test_balance_opt_in(self):
        from copy import deepcopy
        cfg=deepcopy(CONFIG)
        values={'subtotal':'100','tax':'12','total':'112'}
        cfg['validation']['check_amount_balance']=False
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


class PrintedInvoiceTests(unittest.TestCase):
    def test_currency_equivalence_without_changing_digits(self):
        self.assertEqual(money('USD$25.23'),'25.23')
        self.assertEqual(money('￡3.79'),'3.79')
        self.assertIsNone(money('1.827.76'))

    def test_issuer_not_recipient_and_commercial_not_fiscal_folio(self):
        o=ocr_lines(['FACTURA FOLIO Y SERIE: AB123','FOLIO FISCAL: 12345678-ABCD',
                     'EMISOR:','RFC: ABC900101XY1','RECEPTOR:','RFC: XYZ800202ZZ2'])
        f=extract(o,CONFIG)['fields']
        self.assertEqual(f['tax_id'],'ABC900101XY1')
        self.assertEqual(f['document_number'],'AB123')

    def test_recipient_rfc_is_not_issuer(self):
        o=ocr_lines(['RECEPTOR:','RFC: XYZ800202ZZ2'])
        self.assertIsNone(extract(o,CONFIG)['fields']['tax_id'])

    def test_tax_total_is_not_invoice_total(self):
        f=extract(ocr_lines(['HST TOTAL 6.24','CASH 54.24']),CONFIG)['fields']
        self.assertEqual(f['total'],'54.24')

    def test_subtotal_punctuation(self):
        self.assertEqual(extract(ocr_lines(['Sub, Total $14.58']),CONFIG)['fields']['subtotal'],'$14.58')

    def test_balance_warning_preserves_recognized_values(self):
        values=dict(date=None,tax_id=None,document_number=None,subtotal='10.00',tax='9.00',total='12.00')
        before=values.copy()
        self.assertEqual(validate(values,CONFIG)['amount_balance'],'inconsistent_review')
        self.assertEqual(values,before)

    def test_full_year_with_trailing_slash(self):
        from lector_facturas.common import normalize
        value=extract(ocr_lines(['Date 30. 07. 2007/']),CONFIG)['fields']['date']
        self.assertEqual(normalize('date',value,CONFIG['normalization']),'2007-07-30')

class UnseenRandomTests(unittest.TestCase):
    def test_persisted_reservation_never_repeats_ids_or_hashes(self):
        from lector_facturas.experiments import reserve_random_unseen
        rows=[dict(id=str(i),dataset='sroie',sha256=str(i),source_split='test',split='test') for i in range(6)]
        rows.append(dict(id='alias',dataset='sroie',sha256='0',source_split='test',split='test'))
        with tempfile.TemporaryDirectory() as td:
            ledger=Path(td)/'history.json'
            a,_=reserve_random_unseen(rows,{},ledger,3,seed=19)
            b,_=reserve_random_unseen(rows,{},ledger,3,seed=19)
            self.assertEqual(len(a),3);self.assertEqual(len(b),3)
            self.assertFalse({r['sha256'] for r in a}&{r['sha256'] for r in b})
            c,report=reserve_random_unseen(rows,{},ledger,3,seed=19)
            self.assertEqual(c,[]);self.assertEqual(report['status'],'sin_test_inedito')

    def test_random_test_excludes_training_duplicates(self):
        from lector_facturas.experiments import reserve_random_unseen
        rows=[dict(id='train',dataset='sroie',sha256='same',source_split='train',split='train'),
              dict(id='test',dataset='sroie',sha256='same',source_split='test',split='test')]
        with tempfile.TemporaryDirectory() as td:
            chosen,_=reserve_random_unseen(rows,{},Path(td)/'h.json',1)
            self.assertEqual(chosen,[])

    def test_existing_history_blocks_renamed_image(self):
        from lector_facturas.experiments import reserve_random_unseen
        row=dict(id='newname',dataset='sroie',sha256='seen',source_split='test',split='test')
        with tempfile.TemporaryDirectory() as td:
            chosen,_=reserve_random_unseen([row],{'oldname':'seen'},Path(td)/'h.json',1)
            self.assertEqual(chosen,[])

class RandomKnownTests(unittest.TestCase):
    def test_same_seed_cannot_repeat_previous_group_if_alternatives_exist(self):
        from lector_facturas.experiments import random_known_sample
        rows=[dict(id=str(i),dataset='sroie',sha256=str(i),source_split='test',split='test') for i in range(8)]
        first,_=random_known_sample(rows,3,seed=10)
        second,plan=random_known_sample(rows,3,seed=10,previous_ids=[r['id'] for r in first])
        self.assertNotEqual({r['id'] for r in first},{r['id'] for r in second})
        self.assertEqual(len(second),3);self.assertFalse(plan['independent_test'])

    def test_duplicate_images_and_training_duplicates_still_excluded(self):
        from lector_facturas.experiments import random_known_sample
        rows=[dict(id='a',dataset='sroie',sha256='1',source_split='test',split='test'),
              dict(id='alias',dataset='sroie',sha256='1',source_split='test',split='test'),
              dict(id='b',dataset='sroie',sha256='2',source_split='test',split='test'),
              dict(id='train',dataset='sroie',sha256='2',source_split='train',split='train')]
        selected,_=random_known_sample(rows,50,seed=2)
        self.assertEqual(len(selected),1);self.assertEqual(selected[0]['sha256'],'1')

    def test_full_pool_cannot_claim_different_group(self):
        from lector_facturas.experiments import random_known_sample
        rows=[dict(id='a',dataset='sroie',sha256='1',source_split='test',split='test')]
        with self.assertRaises(ValueError):random_known_sample(rows,50,previous_ids=['a'])
