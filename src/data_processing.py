"""Funciones de procesamiento de datos: entrada, imágenes, normalización y datasets.

Todo lo que ocurre antes de reconocer el texto pasa por aquí:

1. :func:`validar_archivo` revisa que el archivo exista, tenga un formato admitido,
   no supere el tamaño ni las páginas permitidas y se pueda abrir.
2. :func:`cargar_paginas` convierte un PDF en una imagen por página.
3. :func:`preprocesar_imagen` aplica una de las transformaciones del modelo y
   devuelve cómo volver a las coordenadas originales.
4. :func:`normalizar_campo` lleva fechas y montos a un formato comparable.
5. :func:`preparar_datasets` arma el manifiesto de SROIE y WildReceipt con la
   partición train / validation / test / quarantine.
"""
from __future__ import annotations

import os
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from PIL import Image, ImageOps, UnidentifiedImageError

from lector_facturas.common import FIELDS, money, normalize, normalize_date
from lector_facturas.datasets import prepare
from lector_facturas.ocr import render_pdf
from lector_facturas.preprocessing import original_box, prepare_image

from .utils import ErrorEntrada, cargar_configuracion, obtener_logger, ruta_proyecto

LOGGER = obtener_logger("datos")
CAMPOS = FIELDS
PREPROCESAMIENTOS = ("original", "resize", "otsu", "illumination", "denoise", "local_binary")


@dataclass
class ArchivoValidado:
    """Resultado de :func:`validar_archivo`."""

    ruta: Path
    tipo: str                       # "imagen" o "pdf"
    tamano_mb: float
    paginas: int = 1
    dimensiones: tuple[int, int] | None = None
    avisos: list[str] = field(default_factory=list)


def _limites(config: dict[str, Any] | None) -> dict[str, Any]:
    return (config or cargar_configuracion())["entrada"]


def validar_archivo(ruta: str | os.PathLike, config: dict[str, Any] | None = None) -> ArchivoValidado:
    """Valida un archivo de entrada antes de procesarlo.

    Args:
        ruta: Imagen (``.jpg``, ``.jpeg``, ``.png``) o PDF.
        config: Configuración de la aplicación; por defecto ``configs/config.yaml``.

    Returns:
        :class:`ArchivoValidado` con el tipo, tamaño, páginas y avisos no bloqueantes.

    Raises:
        ErrorEntrada: con un mensaje para el usuario si el archivo no se puede procesar.
    """
    limites = _limites(config)
    ruta = Path(ruta)
    if not ruta.is_file():
        raise ErrorEntrada(f"No se encontró el archivo «{ruta.name}».")
    extension = ruta.suffix.lower()
    admitidas = [str(e).lower() for e in limites["extensiones"]]
    if extension not in admitidas:
        raise ErrorEntrada(f"Formato «{extension or 'sin extensión'}» no admitido. Usa: {', '.join(admitidas)}.")
    tamano_mb = ruta.stat().st_size / 1_048_576
    if tamano_mb == 0:
        raise ErrorEntrada("El archivo está vacío.")
    if tamano_mb > limites["tamano_maximo_mb"]:
        raise ErrorEntrada(f"El archivo pesa {tamano_mb:.1f} MB; el máximo es {limites['tamano_maximo_mb']} MB.")
    if extension == ".pdf":
        return _validar_pdf(ruta, tamano_mb, limites)
    return _validar_imagen(ruta, tamano_mb, limites)


def _validar_pdf(ruta: Path, tamano_mb: float, limites: dict[str, Any]) -> ArchivoValidado:
    import pypdfium2 as pdfium

    try:
        with pdfium.PdfDocument(str(ruta)) as pdf:
            paginas = len(pdf)
    except pdfium.PdfiumError as exc:
        raise ErrorEntrada("El PDF está dañado o protegido con contraseña.") from exc
    if paginas == 0:
        raise ErrorEntrada("El PDF no tiene páginas.")
    if paginas > limites["paginas_maximas_pdf"]:
        raise ErrorEntrada(f"El PDF tiene {paginas} páginas; el máximo es {limites['paginas_maximas_pdf']}.")
    avisos = ["Cada página se lee como un comprobante independiente."] if paginas > 1 else []
    return ArchivoValidado(ruta, "pdf", round(tamano_mb, 3), paginas, None, avisos)


