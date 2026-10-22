import unittest,copy
from unittest.mock import patch
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from PIL import Image
import numpy as np
from test_pipeline import ocr_lines,CONFIG
from lector_facturas.common import normalize_date
from lector_facturas.preprocessing import prepare_image,original_box,otsu_threshold
from lector_facturas.ocr import transcribe

class OCRTests(unittest.TestCase):
    def test_scaled_box_roundtrip(self):
            im,t=prepare_image(Image.new('RGB',(100,200),'white'),{'preprocess':'resize','target_long_edge':600,'border':20})
            self.assertEqual(im.size,(340,640));self.assertEqual(original_box([50,80,170,320],t),[10,20,50,100])
    def test_threshold_constant(self):
            im=otsu_threshold(Image.new('L',(10,10),255));self.assertEqual(np.asarray(im).min(),255)
    def test_threshold_two_modes(self):
            a=np.array([[10,20,200,250]],dtype=np.uint8);im=otsu_threshold(Image.fromarray(a))
            self.assertEqual(np.asarray(im).tolist(),[[0,0,255,255]])
    def test_transcribe_reads_transformed_image_and_maps_boxes(self):
            with TemporaryDirectory() as d:
                source=Path(d)/'input.png';Image.new('RGB',(100,200),'white').save(source)
                options=copy.deepcopy(CONFIG['ocr']);options.pop('ensemble_views',None);options.update(preprocess='resize',target_long_edge=600,border=20)
                calls=[]
                def fake_run(args,**kwargs):
                    calls.append(args)
                    with Image.open(args[1]) as img:self.assertEqual(img.size,(340,640))
                    return SimpleNamespace(stdout='level\tpage_num\tblock_num\tpar_num\tline_num\tleft\ttop\twidth\theight\tconf\ttext\n5\t1\t1\t1\t1\t50\t80\t120\t240\t90\tTEST\n')
                with patch('lector_facturas.ocr.environment',return_value={'version':'fake','languages':['eng']}),patch('lector_facturas.ocr.subprocess.run',side_effect=fake_run):
                    first=transcribe(source,options,Path(d)/'cache')
                    second=transcribe(source,options,Path(d)/'cache')
                self.assertEqual(first['words'][0]['box'],[10,20,50,100]);self.assertTrue(second['cache_hit']);self.assertEqual(len(calls),1)


class FocusedOCRTests(unittest.TestCase):
    def test_labels_move_with_layout(self):
        from lector_facturas.ocr import find_field_regions
        ocr=ocr_lines(['TOTAL']);ocr.update(width=400,height=300)
        a=find_field_regions(ocr)
        for w in ocr['words']:w['box']=[w['box'][0]+100,w['box'][1]+80,w['box'][2]+100,w['box'][3]+80]
        b=find_field_regions(ocr)
        self.assertEqual(b[0]['box'][0]-a[0]['box'][0],100)
        self.assertEqual(b[0]['field'],'total')
    def test_table_header_and_authorization_date_excluded(self):
        from lector_facturas.ocr import find_field_regions
        ocr=ocr_lines(['V. TOTAL','Fecha de autorizacion']);ocr.update(width=400,height=300)
        self.assertEqual(find_field_regions(ocr),[])
    def test_blue_ink_preserves_geometry(self):
        from PIL import ImageDraw
        im=Image.new('RGB',(100,200),'white');ImageDraw.Draw(im).rectangle([30,40,50,60],fill='blue')
        result,t=prepare_image(im,{'preprocess':'blue_ink','target_long_edge':600,'border':20})
        self.assertEqual(result.size,(340,640));self.assertEqual(original_box([110,140,170,200],t),[30,40,50,60])
    def test_no_fields_is_not_read_success(self):
        from lector_facturas.frozen_runtime import extraction_status
        self.assertEqual(extraction_status({})['reading_status'],'sin_campos')


class ParallelOCRTests(unittest.TestCase):
    def test_parallel_views_keep_order_and_disable_crop_calls(self):
        from unittest.mock import patch
        from lector_facturas.ocr import transcribe
        def fake(image,opts,cache):
            return dict(words=[{'text':'1.00'}],text='1.00',options=opts,cache_hit=False,ocr_seconds=1)
        opts={'ensemble_views':[{'preprocess':'resize','psm':6},{'preprocess':'otsu','psm':11}],
              'workers':2,'focused_reading':{'enabled':False}}
        with patch('lector_facturas.ocr._single_transcribe',side_effect=fake) as call,patch('lector_facturas.ocr.focused_reading') as crop:
            r=transcribe('unused.png',opts)
        self.assertEqual([v['options']['psm'] for v in r['views']],[6,11])
        self.assertEqual(call.call_count,2);crop.assert_not_called()
        self.assertEqual(r['ocr_seconds'],2)
        self.assertGreaterEqual(r['ocr_wall_seconds'],0)


class CacheControlTests(unittest.TestCase):
    def test_routing_flag_does_not_change_recognition_cache_options(self):
        from unittest.mock import patch
        from lector_facturas.ocr import transcribe
        import copy,json
        cache={}
        def fake(image,opts,folder):
            key=json.dumps(opts,sort_keys=True);hit=key in cache;cache[key]=True
            return dict(words=[{'text':'12.00'}],text='12.00',options=opts,cache_hit=hit,ocr_seconds=1)
        opts={'ensemble_views':[{'preprocess':'resize','psm':6}], 'workers':2,'include_spanish':False}
        with patch('lector_facturas.ocr._single_transcribe',side_effect=fake):
            a=transcribe('same.png',opts)
            opts['include_spanish']=True
            b=transcribe('same.png',opts)
        self.assertFalse(a['cache_hit']);self.assertTrue(b['cache_hit'])


