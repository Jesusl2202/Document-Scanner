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
    resumed=[]
    if (out/'predictions.jsonl').exists():
        if not (out/'fingerprint.json').exists() or json.loads((out/'fingerprint.json').read_text())['sha256']!=stamp:
            raise ValueError('No reanudar con otro código, datos o configuración')
        resumed=read_jsonl(out/'predictions.jsonl')
        finished=[p['id'] for p in resumed]
        if len(finished)!=len(set(finished)) or not set(finished).issubset({r['id'] for r in rows}):
            raise ValueError('Predicciones parciales inválidas')
    out.mkdir(parents=True,exist_ok=True)
    write_json(out/'fingerprint.json',{'sha256':stamp,'code_hashes':code_hash})
    write_json(out/'config.json',config);write_jsonl(out/'evaluation_manifest.jsonl',rows)
    env={'python':sys.version,'platform':platform.platform(),'source':source,
         'packages':{n:importlib.metadata.version(n) for n in ['Pillow','numpy','pandas','matplotlib','pypdfium2']}}
    if source=='ocr':env['tesseract']=environment(config['ocr']['executable'])
    write_json(out/'environment.json',env)
    predictions=list(resumed);finished={p['id'] for p in resumed}
    for i,row in enumerate(rows,1):
        if row['id'] in finished:continue
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


from .frozen_runtime import final_sample
GROUPS = [('sroie','date'),('sroie','total'),('wildreceipt','date'),('wildreceipt','subtotal'),('wildreceipt','tax'),('wildreceipt','total')]

def replay_semantic_archive(archive, output):
    """Complete historical extraction comparison; never reruns OCR or calls gold OCR."""
    import zipfile, copy
    output=Path(output)
    if output.exists():
        raise ValueError('Elige una carpeta nueva para conservar resultados anteriores')
    with zipfile.ZipFile(archive) as z:
        root='evaluacion/test/lectura_adaptativa/'
        required=[root+'predictions.jsonl',root+'config.json','evaluacion/test_reservado.jsonl']
        if any(n not in z.namelist() for n in required):
            raise ValueError('Carga el ZIP de resultados de lectura adaptativa del 20 de octubre')
        predictions=[json.loads(s) for s in z.read(required[0]).decode('utf-8-sig').splitlines() if s.strip()]
        config=json.loads(z.read(required[1]))
        rows=[json.loads(s) for s in z.read(required[2]).decode('utf-8-sig').splitlines() if s.strip()]
    ids=[r['id'] for r in rows]
    if not rows or len(ids)!=len(set(ids)) or len(predictions)!=len(rows) or {p['id'] for p in predictions}!=set(ids):
        raise ValueError('Manifiesto incompleto o predicciones duplicadas/ajenas')
    if len({p['id'] for p in predictions})!=len(predictions):
        raise ValueError('Predicciones duplicadas')
    if any(p.get('source')!='ocr' or p.get('ocr',{}).get('reference_only') for p in predictions):
        raise ValueError('Solo se admite OCR real archivado, nunca transcripciones anotadas')
    output.mkdir(parents=True)
    write_jsonl(output/'manifest_historico.jsonl',rows)
    write_json(output/'plan.json',{'mode':'replay_historico_completo','documents':len(rows),
        'archive_sha256':hashlib.sha256(Path(archive).read_bytes()).hexdigest(),
        'code_hashes':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(__file__).parent.glob('*.py')},
        'independent_test':False,'note':'Conjunto conocido utilizado en desarrollo; no demuestra generalización.'})
    started=time.perf_counter();paths={};records=[];tables=[]
    for name,enabled in [('lectura_adaptativa',False),('extraccion_semantica',True)]:
        cfg=copy.deepcopy(config);cfg['semantic_amounts']=enabled
        path=output/name;path.mkdir();paths[name]=path;new=[]
        for i,p in enumerate(predictions,1):
            item=copy.deepcopy(p)
            if enabled and p.get('status')=='ok':
                if not p.get('ocr') or not (p['ocr'].get('views') or p['ocr'].get('words')):
                    raise ValueError('Falta OCR archivado: '+p['id'])
                result=extract(copy.deepcopy(p['ocr']),cfg)
                item.update(result)
                item['validation']=validate(result['fields'],cfg)
            item.update(cache_hit=True,elapsed_seconds=None)
            new.append(item)
            if i%25==0:print(name,i,'/',len(rows),flush=True)
        write_json(path/'config.json',cfg);write_jsonl(path/'predictions.jsonl',new)
        summary=evaluate(rows,new,cfg,path/'evaluation',calculate_cer=False)
        table=field_table(path);table.insert(0,'version',name);tables.append(table)
        records.append(dict(version=name,exactitud_global=summary['micro_exact_match'],
            documentos=len(rows),campos=summary['evaluated_field_instances']))
    a=pd.read_csv(paths['lectura_adaptativa']/'evaluation/errors.csv')
    b=pd.read_csv(paths['extraccion_semantica']/'evaluation/errors.csv')
    pair=a.merge(b,on=['id','dataset','field'],suffixes=('_antes','_despues'),validate='one_to_one')
    pair.to_csv(output/'comparacion_campos.csv',index=False)
    report={'mode':'replay_historico_completo','independent_test':False,
        'comparison':records,'gains':int(((pair.correct_antes==0)&(pair.correct_despues==1)).sum()),
        'losses':int(((pair.correct_antes==1)&(pair.correct_despues==0)).sum()),
        'extraction_replay_seconds':time.perf_counter()-started,
        'note':'Sin nuevas llamadas a Tesseract. Tiempo de replay, no latencia de lectura de imágenes. CER no recalculado.'}
    write_json(output/'resultado_general.json',report)
    comparison=pd.DataFrame(records);comparison.to_csv(output/'comparacion_global.csv',index=False)
    fields=pd.concat(tables,ignore_index=True);fields.to_csv(output/'campos_meta.csv',index=False)
    return comparison,fields,report

