import unittest,copy
from test_pipeline import CONFIG,ocr_lines
from lector_facturas.consensus import extract,clean,near,year_of

def at(rows):
    """Filas (texto, y) con cajas explícitas para probar geometría."""
    words=[];x=10
    for i,(text,y) in enumerate(rows):
        x=10
        for w in text.split():
            words.append(dict(text=w,box=[x,y,x+len(w)*10,y+20],confidence=90,line_id=str(i)));x+=len(w)*10+10
    return dict(words=words,height=2000)

class V7Tests(unittest.TestCase):
    def test_glyph_noise_only_inside_decimal_tokens(self):
        self.assertEqual(clean('NET TOTAL &.00'),'net total 8.00')
        self.assertEqual(clean('TOTAL PM7.00'),'total 7.00')
        self.assertEqual(clean('FOOD & DRINK'),'food & drink')
        self.assertEqual(clean('TOTA LI 7.00'),'total 7.00')

    def test_cash_minus_change_picks_rounded_total_that_was_read(self):
        o=ocr_lines(['TOTAL SALES (INCLUSIVE GST) RM 27.28','ROUNDING RM 27.30','CASH RM 50.00','CHANGE RM 22.70'])
        self.assertEqual(extract(o,CONFIG)['fields']['total'],'27.30')

    def test_payment_never_invents_an_unread_amount(self):
        o=ocr_lines(['CASH 200.00','CHANGE 16.00','TOTAL (INCLUSIVE OF GST) 190.00'])
        self.assertEqual(extract(o,CONFIG)['fields']['total'],'190.00')   # 200-16=184 no aparece: no se usa

    def test_cash_without_label_total_uses_exact_cash_only_when_nothing_better(self):
        self.assertEqual(extract(ocr_lines(['SUBTUTA RM20. 40','CASH RM20, 40']),CONFIG)['fields']['total'],'20.40')
        self.assertEqual(extract(ocr_lines(['TOTAL 12.50','CASH 20.00']),CONFIG)['fields']['total'],'12.50')

    def test_card_digits_are_not_a_total(self):
        o=ocr_lines(['TOTAL $29.92','VISA ENDING 8768'])
        self.assertEqual(extract(o,CONFIG)['fields']['total'],'$29.92')

    def test_strong_label_beats_repeated_generic_total(self):
        a=ocr_lines(['TOTAL SUPPLIES 25.32','TOTAL PAYABLE 65.50'])
        b=ocr_lines(['TOTAL SUPPLIES 25.32'])
        self.assertEqual(extract(dict(a,views=[a,b,b,b]),CONFIG)['fields']['total'],'65.50')

    def test_ocr_misread_votes_support_the_value_they_resemble(self):
        a=ocr_lines(['TOTAL INC. GST 758.70']);b=ocr_lines(['TOTAL INC. GST 758.78']);c=ocr_lines(['FINAL TOTAL 733.70']);d=ocr_lines(['FINAL TOTAL 753.70'])
        r=extract(dict(a,views=[a,a,c,c,b,d]),CONFIG)
        self.assertEqual(r['fields']['total'],'758.70')

    def test_tie_is_resolved_by_primary_reading(self):
        a=dict(ocr_lines(['TOTAL 12.50']),options=dict(preprocess='resize',psm=6))
        b=dict(ocr_lines(['TOTAL 72.50']),options=dict(preprocess='otsu',psm=6))
        self.assertEqual(extract(dict(a,views=[b,a]),CONFIG)['fields']['total'],'12.50')

    def test_three_number_row_must_balance_exactly(self):
        r=extract(ocr_lines(['1,39 11,61 13,00']),CONFIG)['fields']
        self.assertEqual((r['subtotal'],r['tax'],r['total']),('11,61','1,39','13,00'))
        r=extract(ocr_lines(['1,38 11,61 13,00']),CONFIG)['fields']
        self.assertIsNone(r['subtotal']);self.assertIsNone(r['tax'])

    def test_three_number_row_split_in_two_overlapping_rows(self):
        o=at([('20,62 4,33',1600),('24,95',1620)])
        r=extract(o,CONFIG)['fields']
        self.assertEqual((r['subtotal'],r['tax'],r['total']),('20,62','4,33','24,95'))

    def test_item_rows_do_not_become_a_balance(self):
        r=extract(ocr_lines(['2 4.00 8.00']),CONFIG)['fields']
        self.assertIsNone(r['tax'])

    def test_tax_with_base_amount_returns_the_tax_not_the_base(self):
        self.assertEqual(extract(ocr_lines(['T = ID TAX 6.0000% ON $68.26 $4.10']),CONFIG)['fields']['tax'],'$4.10')

    def test_expiry_date_is_not_the_receipt_date(self):
        o=ocr_lines(['09/02/2013 12:43 PM EXPIRES 12/01/13'])
        self.assertEqual(extract(o,CONFIG)['fields']['date'],'09/02/2013')

    def test_implausible_or_truncated_years_are_rejected(self):
        self.assertIsNone(extract(ocr_lines(['OCTOBER 11, 201']),CONFIG)['fields']['date'])
        a=ocr_lines(['OCTOBER 11, 201!']);b=ocr_lines(['OCTOBER 11, 2017'])
        self.assertEqual(extract(dict(a,views=[a,a,b]),CONFIG)['fields']['date'],'OCTOBER 11, 2017')

    def test_dates_with_mixed_separators_misread_month_and_compact_form(self):
        self.assertEqual(extract(ocr_lines(['27. 6- 2015']),CONFIG)['fields']['date'],'27/6/2015')
        self.assertEqual(extract(ocr_lines(['26 3an 2018 21:58:49']),CONFIG)['fields']['date'],'26 jan 2018')
        self.assertEqual(extract(ocr_lines(['20150923']),CONFIG)['fields']['date'],'2015-09-23')

    def test_total_zero_with_decimals_is_kept(self):
        self.assertEqual(extract(ocr_lines(['TOTAL $0.00']),CONFIG)['fields']['total'],'$0.00')

    def test_truncated_integer_total_loses_to_decimal_total(self):
        a=ocr_lines(['GRAND TOTAL 30']);b=ocr_lines(['GRAND TOTAL 029,30'])
        self.assertEqual(extract(dict(a,views=[a,a,b]),CONFIG)['fields']['total'],'029,30')

    def test_total_from_subtotal_is_flagged(self):
        r=extract(ocr_lines(['SUB TOTAL 270.00']),CONFIG)
        self.assertIsNone(r['fields']['total']);self.assertIn('total:subtotal_no_confirma_total',r['alerts'])
        r=extract(ocr_lines(['SUB TOTAL 270.00','TAX 20.00']),CONFIG)
        self.assertNotEqual(r['fields']['total'],'270.00')

    def test_helpers(self):
        self.assertTrue(near('758.70','758.78'));self.assertTrue(near('65.50','5.50'))
        self.assertFalse(near('9.49','9.97'));self.assertFalse(near('1.00','1.00'))
        self.assertEqual(year_of('2018-03-18'),2018);self.assertEqual(year_of('AMBIGUOUS:09/03/2018'),2018)


