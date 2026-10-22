"""V7: consenso de V6 con jerarquía de etiquetas, votos ponderados y difusos, tablas aritméticas
y fechas tolerantes al ruido del OCR. No recibe dataset, gold ni anotaciones y no inventa importes:
solo elige entre valores que alguna lectura realmente produjo."""
import re
from collections import defaultdict
from decimal import Decimal
from itertools import combinations
from .common import FIELDS, MONEY, normalize, money
from .candidate_rules import extract as old_extract, MONTH_DATE
from .geometry import grouped

LABELS={
 'subtotal':r'\b(?:sub\s*[-:]?\s*tota[l1|!)]?|s[ -]total|net\s+amount|netto(?:umsatz)?|before\s+tax)\b',
 'tax':r'\b(?:sales\s+tax|tax(?:es|[12])?|vat|gst|hst|sst|iva|moms|mwst|btw)\b',
 'total':r'\b(?:grand\s+total|amount\s+due|balance(?:\s+due)?|a[mn]ount\s+incl\.?|total\s+payable|final\s+total|net+\s*total|rounded\s+total|total\s+rounded|toataal|totaal(?:rekening)?|totalt|total|tota[!|)]|otal|tien\s+mat)\b'}
STRONG_TOTAL=r'grand|amount\s+due|payable|incl|inc\.|final|net+\s*total|round'
PAYMENT=re.compile(r'\b(?:cash|paid|tender\w*|card|visa|master\w*|debit|credit|received|payment|amex)\b')
AMT=re.compile(r'(?<![\w/.,])(?:[$€£]\s*)?[+-]?(?:\d+(?:[.,]\d+)*|[.,]\d{1,2})(?![\w/.,])')
NOISE=r'(?:rm|rn|pm|fm|tm|am|em|im|om|um|hm|nm|mm|rrm)'
MONTH_FIX={'3an':'jan','ian':'jan','0ct':'oct','oc7':'oct','5ep':'sep','0ec':'dec','de0':'dec','fe6':'feb','ju1':'jul','au9':'aug'}
VIEW_WEIGHT_PRIMARY=1.5
# Interruptores solo para ablación (apagar uno mide cuánto aporta); por defecto todo activo.
FLAGS=dict(fuzzy=True,dominance=True,corroboration=True,balance=True,payment=True,triples=True,dates=True,glyphs=True,total_from_subtotal=True)

def clean(text):
    text=text.lower()
    text=re.sub(r'\bsub\s*tota[|!)]','subtotal',text)
    text=re.sub(r'\btota[|!)]','total',text)
    text=re.sub(r'\btota\s?(?:li|[li1|!)])(?=\W|$)','total',text)
    text=re.sub(r'\bt[o0]tal\b|\btotai\b','total',text)
    # Moneda deformada y pegada a un importe con forma decimal (RM7.00 leído como pm7.00).
    if FLAGS['glyphs']:text=re.sub(r'\b'+NOISE+r'(?=[\do&]*[.,]\s?[\do&]{2}(?!\d))','',text)
    text=re.sub(r'\b(?:rm|usd|eur|gbp|sgd)(?=\d)','',text)
    text=re.sub(r'(\d)\s*([.,])\s*(\d)',r'\1\2\3',text)
    # O->0 y &->8 solo dentro de un token con forma decimal, nunca en prosa.
    text=re.sub(r'(?<!\w)[\do&]+[.,][\do&]{2}(?!\w)',lambda m:m.group().replace('o','0').replace('&','8' if FLAGS['glyphs'] else '&'),text)
    return text


def semantic_amounts(ocr, config, result):
    """Associate observed monetary tokens with semantic labels before voting.

    No reference annotations, dataset identifiers or inferred amounts are used.
    Different preprocessing views corroborate evidence, not independent samples.
    Rates, identifiers, tips and service charges are not tax amounts.
    """
    import math
    patterns = {
        'subtotal': r'\b(?:sub[\s.,-]*total[e]?|subttl|sous[\s-]*total|netto|net\s+amount|net\s+ttl|base\s+imponible|facturaci[oó]n\s+neta|before\s+tax|mdse\s+st)\b',
        'tax': r'\b(?:sales\s+tax|total\s+tax|tax[12]?|vat[s]?|[csi]?gst|hst|sst|iva|tva|mwst|btw|impuesto[s]?)\b',
        'total': r'\b(?:grand\s+total|total\s+due|amount\s+due|balance\s+due|to\s+pay|[aà]\s+payer|total[e]?|totaal|totalt|summe|sum)\b'
    }
    buckets = {f: defaultdict(list) for f in MONEY}
    views = ocr.get('views') or [ocr]
    for vi, view in enumerate(views):
        rows = grouped(view)
        for i, row in enumerate(rows):
            text = clean(row['text'])
            text = re.sub(r'\bg[.]s[.]t[.]?', 'gst', text)
            h = max(1, row['box'][3]-row['box'][1])
            # Card slips distinguish the amount before a tip from final total.
            if re.search(r'\bamount\b',text) and not re.search(r'\bdue\b',text):
                following = ' '.join(clean(r['text']) for r in rows[i+1:i+3])
                if re.search(r'\btip\b',following):
                    vals = decimal_amounts(text,config)
                    if len(vals)==1:
                        raw,value,_,_=vals[0]
                        buckets['subtotal'][value].append(dict(value=raw,normalized=value,
                            view=vi,score=9,rule='semantic_before_tip',text=text,box=row['box']))
            for field, pat in patterns.items():
                hit = re.search(pat, text)
                if not hit:
                    continue
                if field == 'tax' and re.search(r'\b(?:reg(?:istration)?|id|number|taxpayer)\b|\b(?:gst|vat|tax)\s*no\b', text):
                    continue
                if field == 'total' and (re.search(patterns['subtotal'], text) or re.search(r'\b(?:total\s+(?:tax|gst|vat|items|qty|quantity|savings|discount)|(?:tax|gst|vat|hst)\s+total)\b', text)):
                    continue
                if field == 'total' and re.search(r'excl|before\s+tax|includes?.*\b(?:tax|gst|vat)\s+of\b', text):
                    continue
                if field == 'tax' and re.search(r'\b(?:excl|excluding|before)\b', text):
                    continue
                # A total inclusive of tax is a gross amount, not a tax amount.
                if field == 'tax' and re.search(r'\btotal\b.*\b(?:incl|inclusive)\b', text) and not re.search(r'\b(?:tax|gst|vat)\s+of\b', text):
                    continue
                tail = text[hit.end():]
                # Stop at the next semantic label (TAX .26 BAL 2.24).
                tail = re.split(r'\b(?:bal(?:ance)?|cash|change|subtotal|total)\b', tail)[0]
                found = decimal_amounts(tail, config)
                quality = 9
                if field == 'tax':
                    rate = re.search(r'(\d+(?:[.,]\d+)?)\s*%',text)
                    all_values = decimal_amounts(text,config)
                    if rate and len(all_values)==2:
                        rate_value=Decimal(rate.group(1).replace(',','.'))/100
                        low,high=sorted(all_values,key=lambda a:Decimal(a[1]))
                        tax_value,base_value=Decimal(low[1]),Decimal(high[1])
                        if 0 < rate_value < 1 and base_value > tax_value and (
                            abs(tax_value-base_value*rate_value)<=Decimal('.02')
                            or abs(tax_value-base_value*rate_value/(1+rate_value))<=Decimal('.02')):
                            found=[low]
                            quality=11
                if field == 'tax' and len(found) > 1:
                    # In rate/base/tax rows the terminal amount is tax only
                    # when a printed percentage is present and it is smaller.
                    if '%' in tail and Decimal(found[-1][1]) < min(Decimal(v[1]) for v in found[:-1]):
                        found = found[-1:]
                    else:
                        continue
                if len(found) > 1:
                    continue
                if found:
                    raw, value, _, _ = found[0]
                    box = row['box']
                else:
                    # A value may be on the next geometric row. Require
                    # a short gap and alignment; never cross another label.
                    candidates = []
                    for nxt in rows[i+1:i+3]:
                        if not -0.25*h <= nxt['box'][1]-row['box'][3] <= 1.7*h:
                            continue
                        nt = clean(nxt['text'])
                        if any(re.search(p, nt) for p in patterns.values()):
                            break
                        if re.search(r'\b(?:cash|change|tip|service|card|qty)\b', nt):
                            break
                        vals = decimal_amounts(nt, config)
                        if len(vals) != 1 or len(re.findall('[a-z]', nt)) > 6:
                            continue
                        if nxt['box'][2] < row['box'][0] or nxt['box'][0] > row['box'][2]+8*h:
                            continue
                        candidates.append((vals[0], nxt))
                    if len(candidates) != 1:
                        continue
                    (raw,value,_,_), nxt = candidates[0]
                    box = nxt['box']
                    quality = 7
                if field == 'total' and re.search(r'grand|due|payable|to\s+pay|payer', text):
                    quality += 2
                # Explicit tax-of phrasing resolves "total includes ... tax of".
                if field == 'tax' and re.search(r'\b(?:tax|gst|vat)\s+of\b', text):
                    quality += 1
                buckets[field][value].append(dict(value=raw, normalized=value,
                    view=vi, score=quality, rule='semantic_label', text=text, box=box))
    chosen = {}
    for field, values in buckets.items():
        ranked = []
        for value, items in values.items():
            sources = {e['view'] for e in items}
            quality = max(e['score'] for e in items)
            # At least two views for overriding an established result.
            current = normalize(field,result['fields'].get(field),config['normalization'])
            if len(sources) < 2 and current is not None and current != value:
                continue
            if len(sources) < 2 and quality < 9:
                continue
            score = quality + 2*math.log2(1+len(sources))
            ranked.append((score, value, items))
        ranked.sort(key=lambda x:x[0],reverse=True)
        if not ranked:
            continue
        if len(ranked)>1 and ranked[0][0]-ranked[1][0] < .75:
            result['alerts'].append(field+':semantic_conflict')
            continue
        chosen[field] = ranked[0]
    for field, (_, value, items) in chosen.items():
        current = normalize(field,result['fields'].get(field),config['normalization'])
        if current and current != value:
            if not current.startswith('RAW:') and Decimal(current) < 0:
                # Credit notes/refunds may legitimately have negative totals.
                continue
            # Keep existing corroborated monetary evidence. New labels fill
            # gaps; they do not discard a supported rounding/payment result.
            if current in buckets[field] or field == 'subtotal' or near(current,value):
                continue
            if Decimal(value) == 0 and field == 'total':
                continue
            protected = [e for e in result['evidence'][field]
                         if e.get('normalized') == current and e.get('score',0) >= 8
                         and e.get('rule') in ('visual_label','rounded_total','cash_change','fiscal_table')]
            if field == 'total' and protected:
                continue
        if current != value:
            result['alerts'].append(field+':semantic_selection')
        result['fields'][field] = items[0]['value']
        result['evidence'][field].extend(items)
        if field == 'total' and 'total:from_subtotal' in result['alerts']:
            result['alerts'].remove('total:from_subtotal')