def reserve(rows, history, ndev=50, ntest=75, seed=42):
    if min(ndev,ntest)<=0:raise ValueError('Tamaños de muestra positivos requeridos')
    seen=set(history.values()); ids=set(history)
    test=final_sample(rows,ntest,ids,seen,seed)
    used={r['sha256'] for r in test}; dev=[]
    for dataset in ('sroie','wildreceipt'):
        pool=[r for r in rows if r['dataset']==dataset and r['split']=='train' and r.get('source_split')=='train' and r['id'] not in ids and r['sha256'] not in seen]
        pool.sort(key=lambda r:hashlib.sha256(f"{seed}:{r['id']}".encode()).hexdigest())
        chosen=[]
        for row in pool:
            if row['sha256'] in used:continue
            used.add(row['sha256']);chosen.append(row)
            if len(chosen)==ndev:break
        if len(chosen)!=ndev:raise ValueError('No hay suficientes documentos nuevos de desarrollo: '+dataset)
        dev.extend(chosen)
    return dev,test

def field_table(path):
    table=metrics(path).set_index(['dataset','field']).reindex(pd.MultiIndex.from_tuples(GROUPS,names=['dataset','field'])).reset_index()
    table['supera_80']=table.exact_match>.80
    return table

def evaluate_candidates(rows, project, configs, output, ndev=50, ntest=75, seed=42):
    output=Path(output)
    if output.exists():raise ValueError('Usa una carpeta nueva para cada evaluación; no sobrescribir resultados')
    output.mkdir(parents=True)
    history=json.loads((Path(project)/'configs/documentos_revisados.json').read_text(encoding='utf8'))
    dev,test=reserve(rows,history,ndev,ntest,seed)
    write_jsonl(output/'desarrollo_reservado.jsonl',dev);write_jsonl(output/'test_reservado.jsonl',test)
    write_json(output/'plan.json',{'seed':seed,'development':len(dev),'test':len(test),'historical_exclusions':len(history),'groups':GROUPS,'criterion':'Maximizar exactitud global en desarrollo; desempatar por el mínimo de los seis grupos y referencia. Procesamiento >=90%. Meta estricta: cada grupo >80%.'})
    records=[]
    for name,cfg in configs.items():
        path=run(dev,cfg,output/'desarrollo'/name,output/'cache_ocr')
        table=field_table(path);table.to_csv(path/'campos_meta.csv',index=False)
        s=json.loads((path/'evaluation/summary.json').read_text())
        valid=bool(table.support.notna().all() and (table.support>0).all() and table.exact_match.notna().all())
        records.append({'version':name,'min_field':float(table.exact_match.min()) if valid else -1.,'exactitud':s['micro_exact_match'],'procesamiento':s['execution_success_rate'],'all_above_80':bool(valid and table.supera_80.all())})
    comparison=pd.DataFrame(records);comparison.to_csv(output/'comparacion_desarrollo.csv',index=False)
    eligible=[r for r in records if r['procesamiento']>=.90 and r['min_field']>=0]
    if not eligible:raise RuntimeError('Ninguna alternativa elegible: revisar ejecución y cobertura de campos')
    winner=max(eligible,key=lambda r:(r['exactitud'],r['min_field'],r['version']=='referencia_v8'))['version']
    write_json(output/'seleccion_antes_del_test.json',{'winner':winner,'config':configs[winner]})
    paths={}
    for name in dict.fromkeys(['referencia_v8',winner]):
        path=run(test,configs[name],output/'test'/name,output/'cache_ocr');paths[name]=path
        field_table(path).to_csv(path/'campos_meta.csv',index=False)
    selected=field_table(paths[winner]);summary=json.loads((paths[winner]/'evaluation/summary.json').read_text())
    achieved=bool(selected.exact_match.notna().all() and (selected.support>0).all() and selected.supera_80.all())
    result={'selected':winner,'all_six_above_80':achieved,'processing_above_90':summary['execution_success_rate']>=.90,'exact_match':summary['micro_exact_match'],'global_above_80':summary['micro_exact_match']>.80,'note':'No promover automáticamente el candidato: comprobar métricas, errores y tiempo. Test ya observado no vuelve a ser independiente.'}
    test_rows=[]
    for name,path in paths.items():
        measured=json.loads((path/'evaluation/summary.json').read_text())
        test_rows.append({'version':name,'exactitud_global':measured['micro_exact_match'],'procesamiento':measured['execution_success_rate'],'supera_80_global':measured['micro_exact_match']>.80})
    pd.DataFrame(test_rows).to_csv(output/'comparacion_test_global.csv',index=False)
    result['test_comparison']=test_rows
    write_json(output/'resultado_meta_por_campo.json',result)
    if winner!='referencia_v8':write_json(output/'comparacion_pareada.json',bootstrap_delta(paths['referencia_v8'],paths[winner]))
    return comparison,selected,result