if __name__=='__main__':unittest.main()


class FocusedTests(unittest.TestCase):
    def test_two_views_recover_missing_amount(self):
        cfg=copy.deepcopy(CONFIG)
        cfg['ocr']['focused_reading']={'enabled':True,'minimum_agreement':2,'minimum_confidence':35}
        ocr=ocr_lines(['TOTAL'])
        ocr['focused_regions']=[{'field':'total','box':[0,0,100,30],'readings':[
            {'text':'12.50','confidence':85,'preprocess':'resize','psm':7},
            {'text':'12,50','confidence':80,'preprocess':'blue_ink','psm':7}]}]
        self.assertEqual(extract(ocr,cfg)['fields']['total'],'12,50')
        ocr['focused_regions'][0]['readings'].pop()
        self.assertIsNone(extract(ocr,cfg)['fields']['total'])
    def test_missing_decimal_is_not_invented(self):
        ocr=ocr_lines(['TOTAL'])
        ocr['focused_regions']=[{'field':'total','box':[0,0,100,30],'readings':[
            {'text':'1250','confidence':85,'preprocess':'resize','psm':7},
            {'text':'1250','confidence':80,'preprocess':'blue_ink','psm':7}]}]
        self.assertIsNone(extract(ocr,CONFIG)['fields']['total'])
    def test_duplicate_same_view_does_not_confirm_value(self):
        ocr=ocr_lines(['TOTAL']);reading={'text':'12.50','confidence':90,'preprocess':'resize','psm':7}
        ocr['focused_regions']=[{'field':'total','box':[0,0,100,30],'readings':[reading,reading]}]
        self.assertIsNone(extract(ocr,CONFIG)['fields']['total'])
    def test_baseline_remains_reproducible(self):
        cfg=copy.deepcopy(CONFIG)
        cfg['accounting_improvements']=False;cfg['ocr']['focused_reading']['enabled']=False
        self.assertEqual(extract(ocr_lines(['SUB TOTAL 270.00']),cfg)['fields']['total'],'270.00')


