import unittest
from PIL import Image
from lector_facturas.preprocessing import prepare_image,original_box

class SizeLimitTests(unittest.TestCase):
    def test_large_image_is_reduced_not_rejected(self):
        im,t=prepare_image(Image.new('L',(100,200)),dict(preprocess='resize',border=5,max_pixels=10000))
        self.assertLessEqual(im.width*im.height,10000)
        self.assertTrue(t['size_limited'])
        self.assertLess(t['scale_x'],1)
        self.assertEqual(original_box([5,5,im.width-5,im.height-5],t),[0,0,100,200])

    def test_otsu_also_respects_limit(self):
        im,t=prepare_image(Image.new('L',(200,100)),dict(preprocess='otsu',border=5,max_pixels=10000))
        self.assertLessEqual(im.width*im.height,10000)
        self.assertTrue(t['size_limited'])

    def test_unusually_narrow_image(self):
        im,t=prepare_image(Image.new('L',(1,500)),dict(preprocess='resize',border=2,max_pixels=100))
        self.assertLessEqual(im.width*im.height,100)

    def test_invalid_budget_still_fails(self):
        with self.assertRaises(ValueError):
            prepare_image(Image.new('L',(100,200)),dict(preprocess='resize',border=5,max_pixels=120))


class LocalThresholdTests(unittest.TestCase):
    def test_local_threshold_keeps_shape_and_white_background(self):
        from lector_facturas.preprocessing import local_binary
        from PIL import Image,ImageDraw
        import numpy as np
        im=Image.new('L',(120,80),235);ImageDraw.Draw(im).rectangle((40,30,70,38),fill=30)
        result=np.asarray(local_binary(im,21,.2))
        self.assertEqual(result.shape,(80,120))
        self.assertEqual(int(result[0,0]),255);self.assertEqual(int(result[34,55]),0)

    def test_local_threshold_rejects_invalid_window(self):
        from lector_facturas.preprocessing import local_binary
        from PIL import Image
        with self.assertRaises(ValueError):local_binary(Image.new('L',(10,10)),4)

    def test_local_threshold_does_not_change_coordinate_transform(self):
        from lector_facturas.preprocessing import prepare_image,original_box
        from PIL import Image
        im,t=prepare_image(Image.new('L',(100,200),255),{'preprocess':'local_binary','target_long_edge':400,'border':10})
        self.assertEqual(im.size,(220,420))
        self.assertEqual(original_box([10,10,210,410],t),[0,0,100,200])