def evaluate_frozen_pair(rows,project,configs,output,ntest=50,seed=42):
    """Prueba única de configuraciones fijadas en desarrollo; no elige reglas en test."""
    output=Path(output)
    if output.exists():raise ValueError('Usa una carpeta nueva: no sobrescribir el test')
    history=json.loads((Path(project)/'configs/documentos_revisados.json').read_text(encoding='utf8'))
    test=final_sample(rows,ntest,set(history),set(history.values()),seed)
    output.mkdir(parents=True)
    write_jsonl(output/'test_reservado.jsonl',test)
    write_json(output/'plan_congelado.json',{'configs':configs,'seed':seed,'documents':len(test),
        'criterion':'Configuraciones fijadas con desarrollo previo; meta global >80%, desglose por campo; sin selección usando test.'})
    started=time.perf_counter();paths={};records=[];tables=[]
    # Una sola caché: las vistas idénticas no se ejecutan dos veces.
    for name,cfg in configs.items():
        path=run(test,cfg,output/'test'/name,output/'cache_ocr');paths[name]=path
        summary=json.loads((path/'evaluation/summary.json').read_text())
        table=field_table(path);table.insert(0,'version',name);tables.append(table)
        table.to_csv(path/'campos_meta.csv',index=False)
        records.append({'version':name,'exactitud_global':summary['micro_exact_match'],
            'procesamiento':summary['execution_success_rate'],'supera_80_global':summary['micro_exact_match']>.80})
    comparison=pd.DataFrame(records);comparison.to_csv(output/'comparacion_test_global.csv',index=False)
    names=list(configs)
    if len(names)!=2:raise ValueError('Se requieren exactamente dos configuraciones')
    delta=bootstrap_delta(paths[names[0]],paths[names[1]])
    write_json(output/'comparacion_pareada.json',delta)
    result={'test_comparison':records,'comparison':delta,'evaluation_wall_minutes':(time.perf_counter()-started)/60,
        'note':'Tiempo total real de evaluación; las latencias individuales del segundo modelo usan caché y no son comparables. Test observado no vuelve a ser independiente.'}
    write_json(output/'resultado_general.json',result)
    return comparison,pd.concat(tables,ignore_index=True),result