class AccountingTests(unittest.TestCase):
    def test_subtotal_before_tax_not_tax_inclusive_subtotal(self):
        o=ocr_lines(['Sub Total 40.00','Tax 4.00','Sub Total 44.00','TOTAL 50.00'])
        f=extract(o,CONFIG)['fields']
        self.assertEqual(f['subtotal'],'40.00')
        self.assertEqual(f['tax'],'4.00')

    def test_does_not_invent_missing_tax_from_difference(self):
        o=ocr_lines(['Subtotal 40.00','TOTAL 44.00'])
        self.assertIsNone(extract(o,CONFIG)['fields']['tax'])

    def test_vertical_summary_uses_observed_numbers(self):
        f=extract(ocr_lines(['40.00','4.00','TOTAL 44.00']),CONFIG)['fields']
        self.assertEqual(f['subtotal'],'40.00');self.assertEqual(f['tax'],'4.00')

    def test_service_charge_is_not_unlabelled_tax(self):
        f=extract(ocr_lines(['Subtotal 40.00','Service Charge 4.00','TOTAL 44.00']),CONFIG)['fields']
        self.assertIsNone(f['tax'])

    def test_fiscal_table_supports_zero_tax(self):
        f=extract(ocr_lines(['Net Tax Gross','40.00 0.00 40.00']),CONFIG)['fields']
        self.assertEqual(f['subtotal'],'40.00');self.assertEqual(f['tax'],'0.00')

    def test_disabled_crops_are_not_reused(self):
        o=ocr_lines(['Date 2020-01-15'])
        o['focused_regions']=[{'field':'tax','box':[0,0,10,10],'readings':[
            {'text':'3.00','confidence':95,'preprocess':p,'psm':7} for p in ('resize','otsu')]}]
        self.assertIsNone(extract(o,CONFIG)['fields']['tax'])


class ContextAmountTests(unittest.TestCase):
    def test_payment_matches_observed_summary_not_first_cash(self):
        f=extract(ocr_lines(['CASH 20.00','CASH 10.00','Subtotal 23.06','Tax 1.93','Payment 24.99','Change 5.01']),CONFIG)['fields']
        self.assertEqual(f['total'],'24.99')

    def test_tax_inclusive_subtotal_does_not_replace_final_total(self):
        f=extract(ocr_lines(['Sub Total 96.55','Tax 8.57','Sub Total 105.12','TOTAL 122.50']),CONFIG)['fields']
        self.assertEqual(f['total'],'122.50')

    def test_fuel_sale_is_not_price_per_gallon(self):
        f=extract(ocr_lines(['PRICE/G 3.999','FUEL SALE 3.35']),CONFIG)['fields']
        self.assertEqual(f['total'],'3.35')

    def test_unread_total_not_created_by_sum(self):
        f=extract(ocr_lines(['Subtotal 23.06','Tax 1.93']),CONFIG)['fields']
        self.assertIsNone(f['total'])

    def test_total_with_deposit(self):
        f=extract(ocr_lines(['Total 160.00','Deposit 63.00','Balance Due 97.00']),CONFIG)['fields']
        self.assertEqual(f['total'],'160.00')


