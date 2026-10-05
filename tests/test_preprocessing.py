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
