"""Tesseract CLI: TSV trazable; preprocesamiento que conserva coordenadas."""
from pathlib import Path
import csv
import io
import json
import subprocess
import tempfile
import time
import hashlib
from PIL import Image, ImageOps
from .common import digest, write_json


def environment(executable='tesseract'):
    version = subprocess.run([executable, '--version'], capture_output=True, text=True, check=True).stdout.splitlines()[0]
    languages = subprocess.run([executable, '--list-langs'], capture_output=True, text=True, check=True).stdout.splitlines()[1:]
    return {'version': version, 'languages': languages}


def transcribe(image, options, cache_dir=None):
    env = environment(options['executable'])
    missing = set(options['language'].split('+')) - set(env['languages'])
    if missing:
        raise ValueError('Idiomas Tesseract no instalados: ' + ', '.join(sorted(missing)))
    source_hash = digest(image)
    key = hashlib.sha256(json.dumps([source_hash, options, env['version']], sort_keys=True).encode()).hexdigest()
    cache = Path(cache_dir) / (key + '.json') if cache_dir else None
    if cache and cache.exists():
        result = json.loads(cache.read_text(encoding='utf-8'))
        result['cache_hit'] = True
        return result
    start = time.perf_counter()
    with Image.open(image) as im:
        # No EXIF transpose, rotación ni redimensionamiento implícitos:
        # las cajas de referencia permanecen en el sistema de la imagen original.
        im = im.convert('L' if options.get('grayscale', True) else 'RGB')
        if options.get('autocontrast', True):
            im = ImageOps.autocontrast(im)
        width, height = im.size
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'input.png'
            im.save(path)
            proc = subprocess.run([options['executable'], str(path), 'stdout', '-l', options['language'],
                                   '--oem', str(options['oem']), '--psm', str(options['psm']), 'tsv'],
                                  capture_output=True, text=True, encoding='utf-8', errors='replace',
                                  timeout=options['timeout_seconds'], check=True)
    words = []
    for r in csv.DictReader(io.StringIO(proc.stdout), delimiter='\t', quoting=csv.QUOTE_NONE):
        text = r.get('text', '').strip()
        if r.get('level') == '5' and text:
            x, y, w, h = (int(r[k]) for k in ('left', 'top', 'width', 'height'))
            words.append({'text': text, 'box': [x, y, x + w, y + h], 'confidence': float(r['conf']),
                          'line_id': ':'.join(r[k] for k in ('page_num', 'block_num', 'par_num', 'line_num'))})
    result = {'width': width, 'height': height, 'words': words, 'text': '\n'.join(l['text'] for l in lines(words)),
              'ocr_seconds': time.perf_counter() - start, 'cache_hit': False, 'source_sha256': source_hash,
              'engine': env['version'], 'options': options}
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