class AdaptiveRescueTests(unittest.TestCase):
    def test_good_reading_does_not_trigger(self):
        from lector_facturas.ocr import rescue_decision
        v={'words':[{'confidence':95}]*25,'text':'SUBTOTAL 10.00\nTAX 1.00\nTOTAL 11.00'}
        self.assertEqual(rescue_decision([v],{}),[])

    def test_low_confidence_and_missing_amount_trigger(self):
        from lector_facturas.ocr import rescue_decision
        v={'words':[{'confidence':30}]*25,'text':'SUBTOTAL\n????'}
        reasons=rescue_decision([v],{})
        self.assertIn('confianza_baja',reasons);self.assertIn('subtotal_sin_importe_visible',reasons)

    def test_rescue_is_bounded_and_recovers_when_base_empty(self):
        from unittest.mock import patch
        from lector_facturas.ocr import transcribe
        def fake(image,opts,cache):
            words=[] if opts['preprocess']=='resize' else [{'text':'11.00','confidence':90}]
            return dict(words=words,text='11.00',options=opts,cache_hit=False,ocr_seconds=1)
        opts={'ensemble_views':[{'preprocess':'resize','psm':6}], 'rescue_views':[{'preprocess':'local_binary','psm':p} for p in (6,11,3)],
              'adaptive_rescue':{'enabled':True,'max_views':99},'workers':2}
        with patch('lector_facturas.ocr._single_transcribe',side_effect=fake) as call:r=transcribe('unused',opts)
        self.assertEqual(call.call_count,3);self.assertEqual(r['rescue_requested'],2)
        self.assertEqual(len(r['views']),2)

    def test_disabled_rescue_makes_no_extra_calls(self):
        from unittest.mock import patch
        from lector_facturas.ocr import transcribe
        opts={'ensemble_views':[{'preprocess':'resize','psm':6}], 'rescue_views':[{'preprocess':'local_binary','psm':6}], 'adaptive_rescue':{'enabled':False}}
        with patch('lector_facturas.ocr._single_transcribe',return_value={'words':[{'text':'x'}],'options':{},'cache_hit':False,'ocr_seconds':1}) as call:r=transcribe('unused',opts)
        self.assertEqual(call.call_count,1);self.assertEqual(r['rescue_requested'],0)

class SummaryCropTests(unittest.TestCase):
    def test_summary_crop_uses_observed_label_positions(self):
        from lector_facturas.ocr import summary_crop
        v=ocr_lines(['SUBTOTAL 10.00','TAX 1.00','TOTAL 11.00']);v.update(width=600,height=1000)
        for w in v['words']:w['box'][1]+=600;w['box'][3]+=600
        box=summary_crop([v]);self.assertEqual(box[0],0);self.assertEqual(box[2],600)
        self.assertLess(box[1],600);self.assertGreater(box[3],680)
        self.assertIsNone(summary_crop([dict(v,words=[])]))

    def test_crop_boxes_map_back_to_full_image(self):
        with TemporaryDirectory() as td:
            path=Path(td)/'image.png';Image.new('RGB',(200,400),'white').save(path)
            opts=copy.deepcopy(CONFIG['ocr']);opts.pop('ensemble_views',None)
            opts.update(crop_box=[20,100,120,300],preprocess='original',border=0,grayscale=False,autocontrast=False)
            tsv='level\tpage_num\tblock_num\tpar_num\tline_num\tleft\ttop\twidth\theight\tconf\ttext\n5\t1\t1\t1\t1\t10\t20\t30\t40\t90\t10.00\n'
            with patch('lector_facturas.ocr.environment',return_value={'version':'fake','languages':['eng']}),patch('lector_facturas.ocr.subprocess.run',return_value=SimpleNamespace(stdout=tsv)):
                result=transcribe(path,opts)
            self.assertEqual(result['words'][0]['box'],[30,120,60,160])
            self.assertEqual((result['width'],result['height']),(200,400))

    def test_disagreement_requires_different_amounts(self):
        from lector_facturas.ocr import summary_disagreement
        a=ocr_lines(['TOTAL 12.00']);b=ocr_lines(['TOTAL 17.00'])
        self.assertFalse(summary_disagreement([a,a,a,a]))
        self.assertTrue(summary_disagreement([a,a,b,b]))

    def test_summary_rescue_never_exceeds_two_extra_calls(self):
        from lector_facturas.ocr import transcribe
        v=ocr_lines(['TOTAL 12.00']);v.update(width=600,height=1000,text='TOTAL 12.00',cache_hit=False,ocr_seconds=1)
        for w in v['words']:w['box'][1]+=600;w['box'][3]+=600
        def fake(image,opts,cache):return dict(copy.deepcopy(v),options=opts)
        opts={'ensemble_views':[{'preprocess':'resize','psm':6}],
              'adaptive_rescue':{'enabled':True,'max_views':99},'summary_rescue':{'enabled':True},
              'rescue_views':[{'psm':6},{'psm':11},{'psm':3}]}
        with patch('lector_facturas.ocr._single_transcribe',side_effect=fake) as call:
            result=transcribe('unused',opts)
        self.assertEqual(call.call_count,3);self.assertEqual(result['rescue_requested'],2)
        self.assertTrue(all('crop_box' in v['options'] for v in result['views'][1:]))
