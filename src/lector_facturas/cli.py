"""Comandos reproducibles; ejecutar desde la raíz del repositorio."""
import argparse
import hashlib
import importlib.metadata
import json
import platform
from pathlib import Path
import sys
import time
import logging
from . import __version__
from .common import FIELDS, read_jsonl, write_json, write_jsonl, digest
from .datasets import prepare
from .eda import run_eda
from .evaluation import evaluate
from .extraction import extract, validate
from .ocr import transcribe, environment, render_pdf

LOG = logging.getLogger('lector')


def selected(rows, split, limit, seed):
    result = []
    for dataset in sorted({r['dataset'] for r in rows}):
        subset = [r for r in rows if r['dataset'] == dataset and r['split'] == split]
        subset.sort(key=lambda r: hashlib.sha256(f"{seed}:{r['id']}".encode()).hexdigest())
        result.extend(subset[:limit] if limit else subset)
    return result


def predict(image, engine, config, cache_dir):
    start = time.perf_counter()
    if engine == 'tesseract':
        ocr = transcribe(image, config['ocr'], cache_dir)
        result = extract(ocr, config)
        result.update({'text': ocr['text'], 'ocr': ocr, 'cache_hit': ocr['cache_hit']})
    else:
        from .google_ai import process
        result = process(image, config)
        result['cache_hit'] = False
    result['validation'] = validate(result['fields'], config)
    result['status'] = 'ok'
    result['elapsed_seconds'] = time.perf_counter() - start
    return result


def run_experiment(rows, config, out, engine, cache_dir):
    out = Path(out)
    if (out / 'predictions.jsonl').exists():
        raise ValueError(f'{out} ya tiene predicciones: use otro nombre de ejecución para conservar evidencia')
    out.mkdir(parents=True, exist_ok=True)
    if engine == 'tesseract':
        engine_env = environment(config['ocr']['executable'])
        missing = set(config['ocr']['language'].split('+')) - set(engine_env['languages'])
        if missing:
            raise ValueError('Faltan idiomas OCR: ' + ','.join(missing))
    else:
        engine_env = {'provider': 'google_document_ai', 'sdk': importlib.metadata.version('google-cloud-documentai')}
    write_json(out / 'config.json', config)
    write_jsonl(out / 'evaluation_manifest.jsonl', rows)
    write_json(out / 'environment.json', {'python': sys.version, 'platform': platform.platform(), 'project_version': __version__,
               'engine': engine_env, 'packages': {n: importlib.metadata.version(n) for n in ['Pillow', 'numpy', 'pandas', 'pypdfium2']}})
    predictions = []
    for i, row in enumerate(rows, 1):
        start = time.perf_counter()
        try:
            p = predict(row['image'], engine, config, cache_dir)
        except Exception as e:
            LOG.error('%s: %s', row['id'], type(e).__name__)
            p = {'fields': {f: None for f in FIELDS}, 'status': 'error', 'error_type': type(e).__name__,
                 'error': str(e)[:500], 'elapsed_seconds': time.perf_counter()-start, 'text': ''}
        p.update({'id': row['id'], 'dataset': row['dataset'], 'engine': engine})
        predictions.append(p)
        # Checkpoint por documento: una interrupción deja evidencia recuperable.
        with (out / 'predictions.jsonl').open('a', encoding='utf-8') as f:
            f.write(json.dumps(p, ensure_ascii=False) + '\n')
        LOG.info('%s %d/%d %s', engine, i, len(rows), p['status'])
    return evaluate(rows, predictions, config, out / 'evaluation')