def amounts(text,config):
    out=[]
    for m in AMT.finditer(text):
        if text[m.end():].lstrip().startswith('%'):continue
        val=money(m.group(),config['normalization']['decimal_separator'])
        if val is not None and Decimal(val)>=0:out.append((m.group(),val,m.start(),m.end()))
    return out

def year_of(norm):
    if norm is None or norm.startswith('RAW:'):return None
    try:return int(norm.split('/')[-1]) if norm.startswith('AMBIGUOUS:') else int(norm[:4])
    except ValueError:return None

EXPIRY=re.compile(r'(?:exp\w*|valid|until|thru|use\s+by|best\s+before|due|return\w*|retour\w*)[\s:.]*$')

def date_rows(rows,add):
    """Fechas con separadores mezclados, meses mal leídos y formato compacto AAAAMMDD."""
    for row in rows:
        raw=row['text']
        for m in re.finditer(r'(?<![\d/.\-])(\d{1,4})\s*[/.\-]\s*(\d{1,2})\s*[/.\-]\s*(\d{2,4})(?![\d/])',raw):
            if EXPIRY.search(raw[max(0,m.start()-16):m.start()]):continue
            add('date',f'{m.group(1)}/{m.group(2)}/{m.group(3)}',5,raw,'date_lenient',row['box'])
        fixed=re.sub(r'(?<=\d)\s*('+'|'.join(MONTH_FIX)+r')\s*(?=\d)',lambda m:' '+MONTH_FIX[m.group(1)]+' ',raw)
        if fixed!=raw:
            hits=list(MONTH_DATE.finditer(fixed))
            if len(hits)==1:add('date',hits[0].group(),5,raw,'date_month_fix',row['box'])
        for m in re.finditer(r'(?<!\d)(20[012]\d)(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])(?!\d)',raw):
            add('date',f'{m.group(1)}-{m.group(2)}-{m.group(3)}',2,raw,'date_compact',row['box'])

def numeric_row(row,config):
    text=clean(row['text'])
    if len(re.findall(r'[a-z]',text))>8:return text,[]
    return text,[(raw,Decimal(val)) for raw,val,_,_ in amounts(text,config) if re.search(r'[.,]\d{1,2}$',raw.strip())]

def triples(rows,config,add,height=None):
    """Tres cifras con a+b=c exacto en una fila (o en dos filas contiguas del tramo inferior):
    subtotal, impuesto y total ya impresos."""
    pairs=[]
    for i,row in enumerate(rows):
        text,found=numeric_row(row,config);pairs.append((row,text,found))
        if i+1<len(rows) and height and row['box'][1]>0.4*height:
            nxt=rows[i+1];h=max(1,row['box'][3]-row['box'][1])
            if -h<=nxt['box'][1]-row['box'][3]<=1.5*h:
                t2,f2=numeric_row(nxt,config)
                if found and f2 and len(found)+len(f2)>=3:pairs.append((dict(row,box=nxt['box']),text+' / '+t2,found+f2))
    for row,text,found in pairs:
        if not 3<=len(found)<=5:continue
        for combo in combinations(range(len(found)),3):
            items=sorted((found[i] for i in combo),key=lambda t:t[1])
            (r1,a),(r2,b),(r3,c)=items
            if a<=0 or a+b!=c:continue
            if not Decimal('0.02')<=a/b<=Decimal('0.30'):continue
            add('tax',r1,9,text,'arithmetic_row',row['box'])
            add('subtotal',r2,9,text,'arithmetic_row',row['box'])
            add('total',r3,9,text,'arithmetic_row',row['box'])
            return