def _validar_imagen(ruta: Path, tamano_mb: float, limites: dict[str, Any]) -> ArchivoValidado:
    try:
        with Image.open(ruta) as imagen:
            imagen.verify()                      # detecta archivos truncados o falsos
        with Image.open(ruta) as imagen:
            ancho, alto = ImageOps.exif_transpose(imagen).size
    except (UnidentifiedImageError, OSError, SyntaxError) as exc:
        raise ErrorEntrada("La imagen está dañada o no es una imagen válida.") from exc
    minimo = limites["dimension_minima_px"]
    if min(ancho, alto) < minimo:
        raise ErrorEntrada(f"La imagen mide {ancho}×{alto} px; el lado menor debe tener al menos {minimo} px.")
    avisos = []
    if ancho * alto < 300_000:
        avisos.append("Imagen pequeña (< 0,3 MP): la lectura puede ser menos precisa.")
    return ArchivoValidado(ruta, "imagen", round(tamano_mb, 3), 1, (ancho, alto), avisos)


def cargar_paginas(ruta: str | os.PathLike, carpeta_paginas: str | os.PathLike,
                   config: dict[str, Any] | None = None) -> list[Path]:
    """Devuelve la lista de imágenes a leer: la misma imagen o una por página del PDF.

    Raises:
        ErrorEntrada: si el archivo no es válido o el PDF no se puede convertir.
    """
    limites = _limites(config)
    validado = validar_archivo(ruta, config)
    if validado.tipo == "imagen":
        return [validado.ruta]
    try:
        paginas = render_pdf(validado.ruta, Path(carpeta_paginas), dpi=limites.get("dpi_pdf", 200),
                             max_pages=limites["paginas_maximas_pdf"])
    except ValueError as exc:
        raise ErrorEntrada(str(exc)) from exc
    LOGGER.info("PDF %s convertido en %d página(s)", validado.ruta.name, len(paginas))
    return [Path(p) for p in paginas]


def preprocesar_imagen(imagen: Image.Image | str | os.PathLike, metodo: str = "resize",
                       opciones: dict[str, Any] | None = None) -> tuple[Image.Image, dict[str, Any]]:
    """Aplica uno de los preprocesamientos del modelo a una imagen.

    Args:
        imagen: Imagen PIL o ruta a una imagen.
        metodo: Uno de ``original``, ``resize``, ``otsu``, ``illumination``, ``denoise``
            o ``local_binary``.
        opciones: Parámetros (``target_long_edge``, ``max_scale``, ``border``...). Por defecto,
            los de la sección ``ocr`` de ``configs/definitivo.json``.

    Returns:
        La imagen transformada y el diccionario de transformación para volver a las
        coordenadas originales con :func:`coordenadas_originales`.
    """
    if metodo not in PREPROCESAMIENTOS:
        raise ValueError(f"Preprocesamiento desconocido: {metodo}. Opciones: {', '.join(PREPROCESAMIENTOS)}")
    if opciones is None:
        from .utils import leer_json
        config = cargar_configuracion()
        opciones = leer_json(config["rutas"]["configuracion_modelo"])["ocr"]
    if isinstance(imagen, (str, os.PathLike)):
        with Image.open(imagen) as abierta:
            return prepare_image(ImageOps.exif_transpose(abierta), dict(opciones, preprocess=metodo))
    return prepare_image(imagen, dict(opciones, preprocess=metodo))


def coordenadas_originales(caja: Iterable[float], transformacion: dict[str, Any]) -> list[float]:
    """Lleva una caja ``[x1, y1, x2, y2]`` de la imagen transformada a la imagen original."""
    return original_box(list(caja), transformacion)


