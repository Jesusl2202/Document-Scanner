"""EDA de desarrollo; test se limita al inventario, sin distribuciones de etiquetas."""
from collections import Counter
from pathlib import Path
import pandas as pd
from .common import FIELDS, write_json


def run_eda(rows, out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    development = [r for r in rows if r['split'] in ('train', 'validation')]
    inventory, coverage, incidents = [], [], []
    for r in rows:
        for issue in r['issues']:
            incidents.append({'id': r['id'], 'dataset': r['dataset'], 'split': r['split'], 'issue': issue})
    for r in development:
        inventory.append({'id': r['id'], 'dataset': r['dataset'], 'split': r['split'],
                          'width': r['width'], 'height': r['height'], 'regions': len(r['regions']),
                          'readable': r['width'] is not None})
    for dataset in sorted({r['dataset'] for r in development}):
        subset = [r for r in development if r['dataset'] == dataset]
        for field in FIELDS:
            counts = Counter(r['gold'][field]['status'] for r in subset)
            coverage.append({'dataset': dataset, 'field': field, 'documents': len(subset),
                             'annotated': counts['annotated'], 'unannotated': counts['unannotated'],
                             'ambiguous': counts['ambiguous'], 'coverage': counts['annotated'] / len(subset)})
    pd.DataFrame(inventory).to_csv(out / 'documents.csv', index=False, encoding='utf-8-sig')
    pd.DataFrame(coverage).to_csv(out / 'coverage.csv', index=False, encoding='utf-8-sig')
    pd.DataFrame(incidents, columns=['id', 'dataset', 'split', 'issue']).to_csv(out / 'incidents.csv', index=False, encoding='utf-8-sig')
    summary = {'total_manifest': len(rows), 'development_documents': len(development),
               'split_counts': dict(Counter(r['split'] for r in rows)),
               'datasets': dict(Counter(r['dataset'] for r in development)),
               'incident_counts': dict(Counter(i['issue'] for i in incidents)),
               'test_policy': 'No se exploran etiquetas de test; solo integridad y duplicados.',
               'limitations': ['Cobertura de anotación no equivale a exactitud.', 'Duplicados por SHA256; no detecta plantillas parecidas.']}
    write_json(out / 'summary.json', summary)
    if coverage:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        table = pd.DataFrame(coverage).pivot(index='field', columns='dataset', values='coverage')
        ax = table.plot.bar(figsize=(9, 4), ylim=(0, 1), ylabel='Fracción con anotación utilizable', title='Cobertura real de etiquetas — desarrollo')
        ax.figure.tight_layout()
        ax.figure.savefig(out / 'coverage.png', dpi=140)
        plt.close(ax.figure)
    lines = ['# EDA de Semana 2', '', f"Documentos en manifiesto: {len(rows)}. Desarrollo: {len(development)}.", '',
             '| Dataset | Campo | Anotados | Total desarrollo | Cobertura |', '|---|---|---:|---:|---:|']
    for c in coverage:
        lines.append(f"| {c['dataset']} | {c['field']} | {c['annotated']} | {c['documents']} | {c['coverage']:.1%} |")
    lines += ['', 'No confundir etiquetas ausentes con campos que el extractor omitió. Casos con varias referencias se excluyen explícitamente hasta revisarlos.',
              'Revisar incidents.csv antes de entrenar o evaluar. Test oficial no se usa para diseñar reglas.']
    (out / 'EDA.md').write_text('\n'.join(lines), encoding='utf-8')
    return summary
