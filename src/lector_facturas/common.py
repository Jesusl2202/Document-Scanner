"""Esquema común, serialización y normalización sin inferir datos ausentes."""
from pathlib import Path
from decimal import Decimal, InvalidOperation
from datetime import date
import hashlib
import json
import re
import unicodedata

FIELDS = ("tax_id", "date", "document_number", "subtotal", "tax", "total")
MONEY = ("subtotal", "tax", "total")
WILD_FIELDS = {"Date_value": "date", "Subtotal_value": "subtotal", "Tax_value": "tax", "Total_value": "total"}


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")


def read_jsonl(path):
    rows = []
    for n, line in enumerate(Path(path).read_text(encoding="utf-8-sig").splitlines(), 1):
        if line.strip():
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"JSON inválido en {path}, línea {n}") from exc
    return rows


def write_jsonl(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r, ensure_ascii=False, allow_nan=False) + "\n" for r in rows), encoding="utf-8")


def digest(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def text_key(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", s).strip()


def money(s, decimal_separator="auto"):
    """Decimal conservador. Un separador con tres cifras finales es ambiguo en auto."""
    if s is None:
        return None
    t = str(s).strip()
    if '%' in t:
        return None
    negative = t.startswith('(') and t.endswith(')')
    t = re.sub(r"(?i)\b(?:usd|eur|gbp|rm|idr|rp|rs)(?=\d|\s|[.:+-]|$)[.:]?", "", t)
    t = re.sub(r"[$€£¥\s()]", "", t)
    # Admite .00 y ,00 sin inventar decimales en enteros.
    t = re.sub(r'^([+-]?)([.,])(?=\d{1,2}$)', r'\g<1>0\2', t)
    if not re.fullmatch(r"[+-]?\d[\d.,]*", t):
        return None
    if decimal_separator in ('.', ','):
        other = ',' if decimal_separator == '.' else '.'
        if other in t:
            integer = t.split(decimal_separator)[0]
            if not re.fullmatch(r"[+-]?\d{1,3}(?:" + re.escape(other) + r"\d{3})+", integer):
                return None
        t = t.replace(other, '').replace(decimal_separator, '.')
    elif ',' in t and '.' in t:
        sep = ',' if t.rfind(',') > t.rfind('.') else '.'
        return money(s, sep)
    elif ',' in t or '.' in t:
        sep = ',' if ',' in t else '.'
        parts = t.split(sep)
        if len(parts) != 2 or len(parts[1]) not in (1, 2):
            return None
        t = t.replace(sep, '.')
    try:
        v = Decimal(t)
        if negative:
            v = -v
        return format(v.quantize(Decimal('0.01')), 'f')
    except InvalidOperation:
        return None


def _numeric_date(s, date_order="auto"):
    if s is None:
        return None
    t = text_key(s)
    m = re.search(r"(?<!\d)(\d{1,4})[/.\-](\d{1,2})[/.\-](\d{2,4})(?!\d)", t)
    if not m:
        return None
    a, b, c = map(int, m.groups())
    if len(m.group(1)) == 4:
        year, month, day = a, b, c
    else:
        year = c if c >= 100 else (2000 + c if c < 70 else 1900 + c)
        if date_order == 'dmy' or (date_order == 'auto' and a > 12):
            day, month = a, b
        elif date_order == 'mdy' or (date_order == 'auto' and b > 12):
            month, day = a, b
        elif a == b:
            month, day = a, b
        else:
            # No se inventa un país: conserva la ambigüedad explícita.
            return f"AMBIGUOUS:{a:02d}/{b:02d}/{year}"
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return None



def normalize_date(s, date_order="auto"):
    numeric = _numeric_date(s, date_order)
    if numeric is not None or s is None:
        return numeric
    text = text_key(s)
    months = {name:i+1 for i,name in enumerate(['jan','feb','mar','apr','may','jun','jul','aug','sep','oct','nov','dec'])}
    month = r'(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*'
    match = re.search(r'\b(\d{1,2})[\s./\-]*'+month+r'[\s,./\'’°\-]*(\d{2,4})\b',text)
    if match:
        day, mon, year = match.groups()
    else:
        match = re.search(r'\b'+month+r'[\s./\-]*(\d{1,2})[\s,./\'’°\-]+(\d{2,4})\b',text)
        if not match:
            return None
        mon, day, year = match.groups()
    year = int(year)
    if year < 100:
        year += 2000 if year < 70 else 1900
    try:
        return date(year,months[mon],int(day)).isoformat()
    except ValueError:
        return None

def normalize(field, value, config=None):
    if value is None or str(value).strip() == '':
        return None
    config = config or {}
    if field in MONEY:
        parsed = money(value, config.get('decimal_separator', 'auto'))
        return parsed if parsed is not None else 'RAW:' + text_key(value).replace(' ', '')
    if field == 'date':
        parsed = normalize_date(value, config.get('date_order', 'auto'))
        return parsed if parsed is not None else 'RAW:' + text_key(value)
    return re.sub(r"\s+", '', str(value)).upper()


def gold_empty():
    return {f: {'status': 'unannotated', 'value': None} for f in FIELDS}


def bbox(coords):
    if len(coords) == 4:
        return [float(x) for x in coords]
    if len(coords) != 8:
        raise ValueError('Caja debe tener 4 u 8 coordenadas')
    xs, ys = coords[::2], coords[1::2]
    return [float(min(xs)), float(min(ys)), float(max(xs)), float(max(ys))]


def inside(root, name):
    root = Path(root).resolve()
    path = (root / name).resolve()
    if not path.is_relative_to(root):
        raise ValueError(f'Ruta fuera del dataset: {name}')
    return path