def unseen_test_inventory(rows,history):
    """Censo de todo el test oficial elegible, nunca una muestra por rendimiento."""
    seen_hashes=set(history.values());train_hashes={r['sha256'] for r in rows if r.get('source_split')!='test'}
    used=set();selected=[];excluded=[]
    for row in sorted(rows,key=lambda r:(r['dataset'],r['id'])):
        if row.get('source_split')!='test':continue
        reason=None
        if row.get('split')!='test':reason='no_elegible_o_cuarentena'
        elif row['id'] in history:reason='id_ya_revisado'
        elif row['sha256'] in seen_hashes:reason='imagen_ya_revisada'
        elif row['sha256'] in train_hashes:reason='duplicado_de_desarrollo'
        elif row['sha256'] in used:reason='duplicado_dentro_test'
        if reason:excluded.append({'id':row['id'],'sha256':row['sha256'],'reason':reason})
        else:selected.append(row);used.add(row['sha256'])
    if not selected:raise ValueError('No queda test independiente; recopilar nuevos documentos anotados')
    return selected,excluded


def evaluate_all_unseen(rows,project,configs,output):
    """Congelar y evaluar TODOS los documentos oficiales elegibles aún no revisados."""
    names=list(configs)
    if len(names)!=2:raise ValueError('Comparación pareada de dos configuraciones requerida')
    output=Path(output)
    history=json.loads((Path(project)/'configs/documentos_revisados.json').read_text(encoding='utf8'))
    selected,excluded=unseen_test_inventory(rows,history)
    sample_signature=signature(selected)
    plan={'configs':configs,'sample_signature':sample_signature,'mode':'todo_test_inedito_elegible',
          'documents':len(selected),'by_dataset':{d:sum(r['dataset']==d for r in selected) for d in ('sroie','wildreceipt')},
          'note':'Sin seleccionar por facilidad, aciertos o confianza. No es el test oficial completo: se excluye lo ya revisado y se registra cada exclusión.'}
    output.mkdir(parents=True,exist_ok=True)
    if (output/'plan_completo.json').exists():
        old=json.loads((output/'plan_completo.json').read_text())
        if old['configs']!=configs or old['sample_signature']!=json.loads(json.dumps(sample_signature)):
            raise ValueError('Plan distinto: no reanudar ni sobrescribir')
    else:write_json(output/'plan_completo.json',plan)
    write_jsonl(output/'test_reservado.jsonl',selected);write_jsonl(output/'exclusiones_test.jsonl',excluded)
    print('TEST INÉDITO COMPLETO:',plan['by_dataset'],flush=True)
    start=time.perf_counter();paths={};records=[];tables=[]
    for name,cfg in configs.items():
        path=run(selected,cfg,output/'test'/name,output/'cache_ocr');paths[name]=path
        summary=json.loads((path/'evaluation/summary.json').read_text())
        table=field_table(path);table.insert(0,'version',name);tables.append(table)
        table.to_csv(path/'campos_meta.csv',index=False)
        predictions=read_jsonl(path/'predictions.jsonl')
        records.append({'version':name,'exactitud_global':summary['micro_exact_match'],
            'exactitud_macro_seis_grupos':float(table.exact_match.mean()),
            'procesamiento':summary['execution_success_rate'],'supera_80_global':summary['micro_exact_match']>.80,
            'documentos_rescate':sum(bool(p.get('ocr',{}).get('rescue_requested')) for p in predictions),
            'lecturas_extra_solicitadas':sum(p.get('ocr',{}).get('rescue_requested',0) for p in predictions)})
    comparison=pd.DataFrame(records);comparison.to_csv(output/'comparacion_test_global.csv',index=False)
    delta=bootstrap_delta(paths[names[0]],paths[names[1]]);write_json(output/'comparacion_pareada.json',delta)
    result={'test_comparison':records,'comparison':delta,'documents':len(selected),'by_dataset':plan['by_dataset'],
        'invocation_wall_minutes':(time.perf_counter()-start)/60,
        'note':'Tiempo de esta invocación; una reanudación no incluye invocaciones anteriores. La caché invalida comparar latencias completas por modelo. La muestra de SROIE puede ser pequeña. No volver a presentar este conjunto como test nuevo tras observarlo.'}
    write_json(output/'resultado_general.json',result)
    return comparison,pd.concat(tables,ignore_index=True),result

