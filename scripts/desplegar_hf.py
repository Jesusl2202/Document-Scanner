"""Publica la interfaz web en un Space de Hugging Face (SDK Docker).

Lo usa el workflow ``.github/workflows/despliegue.yml``; también se puede ejecutar a mano:

    pip install huggingface_hub
    HF_TOKEN=hf_... python scripts/desplegar_hf.py            # Space <usuario>/lector-facturas
    HF_TOKEN=hf_... HF_SPACE=usuario/otro python scripts/desplegar_hf.py

Sube solo lo que necesita el contenedor (Dockerfile, app/, src/, configs/ y la ficha del
modelo) con un README propio, porque los Spaces leen su configuración del encabezado del README.
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
REPOSITORIO = "https://github.com/Jesusl2202/Document-Scanner"
CARPETAS = ("app", "src", "configs")
ARCHIVOS = ("Dockerfile", ".dockerignore", "requirements.txt", "LICENSE", "models/README.md",
            "models/ficha_modelo.json")

README_SPACE = f"""---
title: Lector de Facturas
emoji: 🧾
colorFrom: green
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
license: mit
short_description: RUC, fecha, número, subtotal, IVA y total desde una factura
---

# Lector de Facturas

Interfaz web del proyecto integrador de la Maestría en Inteligencia Artificial (Universidad
Espíritu Santo). Lee una foto o un PDF de una factura impresa con Tesseract 5 (10 lecturas por
página y consenso) y devuelve el RUC, la fecha, el número de comprobante, el subtotal, el IVA y el
total, con el nivel de confianza y la evidencia de cada valor.

Código, datos, métricas y documentación: <{REPOSITORIO}>
"""


def preparar(destino: Path) -> None:
    ignorar = shutil.ignore_patterns("__pycache__", "*.pyc", "*.traineddata")
    for carpeta in CARPETAS:
        shutil.copytree(RAIZ / carpeta, destino / carpeta, ignore=ignorar)
    for archivo in ARCHIVOS:
        (destino / archivo).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(RAIZ / archivo, destino / archivo)
    (destino / "README.md").write_text(README_SPACE, encoding="utf-8")


def main() -> int:
    from huggingface_hub import HfApi

    token = os.environ.get("HF_TOKEN")
    if not token:
        print("Falta la variable HF_TOKEN.", file=sys.stderr)
        return 1
    api = HfApi(token=token)
    usuario = api.whoami()["name"]
    space = os.environ.get("HF_SPACE") or f"{usuario}/lector-facturas"
    api.create_repo(space, repo_type="space", space_sdk="docker", exist_ok=True)
    with tempfile.TemporaryDirectory() as temporal:
        carpeta = Path(temporal)
        preparar(carpeta)
        commit = os.environ.get("GITHUB_SHA", "local")[:7]
        api.upload_folder(folder_path=carpeta, repo_id=space, repo_type="space",
                          commit_message=f"Despliegue desde GitHub ({commit})",
                          delete_patterns=[f"{c}/**" for c in CARPETAS] + ["models/**"])
    propietario, nombre = space.split("/")
    print(f"Space: https://huggingface.co/spaces/{space}")
    print(f"Aplicación: https://{propietario.lower()}-{nombre.lower().replace('_', '-').replace('.', '-')}.hf.space")
    return 0


if __name__ == "__main__":
    sys.exit(main())