def single(ocr,config):
    norm=config['normalization']
    base=old_extract(ocr,config)
    cand={f:[] for f in FIELDS}
    def add(f,value,score,text,rule,box=None):
        n=normalize(f,value,norm)
        if n is None or n.startswith('RAW:'):return
        if f in MONEY:
            raw=str(value).strip()
            if not re.search(r'[.,]\s?\d{1,2}$',raw):score-=3
            if re.match(r'^[+-]?[.,]\d{1,2}$',raw):score-=4
            score=max(score,1)
        if f=='date':
            y=year_of(n)
            if y is None or not 2000<=y<=2035:return
        cand[f].append(dict(value=value,score=score,text=text,rule=rule,box=box))
    for f,v in base['fields'].items():
        if v is not None:
            supporting=[e for e in base['evidence'][f] if normalize(f,e['value'],norm)==normalize(f,v,norm)]
            if config.get('printed_improvements') and f=='total' and supporting and all(re.search(r'\b(?:hst|sst|gst|vat|tax|iva|tay)\b.*\btotal',e['text'],re.I) for e in supporting):continue
            if config.get('printed_improvements') and f=='date' and supporting and all(re.search(r'expir|return\s+by|valid\s+until|certific|vencim',e['text'],re.I) for e in supporting):continue
            add(f,v,7,'','v5_fallback')
    rows=grouped(ocr)
    rebuilt=dict(ocr,words=[dict(text=r['text'],box=r['box'],confidence=90,line_id=str(i)) for i,r in enumerate(rows)])
    dated=old_extract(rebuilt,config)['fields'].get('date')
    if dated:add('date',dated,5,'','date_geometry')
    if FLAGS['dates']:date_rows(rows,add)
    if config.get('printed_improvements'):printed_candidates(rows,config,add)
    if config.get('accounting_improvements'):accounting_candidates(rows,config,add)
    for i,row in enumerate(rows):
        text=clean(row['text']);h=max(1,row['box'][3]-row['box'][1])
        for field,pattern in LABELS.items():
            match=re.search(pattern,text)
            if not match:continue
            prefix,tail=text[:match.start()],text[match.end():]
            if config.get('printed_improvements') and field=='total':
                if re.search(r'\b(?:hst|sst|gst|vat|tax|iva|tay)\b',prefix):continue
                if re.search(r'(?:total|otal)\s+includes?\s+[0-9o.,]+%\s*(?:gst|hst|sst|vat|tax)',text):continue
                if re.search(r'total\s+(?:con\s+letra|in\s+words|points)',text):continue
            if field=='total':
                if re.search(r'sub\s*total|discount|savings|change|accepted\s+total|supplies|total\s+(?:items|qty|quantity|tax|gst)|(?:gst|vat|tax)\b.*\btotal|excl',text):continue
            if field=='tax':
                if re.search(r'\b(?:reg|registration|number|chk|guest|guests|cashier)\b|#|\b(?:tax|gst|vat|hst|sst)\s*(?:id|no)\b|\bid\s*(?:no|number)\b|\bno\s*[:.]',text):continue
                if re.search(r'total|incl|excl',prefix):continue
            tail=re.sub(r'\b(?:gst|vat|tax)\s*@\s*\d+(?:[.,]\d+)?[a-z%]*','',tail)
            found=amounts(tail,config)
            if field=='tax' and len(found)>1 and '%' in tail:
                found=[v for v in found if re.search(r'[.,]',v[0])]
            if field=='tax' and len(found)>=2 and re.search(r'%|\bon\b',tail):
                vals=[Decimal(v[1]) for v in found]
                if vals[-1]<min(vals[:-1]):found=found[-1:]
            if len(found)==1:
                score=7 if field!='total' else 6
                if field=='total' and re.search(STRONG_TOTAL,text):score=8
                if config.get('printed_improvements') and field=='total' and re.search(r'[.,]\d{2}$',found[0][0]):
                    if any(re.search(r'rounding|redondeo',clean(r['text'])) for r in rows[max(0,i-2):i]):score=9
                add(field,found[0][0],score,text,'visual_label',row['box'])
            elif not found:
                for nxt in rows[i+1:i+3]:
                    if not 0<=nxt['box'][1]-row['box'][3]<=1.5*h:continue
                    raw=clean(nxt['text']).strip(' :|')
                    val=money(raw,norm['decimal_separator'])
                    if val is not None:add(field,raw,4,text+' / '+raw,'near_value',nxt['box'])
        headers=list(re.finditer(r'\b(net|netto|gross|brutto|vat|moms)\b',row['text']))
        if len(headers)>=3 and any(m.group() in ('net','netto') for m in headers):
            for nxt in rows[i+1:i+3]:
                if nxt['box'][1]-row['box'][3]>3*h:continue
                tokens=[]
                for a,b,box in nxt['spans']:
                    raw=clean(nxt['text'][a:b]);val=money(raw,norm['decimal_separator'])
                    if val is not None:tokens.append((raw,box))
                for m in headers:
                    spans=[box for a,b,box in row['spans'] if a<m.end() and b>m.start()]
                    if not spans or not tokens:continue
                    hb=spans[0];cx=(hb[0]+hb[2])/2
                    raw,box=min(tokens,key=lambda t:abs((t[1][0]+t[1][2])/2-cx))
                    if abs((box[0]+box[2])/2-cx)>max(2*h,hb[2]-hb[0]):continue
                    f={'net':'subtotal','netto':'subtotal','gross':'total','brutto':'total','vat':'tax','moms':'tax'}[m.group()]
                    add(f,raw,7,row['text']+' / '+nxt['text'],'tax_table_column',box)
    if FLAGS['triples']:triples(rows,config,add,ocr.get('height'))
    if FLAGS['payment']:payment(rows,config,add)
    if config.get('amount_context'):context_amounts(rows,config,add,cand)
    if config.get('spatial_amounts'):spatial_amount_candidates(rows,config,add,cand)
    # Importes en filas de pago, para corroborar el total (no para inventarlo).
    paid=set()
    for row in rows:
        t=clean(row['text'])
        if PAYMENT.search(t):
            for raw,val,_,_ in amounts(t,config):paid.add(val)
    return cand,paid

CASH=re.compile(r'\b(?:cash|tender\w*|amount\s+paid|paid|received)\b')
CARD=re.compile(r'\b(?:visa|master\w*|debit|credit|card|amex)\b')
CHANGE=re.compile(r'\bchange\b')

def decimal_amounts(text,config,integers=False):
    return [f for f in amounts(text,config) if integers or re.search(r'[.,]\d{1,2}$',f[0].strip())]

def label_amount(rows,i,text,config,integers=False):
    found=decimal_amounts(text,config,integers)
    if len(found)==1:return found[0][1]
    if found:return None
    h=max(1,rows[i]['box'][3]-rows[i]['box'][1])
    for nxt in rows[i+1:i+3]:
        if 0<=nxt['box'][1]-rows[i]['box'][3]<=1.5*h:
            f=decimal_amounts(clean(nxt['text']).strip(' :|'),config,integers)
            if len(f)==1:return f[0][1]
    return None

def payment(rows,config,add):
    """Total pagado = efectivo - cambio, o tarjeta/efectivo exacto. No se inventa nada:
    el valor debe aparecer como cifra leída en otra fila (salvo cambio cero)."""
    tokens=defaultdict(set);cash=[];change=[];card=[]
    for i,row in enumerate(rows):
        t=clean(row['text'])
        for raw,val,_,_ in amounts(t,config):tokens[val].add(i)
        if re.search(r'cashier|exchange',t):continue
        if CHANGE.search(t):
            v=label_amount(rows,i,t[CHANGE.search(t).end():],config,integers=True)
            if v is not None:change.append((Decimal(v),i))
        elif CASH.search(t):
            v=label_amount(rows,i,t[CASH.search(t).end():],config)
            if v is not None:cash.append((Decimal(v),i))
        elif CARD.search(t):
            v=label_amount(rows,i,t[CARD.search(t).end():],config)
            if v is not None:card.append((Decimal(v),i))
    if cash:
        x,xi=cash[0]
        if change:
            y,yi=change[0];t=x-y
            if t>0 and (y==0 or any(r not in (xi,yi) for r in tokens.get(format(t,'.2f'),()))):
                add('total',format(t,'.2f'),9,'cash-change','cash_minus_change',rows[xi]['box'])
        elif x>0:add('total',format(x,'.2f'),5,'cash','cash_exact',rows[xi]['box'])
    elif card and card[0][0]>0:add('total',format(card[0][0],'.2f'),5,'card','card_exact',rows[card[0][1]]['box'])

def near(a,b):
    if a==b or a.startswith('RAW:') or b.startswith('RAW:'):return False
    la,lb=len(a),len(b)
    if abs(la-lb)>1:return False
    if la==lb:return sum(x!=y for x,y in zip(a,b))==1
    s,l=(a,b) if la<lb else (b,a)
    return any(l[:i]+l[i+1:]==s for i in range(len(l)))

