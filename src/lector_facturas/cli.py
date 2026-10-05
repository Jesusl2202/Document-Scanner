"""Inferencia de imágenes/PDF con configuración definitiva."""
import argparse,json,csv,time
from pathlib import Path
from .ocr import transcribe,render_pdf
from .extraction import extract,validate
from .frozen_runtime import ensure_model,review_notes

def predict(image,engine,config,cache_dir=None):
    if engine!='tesseract':raise ValueError('Este proyecto utiliza Tesseract')
    started=time.perf_counter();ocr=transcribe(image,config['ocr'],cache_dir)
    result=extract(ocr,config)
    result.update(text=ocr['text'],ocr=ocr,cache_hit=ocr['cache_hit'],status='ok',validation=validate(result['fields'],config),elapsed_seconds=time.perf_counter()-started)
    return result

def main():
    root=Path(__file__).resolve().parents[2]
    parser=argparse.ArgumentParser(description='Lector definitivo Tesseract')
    parser.add_argument('file');parser.add_argument('--out',default='outputs/lectura')
    parser.add_argument('--config',default=str(root/'configs/definitivo.json'))
    args=parser.parse_args();source=Path(args.file);out=Path(args.out)
    if not source.is_file():raise FileNotFoundError(source)
    out.mkdir(parents=True,exist_ok=True)
    config=json.loads(Path(args.config).read_text(encoding='utf8'))
    model=ensure_model(root/'modelos/eng_fijado')
    pages=render_pdf(source,out/'paginas') if source.suffix.lower()=='.pdf' else [source]
    results=[]
    for i,page in enumerate(pages,1):
        try:
            r=predict(page,'tesseract',config);r['revision']=review_notes(r)
        except Exception as exc:r={'status':'error','error':str(exc),'fields':{},'revision':['No se pudo procesar']}
        r['page']=i;results.append(r)
    (out/'resultado.json').write_text(json.dumps({'source':str(source),'model':model,'pages':results},ensure_ascii=False,indent=2),encoding='utf8')
    with (out/'campos.csv').open('w',newline='',encoding='utf-8-sig') as f:
        writer=csv.DictWriter(f,fieldnames=['page','status','tax_id','date','document_number','subtotal','tax','total','revision']);writer.writeheader()
        for r in results:writer.writerow(dict(page=r['page'],status=r['status'],**r['fields'],revision='; '.join(r['revision'])))
    print(out.resolve())
