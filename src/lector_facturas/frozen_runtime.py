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
    if prediction.get('ocr',{}).get('view_errors'):notes.append('Una o varias lecturas OCR fallaron')
    if 'total:from_subtotal' in notes:notes.append('Total supuesto a partir del subtotal: confirmar impuesto, cargos y descuentos')
    return notes