def reserve_random_unseen(rows, history, ledger_path, n_per_dataset=50, seed=None):
    """Reserve before OCR. Persist IDs/hashes across sessions; never refill with seen rows."""
    import random,secrets,os
    if not isinstance(n_per_dataset,int) or n_per_dataset<=0:raise ValueError('Tamaño positivo requerido')
    ledger_path=Path(ledger_path);ledger_path.parent.mkdir(parents=True,exist_ok=True)
    lock=ledger_path.with_suffix(ledger_path.suffix+'.lock')
    try:fd=os.open(str(lock),os.O_CREAT|os.O_EXCL|os.O_WRONLY)
    except FileExistsError:raise RuntimeError('Hay otra reserva activa; no ejecutar dos evaluaciones simultáneas')
    try:
        os.close(fd)
        ledger=json.loads(ledger_path.read_text(encoding='utf8')) if ledger_path.exists() else {}
        if not isinstance(ledger,dict):raise ValueError('Historial persistente inválido')
        combined=dict(history);combined.update(ledger)
        try:pool,excluded=unseen_test_inventory(rows,combined)
        except ValueError:
            return [],{'status':'sin_test_inedito','selected':0,'seed':None,
                'note':'No se reutilizaron facturas. Se necesitan nuevas imágenes de test anotadas.'}
        seed=secrets.randbits(63) if seed is None else seed
        rng=random.Random(seed);selected=[];inventory={}
        for dataset in sorted({r['dataset'] for r in pool}):
            candidates=sorted((r for r in pool if r['dataset']==dataset),key=lambda r:r['id'])
            inventory[dataset]=len(candidates)
            selected.extend(rng.sample(candidates,min(n_per_dataset,len(candidates))))
        rng.shuffle(selected)
        combined.update({r['id']:r['sha256'] for r in selected})
        temporary=ledger_path.with_suffix(ledger_path.suffix+'.tmp')
        write_json(temporary,combined);os.replace(temporary,ledger_path)
        return selected,{'status':'reservado','selected':len(selected),'seed':seed,
            'eligible_before_selection':inventory,'n_per_dataset':n_per_dataset,
            'reserved_before_ocr':True,'exclusions':excluded,
            'note':'Muestreo aleatorio sin reemplazo. Conservar el historial en Drive para futuras sesiones.'}
    finally:lock.unlink(missing_ok=True)


def evaluate_random_unseen(rows,project,configs,output,ledger_path,n_per_dataset=50):
    """Real-image evaluation on a new random test; all failures remain in denominators."""
    output=Path(output);names=list(configs)
    if len(names)!=2:raise ValueError('Se requieren dos versiones fijadas antes del test')
    plan_path=output/'plan_aleatorio.json'
    code={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(__file__).parent.glob('*.py')}
    if plan_path.exists():
        plan=json.loads(plan_path.read_text(encoding='utf8'))
        if plan['configs']!=configs or plan['code']!=code:raise ValueError('Código/configuración cambiados: no reutilizar ese test para ajustar')
        selected=read_jsonl(output/'test_reservado.jsonl')
        current={r['id']:r for r in rows}
        if any(r['id'] not in current for r in selected) or signature(selected)!=signature([current[r['id']] for r in selected]):
            raise ValueError('Los datos del test reservado cambiaron')
    else:
        history=json.loads((Path(project)/'configs/documentos_revisados.json').read_text(encoding='utf8'))
        selected,selection=reserve_random_unseen(rows,history,ledger_path,n_per_dataset)
        output.mkdir(parents=True,exist_ok=True)
        write_json(output/'inventario_seleccion.json',selection)
        if not selected:
            print(selection['note'],flush=True)
            return pd.DataFrame(),pd.DataFrame(),selection
        plan={'configs':configs,'code':code,'selection':selection,'mode':'test_aleatorio_sin_repetir'}
        write_jsonl(output/'test_reservado.jsonl',selected);write_json(plan_path,plan)
    started=time.perf_counter();paths={};records=[];tables=[]
    for name,cfg in configs.items():
        path=run(selected,cfg,output/name,output/'cache_ocr');paths[name]=path
        summary=json.loads((path/'evaluation/summary.json').read_text())
        table=metrics(path);table=table[table.support>0].copy();table.insert(0,'version',name)
        table['supera_80']=table.exact_match>.80;tables.append(table)
        records.append({'version':name,'documents':len(selected),'fields':summary['evaluated_field_instances'],
            'exactitud_global':summary['micro_exact_match'],'procesamiento':summary['execution_success_rate']})
    comparison=pd.DataFrame(records);comparison.to_csv(output/'comparacion_global.csv',index=False)
    detail=pd.concat(tables,ignore_index=True);detail.to_csv(output/'campos_meta.csv',index=False)
    result={'status':'completo','mode':'test_aleatorio_sin_repetir','comparison':records,
        'paired':bootstrap_delta(paths[names[0]],paths[names[1]]),
        'invocation_wall_minutes':(time.perf_counter()-started)/60,
        'note':'Imágenes reales. La segunda versión comparte caché; no confundir su latencia con lectura desde cero. No ajustar y volver a presentar estos mismos documentos como test nuevo.'}
    write_json(output/'resultado_general.json',result)
    return comparison,detail,result