class SpatialAmountTests(unittest.TestCase):
    def test_currency_suffix_below_label(self):
        f=extract(ocr_lines(['SUBTOTAL','12.34 SR']),CONFIG)['fields']
        self.assertEqual(f['subtotal'],'12.34')

    def test_spatial_recovery_does_not_cross_another_label(self):
        from lector_facturas.consensus import spatial_amount_candidates
        from lector_facturas.geometry import grouped
        from lector_facturas.common import FIELDS
        found=[]
        spatial_amount_candidates(grouped(ocr_lines(['SUBTOTAL','TAX 1.00','TOTAL 12.00'])),CONFIG,lambda *args:found.append(args),{f:[] for f in FIELDS})
        self.assertFalse(any(x[0]=='subtotal' for x in found))

class SemanticAmountTests(unittest.TestCase):
    def read(self, lines, initial=None):
        from lector_facturas.consensus import semantic_amounts
        from lector_facturas.common import FIELDS, normalize
        view=ocr_lines(lines)
        result={'fields':dict.fromkeys(FIELDS),'evidence':{f:[] for f in FIELDS},'alerts':[]}
        result['fields'].update(initial or {})
        semantic_amounts(dict(views=[view,copy.deepcopy(view)]),CONFIG,result)
        return {f:normalize(f,v,CONFIG['normalization']) for f,v in result['fields'].items()}

    def test_multilingual_subtotal_labels(self):
        for label in ['SOUS TOTAL','SUBTTL','SUBTOTALE','BASE IMPONIBLE','NETTO(1) EUR']:
            self.assertEqual(self.read([label+' 42.25'])['subtotal'],'42.25')

    def test_percentage_is_not_tax_amount(self):
        self.assertEqual(self.read(['TVA 8% 16.00'])['tax'],'16.00')

    def test_tax_base_table_selects_observed_tax(self):
        self.assertEqual(self.read(['IVA 10% 50.00 5.00'])['tax'],'5.00')

    def test_tax_before_label_inclusive_rate(self):
        self.assertEqual(self.read(['5.00 BTW 10% 55.00'])['tax'],'5.00')

    def test_tax_amount_can_start_with_decimal_point(self):
        self.assertEqual(self.read(['TAX .45 BAL 7.95'])['tax'],'0.45')

    def test_identifier_and_rate_do_not_invent_tax(self):
        self.assertIsNone(self.read(['GST REG NUMBER 12345','VAT 10%'])['tax'])

    def test_tip_is_not_tax(self):
        r=self.read(['AMOUNT 40.00','TIP 5.00','TOTAL 45.00'])
        self.assertEqual(r['subtotal'],'40.00');self.assertIsNone(r['tax'])

    def test_keep_supported_existing_total(self):
        r=self.read(['TOTAL 48.50','GRAND TOTAL 48.60'],{'total':'48.50'})
        self.assertEqual(r['total'],'48.50')

    def test_do_not_cross_other_label_to_get_value(self):
        r=self.read(['SUBTOTAL','TAX','7.00'])
        self.assertIsNone(r['subtotal'])

    def test_excluding_tax_is_not_gross_total(self):
        self.assertIsNone(self.read(['TOTAL EXCLUDING GST 70.00'])['total'])

