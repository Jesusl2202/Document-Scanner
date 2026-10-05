"""Agrupación espacial compartida de palabras OCR."""
import statistics
from .common import text_key

def grouped(ocr):
    """Alineación visual; no depende del número de línea asignado por Tesseract."""
    rows=[]
    words=[w for w in ocr.get('words',[]) if str(w.get('text','')).strip() and len(w.get('box',[]))==4]
    for w in sorted(words,key=lambda w:((w['box'][1]+w['box'][3])/2,w['box'][0])):
        box=w['box'];cy=(box[1]+box[3])/2;h=max(1,box[3]-box[1])
        compatible=[]
        for r in rows[-8:]:
            rh=statistics.median(max(1,v['box'][3]-v['box'][1]) for v in r)
            ry=statistics.median((v['box'][1]+v['box'][3])/2 for v in r)
            if abs(cy-ry)<=.45*min(h,rh):compatible.append((abs(cy-ry),r))
        if compatible:min(compatible,key=lambda v:v[0])[1].append(w)
        else:rows.append([w])
    result=[]
    for r in rows:
        r.sort(key=lambda w:w['box'][0]); parts=[];spans=[];offset=0
        for w in r:
            s=text_key(w['text']);parts.append(s);spans.append((offset,offset+len(s),w['box']));offset+=len(s)+1
        b=[min(w['box'][0] for w in r),min(w['box'][1] for w in r),max(w['box'][2] for w in r),max(w['box'][3] for w in r)]
        result.append({'text':' '.join(parts),'spans':spans,'box':b})
    return sorted(result,key=lambda r:r['box'][1])
