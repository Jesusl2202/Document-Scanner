"""Tesseract CLI: TSV trazable; preprocesamiento que conserva coordenadas."""
from pathlib import Path
import csv
import io
import json
import subprocess
import tempfile
import time
import hashlib
import os
from concurrent.futures import ThreadPoolExecutor
from PIL import Image, ImageOps
from .common import digest, write_json
from .preprocessing import prepare_image, original_box


def environment(executable='tesseract', tessdata_dir=None):
    version = subprocess.run([executable, '--version'], capture_output=True, text=True, check=True).stdout.splitlines()[0]
    languages = subprocess.run([executable, '--list-langs'] + (['--tessdata-dir',str(tessdata_dir)] if tessdata_dir else []), capture_output=True, text=True, check=True).stdout.splitlines()[1:]
    return {'version': version, 'languages': languages}


def transcribe(image, options, cache_dir=None):
    env = environment(options['executable'],options.get('tessdata_dir'))
    missing = set(options['language'].split('+')) - set(env['languages'])
    if missing:
        raise ValueError('Idiomas Tesseract no instalados: ' + ', '.join(sorted(missing)))
    model_flags=[]
    if options.get('tessdata_dir'):
        model_root=Path(options['tessdata_dir'])
        model_files=[model_root/(lang+'.traineddata') for lang in options['language'].split('+')]
        if not all(p.is_file() for p in model_files):raise FileNotFoundError('Faltan pesos en '+str(model_root))
        actual={p.name:digest(p) for p in model_files}
        if options.get('expected_model_sha256') and actual.get('eng.traineddata')!=options['expected_model_sha256']:
            raise ValueError('Hash incorrecto de los pesos OCR')
        options=dict(options,actual_model_sha256=actual)
        model_flags=['--tessdata-dir',str(model_root)]
    source_hash = digest(image)
    key = hashlib.sha256(json.dumps([source_hash, options, env['version'], digest(__file__), digest(Path(__file__).with_name('preprocessing.py'))], sort_keys=True).encode()).hexdigest()
    cache = Path(cache_dir) / (key + '.json') if cache_dir else None
    if cache and cache.exists():
        result = json.loads(cache.read_text(encoding='utf-8'))
        result['cache_hit'] = True
        return result
    start = time.perf_counter()
    with Image.open(image) as im:
        im=ImageOps.exif_transpose(im)
        width, height = im.size
        offset=(0,0)
        if options.get('crop_box'):
            x0,y0,x1,y1=map(int,options['crop_box'])
            if not (0<=x0<x1<=width and 0<=y0<y1<=height):
                raise ValueError('Recorte fuera de la imagen')
            im=im.crop((x0,y0,x1,y1));offset=(x0,y0)
        im, transform = prepare_image(im, options)
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'input.png'
            im.save(path)
            extra=[]
            if options.get('character_whitelist'):
                extra=['-c','tessedit_char_whitelist='+options['character_whitelist'],'-c','load_system_dawg=0','-c','load_freq_dawg=0']
            proc = subprocess.run([options['executable'], str(path), 'stdout', '-l', options['language'],
                                   '--oem', str(options['oem']), '--psm', str(options['psm'])]+model_flags+extra+['-c','tessedit_create_tsv=1','-c','tessedit_create_txt=0'],
                                  capture_output=True, text=True, encoding='utf-8', errors='replace',
                                  timeout=options['timeout_seconds'], check=True,
                                  env=dict(os.environ,OMP_THREAD_LIMIT=str(options.get('omp_thread_limit',1))))
    reader=csv.DictReader(io.StringIO(proc.stdout),delimiter='\t',quoting=csv.QUOTE_NONE)
    required={'level','page_num','block_num','par_num','line_num','left','top','width','height','conf','text'}
    if not required.issubset(set(reader.fieldnames or [])):
        raise RuntimeError('Tesseract no devolvió TSV válido. '+proc.stderr[-400:] if getattr(proc,'stderr',None) else 'Tesseract no devolvió TSV válido: revisar configuración de salida.')
    words = []
    for r in reader:
        text = r.get('text', '').strip()
        if r.get('level') == '5' and text:
            x, y, w, h = (int(r[k]) for k in ('left', 'top', 'width', 'height'))
            words.append({'text': text, 'box': [v+offset[i%2] for i,v in enumerate(original_box([x, y, x + w, y + h], transform))], 'confidence': float(r['conf']),
                          'line_id': ':'.join(r[k] for k in ('page_num', 'block_num', 'par_num', 'line_num'))})
    result = {'width': width, 'height': height, 'words': words, 'text': '\n'.join(l['text'] for l in lines(words)),
              'ocr_seconds': time.perf_counter() - start, 'cache_hit': False, 'source_sha256': source_hash,
              'engine': env['version'], 'options': options, 'transform': transform, 'crop_offset': list(offset)}
    if cache:
        write_json(cache, result)
    return result


