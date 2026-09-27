"""Descarga optativa de distribuciones públicas; no se ejecuta al instalar el proyecto."""
import argparse
from pathlib import Path
import hashlib
import json
import shutil
import tarfile
import urllib.request
import zipfile
from datetime import datetime, timezone

SOURCES={
 'wildreceipt': ('https://download.openmmlab.com/mmocr/data/wildreceipt.tar', 'wildreceipt.tar'),
 'sroie': ('https://www.kaggle.com/api/v1/datasets/download/urbikn/sroie-datasetv2', 'sroie_v2.zip'),
}


def safe_path(root, name):
    dest=(root/name).resolve()
    if not dest.is_relative_to(root.resolve()):
        raise ValueError('Archivo intenta salir del directorio destino')
    return dest


def main():
    p=argparse.ArgumentParser(description='Descargar base pública para uso autorizado; revisar sus condiciones de uso')
    p.add_argument('dataset',choices=list(SOURCES))
    p.add_argument('--out',default='data/raw')
    a=p.parse_args()
    root=Path(a.out);root.mkdir(parents=True,exist_ok=True)
    url,name=SOURCES[a.dataset];archive=root/name;temporary=root/(name+'.part')
    print('Descargando',a.dataset,'desde su distribución pública...')
    try:
        with urllib.request.urlopen(url,timeout=60) as response,temporary.open('wb') as f:
            shutil.copyfileobj(response,f)
        if a.dataset=='sroie' and not zipfile.is_zipfile(temporary):
            raise ValueError('Kaggle no devolvió un ZIP. Descargar manualmente con la cuenta propia; no se intenta eludir acceso.')
        temporary.replace(archive)
        h=hashlib.sha256()
        with archive.open('rb') as f:
            for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
        if a.dataset=='wildreceipt':
            with tarfile.open(archive) as t:
                for item in t:
                    target=safe_path(root,item.name)
                    if item.isdir():target.mkdir(parents=True,exist_ok=True)
                    elif item.isfile():
                        target.parent.mkdir(parents=True,exist_ok=True)
                        with t.extractfile(item) as src,target.open('wb') as dst:shutil.copyfileobj(src,dst)
                    else:raise ValueError('Tipo de archivo no permitido en TAR')
        else:
            target_root=root/'sroie_distribution'
            with zipfile.ZipFile(archive) as z:
                for item in z.infolist():
                    target=safe_path(target_root,item.filename)
                    if item.is_dir():target.mkdir(parents=True,exist_ok=True)
                    else:
                        target.parent.mkdir(parents=True,exist_ok=True)
                        with z.open(item) as src,target.open('wb') as dst:shutil.copyfileobj(src,dst)
        metadata={'dataset':a.dataset,'url':url,'sha256':h.hexdigest(),'bytes':archive.stat().st_size,
                  'downloaded_at_utc':datetime.now(timezone.utc).isoformat(),
                  'note':'SHA256 registra la descarga; no verifica una firma oficial. No implica permiso de redistribución.'}
        (root/(a.dataset+'_download.json')).write_text(json.dumps(metadata,indent=2),encoding='utf-8')
        print('Descarga y extracción completas. Revise la carpeta y use la raíz que contiene train/.')
    except Exception:
        temporary.unlink(missing_ok=True)
        raise

if __name__=='__main__':main()
