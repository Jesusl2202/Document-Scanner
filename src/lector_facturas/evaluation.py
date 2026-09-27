"""Métricas por campo/dataset. Un valor erróneo cuenta FP+FN; ausente anotación no cuenta."""
from collections import defaultdict
from pathlib import Path
import json
import statistics
import pandas as pd
from .common import FIELDS, normalize, write_json


def edit_distance(a, b):
    # Dos filas: memoria O(len(b)); texto completo, sin recortes ocultos.
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        curr = [i]
        for j, cb in enumerate(b, 1):
            curr.append(min(curr[-1] + 1, prev[j] + 1, prev[j - 1] + (ca != cb)))
        prev = curr
    return prev[-1]


def cer_reference(row):
    if not row['regions'] or any(x in row['issues'] for x in ('invalid_box', 'invalid_box_line', 'invalid_annotation', 'missing_transcription')):
        return None
    return ' '.join(str(r['text']) for r in sorted(row['regions'], key=lambda r: (r['box'][1], r['box'][0])) if r.get('label') != 'Ignore')


def cer_text(s):
    return ' '.join(s.upper().split())


def evaluate(rows, predictions, config, out):
    expected = {r['id'] for r in rows}
    if len(expected) != len(rows):
        raise ValueError('IDs duplicados en evaluación')
    if len({p['id'] for p in predictions}) != len(predictions):
        raise ValueError('Predicciones duplicadas')
    extra = {p['id'] for p in predictions} - expected
    if extra:
        raise ValueError('Predicciones ajenas al manifiesto seleccionado')
    pred_by_id = {p['id']: p for p in predictions}
    details, ocr_errors, doc_rows = [], [], []
    for r in rows:
        p = pred_by_id.get(r['id'], {'fields': {}, 'status': 'missing_prediction'})
        ok = p.get('status') == 'ok'
        doc_rows.append({'id': r['id'], 'dataset': r['dataset'], 'ok': ok,
                         'seconds': p.get('elapsed_seconds'), 'cache_hit': p.get('cache_hit', False)})
        for field in FIELDS:
            gold = r['gold'][field]
            if gold['status'] not in ('annotated', 'absent'):
                continue
            truth = normalize(field, gold['value'], config['normalization'])
            predicted = normalize(field, p.get('fields', {}).get(field), config['normalization']) if ok else None
            correct = ok and truth == predicted
            tp = int(truth is not None and predicted == truth and ok)
            fp = int(predicted is not None and predicted != truth)
            fn = int(truth is not None and predicted != truth)
            details.append({'id': r['id'], 'dataset': r['dataset'], 'field': field,
                            'gold': gold['value'], 'predicted': p.get('fields', {}).get(field),
                            'gold_normalized': truth, 'predicted_normalized': predicted,
                            'correct': int(correct), 'tp': tp, 'fp': fp, 'fn': fn, 'execution_ok': ok})
        reference = cer_reference(r)
        if reference:
            ref = cer_text(reference)
            hyp = cer_text(p.get('text', '')) if ok else ''
            if ref:
                distance = edit_distance(ref, hyp)
                ocr_errors.append({'id': r['id'], 'dataset': r['dataset'], 'edits': distance, 'reference_characters': len(ref), 'cer': distance / len(ref)})
    metrics = []
    for dataset in sorted({r['dataset'] for r in rows}) + ['ALL']:
        for field in FIELDS:
            group = [d for d in details if d['field'] == field and (dataset == 'ALL' or d['dataset'] == dataset)]
            tp, fp, fn = (sum(d[x] for d in group) for x in ('tp', 'fp', 'fn'))
            support = len(group)
            metrics.append({'dataset': dataset, 'field': field, 'support': support,
                            'exact_match': sum(d['correct'] for d in group)/support if support else None,
                            'precision': tp/(tp+fp) if tp+fp else (0.0 if support else None),
                            'recall': tp/(tp+fn) if tp+fn else (0.0 if support else None),
                            'f1': 2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else (0.0 if support else None),
                            'tp': tp, 'fp': fp, 'fn': fn})
    completed = sum(x['ok'] for x in doc_rows)
    times = sorted(x['seconds'] for x in doc_rows if x['seconds'] is not None and not x['cache_hit'])
    micro_total = len(details)
    summary = {'documents': len(rows), 'successful_executions': completed,
               'execution_success_rate': completed/len(rows) if rows else None,
               'evaluated_field_instances': micro_total,
               'micro_exact_match': sum(x['correct'] for x in details)/micro_total if micro_total else None,
               'median_seconds_uncached': statistics.median(times) if times else None,
               'p95_seconds_uncached': times[min(len(times)-1, max(0, __import__('math').ceil(.95*len(times))-1))] if times else None,
               'latency_sample_size': len(times),
               'cer_layout_order_sensitive': sum(x['edits'] for x in ocr_errors)/sum(x['reference_characters'] for x in ocr_errors) if ocr_errors else None,
               'cer_documents': len(ocr_errors),
               'notes': ['CER usa orden geométrico de referencia y orden OCR; no es puntuación oficial SROIE.',
                         'Sin soporte no se reporta cero: queda null.', 'Métricas de extracción no acreditan validez fiscal.',
                         'Micro global tiene distinta cobertura por dataset; comparar también fecha y total por separado.']}
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    for name, content in [('metrics', metrics), ('errors', details), ('cer', ocr_errors), ('documents', doc_rows)]:
        pd.DataFrame(content).to_csv(out / f'{name}.csv', index=False, encoding='utf-8-sig')
    write_json(out / 'summary.json', summary)
    lines = ['# Resultados medidos', '', f"Documentos: {len(rows)}; ejecuciones correctas: {completed}.", '',
             '| Dataset | Campo | Soporte | Exactitud | F1 |', '|---|---|---:|---:|---:|']
    for m in metrics:
        if m['support']:
            lines.append(f"| {m['dataset']} | {m['field']} | {m['support']} | {m['exact_match']:.1%} | {m['f1']:.3f} |")
    lines += ['', 'Resultados iniciales; no son métricas finales ni del benchmark oficial.',
              'Campos sin anotación y referencias ambiguas están excluidos; ver cobertura EDA. Errores de ejecución permanecen en denominadores.']
    (out / 'RESULTADOS.md').write_text('\n'.join(lines), encoding='utf-8')
    return summary