def lines(words):
    groups = {}
    for word in words:
        groups.setdefault(word['line_id'], []).append(word)
    result = []
    for line_id, group in groups.items():
        group = sorted(group, key=lambda w: w['box'][0])
        result.append({'id': line_id, 'text': ' '.join(w['text'] for w in group), 'words': group,
                       'box': [min(w['box'][0] for w in group), min(w['box'][1] for w in group),
                               max(w['box'][2] for w in group), max(w['box'][3] for w in group)]})
    return result


def render_pdf(path, output_dir, dpi=200, max_pages=20):
    import pypdfium2 as pdfium
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    result = []
    with pdfium.PdfDocument(str(path)) as pdf:
        if len(pdf) > max_pages:
            raise ValueError(f'PDF tiene {len(pdf)} páginas; límite local {max_pages}. No se trunca.')
        for i in range(len(pdf)):
            page = pdf[i]
            bitmap = page.render(scale=dpi / 72)
            image = bitmap.to_pil()
            dest = output_dir / f'page_{i+1:03d}.png'
            image.save(dest)
            result.append(dest)
            image.close()
            bitmap.close()
            page.close()
    return result

# Varias lecturas de la MISMA imagen, sin acceder a etiquetas de evaluación.
_single_transcribe = transcribe
def transcribe(image,options,cache_dir=None):
    if not options.get('ensemble_views'):
        return _single_transcribe(image,options,cache_dir)
    started=time.perf_counter()
    views=[];errors=[]
    def read_view(spec):
        opts={k:v for k,v in options.items() if k not in ('ensemble_views','focused_reading','workers','include_spanish','adaptive_rescue','rescue_views','summary_rescue')}
        opts.update(spec)
        try:
            view=_single_transcribe(image,opts,cache_dir)
            return (view,None) if view['words'] else (None,{'view':spec,'error':'OCR sin palabras'})
        except Exception as exc:return None,{'view':spec,'error':str(exc)}
    workers=max(1,min(2,int(options.get('workers',1))))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        # map conserva el orden de las vistas; terminar antes no da más votos.
        for view,error in pool.map(read_view,options['ensemble_views']):
            if view is not None:views.append(view)
            if error is not None:errors.append(error)
    rescue_settings=options.get('adaptive_rescue',{})
    rescue_reasons=rescue_decision(views,rescue_settings) if rescue_settings.get('enabled') else []
    summary_settings=options.get('summary_rescue',{})
    if summary_settings.get('enabled') and summary_disagreement(views):
        rescue_reasons.append('discrepancia_importes')
    rescue_count=0
    if rescue_reasons:
        specs=options.get('rescue_views',[])[:max(0,min(2,int(rescue_settings.get('max_views',2))))]
        crop=summary_crop(views) if summary_settings.get('enabled') else None
        if crop:
            specs=[dict(spec,crop_box=crop,preprocess=('resize' if i==0 else 'local_binary'),
                        target_long_edge=3200,max_scale=6,max_pixels=6000000) for i,spec in enumerate(specs)]
        rescue_count=len(specs)
        with ThreadPoolExecutor(max_workers=workers) as pool:
            for view,error in pool.map(read_view,specs):
                if view is not None:views.append(dict(view,rescue=True))
                if error is not None:errors.append(dict(error,rescue=True))
    if not views:raise RuntimeError('Ninguna lectura OCR útil: '+str(errors))
    # El CER corresponde solo a esta lectura primaria, no al consenso de campos.
    primary=next((v for v in views if v.get('options',{}).get('preprocess')=='resize' and v.get('options',{}).get('psm')==6),views[0])
    result=dict(primary,views=views,view_errors=errors,requested_views=len(options['ensemble_views'])+rescue_count,
                rescue_reasons=rescue_reasons,rescue_requested=rescue_count)
    result['cache_hit']=any(v.get('cache_hit',False) for v in views)
    result['ocr_seconds']=sum(v.get('ocr_seconds',0) for v in views)
    result['ocr_wall_seconds']=time.perf_counter()-started
    if options.get('focused_reading',{}).get('enabled'):
        result=focused_reading(image,options,result,cache_dir)
    return result


