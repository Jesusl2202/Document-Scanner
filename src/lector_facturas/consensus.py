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
        if v is not None:add(f,v,7,'','v5_fallback')
    rows=grouped(ocr)
    rebuilt=dict(ocr,words=[dict(text=r['text'],box=r['box'],confidence=90,line_id=str(i)) for i,r in enumerate(rows)])
    dated=old_extract(rebuilt,config)['fields'].get('date')
    if dated:add('date',dated,5,'','date_geometry')
    if FLAGS['dates']:date_rows(rows,add)
    for i,row in enumerate(rows):
        text=clean(row['text']);h=max(1,row['box'][3]-row['box'][1])
        for field,pattern in LABELS.items():
            match=re.search(pattern,text)
            if not match:continue
            prefix,tail=text[:match.start()],text[match.end():]
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
    weight=[VIEW_WEIGHT_PRIMARY if is_primary(v) else 1.0 for v in views]
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
            votes=sum(weight[v] for v in g['views'])
            fuzzy=sum(weight[v] for k2,g2 in gs.items() if near(k,k2) for v in g2['views'] if v not in g['views']) if FLAGS['fuzzy'] else 0
            rank=g['score']+2*(votes-1)+0.5*fuzzy
            if FLAGS['corroboration'] and f=='total' and any(k in paid_by_view[v] for v in g['views']):rank+=2
            if FLAGS['balance'] and (f,k) in balanced:rank+=3
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