def normalizar_campo(campo: str, valor: Any, normalizacion: dict[str, str] | None = None) -> str | None:
    """Normaliza un campo para compararlo: fechas a ISO y montos a decimal con 2 cifras.

    Los valores que no se pueden interpretar quedan como ``RAW:<texto>`` y las fechas con día y
    mes intercambiables como ``AMBIGUOUS:...``. Los identificadores quedan en mayúsculas sin espacios.
    """
    if campo not in CAMPOS:
        raise ValueError(f"Campo desconocido: {campo}. Campos: {', '.join(CAMPOS)}")
    return normalize(campo, valor, normalizacion or {"date_order": "auto", "decimal_separator": "auto"})


def normalizar_monto(texto: Any, separador_decimal: str = "auto") -> str | None:
    """Monto a decimal con dos cifras (``'1.234,50'`` → ``'1234.50'``); ``None`` si es ambiguo."""
    return money(texto, separador_decimal)


def normalizar_fecha(texto: Any, orden: str = "auto") -> str | None:
    """Fecha a ``AAAA-MM-DD``. Con ``orden='dmy'`` se asume día/mes/año (Ecuador)."""
    if orden not in ("auto", "dmy", "mdy"):
        raise ValueError("orden debe ser 'auto', 'dmy' o 'mdy'")
    return normalize_date(texto, orden)


def preparar_datasets(raiz_sroie: str | os.PathLike | None, raiz_wildreceipt: str | os.PathLike | None,
                      carpeta_salida: str | os.PathLike, config_modelo: dict[str, Any]) -> list[dict[str, Any]]:
    """Lee SROIE y WildReceipt y escribe ``manifest.jsonl`` con la partición del proyecto.

    Returns:
        Una fila por documento con ``id``, ``dataset``, ``split``, ``image``, ``gold``, ``regions``...

    Raises:
        ErrorEntrada: si no se indicó ningún dataset o su estructura no es la esperada.
    """
    if not raiz_sroie and not raiz_wildreceipt:
        raise ErrorEntrada("Indica la carpeta de SROIE, de WildReceipt o de ambas (ver data/raw/README.md).")
    try:
        filas = prepare(raiz_sroie and ruta_proyecto(raiz_sroie), raiz_wildreceipt and ruta_proyecto(raiz_wildreceipt),
                        ruta_proyecto(carpeta_salida), config_modelo)
    except (FileNotFoundError, KeyError, ValueError) as exc:
        raise ErrorEntrada(f"No se pudieron preparar los datasets: {exc}") from exc
    LOGGER.info("Manifiesto con %d documentos: %s", len(filas), dict(resumir_particiones(filas)))
    return filas


def localizar_datasets(carpeta: str | os.PathLike) -> tuple[Path | None, Path | None]:
    """Busca SROIE y WildReceipt dentro de ``carpeta`` por su contenido, no por el nombre.

    Returns:
        ``(raiz_sroie, raiz_wildreceipt)``; cada una es ``None`` si no se encontró.
    """
    carpeta = ruta_proyecto(carpeta)
    if not carpeta.is_dir():
        return None, None
    sroie = next((p.parent.parent for p in carpeta.rglob("entities") if p.is_dir() and p.parent.name == "train"
                  and (p.parent / "img").is_dir() and (p.parent / "box").is_dir()), None)
    wild = next((p.parent for p in carpeta.rglob("class_list.txt")
                 if (p.parent / "train.txt").is_file() and (p.parent / "test.txt").is_file()), None)
    return sroie, wild


def resumir_particiones(filas: Iterable[dict[str, Any]]) -> Counter:
    """Cuenta documentos por (dataset, partición)."""
    return Counter((f["dataset"], f["split"]) for f in filas)


def cobertura_etiquetas(filas: Iterable[dict[str, Any]]) -> dict[tuple[str, str], float]:
    """Fracción de documentos de desarrollo con referencia utilizable, por dataset y campo."""
    desarrollo = [f for f in filas if f["split"] in ("train", "validation")]
    cobertura = {}
    for dataset in sorted({f["dataset"] for f in desarrollo}):
        grupo = [f for f in desarrollo if f["dataset"] == dataset]
        for campo in CAMPOS:
            anotados = sum(f["gold"][campo]["status"] == "annotated" for f in grupo)
            cobertura[(dataset, campo)] = anotados / len(grupo) if grupo else 0.0
    return cobertura
