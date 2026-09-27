"""Adaptadores de SROIE (img/box/entities) y WildReceipt oficial, sin mezclar etiquetas."""
from pathlib import Path
import hashlib
import json
from PIL import Image
from .common import FIELDS, WILD_FIELDS, bbox, digest, gold_empty, inside, normalize, write_json, write_jsonl


def annotation_text(path, issues):
    raw = Path(path).read_bytes()
    try:
        return raw.decode('utf-8-sig')
    except UnicodeDecodeError:
        try:
            text = raw.decode('cp1252')
            issues.append('encoding_fallback_cp1252')
        except UnicodeDecodeError:
            text = raw.decode('latin-1')
            issues.append('encoding_fallback_latin1')
        return text


def record(image, dataset, source_split, doc_id, gold, regions, issues=None):
    row = {'id': f'{dataset}/{source_split}/{doc_id}', 'dataset': dataset,
           'source_split': source_split, 'image': str(Path(image).resolve()),
           'gold': gold, 'regions': regions, 'issues': list(issues or [])}
    try:
        row['sha256'] = digest(image)
        with Image.open(image) as im:
            im.load()
            row['width'], row['height'] = im.size
        for r in regions:
            x1, y1, x2, y2 = r['box']
            if not (0 <= x1 < x2 <= row['width'] and 0 <= y1 < y2 <= row['height']):
                row['issues'].append('invalid_box')
    except (OSError, ValueError) as e:
        row['sha256'] = None
        row['width'] = row['height'] = None
        row['issues'].append(f'image_error:{type(e).__name__}')
    return row


def sroie(root):
    """Reconoce train/test/{img,box,entities}; no asume cantidad oficial fija."""
    root = Path(root)
    rows = []
    for split in ('train', 'test'):
        images = root / split / 'img'
        if not images.is_dir():
            continue
        # Unión de IDs: una imagen faltante también debe quedar registrada.
        index = {}
        for image in sorted(images.iterdir()):
            if image.suffix.lower() in ('.jpg', '.jpeg', '.png'):
                if image.stem in index:
                    raise ValueError(f'ID de imagen repetido: {image.stem}')
                index[image.stem] = image
        entdir = root / split / 'entities'
        stems = set(index) | {p.stem for p in entdir.glob('*') if p.suffix in ('.txt', '.json')}
        for stem in sorted(stems):
            issues, regions, gold = [], [], gold_empty()
            entity_path = entdir / (stem + '.txt')
            if not entity_path.exists():
                entity_path = entdir / (stem + '.json')
            if entity_path.exists():
                try:
                    entities = json.loads(annotation_text(entity_path, issues))
                    for key, field in [('date', 'date'), ('total', 'total')]:
                        if key in entities:
                            value = str(entities[key]).strip() if entities[key] is not None else ''
                            gold[field] = {'status': 'annotated' if value else 'unannotated', 'value': value or None}
                except (ValueError, TypeError) as e:
                    issues.append('invalid_entities:' + str(e))
            else:
                issues.append('missing_entities')
            boxes = root / split / 'box' / (stem + '.txt')
            if boxes.exists():
                for line in annotation_text(boxes, issues).splitlines():
                    try:
                        values = line.split(',', 8)
                        regions.append({'box': bbox([float(x) for x in values[:8]]), 'text': values[8], 'label': None})
                    except (ValueError, IndexError):
                        issues.append('invalid_box_line')
            else:
                issues.append('missing_transcription')
            rows.append(record(index.get(stem, images / (stem + '.jpg')), 'sroie', split, stem, gold, regions, issues))
    if not rows:
        raise ValueError(f'SROIE vacío: se esperaba {root}/train/img y train/entities')
    return rows


