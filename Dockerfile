# Imagen de la interfaz web del Lector de Facturas (Hugging Face Spaces, Render o cualquier Docker).
# Ubuntu 24.04 trae Tesseract 5.3.4, la misma versión con la que se evaluó el modelo.
FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_BREAK_SYSTEM_PACKAGES=1 \
    LECTOR_PRECARGAR=1 \
    PORT=7860

RUN apt-get update \
 && apt-get install -y --no-install-recommends tesseract-ocr python3 python3-pip ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# Hugging Face Spaces ejecuta el contenedor con el usuario 1000.
RUN userdel -r ubuntu 2>/dev/null || true \
 && useradd -m -u 1000 lector
WORKDIR /home/lector/app

COPY --chown=lector requirements.txt requirements.txt
COPY --chown=lector app/requirements.txt app/requirements.txt
RUN pip3 install -r requirements.txt -r app/requirements.txt

COPY --chown=lector . .
USER lector

# Descarga y verifica (SHA-256) los pesos de Tesseract durante la construcción, no en la primera visita.
RUN python3 -c "import src; from src.model import LectorFacturas; LectorFacturas().cargar()"

EXPOSE 7860
HEALTHCHECK --interval=60s --timeout=10s CMD python3 -c "import urllib.request,os; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\",\"7860\")}/salud', timeout=5)"
CMD gunicorn --bind 0.0.0.0:${PORT} --workers 1 --threads 4 --timeout 300 "app.app:crear_app()"
