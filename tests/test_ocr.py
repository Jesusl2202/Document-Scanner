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