def is_primary(view):
    o=view.get('options',{});return o.get('preprocess')=='resize' and o.get('psm')==6

def extract(ocr,config):
    views=ocr.get('views') or [ocr]
    hp=config.get('consensus_parameters',{})
    weight=[hp.get('primary_weight',VIEW_WEIGHT_PRIMARY) if is_primary(v) else 1.0 for v in views]
    evidence={f:[] for f in FIELDS};groups={f:{} for f in FIELDS};paid_by_view=[]
    for vi,view in enumerate(views):
        cand,paid=single(view,config);paid_by_view.append(paid)
        for f,items in cand.items():
            best={}
            for item in items:
                k=normalize(f,item['value'],config['normalization'])
                if k not in best or item['score']>best[k]['score']:best[k]=item
            for k,item in best.items():
                evidence[f].append(dict(item,view=vi,normalized=k))
                g=groups[f].setdefault(k,dict(views={},score=0))
                g['views'][vi]=max(g['views'].get(vi,0),item['score']);g['score']=max(g['score'],item['score'])
    confidence_votes={}
    if config.get('confidence_consensus'):
        for vi,view in enumerate(views):
            for word in view.get('words',[]):
                raw=str(word.get('text','')).strip(':;|')
                conf=max(0,min(100,float(word.get('confidence',0))))/100
                for f in ('date','subtotal','tax','total'):
                    k=normalize(f,raw,config['normalization'])
                    if k in groups[f]:
                        key=(f,k,vi);confidence_votes[key]=max(confidence_votes.get(key,0),conf)
    # Consistencia aritmética: subtotal + impuesto = total entre valores realmente leídos.
    balanced=set()
    for s,gs in groups['subtotal'].items():
        for t,gt in groups['tax'].items():
            try:ds,dt=Decimal(s),Decimal(t)
            except Exception:continue
            if dt<=0 or ds<dt:continue
            if str(ds+dt) in groups['total'] or format(ds+dt,'.2f') in groups['total']:
                balanced.update({('subtotal',s),('tax',t),('total',format(ds+dt,'.2f'))})
    fields={f:None for f in FIELDS};alerts=[]
    for f,gs in groups.items():
        if not gs:continue
        if FLAGS['dominance'] and f=='total' and any(g['score']>=8 for g in gs.values()):
            gs={k:g for k,g in gs.items() if g['score']>=8}
        ranked=[]
        for k,g in gs.items():
            votes=sum(weight[v] * (0.5+confidence_votes.get((f,k,v),0.5) if config.get('confidence_consensus') else 1.) for v in g['views'])
            fuzzy=sum(weight[v] for v in {v for k2,g2 in gs.items() if near(k,k2) for v in g2['views'] if v not in g['views']}) if FLAGS['fuzzy'] else 0
            rank=g['score']+hp.get('vote_weight',2)*(votes-1)+hp.get('fuzzy_weight',.5)*fuzzy
            if config.get('printed_improvements'):
                explicit=[e for e in evidence[f] if e['normalized']==k and e['rule'] in ('visual_label','printed_label')]
                if f=='subtotal' and explicit:rank+=3
            if FLAGS['corroboration'] and f=='total' and any(k in paid_by_view[v] for v in g['views']):rank+=2
            if FLAGS['balance'] and (f,k) in balanced:rank+=hp.get('balance_bonus',3)
            ranked.append((rank,g['score'],max(weight[v] for v in g['views']),k))
        ranked.sort(reverse=True)
        if len(ranked)>1 and ranked[0][:3]==ranked[1][:3]:
            alerts.append(f+':ambiguous_consensus');continue
        best=ranked[0][3]
        fields[f]=next(c['value'] for c in evidence[f] if c['normalized']==best)
    # Recibos sin impuesto ni otro total: el total coincide con el subtotal leído.
    if FLAGS['total_from_subtotal'] and fields['total'] is None and fields['subtotal'] is not None and fields['tax'] is None:
        fields['total']=fields['subtotal'];alerts.append('total:from_subtotal')
    return dict(fields=fields,evidence=evidence,alerts=alerts)


_extract_consensus=extract

def extract(ocr,config):
    result=_extract_consensus(ocr,config)
    if config.get('printed_improvements'):printed_identifiers(ocr,result)
    if config.get('semantic_amounts'):semantic_amounts(ocr,config,result)
    if config.get('document_consistency'):
        word_geometry_amounts(ocr,config,result)
        document_consistency(ocr,config,result)
    if config.get('structured_fields'):
        structured_fields(ocr,config,result)
    if config.get('observed_accounting'):
        observed_accounting(ocr,config,result)
    settings=config.get('ocr',{}).get('focused_reading',{})
    if not settings.get('enabled') and not config.get('accounting_improvements'):return result
    result['focused_proposals']=[]
    # Una ausencia de impuesto no demuestra que subtotal y total sean iguales.
    if 'total:from_subtotal' in result['alerts']:
        result['fields']['total']=None
        result['alerts'].remove('total:from_subtotal')
        result['alerts'].append('total:subtotal_no_confirma_total')
    if not settings.get('enabled'):return result
    proposals=defaultdict(list)
    for region in ocr.get('focused_regions',[]):
        field=region['field'];votes=defaultdict(set);raw={}
        for reading in region['readings']:
            if reading['confidence']<settings.get('minimum_confidence',35):continue
            text=reading['text'].strip()
            pattern=r'\d{1,4}[/-]\d{1,2}[/-]\d{1,4}' if field=='date' else r'\d+(?:[.,]\d{3})*[.,]\d{2}'
            if not re.fullmatch(pattern,text):continue
            key=normalize(field,text,config['normalization'])
            if not key or key.startswith(('RAW:','AMBIGUOUS:')):continue
            votes[key].add((reading['preprocess'],reading['psm']));raw[key]=text
        supported=[key for key,sources in votes.items() if len(sources)>=settings.get('minimum_agreement',2)]
        if len(supported)==1:
            key=supported[0]
            proposals[field].append((key,raw[key],region['box']))
    for field,items in proposals.items():
        values={item[0] for item in items}
        if len(values)!=1:
            result['alerts'].append(field+':focused_conflict');continue
        key,value,box=items[0]
        result['focused_proposals'].append({'field':field,'value':value,'normalized':key,'box':box})
        if result['fields'].get(field) is None:
            result['fields'][field]=value
            result['evidence'][field].append({'value':value,'normalized':key,'box':box,'rule':'focused_agreement'})
            result['alerts'].append(field+':focused_recovery_revisar')
        elif normalize(field,result['fields'][field],config['normalization'])!=key:
            result['alerts'].append(field+':focused_disagrees_revisar')
    if ocr.get('focused_errors'):result['alerts'].append('focused:partial_failure')
    return result


def printed_candidates(rows, config, add):
    """Etiquetas separadas y geometría, sin reglas para facturas individuales."""
    for row in rows:
        text=clean(row['text'])
        text=re.sub(r'\bsub[.,\s-]+total\b|\bsuototal\b','subtotal',text)
        text=re.sub(r'\bfotal\b','total',text)
        hits=sorted((m.start(),m.end(),f) for f,pat in LABELS.items() for m in re.finditer(pat,text))
        for i,(start,end,field) in enumerate(hits):
            if field=='total' and not re.search(r'\bfotal\b',clean(row['text'])):continue
            if field=='total' and re.search(r'sub\s*$|(?:tax|gst|hst|sst|vat|iva|tay)\s*$',text[:start]):continue
            if field=='total' and re.search(r'con\s+letra|in\s+words|quantity|discount|savings|items',text):continue
            if field=='tax' and re.search(r'\b(?:id|number|reg|no)\b',text):continue
            tail=text[end:hits[i+1][0] if i+1<len(hits) else len(text)]
            found=amounts(tail,config)
            if len(found)==1:
                add(field,found[0][0],7,text,'printed_label',row['box'])
        # Fechas terminales con barra de impresión: no truncar el año.
        for m in re.finditer(r'(?<!\d)(\d{1,2})\s*[./-]\s*(\d{1,2})\s*[./-]\s*(\d{4})(?!\d)',text):
            if re.search(r'expir|return|valid|certific|vencim',text[:m.start()]):continue
            add('date','/'.join(m.groups()),6,text,'printed_date',row['box'])