def compare(a, b, out):
    """No permite presentar una comparación sobre documentos diferentes."""
    a, b = Path(a), Path(b)
    ma, mb = read_jsonl(a/'evaluation_manifest.jsonl'), read_jsonl(b/'evaluation_manifest.jsonl')
    signature = lambda rows: {(r['id'], r['sha256'], json.dumps(r['gold'], sort_keys=True)) for r in rows}
    if signature(ma) != signature(mb):
        raise ValueError('Comparación inválida: cambian documentos, contenido o referencias')
    ca, cb = (json.loads((p/'config.json').read_text(encoding='utf-8')) for p in (a,b))
    if ca['normalization'] != cb['normalization']:
        raise ValueError('Comparación inválida: normalización distinta')
    import pandas as pd
    ta, tb = (pd.read_csv(p/'evaluation'/'metrics.csv') for p in (a,b))
    merged = ta.merge(tb, on=['dataset','field','support'], suffixes=('_a','_b'), validate='one_to_one')
    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    merged.to_csv(out/'comparison.csv', index=False, encoding='utf-8-sig')
    write_json(out/'sources.json', {'a': str(a), 'b': str(b), 'documents': len(ma),
                                  'note': 'Revisar tasas de fallos y latencia en ambas evaluaciones; no seleccionar solo por una métrica.'})


def main():
    logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')
    parser = argparse.ArgumentParser(description='Proyecto SROIE + WildReceipt, Semana 2')
    parser.add_argument('--config', default='configs/default.json')
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('prepare')
    p.add_argument('--sroie'); p.add_argument('--wildreceipt'); p.add_argument('--out', default='data/processed')
    p = sub.add_parser('eda')
    p.add_argument('--manifest', default='data/processed/manifest.jsonl'); p.add_argument('--out', default='outputs/eda')
    p = sub.add_parser('run')
    p.add_argument('--manifest', default='data/processed/manifest.jsonl')
    p.add_argument('--split', choices=['train','validation','test'], default='validation')
    p.add_argument('--limit-per-dataset', type=int, default=0)
    p.add_argument('--engine', choices=['tesseract','google'], default='tesseract')
    p.add_argument('--out', required=True); p.add_argument('--cache', default='artifacts/ocr_cache')
    p.add_argument('--allow-cloud', action='store_true', help='Autoriza enviar estos documentos al procesador configurado')
    p = sub.add_parser('extract')
    p.add_argument('file'); p.add_argument('--out', required=True)
    p.add_argument('--engine', choices=['tesseract','google'], default='tesseract'); p.add_argument('--allow-cloud', action='store_true')
    p = sub.add_parser('compare')
    p.add_argument('--a', required=True); p.add_argument('--b', required=True); p.add_argument('--out', required=True)
    sub.add_parser('doctor')
    args = parser.parse_args()
    try:
        config = json.loads(Path(args.config).read_text(encoding='utf-8'))
        if args.command == 'doctor':
            print(json.dumps(environment(config['ocr']['executable']), indent=2))
        elif args.command == 'prepare':
            rows = prepare(args.sroie, args.wildreceipt, args.out, config)
            print(f'{len(rows)} documentos registrados; revisar incidencias con eda.')
        elif args.command == 'eda':
            print(json.dumps(run_eda(read_jsonl(args.manifest), args.out), indent=2))
        elif args.command == 'run':
            if args.limit_per_dataset < 0:
                raise ValueError('El límite no puede ser negativo')
            if args.engine == 'google' and not args.allow_cloud:
                raise ValueError('Google requiere --allow-cloud y credenciales; no se envió ningún documento')
            rows = selected(read_jsonl(args.manifest), args.split, args.limit_per_dataset, config['seed'])
            if not rows:
                raise ValueError('La partición seleccionada no tiene documentos')
            print(json.dumps(run_experiment(rows, config, args.out, args.engine, args.cache), indent=2))
        elif args.command == 'extract':
            if args.engine == 'google' and not args.allow_cloud:
                raise ValueError('Google requiere --allow-cloud')
            path, out = Path(args.file), Path(args.out)
            if path.suffix.lower() == '.pdf' and args.engine == 'tesseract':
                paths = render_pdf(path, out/'pages')
                result = [dict(predict(p,args.engine,config,None), page=i+1) for i,p in enumerate(paths)]
                write_json(out/'prediction.json', {'source': str(path), 'pages': result,
                     'note': 'Resultados separados por página. No se fusionan totales de facturas multipágina.'})
            else:
                write_json(out/'prediction.json', predict(path,args.engine,config,None))
            print(out/'prediction.json')
        elif args.command == 'compare':
            compare(args.a,args.b,args.out)
    except (ValueError, OSError, ImportError) as exc:
        parser.exit(2, f'Error: {exc}\n')


if __name__ == '__main__':
    main()
