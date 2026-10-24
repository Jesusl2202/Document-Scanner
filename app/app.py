"""Interfaz web del Lector de Facturas (Flask).

Ejecutar en local, desde la raíz del repositorio::

    python -m app.app                 # http://127.0.0.1:7860

En producción (Docker / Hugging Face Spaces) la sirve gunicorn: ``gunicorn "app.app:crear_app()"``.

Rutas:

* ``GET /``                  página principal.
* ``POST /api/leer``         lee el archivo enviado en el campo ``archivo``.
* ``POST /api/ejemplo/<id>`` lee uno de los comprobantes sintéticos de ``app/assets/ejemplos``.
* ``GET /api/acerca``        métricas, límites y casos fuera de alcance del modelo.
* ``GET /salud``             estado del servicio (para el despliegue).
"""
from __future__ import annotations

import os
import sys
import tempfile
import threading
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from flask import Flask, jsonify, render_template, request, send_from_directory  # noqa: E402
from werkzeug.exceptions import HTTPException, RequestEntityTooLarge  # noqa: E402

import src  # noqa: E402,F401  (registra el motor lector_facturas en sys.path)
from app.servicio import CARPETA_EJEMPLOS, ServicioLector, respuesta_error  # noqa: E402
from src.utils import ErrorEntrada, cargar_configuracion, configurar_registro, obtener_logger  # noqa: E402

LOGGER = obtener_logger("app")


def crear_app(servicio: ServicioLector | None = None, precargar: bool | None = None) -> Flask:
    """Crea la aplicación. ``servicio`` permite inyectar un lector simulado en las pruebas."""
    config = servicio.config if servicio else cargar_configuracion()
    configurar_registro(config)
    servicio = servicio or ServicioLector(config)
    app = Flask(__name__, template_folder="templates", static_folder="static")
    limites = servicio.limites()
    app.config["MAX_CONTENT_LENGTH"] = int((limites["tamano_maximo_mb"] + 1) * 1024 * 1024)
    app.config["JSON_AS_ASCII"] = False
    app.extensions["lector"] = servicio

    if precargar is None:
        precargar = os.environ.get("LECTOR_PRECARGAR", "1") == "1"
    if precargar:
        # Prepara Tesseract y los pesos al arrancar, para que la primera lectura no espere.
        threading.Thread(target=_precargar, args=(servicio,), daemon=True).start()

    @app.get("/")
    def inicio():
        return render_template("index.html", limites=limites, ejemplos=servicio.ejemplos(),
                               version=config["proyecto"].get("version", ""))

    @app.get("/salud")
    def salud():
        return jsonify(estado="ok", modelo_cargado=servicio.lector.cargado)

    @app.get("/api/acerca")
    def acerca():
        return jsonify(servicio.acerca_de())

    @app.get("/ejemplos/<path:archivo>")
    def archivo_ejemplo(archivo: str):
        return send_from_directory(CARPETA_EJEMPLOS, archivo)

    @app.post("/api/ejemplo/<identificador>")
    def leer_ejemplo(identificador: str):
        try:
            ruta = servicio.ruta_ejemplo(identificador)
            return jsonify(servicio.leer(ruta, ruta.name))
        except Exception as exc:  # noqa: BLE001 - toda falla vuelve como mensaje claro
            return _error(exc)

    @app.post("/api/leer")
    def leer():
        subido = request.files.get("archivo")
        if subido is None or not subido.filename:
            return _error(ErrorEntrada("No se recibió ningún archivo. Elige una imagen o un PDF."))
        extension = Path(subido.filename).suffix.lower()
        if extension not in limites["extensiones"]:
            return _error(ErrorEntrada(
                f"Formato no admitido ({extension or 'sin extensión'}). Sube una imagen JPG o PNG, o un PDF."))
        with tempfile.TemporaryDirectory(prefix="lector_subida_") as temporal:
            ruta = Path(temporal) / f"documento{extension}"
            subido.save(ruta)
            try:
                return jsonify(servicio.leer(ruta, Path(subido.filename).name))
            except Exception as exc:  # noqa: BLE001
                return _error(exc)

    @app.errorhandler(RequestEntityTooLarge)
    def demasiado_grande(_exc):
        return jsonify(error=f"El archivo supera el máximo de {limites['tamano_maximo_mb']} MB. "
                             "Reduce la resolución o comprime el PDF.", tipo="entrada"), 413

    @app.errorhandler(HTTPException)
    def error_http(exc: HTTPException):
        if request.path.startswith("/api/"):
            return jsonify(error="Ruta o método no válido.", tipo="http"), exc.code
        return exc

    def _error(exc: BaseException):
        cuerpo, codigo = respuesta_error(exc)
        if codigo >= 500 and not isinstance(exc, TimeoutError):
            LOGGER.error("Error al leer un documento", exc_info=exc)
        return jsonify(cuerpo), codigo

    return app


def _precargar(servicio: ServicioLector) -> None:
    try:
        servicio.lector.cargar()
    except Exception:  # noqa: BLE001 - el error se mostrará en la primera lectura
        LOGGER.exception("No se pudo precargar el modelo")


def main(argumentos: list[str] | None = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Interfaz web del Lector de Facturas")
    parser.add_argument("--host", default=os.environ.get("HOST", "127.0.0.1"))
    parser.add_argument("--puerto", type=int, default=int(os.environ.get("PORT", 7860)))
    args = parser.parse_args(argumentos)
    crear_app().run(host=args.host, port=args.puerto, threaded=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
