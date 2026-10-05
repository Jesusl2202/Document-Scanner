"""Experimentos de inferencia reproducibles, con referencia separada del OCR real."""
import json, time, hashlib, sys, platform, importlib.metadata
from pathlib import Path
import pandas as pd
from .common import read_jsonl, write_json, write_jsonl
from .ocr import transcribe, environment
from .extraction import extract, validate
from .geometry import grouped
from .evaluation import evaluate

def signature(rows):
    return sorted((r['id'],r['sha256'],json.dumps(r['gold'],sort_keys=True)) for r in rows)

def reference_ocr(row):
    # El extractor nunca recibe la etiqueta semántica ni los campos gold.
    words=[{'text':r['text'],'box':r['box'],'confidence':100,'line_id':str(i)}
           for i,r in enumerate(row['regions']) if str(r.get('text','')).strip()]
    # Se reconstruyen líneas geométricas; la transcripción no es una salida de Tesseract.
    rows=grouped({'words':words}); rebuilt=[]
    for i,r in enumerate(rows):
        for a,b,box in r['spans']:
            rebuilt.append({'text':r['text'][a:b],'box':box,'confidence':100,'line_id':str(i)})
    return {'words':rebuilt,'text':'\n'.join(r['text'] for r in rows),'cache_hit':False,
            'reference_only':True,'width':row.get('width'),'height':row.get('height')}

def run(rows,config,out,cache,source='ocr'):
    out=Path(out); cache=Path(cache)
    code_hash={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(__file__).parent.glob('*.py')}
    specification={'config':config,'source':source,'sample':signature(rows),'code':code_hash}
    stamp=hashlib.sha256(json.dumps(specification,sort_keys=True).encode()).hexdigest()
    if (out/'evaluation/summary.json').exists():
        assert json.loads((out/'fingerprint.json').read_text())['sha256']==stamp,'No reutilizar una carpeta con otro experimento.'
        return out
    if (out/'predictions.jsonl').exists():
        archived=out.with_name(out.name+'_incompleto_'+str(time.time_ns()));out.rename(archived)
    out.mkdir(parents=True,exist_ok=True)
    write_json(out/'fingerprint.json',{'sha256':stamp,'code_hashes':code_hash})
    write_json(out/'config.json',config);write_jsonl(out/'evaluation_manifest.jsonl',rows)
    env={'python':sys.version,'platform':platform.platform(),'source':source,
         'packages':{n:importlib.metadata.version(n) for n in ['Pillow','numpy','pandas','matplotlib','pypdfium2']}}
    if source=='ocr':env['tesseract']=environment(config['ocr']['executable'])
    write_json(out/'environment.json',env)
    predictions=[]
    for i,row in enumerate(rows,1):
        started=time.perf_counter()
        try:
            ocr=transcribe(row['image'],config['ocr'],cache) if source=='ocr' else reference_ocr(row)
            result=extract(ocr,config)
            result.update(text=ocr['text'],ocr=ocr,cache_hit=ocr.get('cache_hit',False),status='ok',
                          validation=validate(result['fields'],config))
        except Exception as exc:
            result={'fields':{},'text':'','status':'error','error':str(exc),'cache_hit':False}
        result.update(id=row['id'],dataset=row['dataset'],source=source,
                      elapsed_seconds=time.perf_counter()-started if source=='ocr' else None)
        predictions.append(result)
        with (out/'predictions.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(result,ensure_ascii=False)+'\n')
        if i%10==0 or i==len(rows):print(out.name,i,'/',len(rows),flush=True)
    summary=evaluate(rows,predictions,config,out/'evaluation')
    if source!='ocr':
        summary.update(cer_layout_order_sensitive=None,cer_documents=0,
                       median_seconds_uncached=None,p95_seconds_uncached=None,latency_sample_size=0)
        summary['notes'].append('Diagnóstico con transcripción y geometría anotadas; no desempeño real ni límite superior garantizado.')
        write_json(out/'evaluation/summary.json',summary)
        # El CER calculado automáticamente no aplica a la referencia.
        (out/'evaluation/cer.csv').write_text('id,dataset,edits,reference_characters,cer\n',encoding='utf-8')
    print('Exactitud:',summary['micro_exact_match'])
    return out

def metrics(path):return pd.read_csv(Path(path)/'evaluation/metrics.csv')

def scores(path,dataset=None,common=False):
    table=metrics(path);table=table[(table.dataset!='ALL')&(table.support>0)]
    if dataset:table=table[table.dataset==dataset]
    if common:table=table[table.field.isin(['date','total'])]
    if table.empty:raise ValueError('No hay soporte para evaluar esta selección')
    # Accuracy macro evita que los campos más frecuentes oculten a otros.
    return {'f1_macro':float(table.f1.mean()),'exactitud_macro':float(table.exact_match.mean()),
            'soporte':int(table.support.sum())}

def bootstrap_delta(base,other,seed=4242,repetitions=1000):
    """Intervalo pareado por documento del cambio de exactitud micro, no por campo."""
    import numpy as np
    a=pd.read_csv(Path(base)/'evaluation/errors.csv');b=pd.read_csv(Path(other)/'evaluation/errors.csv')
    joined=a.merge(b,on=['id','dataset','field'],suffixes=('_a','_b'),validate='one_to_one')
    assert len(joined)==len(a)==len(b)
    per=joined.assign(delta=joined.correct_b-joined.correct_a).groupby(['dataset','id']).agg(delta=('delta','sum'),n=('delta','size'))
    rng=np.random.default_rng(seed); draws=[]
    groups=[g for _,g in per.groupby(level='dataset')]
    for _ in range(repetitions):
        numerator=denominator=0
        for g in groups:
            sample=g.iloc[rng.integers(0,len(g),len(g))];numerator+=sample.delta.sum();denominator+=sample.n.sum()
        draws.append(numerator/denominator)
    return {'delta_pp':float(per.delta.sum()/per.n.sum()*100),
            'ic95_inferior_pp':float(np.percentile(draws,2.5)*100),
            'ic95_superior_pp':float(np.percentile(draws,97.5)*100),
            'nota':'Bootstrap pareado por documento, estratificado por dataset; muestra pequeña, no prueba causal.'}
