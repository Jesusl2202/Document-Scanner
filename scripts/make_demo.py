"""Crea comprobantes sintéticos propios SOLO para verificar la instalación."""
from pathlib import Path
import json
from PIL import Image, ImageDraw, ImageFont
root=Path(__file__).resolve().parents[1]
out=root/'samples';out.mkdir(parents=True,exist_ok=True)
font=None
for name in ['DejaVuSans.ttf','Arial.ttf','LiberationSans-Regular.ttf']:
    try:
        font=ImageFont.truetype(name,28);break
    except OSError:pass
font=font or ImageFont.load_default()
im=Image.new('RGB',(850,680),'white');draw=ImageDraw.Draw(im)
texts=['SYNTHETIC TEST RECEIPT','DEMO STORE - NOT A REAL INVOICE',
       'DATE: 2026-09-27','INVOICE NO: 001-002-000123','TAX ID: 1234567890',
       'SUBTOTAL 100.00','TAX 12.00','TOTAL 112.00']
for i,line in enumerate(texts):draw.text((35,35+i*65),line,fill='black',font=font)
im.save(out/'synthetic_receipt.png')
im.save(out/'synthetic_receipt.pdf',resolution=150)
(out/'synthetic_gold.json').write_text(json.dumps({'synthetic':True,'not_a_dataset_sample':True,
    'fields':{'tax_id':'1234567890','date':'2026-09-27','document_number':'001-002-000123','subtotal':'100.00','tax':'12.00','total':'112.00'}},indent=2))
print(out)