def wildreceipt(root):
    root = Path(root)
    labels = {}
    for line in (root / 'class_list.txt').read_text(encoding='utf-8-sig').splitlines():
        if line.strip():
            code, name = line.split(maxsplit=1)
            labels[int(code)] = name.strip()
    if not set(WILD_FIELDS).issubset(set(labels.values())):
        raise ValueError('class_list no contiene las cuatro etiquetas de valores esperadas')
    rows = []
    for split in ('train', 'test'):
        path = root / f'{split}.txt'
        if not path.exists():
            continue
        for n, line in enumerate(path.read_text(encoding='utf-8-sig').splitlines(), 1):
            if not line.strip():
                continue
            try:
                item = json.loads(line)
                image = inside(root, item['file_name'])
            except (ValueError, KeyError) as e:
                raise ValueError(f'{path}:{n}: registro inválido') from e
            gold, regions, issues = gold_empty(), [], []
            collected = {f: [] for f in WILD_FIELDS.values()}
            for annotation in item['annotations']:
                try:
                    name = labels[int(annotation['label'])]
                    r = {'box': bbox(annotation['box']), 'text': annotation['text'], 'label': name}
                    regions.append(r)
                    if name in WILD_FIELDS and str(r['text']).strip():
                        collected[WILD_FIELDS[name]].append(str(r['text']).strip())
                except (KeyError, TypeError, ValueError):
                    issues.append('invalid_annotation')
            for f, values in collected.items():
                unique = list(dict.fromkeys(values))
                if len(unique) == 1:
                    gold[f] = {'status': 'annotated', 'value': unique[0]}
                elif len(unique) > 1:
                    # No se suman impuestos ni se escoge un total de referencia arbitrariamente.
                    gold[f] = {'status': 'ambiguous', 'value': None, 'candidates': unique}
            row = record(image, 'wildreceipt', split, item['file_name'], gold, regions, issues)
            if row['width'] and (row['width'] != item['width'] or row['height'] != item['height']):
                row['issues'].append('annotation_dimensions_mismatch')
            rows.append(row)
    if not rows:
        raise ValueError('WildReceipt sin registros')
    return rows


def prepare(sroie_root, wild_root, out, config):
    rows = []
    if sroie_root:
        rows.extend(sroie(sroie_root))
    if wild_root:
        rows.extend(wildreceipt(wild_root))
    if not rows:
        raise ValueError('Indicar --sroie y/o --wildreceipt; el avance completo requiere ambas')
    ids = [r['id'] for r in rows]
    if len(ids) != len(set(ids)):
        raise ValueError('Hay identificadores repetidos; no se sobrescribe el manifiesto')
    fraction = config['validation_fraction']
    if not 0 < fraction < 1:
        raise ValueError('validation_fraction debe estar entre 0 y 1')
    test_hashes = {r['sha256'] for r in rows if r['source_split'] == 'test' and r['sha256']}
    seen = set()
    for row in sorted(rows, key=lambda r: (r['source_split'] != 'test', r['id'])):
        h = row['sha256']
        row['split'] = 'test' if row['source_split'] == 'test' else 'train'
        if row['source_split'] != 'test':
            key = h or row['id']
            score = int(hashlib.sha256(f"{config['seed']}:{key}".encode()).hexdigest()[:8], 16) / 2**32
            row['split'] = 'validation' if score < fraction else 'train'
            if h and h in test_hashes:
                row['split'] = 'quarantine'
                row['issues'].append('duplicate_in_official_test')
        if h and h in seen:
            row['split'] = 'quarantine'
            row['issues'].append('duplicate_image_hash')
        if h:
            seen.add(h)
    out = Path(out)
    write_jsonl(out / 'manifest.jsonl', rows)
    write_json(out / 'manifest_metadata.json', {
        'seed': config['seed'], 'validation_fraction': fraction,
        'sources': {'sroie': str(sroie_root), 'wildreceipt': str(wild_root)},
        'count': len(rows), 'note': 'Split determinista por hash de imagen; test oficial reservado. Sin agrupación por emisor.'})
    return rows
