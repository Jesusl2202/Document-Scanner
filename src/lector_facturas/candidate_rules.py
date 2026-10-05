"""Reglas iniciales bilingües, candidatos y comprobaciones configurables."""
import re
from decimal import Decimal
from .common import FIELDS, MONEY, money, normalize, normalize_date, text_key
from .ocr import lines

KEYS = {
 'subtotal': r'\b(?:sub[\s-]*total|net\s+amount)\b',
 'tax': r'\b(?:tax\d*|vat|iva|gst|hst|sst|impuesto)\b',
 'total': r'\b(?:grand\s*total|net+t?\s*total|amount\s+due|balance\s+due|total\s+due|total|totaal|totalt|importe\s+total)\b',
 'tax_id': r'\b(?:ruc|rut|nit|tax\s*id|vat\s*(?:id|no))\b',
 'document_number': r'\b(?:invoice|receipt|factura|comprobante|ticket)\s*(?:number|no\.?|nro\.?|num\.?|#|numero|:)',
}
AMOUNT = re.compile(r'(?<![\w/.,])(?:[$€£]\s*)?[-+]?\d+(?:[.,]\d+)*(?![\w/%.,])')
DATE = re.compile(r"(?<![a-zA-Z0-9/])\d{1,4}([/.\-])\d{1,2}\1\d{2,4}(?![\d/])")
MONTH_DATE = re.compile(r"(?i)\b(?:\d{1,2}[\s./-]*(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*[\s,./'’°-]*\d{2,4}|(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*[\s./-]*\d{1,2}[\s,./'’°-]+\d{2,4})\b")


