"""Identidad fija de pesos y selección final independiente por hash."""
import hashlib,json,os,urllib.request,shutil
from pathlib import Path
MODEL_SHA='7d4322bd2a7749724879683fc3912cb542f19906c83bcc1a52132556427170b2'
MODEL_URL='https://raw.githubusercontent.com/tesseract-ocr/tessdata_fast/87416418657359cb625c412a48b6e1d6d41c29bd/eng.traineddata'

def ensure_model(directory):
    root=Path(directory).resolve();root.mkdir(parents=True,exist_ok=True)
    model=root/'eng.traineddata'
    if not model.exists() or hashlib.sha256(model.read_bytes()).hexdigest()!=MODEL_SHA:
        part=root/'eng.download'
        with urllib.request.urlopen(MODEL_URL,timeout=120) as response,part.open('wb') as target:
            shutil.copyfileobj(response,target)
        if hashlib.sha256(part.read_bytes()).hexdigest()!=MODEL_SHA:raise ValueError('Modelo descargado incompleto o distinto')
        part.replace(model)
    # Tesseract busca su configuración TSV dentro del directorio de pesos elegido.
    configs=root/'configs';configs.mkdir(exist_ok=True)
    (configs/'tsv').write_text('tessedit_create_tsv 1\n',encoding='ascii')
    os.environ['TESSDATA_PREFIX']=str(root)
    return {'sha256':MODEL_SHA,'url':MODEL_URL,'path':str(model)}

def final_sample(rows,n_per_dataset,seen_ids=(),seen_hashes=(),seed=42):
    if n_per_dataset<=0:raise ValueError('El tamaño por base debe ser positivo')
    forbidden=set(seen_hashes)|{r['sha256'] for r in rows if r.get('source_split')!='test' and r.get('sha256')}
    used=set();selected=[]
    for dataset in ('sroie','wildreceipt'):
        pool=[r for r in rows if r['dataset']==dataset and r['split']=='test' and r.get('source_split')=='test'
              and r['id'] not in seen_ids and r.get('sha256') and r['sha256'] not in forbidden]
        pool.sort(key=lambda r:hashlib.sha256(f"{seed}:{r['id']}".encode()).hexdigest())
        chosen=[]
        for row in pool:
            if row['sha256'] in used:continue
            used.add(row['sha256']);chosen.append(row)
            if len(chosen)==n_per_dataset:break
        if len(chosen)!=n_per_dataset:raise ValueError(f'Test insuficiente para {dataset}: {len(chosen)} de {n_per_dataset}')
        selected.extend(chosen)
    return selected

def review_notes(prediction):
    """Recomendación de revisión, sin modificar los campos usados para medir."""
    notes=list(prediction.get('alerts',[]))
    if prediction.get('accounting_summary',{}).get('observed_only'):
        notes.append('Resumen comprobado con descuentos/cargos observados: '+str(prediction['accounting_summary']['adjustments']))
    elif prediction.get('validation',{}).get('amount_balance')=='inconsistent_review':notes.append('Subtotal + impuesto no coincide con total: revisar descuentos, cargos o datos del documento; los valores leídos se conservan.')
    if prediction.get('ocr',{}).get('view_errors'):notes.append('Una o varias lecturas OCR fallaron')
    if 'total:from_subtotal' in notes:notes.append('Total supuesto a partir del subtotal: confirmar impuesto, cargos y descuentos')
    return notes


def bind_models(config,directory):
    """Configurar pesos locales. Solo descargas públicas de Tesseract; nunca subir facturas."""
    import copy
    config=copy.deepcopy(config);root=Path(directory)
    specs={'fast':('tessdata_fast','87416418657359cb625c412a48b6e1d6d41c29bd',MODEL_SHA),
           'best':('tessdata_best','e12c65a915945e4c28e237a9b52bc4a8f39a0cec','8280aed0782fe27257a68ea10fe7ef324ca0f8d85bd2fd145d1c2b560bcb66ba')}
    def download(name,language):
        repo,revision,expected=specs[name];folder=root/name;folder.mkdir(parents=True,exist_ok=True)
        path=folder/(language+'.traineddata')
        valid=path.exists() and (language!='eng' or hashlib.sha256(path.read_bytes()).hexdigest()==expected)
        if not valid:
            url=f'https://raw.githubusercontent.com/tesseract-ocr/{repo}/{revision}/{language}.traineddata'
            part=folder/(language+'.download')
            with urllib.request.urlopen(url,timeout=120) as source,part.open('wb') as target:shutil.copyfileobj(source,target)
            if language=='eng' and hashlib.sha256(part.read_bytes()).hexdigest()!=expected:raise ValueError('Pesos incompletos: '+name)
            if part.stat().st_size<100000:raise ValueError('Descarga incompleta: '+language)
            part.replace(path)
        return folder
    for view in config['ocr']['ensemble_views']+config['ocr'].get('rescue_views',[]):
        name=view.pop('model','best' if view.get('expected_model_sha256')==specs['best'][2] else 'fast');folder=download(name,'eng')
        view.update(tessdata_dir=str(folder.resolve()),expected_model_sha256=specs[name][2])
    if config['ocr'].get('include_spanish') or config['ocr'].get('focused_reading',{}).get('enabled'):
        folder=download('fast','spa')
        if not any(v.get('language')=='eng+spa' for v in config['ocr']['ensemble_views']):
            config['ocr']['ensemble_views'].append({'preprocess':'denoise','psm':6,'language':'eng+spa',
                'tessdata_dir':str(folder.resolve()),'expected_model_sha256':MODEL_SHA})
    return config


def extraction_status(fields):
    count=sum(fields.get(f) not in (None,'') for f in ('date','subtotal','tax','total'))
    return {'fields_found':count,'fields_requested':4,
            'reading_status':'sin_campos' if count==0 else ('lectura_parcial' if count<4 else 'lectura_por_verificar'),
            'note':'Cobertura no es exactitud; dato ausente no equivale a cero.'}
