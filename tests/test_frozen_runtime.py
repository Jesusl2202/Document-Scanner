import unittest,copy,os,io,hashlib
from tempfile import TemporaryDirectory
from pathlib import Path
from unittest.mock import patch
from lector_facturas.frozen_runtime import final_sample,ensure_model,review_notes

class FrozenTests(unittest.TestCase):
    def test_test_selection_excludes_seen_train_and_duplicates(self):
        rows=[]
        for d in ('sroie','wildreceipt'):
            for i in range(7):rows.append(dict(id=d+str(i),dataset=d,split='test',source_split='test',sha256=d+str(i)))
        rows.append(dict(id='train',dataset='sroie',split='train',source_split='train',sha256='sroie0'))
        before=copy.deepcopy(rows)
        chosen=final_sample(rows,3,{'sroie1'},{'wildreceipt1'})
        self.assertEqual(len(chosen),6)
        self.assertFalse({'sroie0','sroie1','wildreceipt1'}&{r['sha256'] for r in chosen})
        self.assertEqual(chosen,final_sample(rows[::-1],3,{'sroie1'},{'wildreceipt1'}))
        self.assertEqual(rows,before)

    def test_insufficient_test_does_not_use_train(self):
        with self.assertRaises(ValueError):final_sample([],1)

    def test_model_install_checks_hash_and_supplies_tsv_config(self):
        data=b'fake-model-for-test'
        with TemporaryDirectory() as d,patch.dict(os.environ),patch('lector_facturas.frozen_runtime.MODEL_SHA',hashlib.sha256(data).hexdigest()),patch('lector_facturas.frozen_runtime.urllib.request.urlopen',return_value=io.BytesIO(data)) as download:
            ensure_model(d);ensure_model(d)
            self.assertEqual(download.call_count,1)
            self.assertEqual((Path(d)/'configs/tsv').read_text(),'tessedit_create_tsv 1\n')

    def test_review_notes_do_not_change_predicted_fields(self):
        p={'fields':{'total':'12.00'},'alerts':['total:from_subtotal']};before=copy.deepcopy(p)
        self.assertTrue(any('confirmar' in s for s in review_notes(p)))
        self.assertEqual(p,before)


class UnseenInventoryTests(unittest.TestCase):
    def test_uses_all_remaining_and_excludes_seen_hashes_and_train_duplicates(self):
        from lector_facturas.experiments import unseen_test_inventory
        def row(i,h,split='test',dataset='sroie'):
            return {'id':i,'sha256':h,'source_split':split,'split':split,'dataset':dataset}
        rows=[row('train','trainhash','train'),row('old','oldhash'),row('copy','oldhash'),row('leak','trainhash'),row('a','a'),row('b','b','test','wildreceipt'),row('bcopy','b','test','wildreceipt')]
        selected,excluded=unseen_test_inventory(rows,{'old':'oldhash'})
        self.assertEqual({r['id'] for r in selected},{'a','b'})
        self.assertEqual(len(excluded),4)

    def test_empty_independent_test_is_an_error(self):
        from lector_facturas.experiments import unseen_test_inventory
        with self.assertRaises(ValueError):unseen_test_inventory([],{})
