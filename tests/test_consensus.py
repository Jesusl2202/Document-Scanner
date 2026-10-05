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
        self.assertEqual(r['fields']['total'],'270.00');self.assertIn('total:from_subtotal',r['alerts'])
        r=extract(ocr_lines(['SUB TOTAL 270.00','TAX 20.00']),CONFIG)
        self.assertNotEqual(r['fields']['total'],'270.00')

    def test_helpers(self):
        self.assertTrue(near('758.70','758.78'));self.assertTrue(near('65.50','5.50'))
        self.assertFalse(near('9.49','9.97'));self.assertFalse(near('1.00','1.00'))
        self.assertEqual(year_of('2018-03-18'),2018);self.assertEqual(year_of('AMBIGUOUS:09/03/2018'),2018)


if __name__=='__main__':unittest.main()