class JointConsistencyTests(unittest.TestCase):
    def solve(self,lines):
        from lector_facturas.consensus import document_consistency
        from lector_facturas.common import FIELDS
        view=ocr_lines(lines)
        result={'fields':dict.fromkeys(FIELDS),'evidence':{f:[] for f in FIELDS},'alerts':[]}
        result['fields'].update(subtotal='4.00',total='4.40',tax='40.00')
        for f,y,value in [('subtotal',0,'4.00'),('total',60,'4.40')]:
            result['evidence'][f]=[dict(value=value,normalized=value,score=9,view=i,box=[10,y,160,y+20]) for i in (0,1)]
        document_consistency(dict(views=[view,copy.deepcopy(view)]),CONFIG,result)
        return result

    def test_decimal_repair_requires_rate_and_totals(self):
        result=self.solve(['SUBTOTAL 4.00','TAX 10% 40','TOTAL 4.40'])
        self.assertEqual(result['fields']['tax'],'0.40')
        self.assertEqual(result['evidence']['tax'][0]['original_token'],'40')

    def test_no_decimal_repair_without_rate(self):
        result=self.solve(['SUBTOTAL 4.00','TAX 40','TOTAL 4.40'])
        self.assertEqual(result['fields']['tax'],'40.00')

    def test_no_simple_balance_when_tip_present(self):
        result=self.solve(['SUBTOTAL 4.00','TAX 10% 40','TOTAL 4.40','TIP .40'])
        self.assertEqual(result['fields']['tax'],'40.00')

class StructuredFieldsTests(unittest.TestCase):
    def result(self, lines, fields=None):
        from lector_facturas.consensus import structured_fields
        from lector_facturas.common import FIELDS
        cfg=copy.deepcopy(CONFIG);o=at([(s,100+i*35) for i,s in enumerate(lines)])
        o['text']='\n'.join(lines)
        result={'fields':dict.fromkeys(FIELDS),'evidence':{f:[] for f in FIELDS},'alerts':[]}
        result['fields'].update(fields or {})
        structured_fields(dict(o,views=[o,copy.deepcopy(o),copy.deepcopy(o)]),cfg,result)
        return result

    def test_food_total_is_subtotal_and_due_is_final(self):
        r=self.result(['FOOD TOTAL 80.00','SVC CHG TOTAL 12.00','TAX 4.00','TOTAL DUE 96.00'])
        self.assertEqual(r['fields']['subtotal'],'80.00')
        self.assertEqual(r['fields']['total'],'96.00')

    def test_tax_registration_never_becomes_tax_amount(self):
        r=self.result(['GST NO 12345678','SUBTOTAL 20.00','TOTAL 21.00'])
        self.assertIsNone(r['fields']['tax'])

    def test_observed_iso_date_and_expiry(self):
        r=self.result(['DATE 2024-05-23','EXPIRES 2025-06-24'])
        self.assertEqual(r['fields']['date'],'2024-05-23')

    def test_discount_not_forced_to_balance(self):
        r=self.result(['SUBTOTAL 50.00','TAX 5.00','DISCOUNT 10.00','TOTAL DUE 45.00'])
        self.assertEqual(r['fields']['total'],'45.00')

    def test_currency_suffix_normalization(self):
        from lector_facturas.common import money
        self.assertEqual(money('123,45EUR'),'123.45')
        self.assertEqual(money('123.45USD'),'123.45')
        self.assertIsNone(money('123.45unknown'))
        self.assertIsNone(money('12%'))

    def test_invoice_header_column(self):
        r=self.result(['N. DE FACTURA','AB-23456'])
        self.assertEqual(r['fields']['document_number'],'AB-23456')

    def test_dates_in_spanish_and_french(self):
        from lector_facturas.common import normalize_date
        self.assertEqual(normalize_date('18AVR2014'),'2014-04-18')
        self.assertEqual(normalize_date('23 DIC 2024'),'2024-12-23')
        self.assertIsNone(normalize_date('31 AVR 2014'))
        r=self.result(['VEN 18 AVR 2014 16:23'])
        self.assertEqual(normalize_date(r['fields']['date']),'2014-04-18')