def find_field_regions(ocr,limit=8,printed=False):
    """Detectar etiquetas en el OCR, sin posiciones fijas ni anotaciones externas."""
    import re
    from .geometry import grouped
    patterns={'subtotal':r'\bsub\s*total\b','tax':r'\b(?:iva|tax|vat|impuesto)\b',
              'total':r'\b(?:grand\s+total|amount\s+due|total)\b',
              'date':r'\b(?:fecha|date|dia\s+mes(?:\s+ano)?)\b'}
    regions=[];seen=set();width,height=ocr['width'],ocr['height']
    for view in ocr.get('views',[ocr]):
        for row in grouped(view):
            text=row['text']
            if printed and __import__('re').search(r'certific|total\s+con\s+letra|total\s+in\s+words',text):continue
            for field,pattern in patterns.items():
                if field=='total' and re.search(r'\bsub\s*total\b|\bv[.\s]*total\b|\bunit\b',text):continue
                if field=='tax' and re.search(r'\b(?:tax\s*id|vat\s*(?:no|number)|ruc)\b',text):continue
                if field=='date' and re.search(r'autori|vencim|caduc|expir|valid',text):continue
                match=re.search(pattern,text)
                if not match:continue
                boxes=[b for a,z,b in row['spans'] if a<match.end() and z>match.start()]
                if not boxes:continue
                x0=min(b[0] for b in boxes);x1=max(b[2] for b in boxes)
                y0=min(b[1] for b in boxes);y1=max(b[3] for b in boxes);h=max(10,y1-y0)
                # Una franja a la derecha de la etiqueta; fecha también puede estar debajo.
                boxes=[[int(x1+2),max(0,int(y0-.6*h)),width,min(height,int(y1+.6*h))]]
                if field=='date':boxes.append([int(x0),int(y1),width,min(height,int(y1+2*h))])
                for box in boxes:
                    if box[2]-box[0]<18 or box[3]-box[1]<8:continue
                    key=(field,round(box[0]/24),round(box[1]/16))
                    if key in seen:continue
                    seen.add(key);regions.append({'field':field,'box':box,'label':match.group()})
                    if len(regions)>=limit:return regions
    return regions


def focused_reading(image,options,result,cache_dir):
    import copy
    settings=options['focused_reading'];readings=[];errors=[]
    templates=options['ensemble_views']
    best=next((v for v in templates if 'best' in str(v.get('tessdata_dir',''))),templates[0])
    with Image.open(image) as source,tempfile.TemporaryDirectory() as td:
        source=ImageOps.exif_transpose(source).convert('RGB')
        for index,region in enumerate(find_field_regions(result,settings.get('max_regions',8),settings.get('printed',False))):
            path=Path(td)/f'crop_{index}.png';source.crop(region['box']).save(path)
            local=[]
            methods=[('resize',7),('otsu',7),('denoise',13)] if settings.get('printed') else [('resize',7),('denoise',13),('blue_ink',7)]
            for method,psm in methods:
                opts={k:v for k,v in options.items() if k not in ('ensemble_views','focused_reading')}
                opts.update(best);opts.update(language='eng',preprocess=method,psm=psm,target_long_edge=1600,max_scale=4,
                                             border=16,character_whitelist='0123456789.,/- ')
                try:
                    view=_single_transcribe(path,opts,cache_dir)
                    local.append({'text':view['text'],'confidence':sum(w['confidence'] for w in view['words'])/len(view['words']) if view['words'] else 0,
                                  'preprocess':method,'psm':psm,'cache_hit':view['cache_hit'],'ocr_seconds':view['ocr_seconds']})
                except Exception as exc:errors.append({'region':index,'method':method,'error':str(exc)})
            readings.append(dict(region,readings=local))
    # Las lecturas de recorte se mantienen separadas; no aumentan artificialmente los votos globales.
    return dict(result,focused_regions=readings,focused_errors=errors,
                ocr_seconds=result['ocr_seconds']+sum(v['ocr_seconds'] for r in readings for v in r['readings']),
                cache_hit=result['cache_hit'] or any(v['cache_hit'] for r in readings for v in r['readings']))