def load_external_test(root):
    """Read human-annotated test images. Annotations are NEVER given to OCR/extractor."""
    from PIL import Image,ImageOps
    from .common import inside,digest,FIELDS,gold_empty
    root=Path(root);items=read_jsonl(root/'anotaciones.jsonl');rows=[];ids=set()
    for item in items:
        path=inside(root,item['image'])
        if not path.is_file():raise FileNotFoundError(path)
        ident='externas/test/'+str(item['id'])
        if ident in ids:raise ValueError('ID externo duplicado')
        ids.add(ident);gold=gold_empty()
        if not item.get('gold'):raise ValueError('Faltan anotaciones verificadas')
        for f,g in item['gold'].items():
            if f not in FIELDS:raise ValueError('Campo desconocido: '+f)
            if not isinstance(g,dict) or g.get('status') not in ('annotated','absent','unannotated'):raise ValueError('Estado de anotación inválido')
            if g['status']=='annotated' and (g.get('value') is None or str(g['value']).strip()==''):raise ValueError('Falta valor anotado')
            if g['status']=='absent' and g.get('value') is not None:raise ValueError('Campo ausente no admite valor')
            gold[f]={'status':g['status'],'value':g.get('value')}
        if not any(g['status']=='annotated' for g in gold.values()):raise ValueError('No hay campos anotados')
        with Image.open(path) as image:w,h=ImageOps.exif_transpose(image).size
        rows.append({'id':ident,'dataset':'externas','source_split':'test','split':'test',
                     'image':str(path),'sha256':digest(path),'width':w,'height':h,
                     'gold':gold,'regions':[],'issues':[]})
    return rows

def random_known_sample(rows,n_per_dataset=50,seed=None,previous_ids=None):
    """Random test sampling; historical documents allowed, no duplicate image within run."""
    import random,secrets
    if not isinstance(n_per_dataset,int) or n_per_dataset<1:raise ValueError('Tamaño de muestra positivo requerido')
    train_hashes={r['sha256'] for r in rows if r.get('source_split')!='test'}
    unique={}
    for r in sorted(rows,key=lambda r:(r['dataset'],r['id'])):
        if r.get('source_split')=='test' and r.get('split')=='test' and r['sha256'] not in train_hashes:
            unique.setdefault(r['sha256'],r)
    pool=list(unique.values())
    if not pool:raise ValueError('No hay test elegible')
    seed=secrets.randbits(63) if seed is None else seed;rng=random.Random(seed);chosen=[]
    for dataset in sorted({r['dataset'] for r in pool}):
        subset=[r for r in pool if r['dataset']==dataset]
        chosen.extend(rng.sample(subset,min(n_per_dataset,len(subset))))
    old=set(previous_ids or []);ids={r['id'] for r in chosen}
    if old and ids==old:
        alternatives=[r for r in pool if r['id'] not in ids]
        if not alternatives:raise ValueError('La muestra abarca todo el test: reduce N_POR_BASE para obtener grupos diferentes')
        replacement=rng.choice(alternatives)
        positions=[i for i,r in enumerate(chosen) if r['dataset']==replacement['dataset']]
        chosen[rng.choice(positions)]=replacement
    rng.shuffle(chosen)
    return chosen,{'seed':seed,'eligible_pool':len(pool),'documents':len(chosen),
        'by_dataset':{d:sum(r['dataset']==d for r in chosen) for d in sorted({r['dataset'] for r in chosen})},
        'overlap_with_previous':len({r['id'] for r in chosen}&old),'historical_documents_allowed':True,
        'independent_test':False}