def printed_identifiers(ocr, result):
    """RFC del emisor y folio comercial; no confundir receptor ni UUID fiscal."""
    votes={f:defaultdict(list) for f in ('tax_id','document_number')}
    for vi,view in enumerate(ocr.get('views') or [ocr]):
        section=None
        for row in grouped(view):
            text=row['text'].upper()
            if re.search(r'\b(?:RECEPTOR|CLIENTE|CUSTOMER|BILL TO)\b',text):section='recipient'
            elif re.search(r'\b(?:EMISOR|ISSUER|SUPPLIER)\b',text):section='issuer'
            rfc=re.search(r'\bRFC\s*[:. -]*([A-Z&Ñ]{3,4}\d{6}[A-Z0-9]{3})\b',text)
            if rfc and section=='issuer':
                votes['tax_id'][rfc.group(1)].append((vi,row))
            folio=re.search(r'\bFOLIO(?!\s+FISCAL)(?:\s+Y\s+SERIE)?\s*[:#-]\s*([A-Z0-9]+(?:[-/][A-Z0-9]+)*)',text)
            if folio and any(c.isdigit() for c in folio.group(1)):
                votes['document_number'][folio.group(1)].append((vi,row))
    for field,values in votes.items():
        ranked=sorted(values.items(),key=lambda kv:len({v for v,_ in kv[1]}),reverse=True)
        if not ranked:continue
        value,items=ranked[0];n=len({v for v,_ in items})
        if len(ranked)>1 and n==len({v for v,_ in ranked[1][1]}):
            result['alerts'].append(field+':identifiers_conflict');continue
        result['fields'][field]=value
        result['evidence'][field].append(dict(value=value,rule='issuer_rfc' if field=='tax_id' else 'commercial_folio',text=items[0][1]['text'],box=items[0][1]['box'],views=n))


def accounting_candidates(rows,config,add):
    """Importes observados, cercanía y etiquetas; nunca fabricar una diferencia."""
    for i,row in enumerate(rows):
        text=clean(row['text'])
        # Tabla fiscal: neto, impuesto y bruto alineados bajo sus encabezados.
        headers=list(re.finditer(r'\b(net|netto|tax|vat|gross|brutto)\b',text))
        if [m.group() for m in headers]==['net','tax','gross']:
            for nxt in rows[i+1:i+3]:
                h=max(1,row['box'][3]-row['box'][1])
                if nxt['box'][1]-row['box'][3]>3*h:continue
                vals=amounts(clean(nxt['text']),config)
                decimals=[v for v in vals if re.search(r'[.,]\d{2}$',v[0])]
                if len(decimals)==3:
                    (sr,sv,_,_),(tr,tv,_,_),(gr,gv,_,_)=decimals
                    if Decimal(tv)>=0 and Decimal(sv)>=Decimal(tv):
                        add('subtotal',sr,9,text+' / '+nxt['text'],'fiscal_table',nxt['box'])
                        add('tax',tr,9,text+' / '+nxt['text'],'fiscal_table',nxt['box'])
        # Dos subtotales a ambos lados de un impuesto: antes y después de impuesto.
        if not re.search(LABELS['subtotal'],text):continue
        a=amounts(text,config)
        if len(a)!=1:continue
        for j in range(i+1,min(i+4,len(rows))):
            mid=clean(rows[j]['text'])
            if not re.search(LABELS['tax'],mid):continue
            b=amounts(mid,config)
            if len(b)!=1:continue
            for nxt in rows[j+1:min(j+3,len(rows))]:
                nt=clean(nxt['text'])
                if not re.search(LABELS['subtotal']+'|'+LABELS['total'],nt):continue
                c=amounts(nt,config)
                if len(c)!=1:continue
                if Decimal(a[0][1])+Decimal(b[0][1])==Decimal(c[0][1]):
                    add('subtotal',a[0][0],12,text,'subtotal_before_tax',row['box'])
                    add('tax',b[0][0],11,mid,'tax_between_totals',rows[j]['box'])
        # Importe de impuesto en fila sin etiqueta legible entre subtotal y total.
        for j in range(i+1,min(i+3,len(rows)-1)):
            mid=clean(rows[j]['text']);end=clean(rows[j+1]['text'])
            if not re.search(LABELS['total'],end) or re.search(r'change|discount|gratuity|service|tip',mid):continue
            b=amounts(mid,config);c=amounts(end,config)
            if len(b)!=1 or len(c)!=1:continue
            av,bv,cv=map(Decimal,(a[0][1],b[0][1],c[0][1]))
            if av>0 and 0<bv<=av*Decimal('.30') and av+bv==cv:
                add('tax',b[0][0],8,mid,'observed_tax_between_totals',rows[j]['box'])

    # Resumen vertical: tres importes leídos en tres filas próximas, total etiquetado.
    for i in range(2,len(rows)):
        end=clean(rows[i]['text'])
        if not re.search(LABELS['total'],end) or re.search(r'sub|tax|vat|gst|change|discount',end):continue
        earlier=rows[i-2:i]
        if any(len(re.findall('[a-z]',clean(r['text'])))>7 for r in earlier):continue
        vals=[amounts(clean(r['text']),config) for r in rows[i-2:i+1]]
        if any(len(v)!=1 for v in vals):continue
        a,b,c=[v[0] for v in vals];av,bv,cv=map(Decimal,(a[1],b[1],c[1]))
        h=max(1,max(r['box'][3]-r['box'][1] for r in rows[i-2:i+1]))
        if rows[i]['box'][1]-rows[i-2]['box'][3]>6*h:continue
        if av>0 and 0<bv<=av*Decimal('.30') and av+bv==cv:
            add('subtotal',a[0],8,earlier[0]['text'],'observed_vertical_summary',earlier[0]['box'])
            add('tax',b[0],8,earlier[1]['text'],'observed_vertical_summary',earlier[1]['box'])


def context_amounts(rows,config,add,candidates):
    """Totales observados corroborados por subtotal/impuesto o depósito/saldo."""
    values={f:{} for f in ('subtotal','tax')}
    for f in values:
        for item in candidates[f]:
            if item['score']<7:continue
            key=money(item['value'],config['normalization']['decimal_separator'])
            if key is not None:values[f].setdefault(key,[]).append(item)
    # No usar listas extensas de candidatos ruidosos para buscar coincidencias casuales.
    if 0<len(values['subtotal'])<=3 and 0<len(values['tax'])<=3:
        for sub,ss in values['subtotal'].items():
            for tax,tt in values['tax'].items():
                a,b=Decimal(sub),Decimal(tax)
                if a<=0 or not 0<=b<=a*Decimal('.30'):continue
                for row in rows:
                    text=clean(row['text'])
                    if re.search(LABELS['subtotal'],text) or re.search(r'discount|change|savings|service|gratuity|tip|deposit',text):continue
                    found=amounts(text,config)
                    if len(found)!=1 or Decimal(found[0][1])!=a+b:continue
                    boxes=[x['box'] for x in ss+tt if x.get('box')]
                    if len(boxes)<2:continue
                    h=max(1,row['box'][3]-row['box'][1])
                    if not all(abs(row['box'][1]-box[1])<=8*h for box in boxes):continue
                    if not re.search(r'total|tota|lota|paym(?:ent|erit)|amount\s+due',text):continue
                    add('total',found[0][0],11,text,'observed_summary_total',row['box'])
    deposits=[];balances=[];totals=[]
    for row in rows:
        text=clean(row['text']);found=amounts(text,config)
        if len(found)!=1:continue
        v=found[0]
        if re.search(r'\bdeposit\b|\banticipo\b',text):deposits.append((v,row))
        elif re.search(r'\bbalance\s+due\b|\bsaldo\b',text):balances.append((v,row))
        elif re.search(r'^\W*(?:grand\s+)?total\b',text):totals.append((v,row))
        if re.search(r'^\W*(?:importo|fuel\s+sale|gas\s+total)\b',text):
            add('total',v[0],8,text,'localized_total_label',row['box'])
    for dep,dr in deposits:
        for bal,br in balances:
            for total,tr in totals:
                h=max(1,tr['box'][3]-tr['box'][1])
                if max(abs(tr['box'][1]-r['box'][1]) for r in (dr,br))>10*h:continue
                if Decimal(dep[1])>0 and Decimal(dep[1])+Decimal(bal[1])==Decimal(total[1]):
                    add('total',total[0],12,tr['text'],'total_before_deposit',tr['box'])