class ObservedAccountingTests(unittest.TestCase):
    def check(self,lines,fields):
        from lector_facturas.consensus import observed_accounting
        from lector_facturas.common import FIELDS
        v=at([(s,100+i*35) for i,s in enumerate(lines)]);v['text']='\n'.join(lines)
        r=dict(fields=dict.fromkeys(FIELDS),evidence={f:[] for f in FIELDS},alerts=[])
        r['fields'].update(fields)
        observed_accounting(dict(v,views=[v,copy.deepcopy(v)]),CONFIG,r)
        return r

    def test_discount_and_shipping_select_observed_tax(self):
        r=self.check(['SUBTOTAL 100.00','TAX 20.00','DISCOUNT 10.00','SHIPPING 5.00','TOTAL 115.00'],dict(subtotal='100.00',tax='21.00',total='115.00'))
        self.assertEqual(r['fields']['tax'],'20.00')
        self.assertEqual(r['accounting_summary']['adjustments'],{'discount':'10.00','shipping':'5.00'})

    def test_unread_difference_never_becomes_tax(self):
        r=self.check(['SUBTOTAL 100.00','TOTAL 120.00'],dict(subtotal='100.00',tax=None,total='120.00'))
        self.assertIsNone(r['fields']['tax'])

    def test_multiple_discounts_do_not_assume_one(self):
        r=self.check(['SUBTOTAL 100.00','TAX 20.00','DISCOUNT 10.00','DISCOUNT 5.00','TOTAL 110.00'],dict(subtotal='100.00',tax='21.00',total='110.00'))
        self.assertEqual(r['fields']['tax'],'21.00')

    def test_inclusive_tax_not_added_twice(self):
        r=self.check(['SUBTOTAL 100.00','TAX 10.00','TOTAL 100.00'],dict(subtotal='100.00',tax='10.00',total='100.00'))
        self.assertEqual(r['fields']['total'],'100.00')

    def test_default_parameterization_preserves_prediction(self):
        o=ocr_lines(['SUBTOTAL 20.00','TAX 2.00','TOTAL 22.00']);c=copy.deepcopy(CONFIG)
        a=extract(o,c)['fields'];c['consensus_parameters']=dict(primary_weight=1.5,vote_weight=2.,fuzzy_weight=.5,balance_bonus=3.)
        self.assertEqual(a,extract(o,c)['fields'])

    def test_geometry_cache_does_not_survive_a_prediction(self):
        from lector_facturas.geometry import grouped,row_cache
        o=at([('TOTAL 20.00',100)])
        with row_cache():
            first=grouped(o);first.append({'text':'spurious'})
            self.assertEqual(len(grouped(o)),1)
        o['words'][1]['text']='25.00'
        self.assertIn('25.00',grouped(o)[0]['text'])

class OptimizationSplitTests(unittest.TestCase):
    def test_validation_split_excludes_test_duplicates_and_separates_hashes(self):
        from lector_facturas.experiments import validation_samples
        rows=[]
        for ds in ('sroie','wildreceipt'):
            for i in range(5):rows.append(dict(id=ds+str(i),dataset=ds,split='validation',source_split='train',sha256=ds+str(i)))
        rows.append(dict(rows[0],id='test_copy',split='test',source_split='test'))
        a,b=validation_samples(rows,2,2,42)
        self.assertFalse({r['sha256'] for r in a}&{r['sha256'] for r in b})
        self.assertNotIn(rows[0]['sha256'],{r['sha256'] for r in a+b})
        self.assertEqual(len(a),4);self.assertEqual(len(b),4)
        with self.assertRaises(ValueError):validation_samples(rows,10,10)

    def test_rescue_keeps_existing_fields(self):
        from unittest.mock import patch
        from lector_facturas.common import FIELDS
        import lector_facturas.consensus as c
        def inner(o,cfg):
            v='99.00' if cfg.get('confidence_consensus') else '25.00'
            return dict(fields=dict.fromkeys(FIELDS)|{'total':v},evidence={f:[] for f in FIELDS},alerts=[])
        with patch.object(c,'_extract_all_stages',side_effect=inner):
            r=c.extract({},dict(CONFIG,confidence_rescue=True))
        self.assertEqual(r['fields']['total'],'25.00')