def evaluate_random_known(rows,project,configs,output,n_per_dataset=50,previous_sample_path=None):
    """Both versions use the same random group. This is not an unseen holdout."""
    names=list(configs);output=Path(output)
    if len(names)!=2:raise ValueError('Se requieren dos versiones')
    if output.exists():raise ValueError('Usa una carpeta nueva para cada grupo aleatorio')
    previous=json.loads(Path(previous_sample_path).read_text(encoding='utf8')) if previous_sample_path and Path(previous_sample_path).exists() else []
    selected,plan=random_known_sample(rows,n_per_dataset,previous_ids=previous)
    history=json.loads((Path(project)/'configs/documentos_revisados.json').read_text(encoding='utf8'))
    hashes=set(history.values());plan['previously_reviewed']=sum(r['id'] in history or r['sha256'] in hashes for r in selected)
    plan['configs']=configs;plan['mode']='test_aleatorio_con_reutilizacion'
    plan['code']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(__file__).parent.glob('*.py')}
    output.mkdir(parents=True);write_json(output/'plan_aleatorio.json',plan);write_jsonl(output/'test_reservado.jsonl',selected)
    if previous_sample_path:write_json(previous_sample_path,[r['id'] for r in selected])
    print('Muestra aleatoria:',plan['by_dataset'],'Coincidencias con el grupo anterior:',plan['overlap_with_previous'],flush=True)
    paths={};records=[];tables=[];start=time.perf_counter()
    for name,cfg in configs.items():
        path=run(selected,cfg,output/name,output.parent/'cache_ocr');paths[name]=path
        summary=json.loads((path/'evaluation/summary.json').read_text())
        table=metrics(path);table=table[table.support>0].copy();table.insert(0,'version',name);tables.append(table)
        records.append({'version':name,'documents':len(selected),'fields':summary['evaluated_field_instances'],
            'exactitud_global':summary['micro_exact_match'],'procesamiento':summary['execution_success_rate']})
    comparison=pd.DataFrame(records);detail=pd.concat(tables,ignore_index=True)
    comparison.to_csv(output/'comparacion_global.csv',index=False);detail.to_csv(output/'campos_meta.csv',index=False)
    report={'mode':plan['mode'],'independent_test':False,'comparison':records,
        'paired':bootstrap_delta(paths[names[0]],paths[names[1]]),
        'evaluation_minutes':(time.perf_counter()-start)/60,
        'note':'Muestra aleatoria de test con documentos ya revisados permitidos. No es validación independiente. Caché compartida: tiempo no equivale a lectura desde cero.'}
    write_json(output/'resultado_general.json',report)
    return comparison,detail,report

def validation_samples(rows,n_opt=30,n_control=20,seed=42):
    """Disjoint by hash; never use official test images for parameter search."""
    import random
    if min(n_opt,n_control)<1:raise ValueError('Las muestras deben ser positivas')
    forbidden={r['sha256'] for r in rows if r.get('source_split')=='test'}
    unique={}
    for r in sorted(rows,key=lambda r:r['id']):
        if r.get('split')=='validation' and r.get('source_split')=='train' and r.get('sha256') and r['sha256'] not in forbidden:
            unique.setdefault(r['sha256'],r)
    rng=random.Random(seed);opt=[];control=[]
    for ds in ('sroie','wildreceipt'):
        pool=[r for r in unique.values() if r['dataset']==ds];rng.shuffle(pool)
        if len(pool)<n_opt+n_control:raise ValueError(f'Validacion insuficiente en {ds}: {len(pool)}; reduce N_OPT y N_CONTROL')
        opt.extend(pool[:n_opt]);control.extend(pool[n_opt:n_opt+n_control])
    return opt,control