def extract(ocr, config):
    ls = lines(ocr['words'])
    candidates = {f: [] for f in FIELDS}
    norm = config['normalization']
    for i, line in enumerate(ls):
        text, key = line['text'], text_key(line['text'])
        # Textos ASCII para regex; posiciones solo se usan como evidencia de línea.
        named_dates = list(MONTH_DATE.finditer(text))
        # Rangos de promociones no se tratan como fecha única del comprobante.
        if len(named_dates) > 1:
            named_dates = []
        for m in list(DATE.finditer(text)) + named_dates:
            if normalize_date(m.group(), norm['date_order']) is not None:
                candidates['date'].append({'value': m.group(), 'score': 3 if re.search(r'\b(date|fecha)\b', key) else (2 if re.search(r'\d{1,2}:\d{2}',key) else 1),
                                           'box': line['box'], 'text': text, 'rule': 'recognized_date'})
        for field, pattern in KEYS.items():
            match = re.search(pattern, key)
            if not match:
                continue
            if field == 'total' and (re.search(KEYS['subtotal'], key) or re.search(r'\b(total\s+(?:items|qty|quantity|tax)|tax\s+total)\b', key)):
                continue
            if field == 'tax' and re.search(KEYS['tax_id'], key):
                continue
            tail = key[match.end():].strip(' :#')
            if field == 'tax' and re.search(r'#|\b(?:id|reg|registration|no|number)\b',key[match.end():]):
                continue
            if field == 'total':
                # Impuestos y pagos entregados no son el total de la compra.
                if re.search(r'\b(?:total\s*(?:gst|hst|sst|vat|iva)|(?:gst|hst|sst|vat|tax)\b.*\btotal|accepted\s+total|total\s+(?:gu|qty|quantity))\b',key):
                    continue
            # En TOTAL INCL GST@6% RM 57.40, la tasa no es otro importe.
            if field == 'total':
                tail = re.sub(r'\b(?:gst|vat|iva|hst|sst|tax)\s*@\s*\d+(?:[.,]\d+)?[a-z%]*', '', tail)
            # Etiquetas de impuesto/valores múltiples requieren abstención, no tomar el último.
            # Separar moneda pegada al valor, manteniendo sus cifras.
            tail = re.sub(r'\b(?:rm|usd|eur|gbp|idr|rp|rs)(?=\d)', '', tail)
            if field in MONEY:
                tail = re.sub(r'(?<![\w.,])([.,])(\d{1,2})(?![\d.,%])',r'0\1\2',tail)
            total_score = 3
            if field == 'total':
                # Excluir descuentos, cantidades y totales sin impuestos.
                if re.search(r'\b(discount|descuento|items?|count|qty|quantity|change|cambio|ahorro|savings)\b|\bexcl\w*|\bsin\s+impuestos\b', key):
                    continue

                # Priorizar el monto final después de ajustes.
                if re.search(r'\bafter\s+adj\w*|\btotal\s+final\b|\btotal\s+payable\b', key):
                    total_score = 6
                elif re.search(r'\bgrand\s+total\b|\bamount\s+due\b|\btotal\s+due\b|\bincl\w*|\binel\b', key):
                    total_score = 5

                # Recuperar dos decimales separados al final de la línea.
                tail = re.sub(
                    r'(?<![\w.,])([+-]?\d+)[.,]\s+(\d{2})(?=\s*$)',
                    r'\1.\2', tail
                )
                tail = re.sub(
                    r'(?<![\w.,])([+-]?\d+)\s+(\d{2})(?=\s*$)',
                    r'\1.\2', tail
                )

                # No adivinar cifras en montos como "4B 54".
                if re.search(r'\b\d+[a-z]+\b', tail):
                    continue
            if field in MONEY:
                # Rechaza tasas porcentuales y no confunde el 1 de TAX1 con un valor.
                amounts = [m.group().strip() for m in AMOUNT.finditer(tail)
                           if not tail[m.end():].lstrip().startswith('%') and money(m.group(), norm['decimal_separator']) is not None]
                if len(amounts) > 1:
                    continue
                if amounts:
                    candidates[field].append({'value': amounts[-1], 'score': total_score if field == 'total' else 3, 'box': line['box'], 'text': text, 'rule': 'label_same_line'})
                elif i + 1 < len(ls):
                    following = ls[i+1]
                    # Solo siguiente línea próxima con importe único y sin otra etiqueta.
                    height = max(1, line['box'][3] - line['box'][1])
                    near = 0 <= following['box'][1] - line['box'][3] <= 2 * height
                    value = following['text'].strip()
                    if near and money(value, norm['decimal_separator']) is not None:
                        candidates[field].append({'value': value, 'score': 1, 'box': following['box'], 'text': value, 'rule': 'label_next_line'})
            else:
                m = re.match(r'([a-z0-9][a-z0-9.\-/]*)', tail)
                if m and any(ch.isdigit() for ch in m.group(1)):
                    candidates[field].append({'value': m.group(1), 'score': 2, 'box': line['box'], 'text': text, 'rule': 'explicit_identifier_label'})
    values, evidence, alerts = {}, {}, []
    for f in FIELDS:
        options = sorted(candidates[f], key=lambda c: c['score'], reverse=True)
        values[f] = None
        evidence[f] = options
        if not options:
            alerts.append(f'{f}:no_candidate')
            continue
        best = [x for x in options if x['score'] == options[0]['score']]
        distinct = {normalize(f, x['value'], norm) for x in best}
        if len(distinct) > 1:
            if f == 'date':
                from collections import Counter
                counts = Counter(normalize(f, x['value'], norm) for x in best)
                ranked = counts.most_common()
                if ranked[0][1] >= 2 and ranked[0][1] > ranked[1][1]:
                    values[f] = next(x['value'] for x in best if normalize(f,x['value'],norm)==ranked[0][0])
                else:
                    alerts.append(f'{f}:ambiguous_candidates')
            else:
                alerts.append(f'{f}:ambiguous_candidates')
        else:
            values[f] = best[0]['value']
    return {'fields': values, 'evidence': evidence, 'alerts': alerts}


def validate(values, config):
    result = {}
    norm = config['normalization']
    for f in FIELDS:
        v = values.get(f)
        if v is None:
            result[f] = 'missing'
        elif f in MONEY:
            result[f] = 'valid_format' if money(v, norm['decimal_separator']) is not None else 'ambiguous_or_invalid_format'
        elif f == 'date':
            date = normalize_date(v, norm['date_order'])
            result[f] = 'invalid_format' if date is None else ('ambiguous_date_order' if date.startswith('AMBIGUOUS:') else 'valid_format')
    pattern = config['validation'].get('tax_id_pattern')
    result['tax_id'] = ('missing' if not values.get('tax_id') else 'not_configured')
    if pattern and values.get('tax_id'):
        result['tax_id'] = 'valid_structure' if re.fullmatch(pattern, values['tax_id']) else 'invalid_structure'
    result['amount_balance'] = 'not_applicable'
    if config['validation']['check_amount_balance']:
        amounts = [money(values.get(f), norm['decimal_separator']) for f in MONEY]
        if any(v is None for v in amounts):
            result['amount_balance'] = 'insufficient_data'
        else:
            subtotal, tax, total = map(Decimal, amounts)
            tolerance = Decimal(config['validation']['amount_tolerance'])
            result['amount_balance'] = 'consistent' if abs(subtotal + tax - total) <= tolerance else 'inconsistent_review'
    return result