def spatial_amount_candidates(rows,config,add,candidates):
    """Recuperar campos vacíos con importe próximo y alineado debajo de su etiqueta."""
    patterns={'subtotal':r'\b(?:sub[ .,\-]*total|net\s+amount|base\s+imponible)\b',
              'tax':r'\b(?:tax(?:es)?|iva|vat|gst|impuesto)\b',
              'total':r'\b(?:grand\s+total|total|importe\s+total|amount\s+due)\b'}
    for field,pattern in patterns.items():
        if candidates[field]:continue
        for i,row in enumerate(rows):
            text=clean(row['text']);match=re.search(pattern,text)
            if not match:continue
            if re.search(r'\b(?:id|reg|registration|number|items|quantity|discount|change)\b',text):continue
            if field=='total' and re.search(r'sub[ .,\-]*total|total\s+(?:tax|gst|iva|vat)',text):continue
            # No rescatar a partir de una etiqueta que ya contiene valores contradictorios.
            if amounts(text[match.end():],config):continue
            h=max(1,row['box'][3]-row['box'][1])
            for nxt in rows[i+1:i+3]:
                gap=nxt['box'][1]-row['box'][3]
                if gap<0 or gap>2.5*h:continue
                if nxt['box'][0]<row['box'][0]-h:continue
                raw=clean(nxt['text']).strip(' :|')
                if any(re.search(p,raw) for p in patterns.values()):continue
                values=amounts(raw,config)
                if len(values)!=1:continue
                value=values[0]
                if not re.search(r'[.,]\d{2}$',value[0]):continue
                remainder=raw[:value[2]]+raw[value[3]:]
                remainder=re.sub(r'\b(?:usd|eur|gbp|rm|chf|sr|zr)\b|[$€£:|]','',remainder).strip()
                if remainder:continue
                add(field,value[0],7,text+' / '+raw,'aligned_amount_below_label',nxt['box'])

def document_consistency(ocr, config, result):
    """Recover an observed summary amount using two corroborated anchors.

    Arithmetic never overrides all three fields to force a balance. Decimal
    repair requires visible digits, an explicit rate and matching printed totals.
    """
    from decimal import ROUND_HALF_UP
    norm=config['normalization']
    current={f:money(result['fields'].get(f),norm.get('decimal_separator','auto')) for f in MONEY}
    evidence=result['evidence']
    anchors={}
    for f,value in current.items():
        if value is None or Decimal(value)<0:continue
        supported=[e for e in evidence[f] if e.get('normalized')==value and e.get('box') and e.get('score',0)>=7]
        if len({e.get('view') for e in supported if e.get('view') is not None})>=2:anchors[f]=supported
    proposals={f:defaultdict(list) for f in MONEY}
    labels={'subtotal':r'\b(?:sub\s*total|subttl|sous.?total|base\s+imponible|netto|net\s+amount|gross\s+amount)\b',
            'tax':r'\b(?:tax[12]?|gst|vat|tva|iva|hst|sst|mwst|btw|impuesto)\b',
            'total':r'\b(?:total[e]?|totaal|amount\s+due|to\s+pay|summe|net\s+amount)\b'}
    for field in MONEY:
        if field!='tax' and current[field] is not None:continue
        others=[f for f in MONEY if f!=field]
        if not all(f in anchors for f in others):continue
        values={f:Decimal(current[f]) for f in others}
        expected=(values['subtotal']+values['tax'] if field=='total' else
                  values['total']-values['tax'] if field=='subtotal' else values['total']-values['subtotal'])
        if expected<0:continue
        if field=='tax' and (values['subtotal']<=0 or expected>values['subtotal']*Decimal('.30')):continue
        if current[field] is not None and Decimal(current[field])==expected:continue
        for vi,view in enumerate(ocr.get('views') or [ocr]):
            boxes=[e['box'] for f in others for e in anchors[f] if e.get('view')==vi]
            if len(boxes)<2:continue
            height=max(1,max(b[3]-b[1] for b in boxes));lo=min(b[1] for b in boxes)-4*height;hi=max(b[3] for b in boxes)+4*height
            if hi-lo>24*height:continue
            rows=[r for r in grouped(view) if lo<=r['box'][1]<=hi]
            # Discounts, tips and service charges invalidate the simple equation.
            if any(re.search(r'\b(?:discount|savings|tip|gratuity|service|svc|rounding|deposit|change)\b',clean(r['text'])) for r in rows):continue
            for row in rows:
                text=clean(row['text'])
                role=bool(re.search(labels[field],text))
                # Reject a competing explicit role, except gross/net ambiguity.
                if not role and any(re.search(p,text) for p in labels.values()):continue
                vals=decimal_amounts(text,config)
                matches=[a for a in vals if Decimal(a[1])==expected]
                if len(matches)==1 and (role or len(vals)==1):
                    raw,val,_,_=matches[0]
                    # A contradictory established amount requires an explicit label.
                    if current[field] is not None and not role:continue
                    proposals[field][val].append(dict(value=raw,normalized=val,view=vi,
                        score=10,rule='joint_observed_amount',text=text,box=row['box']))
                if field!='tax' or not role:continue
                rate=re.search(r'(\d+(?:[.,]\d+)?)\s*%',text)
                if not rate:continue
                percent=Decimal(rate.group(1).replace(',','.'))/100
                if not 0<percent<1:continue
                # Only exclusive tax base supported by subtotal + tax = total.
                estimated=(values['subtotal']*percent).quantize(Decimal('.01'),rounding=ROUND_HALF_UP)
                if abs(estimated-expected)>Decimal('.01'):continue
                for raw,val,_,_ in amounts(text,config):
                    if not re.fullmatch(r'\d{1,6}',raw.strip()):continue
                    if Decimal(val)/100!=expected:continue
                    repaired=format(expected,'.2f')
                    proposals[field][repaired].append(dict(value=repaired,normalized=repaired,view=vi,
                        score=10,rule='decimal_point_repaired',original_token=raw,rate=rate.group(),
                        text=text,box=row['box']))
    for f,values in proposals.items():
        supported=[(value,es) for value,es in values.items() if len({e['view'] for e in es})>=2]
        if len(supported)!=1:continue
        value,items=supported[0]
        result['fields'][f]=items[0]['value'];evidence[f].extend(items)
        result['alerts'].append(f+':'+items[0]['rule'])
        if f=='total' and 'total:from_subtotal' in result['alerts']:result['alerts'].remove('total:from_subtotal')