def optimize_consensus_cached(rows,config,output,cache,n_opt=30,n_control=20,trials=24,seed=42):
    """Run OCR once; search the actual production extractor on validation only."""
    import copy,random,itertools
    from .common import normalize,FIELDS
    output=Path(output)
    if output.exists():raise ValueError('Elige una salida nueva para optimizacion')
    if trials<1:raise ValueError('trials debe ser positivo')
    opt,control=validation_samples(rows,n_opt,n_control,seed)
    output.mkdir(parents=True)
    write_jsonl(output/'optimizacion.jsonl',opt);write_jsonl(output/'control.jsonl',control)
    # Freeze before inference, including dataset membership and code hashes.
    write_json(output/'plan.json',dict(seed=seed,trials=trials,config=config,
        code={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(__file__).parent.glob('*.py')},
        note='Validacion historica; separacion interna no demuestra datos nunca revisados.'))
    path=run(opt+control,config,output/'ocr_unico',cache)
    archived={p['id']:p for p in read_jsonl(path/'predictions.jsonl')}
    defaults=dict(primary_weight=1.5,vote_weight=2.,fuzzy_weight=.5,balance_bonus=3.)
    defaults.update(config.get('consensus_parameters',{}))
    space=dict(primary_weight=[1.,1.5,2.],vote_weight=[1.,2.,3.],fuzzy_weight=[0.,.5],balance_bonus=[0.,3.,6.])
    options=[dict(zip(space,values)) for values in itertools.product(*space.values())]
    random.Random(seed).shuffle(options);options=[defaults]+[p for p in options if p!=defaults][:trials-1]
    def replay(sample,hp,dest=None):
        cfg=copy.deepcopy(config);cfg['consensus_parameters']=hp;predictions=[];groups={}
        for row in sample:
            p=archived[row['id']]
            try:
                if p.get('status')!='ok':raise ValueError(p.get('error','OCR no disponible'))
                result=extract(p['ocr'],cfg);result.update(status='ok',text=p.get('text',''))
            except Exception as exc:result=dict(fields={},status='error',error=str(exc),text='')
            result.update(id=row['id'],dataset=row['dataset'],cache_hit=True,elapsed_seconds=None)
            predictions.append(result)
            for f in FIELDS:
                g=row['gold'][f]
                if g['status'] not in ('annotated','absent'):continue
                pair=groups.setdefault(row['dataset']+'/'+f,[0,0]);pair[1]+=1
                pair[0]+=int(result['status']=='ok' and normalize(f,result['fields'].get(f),cfg['normalization'])==normalize(f,g['value'],cfg['normalization']))
        values=[a/n for a,n in groups.values() if n]
        if not values:raise ValueError('No hay referencias evaluables')
        scores=dict(macro=sum(values)/len(values),minimum=min(values),global_accuracy=sum(a for a,n in groups.values())/sum(n for a,n in groups.values()),groups=groups)
        if dest:
            write_json(dest/'config.json',cfg);write_jsonl(dest/'predictions.jsonl',predictions);evaluate(sample,predictions,cfg,dest/'evaluation')
        return scores
    records=[]
    for i,hp in enumerate(options):
        score=replay(opt,hp);records.append(dict(index=i,parameters=hp,**score))
        print('Configuracion',i+1,'/',len(options),'macro:',round(score['macro'],4),flush=True)
    # Explicit tie breaker prefers fewer deviations from the delivered configuration.
    best=max(records,key=lambda r:(r['macro'],r['minimum'],r['global_accuracy'],-sum(r['parameters'][k]!=defaults[k] for k in defaults)))
    baseline=replay(control,defaults,output/'control_base')
    selected=replay(control,best['parameters'],output/'control_candidata')
    delta=bootstrap_delta(output/'control_base',output/'control_candidata')
    adopt=delta['ic95_inferior_pp']>0 and selected['minimum']>=baseline['minimum']
    winner=copy.deepcopy(config);winner['consensus_parameters']=best['parameters'] if adopt else defaults
    report=dict(search=records,best=best,control_base=baseline,control_candidate=selected,paired=delta,
        adopted=adopt,config=winner,note='No entrenar ni seleccionar configuracion con test. Mejora no garantizada.')
    write_json(output/'seleccion.json',report);write_json(output/'configuracion_recomendada.json',winner)
    return report