def rescue_decision(views,settings):
    """Decidir solo con la lectura observada; no recibe datos de evaluación."""
    import re,statistics
    if not views:return ['sin_lectura_base']
    usable=[v for v in views if len(v.get('words',[]))>=settings.get('minimum_words',20)]
    if not usable:return ['pocas_palabras']
    medians=[statistics.median(w.get('confidence',0) for w in v['words']) for v in usable]
    reasons=[]
    if max(medians)<settings.get('confidence_threshold',70):reasons.append('confianza_baja')
    # Etiquetas legibles sin importe en esa línea o la siguiente en ninguna vista.
    labels={'subtotal':r'\bsub[ -]*total\b','tax':r'\b(?:tax|iva|vat|gst)\b','total':r'(?<!sub)\btotal\b'}
    any_label=False
    for field,pattern in labels.items():
        seen=found=False
        for view in usable:
            ls=view.get('text','').lower().splitlines()
            for i,line in enumerate(ls):
                if not re.search(pattern,line):continue
                if re.search(r'\b(?:id|reg|registration|number|quantity|items)\b',line):continue
                if field=='total' and re.search(r'sub[ -]*total|total\s+tax',line):continue
                seen=True;any_label=True
                nearby=' '.join(ls[i:i+2])
                if re.search(r'(?<!\w)\d+(?:[.,]\d{3})*[.,]\d{2}(?!\d|%)',nearby):found=True
        if seen and not found:reasons.append(field+'_sin_importe_visible')
    if not any_label:reasons.append('sin_etiquetas_de_importes')
    return reasons

def summary_disagreement(views):
    """Trigger on disagreements between label-associated decimal readings only."""
    import re
    from collections import Counter
    from .geometry import grouped
    totals=Counter()
    for view in views:
        found=set()
        for row in grouped(view):
            text=row['text']
            if not re.search(r'\b(?:grand\s+total|total|subtotal|subttl|tax|vat|gst|iva)\b',text):continue
            if re.search(r'\b(?:id|reg|registration|items|qty|number)\b',text):continue
            amounts=re.findall(r'(?<!\w)\d+[.,]\d{2}(?!\d|\s*%)',text)
            if len(amounts)==1:
                label='subtotal' if re.search(r'subtotal|subttl',text) else 'tax' if re.search(r'tax|vat|gst|iva',text) else 'total'
                found.add((label,amounts[0].replace(',','.')))
        totals.update(found)
    for label in ('subtotal','tax','total'):
        counts=[n for (f,v),n in totals.items() if f==label]
        if len(counts)>1 and sum(counts)>=4 and max(counts)/sum(counts)<.75:return True
    return False


def summary_crop(views):
    """Locate a summary from observed labels, never annotation boxes."""
    import re,statistics
    from .geometry import grouped
    if not views:return None
    width,height=views[0]['width'],views[0]['height'];ys=[];hs=[]
    for view in views:
        for row in grouped(view):
            text=row['text']
            if not re.search(r'\b(?:subtotal|subttl|grand\s+total|total|tax|vat|gst|iva|amount\s+due)\b',text):continue
            if re.search(r'\b(?:id|reg|registration|items|qty|number|unit)\b',text):continue
            y0,y1=row['box'][1],row['box'][3]
            if y0<.25*height:continue
            ys.extend([y0,y1]);hs.append(max(1,y1-y0))
    if not ys:return None
    h=statistics.median(hs);top=max(0,int(min(ys)-3*h));bottom=min(height,int(max(ys)+4*h))
    if bottom-top<20 or bottom-top>.8*height:return None
    return [0,top,width,bottom]