def word_geometry_amounts(ocr,config,result):
    """Match label boxes with nearby number boxes independently of OCR lines.

    For gaps only: do not replace established values using proximity alone.
    Every selected amount must be visible in at least two archived OCR views.
    """
    patterns={'subtotal':r'\b(?:sub[\s.,-]*total[e]?|subttl|sous[\s-]*total|base\s+imponible|netto)\b',
              'tax':r'\b(?:tax[12]?|vat[s]?|tva|gst|hst|sst|iva|impuesto|mwst|btw)\b',
              'total':r'\b(?:grand\s+total|total[e]?|totaal|totalt|amount\s+due|to\s+pay|summe)\b'}
    votes={f:defaultdict(list) for f in MONEY if result['fields'].get(f) is None}
    if not votes:return
    for vi,view in enumerate(ocr.get('views') or [ocr]):
        numbers=[]
        for word in view.get('words',[]):
            raw=str(word.get('text','')).strip().strip(':;|')
            val=money(raw,config['normalization'].get('decimal_separator','auto'))
            box=word.get('box')
            if val is None or not box or Decimal(val)<0 or not re.search(r'[.,]\d{2}(?:\W|[a-zA-Z])?$',raw):continue
            if word.get('confidence',0)<30:continue
            numbers.append((raw,val,box,word.get('confidence',0)))
        visual_rows=grouped(view)
        for row in visual_rows:
            text=row['text']
            if re.search(r'\b(?:reg|registration|taxpayer|number|qty|items|change|discount|service|tip)\b',text):continue
            for field in votes:
                match=re.search(patterns[field],text)
                if not match:continue
                if field=='total' and (re.search(patterns['subtotal'],text) or re.search(r'(?:tax|gst|vat|hst).*total|total.*(?:tax|excl)',text)):continue
                if field=='tax' and re.search(r'total.*(?:incl|excl)|tax\s*(?:id|no)',text):continue
                boxes=[b for a,z,b in row['spans'] if a<match.end() and z>match.start()]
                if not boxes:continue
                label=[min(b[0] for b in boxes),min(b[1] for b in boxes),max(b[2] for b in boxes),max(b[3] for b in boxes)]
                h=max(1,label[3]-label[1]);cy=(label[1]+label[3])/2
                candidates=[]
                for raw,val,b,conf in numbers:
                    dy=abs((b[1]+b[3])/2-cy)
                    if b[0]<label[2]-.25*h or dy>1.2*h:continue
                    # Nearby label in another row owns the number if closer.
                    competing=False
                    for other in visual_rows:
                        if other is row or other['text']==text:continue
                        if any(re.search(p,other['text']) for p in patterns.values()):
                            oy=(other['box'][1]+other['box'][3])/2
                            if abs((b[1]+b[3])/2-oy)+.2*h<dy:competing=True;break
                    if competing:continue
                    score=dy/h+.002*max(0,b[0]-label[2])-.002*conf
                    candidates.append((score,raw,val,b))
                candidates.sort()
                if not candidates or (len(candidates)>1 and candidates[1][0]-candidates[0][0]<.3):continue
                _,raw,val,b=candidates[0]
                votes[field][val].append(dict(value=raw,normalized=val,view=vi,score=8,
                    rule='word_geometry_alignment',text=text,box=b))
    for f,groups in votes.items():
        ranked=sorted(((len({e['view'] for e in es}),v,es) for v,es in groups.items()),reverse=True)
        if not ranked or ranked[0][0]<2:continue
        if len(ranked)>1 and ranked[0][0]<=ranked[1][0]:continue
        _,value,items=ranked[0]
        result['fields'][f]=items[0]['value'];result['evidence'][f].extend(items)
        result['alerts'].append(f+':word_geometry_alignment')
        if f=='total' and 'total:from_subtotal' in result['alerts']:result['alerts'].remove('total:from_subtotal')

def structured_fields(ocr, config, result):
    """Corroborate explicit labels and header columns using observed tokens only.

    No dataset labels, reference amounts, document identifiers or arithmetic
    generation are inputs. A view contributes at most one vote per value.
    """
    from .common import normalize_date
    patterns = {
        'subtotal': r'\b(?:sub[ .-]*total|food\s+total|merchandise\s+total|net\s+sales)\b',
        'tax': r'\b(?:sales\s+tax|total\s+tax|tax(?:es)?|gst|vat|iva|impuestos?|tva)\b',
        'total': r'\b(?:grand\s+total|gnd\s+total|total\s+due|amount\s+due|amourt\s+due|balance\s+due|net\s+total|due|total)\b',
    }
    buckets={f:defaultdict(list) for f in (*MONEY,'date','document_number')}
    def add(f,raw,vi,row,rule,quality):
        norm=normalize(f,raw,config['normalization'])
        if norm is None or norm.startswith('RAW:'):return
        buckets[f][norm].append(dict(value=raw,normalized=norm,view=vi,box=row['box'],
            text=row['text'],rule=rule,score=quality))
    for vi,view in enumerate(ocr.get('views') or [ocr]):
        rows=grouped(view)
        rows += [dict(text=line,box=[0,0,0,1],spans=[]) for line in view.get('text','').splitlines() if line.strip()]
        for i,row in enumerate(rows):
            text=clean(row['text']);h=max(1,row['box'][3]-row['box'][1])
            for f,pat in patterns.items():
                hit=re.search(pat,text)
                if not hit:continue
                if re.search(r'\b(?:reg|registration|number|taxpayer|qty|quantity|items|change|savings|discount|tip|gratuity|service|svc|recipient)\b',text):continue
                if f=='tax' and re.search(r'\b(?:id|no)\b|\btotal\b.*\b(?:incl|excl)',text):continue
                if f=='total' and (re.search(patterns['subtotal'],text) or re.search(r'\b(?:tax|gst|vat|iva|food|merchandise)\b',text)):continue
                tail=text[hit.end():]
                tail=re.split(r'\b(?:cash|change|paid|tender|balance|total|subtotal)\b',tail)[0]
                vals=decimal_amounts(tail,config)
                quality=11 if re.search(r'grand|gnd|due|net\s+total',hit.group()) else 9
                if len(vals)==1:
                    add(f,vals[0][0],vi,row,'explicit_summary_label',quality)
                elif quality>=11 or not amounts(tail,config):
                    # An amount alone directly under a summary heading.
                    below=[]
                    for nxt in rows[i+1:i+3]:
                        if not 0<=nxt['box'][1]-row['box'][3]<=2.5*h:continue
                        nt=clean(nxt['text']);nv=decimal_amounts(nt,config)
                        if len(nv)!=1 or re.search(r'[a-z]',re.sub(r'\b(?:rm|usd|eur)\b','',nt)):continue
                        if nxt['box'][2]<row['box'][0] or nxt['box'][0]>row['box'][2]+10*h:continue
                        below.append((nv[0][0],nxt))
                    if len(below)==1:add(f,below[0][0],vi,below[0][1],'summary_value_below',quality)
            # Prefer intact dates over substrings or character-repaired dates.
            if not re.search(r'\b(?:expiry|expires|valid|until|return|vencimiento|due)\b',text):
                datepat=r'(?<!\w)(?:\d{4}[-/.]\d{1,2}[-/.]\d{1,2}|\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4}|\d{1,2}\s*(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|avr|mai|juin|juil|aout|ene|abr|ago|dic)[a-z]*[\s\x27.,/-]*\d{2,4}|(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|avr|mai|juin|juil|aout|ene|abr|ago|dic)[a-z]*\s*\d{1,2}[\s\x27.,/-]+\d{2,4})(?!\d)'
                for m in re.finditer(datepat,text):
                    if normalize_date(m.group(),config['normalization'].get('date_order','auto')):
                        add('date',m.group(),vi,row,'intact_printed_date',9)
            # Column header number can be beneath the label, beside a date.
            hit=re.search(r'\b(?:invoice\s*(?:no\.?|number|#)|(?:n[. ]*(?:o|0)?[. ]*|numero\s+)de\s+factura|factura\s*(?:no\.?|numero|#))\b',text)
            if hit and not result['fields'].get('document_number'):
                spans=[b for a,z,b in row['spans'] if a<hit.end() and z>hit.start()]
                if not spans:continue
                x0=min(b[0] for b in spans);x1=max(b[2] for b in spans)
                choices=[]
                for word in view.get('words',[]):
                    b=word['box'];raw=str(word['text']).strip(':#.;')
                    if not re.fullmatch(r'[A-Za-z0-9]+(?:[-/][A-Za-z0-9]+)*',raw) or not any(c.isdigit() for c in raw):continue
                    if len(raw)<3 or word.get('confidence',0)<40:continue
                    if normalize_date(raw) is not None:continue
                    gap=b[1]-row['box'][3]
                    if 0<=gap<=3*h and x0-h<=(b[0]+b[2])/2<=x1+h:choices.append((raw,dict(text=raw,box=b)))
                if len(choices)==1:add('document_number',choices[0][0],vi,choices[0][1],'header_column',9)
    for f,groups in buckets.items():
        ranked=sorted(((len({e['view'] for e in es}),max(e['score'] for e in es),value,es) for value,es in groups.items()),reverse=True)
        if not ranked:continue
        if f=='total':
            strong=[item for item in ranked if item[1]>=11 and item[0]>=2]
            if strong:ranked=strong
        n,quality,value,es=ranked[0]
        if n<2 or (len(ranked)>1 and n<=ranked[1][0]):continue
        current=normalize(f,result['fields'].get(f),config['normalization'])
        if current==value:continue
        old=[e for e in result['evidence'].get(f,[]) if e.get('normalized')==current]
        old_explicit={e.get('view') for e in old if e.get('box') and e.get('score',0)>=7}
        # Existing amounts only change for stronger explicit evidence, never proximity alone.
        if current is not None:
            if f=='date':
                old_intact=groups.get(current,[])
                if n<3 or n<2*len({e['view'] for e in old_intact}):continue
            elif f=='tax' and old_explicit:continue
            elif n<3:continue
            elif f=='total':
                if quality<11 and old_explicit:continue
                strong_old=[e for e in old if re.search(r'grand|due|net.?total|payable|rounded',clean(e.get('text','')))]
                if strong_old:continue
            elif n<=len(old_explicit):continue
        result['fields'][f]=es[0]['value'];result['evidence'][f].extend(es)
        result['alerts'].append(f+':structured_selection')
        if f=='total' and 'total:from_subtotal' in result['alerts']:result['alerts'].remove('total:from_subtotal')

