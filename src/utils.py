"""Funciones auxiliares: configuración, rutas, registro de eventos y errores.

La configuración se lee de ``configs/config.yaml`` y se puede sobreescribir con
variables de entorno o con un archivo ``.env`` en la raíz del repositorio. Todas
las rutas de la configuración son relativas a la raíz, de modo que el proyecto
funciona igual en Colab, en Windows o en Linux.
"""
from __future__ import annotations

import copy
import hashlib
import json
import logging
import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

import yaml

RAIZ_PROYECTO = Path(__file__).resolve().parents[1]
CONFIG_POR_DEFECTO = RAIZ_PROYECTO / "configs" / "config.yaml"
NOMBRE_LOGGER = "lector"
SECCIONES_REQUERIDAS = ("rutas", "entrada", "evaluacion", "registro")

# Variable de entorno -> (sección, clave) de la configuración que reemplaza.
VARIABLES_ENTORNO = {
    "LECTOR_NIVEL_LOG": ("registro", "nivel"),
    "LECTOR_PESOS": ("rutas", "pesos"),
    "LECTOR_SALIDAS": ("rutas", "salidas"),
}


class ErrorLector(Exception):
    """Error base del proyecto. Su mensaje está pensado para el usuario final."""


class ErrorConfiguracion(ErrorLector):
    """La configuración falta, está mal escrita o tiene valores inválidos."""


class ErrorEntrada(ErrorLector):
    """El archivo que se quiere leer no es válido (formato, tamaño, páginas...)."""


class ErrorModelo(ErrorLector):
    """El modelo no se pudo cargar o ejecutar (Tesseract, pesos, OCR)."""


def ruta_proyecto(ruta: str | os.PathLike) -> Path:
    """Convierte una ruta relativa a la raíz del repositorio en una ruta absoluta.

    Las rutas absolutas se devuelven sin cambios.
    """
    ruta = Path(ruta).expanduser()
    return ruta if ruta.is_absolute() else RAIZ_PROYECTO / ruta


def cargar_env(ruta: str | os.PathLike | None = None) -> dict[str, str]:
    """Lee un archivo ``.env`` sencillo (``CLAVE=valor``) sin dependencias externas.

    Las variables ya definidas en el entorno tienen prioridad y no se sobreescriben.

    Returns:
        Diccionario con las variables leídas del archivo (vacío si no existe).
    """
    ruta = ruta_proyecto(ruta or ".env")
    leidas: dict[str, str] = {}
    if not ruta.is_file():
        return leidas
    for numero, linea in enumerate(ruta.read_text(encoding="utf-8").splitlines(), 1):
        linea = linea.strip()
        if not linea or linea.startswith("#"):
            continue
        if "=" not in linea:
            raise ErrorConfiguracion(f"Línea {numero} de {ruta.name} sin '=': {linea!r}")
        clave, valor = (parte.strip() for parte in linea.split("=", 1))
        valor = valor.strip("'\"")
        leidas[clave] = valor
        os.environ.setdefault(clave, valor)
    return leidas