def observed_accounting(ocr,config,result):
    """Resolve observed amount alternatives against a corroborated summary.

    Never generate an amount from a difference. Two unchanged, explicitly
    labelled anchors and a unique observed third amount are required. Discounts
    and charges must themselves be read in at least two views. Inclusive tax
    summaries are not forced into an exclusive-tax equation.
    """
    from itertools import product
    pats={
        'subtotal':r'\b(?:sub[ .-]*total[e]?|sous.total|food\s+total|net\s+amount|netto)\b',
        'tax':r'\b(?:sales\s+tax|tax(?:es)?|gst|vat|iva|impuestos?|tva|hst|sst)\b',
        'total':r'\b(?:grand\s+total|net\s+total|total\s+due|amount\s+due|balance\s+due|total[e]?|totaal|summe|a\s+payer)\b',
        'discount':r'\b(?:discount|descuento|remise|rabais)\b',
        'shipping':r'\b(?:shipping|freight|envio|manipulacion|delivery)\b',
        'service':r'\b(?:service\s+charge|svc\s+chg|cargo\s+servicio)\b',
        'tip':r'\b(?:tip|gratuity|propina)\b',
        'rounding':r'\b(?:rounding|redondeo|round\s+off)\b'}
    buckets={f:defaultdict(list) for f in pats}
    def record(f,raw,vi,row):
        value=money(raw,config['normalization'].get('decimal_separator','auto'))
        if value is None:return
        if f!='rounding' and Decimal(value)<0:return
        buckets[f][value].append(dict(value=raw,normalized=value,view=vi,text=row['text'],box=row.get('box'),score=10,rule='observed_accounting_label'))
    for vi,view in enumerate(ocr.get('views') or [ocr]):
        rows=grouped(view)+[dict(text=t,box=None) for t in view.get('text','').splitlines()]
        for row in rows:
            text=clean(row['text'])
            if re.search(r'\b(?:reg|registration|number|taxpayer|qty|items|recipient)\b',text):continue
            for f,pat in pats.items():
                hit=re.search(pat,text)
                if not hit:continue
                if f=='total' and (re.search(pats['subtotal'],text) or re.search(r'\b(?:tax|gst|vat|iva|discount|service|svc|food)\b',text)):continue
                if f=='tax' and (re.search(r'\b(?:id|no)\b',text) or re.search(pats['total'],text)):continue
                tail=text[hit.end():]
                # Keep only one unambiguous decimal monetary token, not a rate.
                found=[]
                for m in AMT.finditer(tail):
                    if tail[m.end():].lstrip().startswith('%'):continue
                    if re.search(r'[.,]\d{2}$',m.group().strip()):found.append(m.group())
                if len(found)==1:record(f,found[0],vi,row)
    supported={f:{v:es for v,es in gs.items() if len({e['view'] for e in es})>=2} for f,gs in buckets.items()}
    adjustments={};delta=Decimal(0)
    for f in ('discount','shipping','service','tip','rounding'):
        gs=supported[f]
        # An observed but uncorroborated adjustment prevents assuming zero.
        if buckets[f] and not gs:return
        if not gs:continue
        rank=sorted(gs,key=lambda v:len({e['view'] for e in gs[v]}),reverse=True)
        if len(rank)>1:return
        v=rank[0];adjustments[f]=v;delta+=(-Decimal(v) if f=='discount' else Decimal(v))
    current={f:money(result['fields'].get(f),config['normalization'].get('decimal_separator','auto')) for f in MONEY}
    # No algebraic reinterpretation of negative receipts/refunds.
    if any(v is not None and Decimal(v)<0 for v in current.values()):return
    proposals=[]
    for target in MONEY:
        anchors=[f for f in MONEY if f!=target]
        if not all(current[f] in supported[f] for f in anchors):continue
        for value,es in supported[target].items():
            candidate={**current,target:value}
            s,t,g=(Decimal(candidate[f]) for f in MONEY)
            if s<=0 or t<0 or t>s*Decimal('.40'):continue
            residual=abs(s+t+delta-g)
            if residual>Decimal('.01'):continue
            proposals.append((target,value,es,residual))
    changed=[p for p in proposals if p[1]!=current[p[0]]]
    # Preserve already balanced readings; don't chase another balanced combination.
    if all(v is not None for v in current.values()):
        s,t,g=(Decimal(current[f]) for f in MONEY)
        if abs(s+t+delta-g)<=Decimal('.01'):
            result['accounting_summary']={'adjustments':adjustments,'residual':str(s+t+delta-g),'observed_only':True}
            return
    if len(changed)!=1:return
    field,value,es,residual=changed[0]
    result['fields'][field]=es[0]['value'];result['evidence'][field].extend(es)
    result['alerts'].append(field+':observed_accounting_selection')
    result['accounting_summary']={'adjustments':adjustments,'residual':str(residual),'observed_only':True,
        'corrected_field':field,'previous_value':current[field]}
    if field=='total' and 'total:from_subtotal' in result['alerts']:result['alerts'].remove('total:from_subtotal')


_extract_all_stages = extract

def extract(ocr, config):
    from .geometry import row_cache
    with row_cache():
        result = _extract_all_stages(ocr, dict(config, confidence_consensus=False))
        missing = [f for f in ('date','subtotal','tax','total') if result['fields'].get(f) is None]
        if config.get('confidence_rescue') and missing:
            alternate = _extract_all_stages(ocr, dict(config, confidence_consensus=True))
            for field in missing:
                value = alternate['fields'].get(field)
                key = normalize(field,value,config['normalization'])
                if key is None or key.startswith('RAW:'):continue
                es = [e for e in alternate['evidence'][field] if e.get('normalized')==key and e.get('score',0)>=6]
                if len({e.get('view') for e in es if e.get('view') is not None})<2:continue
                result['fields'][field]=value
                result['evidence'][field].extend(es)
                result['alerts'].append(field+':confidence_gap_recovery')
        return result