def cargar_configuracion(ruta: str | os.PathLike | None = None) -> dict[str, Any]:
    """Carga ``configs/config.yaml`` (u otro archivo) y aplica el ``.env`` y el entorno.

    Args:
        ruta: Archivo YAML. Si es ``None`` se usa ``LECTOR_CONFIG`` o el archivo por defecto.

    Returns:
        Configuración como diccionario.

    Raises:
        ErrorConfiguracion: si el archivo no existe, no es YAML válido o le faltan secciones.
    """
    cargar_env()
    ruta = ruta_proyecto(ruta or os.environ.get("LECTOR_CONFIG") or CONFIG_POR_DEFECTO)
    if not ruta.is_file():
        raise ErrorConfiguracion(f"No se encontró el archivo de configuración: {ruta}")
    try:
        config = yaml.safe_load(ruta.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise ErrorConfiguracion(f"{ruta.name} no es un YAML válido: {exc}") from exc
    if not isinstance(config, dict):
        raise ErrorConfiguracion(f"{ruta.name} debe contener secciones clave: valor")
    faltantes = [s for s in SECCIONES_REQUERIDAS if not isinstance(config.get(s), dict)]
    if faltantes:
        raise ErrorConfiguracion(f"Faltan secciones en {ruta.name}: {', '.join(faltantes)}")
    config = copy.deepcopy(config)
    for variable, (seccion, clave) in VARIABLES_ENTORNO.items():
        if os.environ.get(variable):
            config[seccion][clave] = os.environ[variable]
    _validar_configuracion(config)
    return config


def _validar_configuracion(config: dict[str, Any]) -> None:
    """Revisa los valores numéricos que, mal puestos, romperían la lectura."""
    entrada = config["entrada"]
    for clave in ("tamano_maximo_mb", "paginas_maximas_pdf", "dimension_minima_px"):
        valor = entrada.get(clave)
        if not isinstance(valor, (int, float)) or valor <= 0:
            raise ErrorConfiguracion(f"entrada.{clave} debe ser un número positivo (valor: {valor!r})")
    extensiones = entrada.get("extensiones")
    if not extensiones or not all(str(e).startswith(".") for e in extensiones):
        raise ErrorConfiguracion("entrada.extensiones debe ser una lista como [.jpg, .png, .pdf]")
    nivel = str(config["registro"].get("nivel", "INFO")).upper()
    if nivel not in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
        raise ErrorConfiguracion(f"registro.nivel no reconocido: {nivel}")


def configurar_registro(config: dict[str, Any] | None = None, a_archivo: bool = True) -> logging.Logger:
    """Configura el logger ``lector`` con salida a consola y, si se pide, a archivo.

    Es idempotente: llamarla varias veces no duplica los mensajes.
    """
    config = config or cargar_configuracion()
    logger = logging.getLogger(NOMBRE_LOGGER)
    logger.setLevel(str(config["registro"].get("nivel", "INFO")).upper())
    formato = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s", "%Y-%m-%d %H:%M:%S")
    consolas = [h for h in logger.handlers if type(h) is logging.StreamHandler]
    if not consolas:
        consola = logging.StreamHandler()
        consola.setFormatter(formato)
        logger.addHandler(consola)
    archivo = config["registro"].get("archivo")
    if a_archivo and archivo and not any(isinstance(h, logging.FileHandler) for h in logger.handlers):
        ruta = ruta_proyecto(archivo)
        try:
            ruta.parent.mkdir(parents=True, exist_ok=True)
            manejador = logging.FileHandler(ruta, encoding="utf-8")
            manejador.setFormatter(formato)
            logger.addHandler(manejador)
        except OSError as exc:  # Carpeta de solo lectura: seguir solo con la consola.
            logger.warning("No se pudo escribir el registro en %s: %s", ruta, exc)
    return logger


def obtener_logger(nombre: str | None = None) -> logging.Logger:
    """Devuelve el logger del proyecto o uno hijo (``lector.<nombre>``)."""
    return logging.getLogger(f"{NOMBRE_LOGGER}.{nombre}" if nombre else NOMBRE_LOGGER)


def sha256_archivo(ruta: str | os.PathLike, bloque: int = 1 << 20) -> str:
    """SHA-256 de un archivo leído por bloques (sirve para archivos grandes)."""
    resumen = hashlib.sha256()
    with open(ruta, "rb") as archivo:
        for parte in iter(lambda: archivo.read(bloque), b""):
            resumen.update(parte)
    return resumen.hexdigest()


def leer_json(ruta: str | os.PathLike) -> Any:
    """Lee un JSON en UTF-8 con un mensaje claro si no existe o está dañado."""
    ruta = ruta_proyecto(ruta)
    try:
        return json.loads(ruta.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ErrorConfiguracion(f"No existe el archivo {ruta}") from exc
    except json.JSONDecodeError as exc:
        raise ErrorConfiguracion(f"{ruta.name} no es un JSON válido (línea {exc.lineno})") from exc


def escribir_json(ruta: str | os.PathLike, datos: Any) -> Path:
    """Escribe un JSON legible en UTF-8 creando las carpetas necesarias."""
    ruta = ruta_proyecto(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    return ruta


@contextmanager
def cronometro(descripcion: str, logger: logging.Logger | None = None) -> Iterator[dict[str, float]]:
    """Mide el tiempo de un bloque y lo registra al terminar.

    Ejemplo::

        with cronometro("OCR de la página 1") as tiempo:
            ...
        print(tiempo["segundos"])
    """
    medicion = {"segundos": 0.0}
    inicio = time.perf_counter()
    try:
        yield medicion
    finally:
        medicion["segundos"] = time.perf_counter() - inicio
        (logger or obtener_logger()).debug("%s: %.2f s", descripcion, medicion["segundos"])


def mensaje_para_usuario(error: BaseException) -> str:
    """Traduce una excepción a un mensaje corto y sin detalles técnicos para la interfaz."""
    if isinstance(error, ErrorLector):
        return str(error)
    if isinstance(error, FileNotFoundError):
        return "No se encontró el archivo indicado."
    if isinstance(error, PermissionError):
        return "No hay permiso para leer o escribir el archivo."
    if isinstance(error, MemoryError):
        return "La imagen es demasiado grande para procesarla en este equipo."
    return "Ocurrió un error inesperado al procesar el documento. Revisa el registro para más detalles."
