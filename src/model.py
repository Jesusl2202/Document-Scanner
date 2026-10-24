"""Definición del modelo: la clase :class:`LectorFacturas`.

El modelo final («resumen contable») combina:

* **Tesseract 5 preentrenado** (pesos ``eng`` de ``tessdata_fast`` y ``tessdata_best`` y
  ``spa``), que lee cada imagen con 10 vistas y hasta 2 de rescate; y
* un **extractor de reglas, geometría y consenso** que elige un valor por campo entre
  los que alguna vista leyó de verdad, con resumen contable observado.

No hay pesos entrenados por el equipo: el modelo queda definido por
``configs/definitivo.json``, los pesos verificados por SHA-256 y el código de
``src/lector_facturas``. Esta clase los carga una vez y expone una API sencilla
para la interfaz, los scripts y las pruebas.

Ejemplo::

    from src.model import LectorFacturas
    lector = LectorFacturas().cargar()
    resultado = lector.leer("samples/synthetic_receipt.pdf")
    resultado.guardar("outputs/ejemplo")
    print(resultado.tabla())
"""
from __future__ import annotations

import argparse
import csv
import os
import shutil
import sys
import tempfile
import urllib.error
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from lector_facturas.cli import predict
from lector_facturas.common import FIELDS, normalize
from lector_facturas.frozen_runtime import bind_models, review_notes

from .data_processing import cargar_paginas, validar_archivo
from .utils import (ErrorEntrada, ErrorLector, ErrorModelo, cargar_configuracion, configurar_registro,
                    cronometro, escribir_json, leer_json, mensaje_para_usuario, obtener_logger, ruta_proyecto)

LOGGER = obtener_logger("modelo")
CAMPOS = FIELDS
NOMBRES_CAMPOS = {"tax_id": "RUC / identificador fiscal", "date": "Fecha de emisión",
                  "document_number": "Número de comprobante", "subtotal": "Subtotal", "tax": "Impuesto (IVA)",
                  "total": "Total"}


@dataclass
class ResultadoPagina:
    """Lectura de una página: campos, confianza, alertas y evidencia."""

    pagina: int
    estado: str                                      # "ok" o "error"
    campos: dict[str, str | None] = field(default_factory=dict)
    confianza: dict[str, dict[str, Any]] = field(default_factory=dict)
    alertas: list[str] = field(default_factory=list)
    revision: list[str] = field(default_factory=list)
    validacion: dict[str, str] = field(default_factory=dict)
    cobertura: dict[str, Any] = field(default_factory=dict)
    evidencia: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    texto: str = ""
    palabras: list[dict[str, Any]] = field(default_factory=list)   # palabras del OCR principal con su caja
    segundos: float | None = None
    error: str | None = None

    def campos_encontrados(self) -> int:
        """Cuántos de los seis campos tienen un valor."""
        return sum(self.campos.get(c) not in (None, "") for c in CAMPOS)


@dataclass
class ResultadoDocumento:
    """Lectura de un archivo completo (una o varias páginas)."""

    archivo: str
    paginas: list[ResultadoPagina]
    avisos_entrada: list[str] = field(default_factory=list)

    @property
    def estado(self) -> str:
        """``ok`` si todas las páginas se leyeron, ``parcial`` o ``error`` si no."""
        estados = {p.estado for p in self.paginas}
        return "ok" if estados == {"ok"} else ("error" if estados == {"error"} else "parcial")

    def campos(self, pagina: int = 1) -> dict[str, str | None]:
        """Campos extraídos de una página (por defecto, la primera)."""
        return self._pagina(pagina).campos

    def tabla(self, pagina: int = 1) -> list[dict[str, Any]]:
        """Filas listas para mostrar en la interfaz: campo, valor, confianza y alertas."""
        resultado = self._pagina(pagina)
        filas = []
        for campo in CAMPOS:
            valor = resultado.campos.get(campo)
            confianza = resultado.confianza.get(campo, {})
            filas.append({"campo": NOMBRES_CAMPOS[campo], "clave": campo,
                          "valor": valor if valor not in (None, "") else "No detectado",
                          "confianza": confianza.get("nivel", "sin_valor"),
                          "acuerdo_vistas": confianza.get("acuerdo"),
                          "alertas": "; ".join(a for a in resultado.alertas if a.startswith(campo + ":"))})
        return filas

    def a_dict(self) -> dict[str, Any]:
        """Representación serializable (sin el texto OCR si se quiere compartir, ver ``guardar``)."""
        return {"archivo": self.archivo, "estado": self.estado, "avisos_entrada": self.avisos_entrada,
                "paginas": [asdict(p) for p in self.paginas]}

    def filas_csv(self) -> list[dict[str, Any]]:
        """Una fila por página con los seis campos, igual que ``campos.csv`` del lector."""
        return [{"page": p.pagina, "status": p.estado, **{c: p.campos.get(c) for c in CAMPOS},
                 "revision": "; ".join(p.revision)} for p in self.paginas]

    def guardar(self, carpeta: str | os.PathLike, incluir_texto: bool = True) -> dict[str, Path]:
        """Escribe ``resultado.json`` y ``campos.csv`` en ``carpeta``.

        Args:
            incluir_texto: Si es ``False`` se omiten el texto OCR, las palabras y la evidencia (útil para
                compartir resultados sin el contenido completo de la factura).
        """
        carpeta = ruta_proyecto(carpeta)
        carpeta.mkdir(parents=True, exist_ok=True)
        datos = self.a_dict()
        if not incluir_texto:
            for pagina in datos["paginas"]:
                pagina["texto"], pagina["evidencia"], pagina["palabras"] = "", {}, []
        ruta_json = escribir_json(carpeta / "resultado.json", datos)
        ruta_csv = carpeta / "campos.csv"
        with ruta_csv.open("w", newline="", encoding="utf-8-sig") as archivo:
            escritor = csv.DictWriter(archivo, fieldnames=["page", "status", *CAMPOS, "revision"])
            escritor.writeheader()
            escritor.writerows(self.filas_csv())
        return {"json": ruta_json, "csv": ruta_csv}

    def _pagina(self, numero: int) -> ResultadoPagina:
        for pagina in self.paginas:
            if pagina.pagina == numero:
                return pagina
        raise IndexError(f"El documento no tiene la página {numero}")


def calcular_confianza(campos: dict[str, Any], evidencia: dict[str, list[dict[str, Any]]], alertas: list[str],
                       vistas_totales: int, normalizacion: dict[str, str], umbral_alta: float = 0.6,
                       umbral_media: float = 0.3) -> dict[str, dict[str, Any]]:
    """Nivel de confianza por campo según el acuerdo entre vistas OCR.

    ``acuerdo`` es la fracción de vistas que leyeron el valor elegido. No es una probabilidad
    calibrada: es una señal de cuántas lecturas independientes coinciden. Si el campo tiene una
    alerta (ajuste del resumen contable, rescate, ambigüedad), el nivel baja un escalón.

    Returns:
        ``{campo: {"nivel": "alta"|"media"|"baja"|"sin_valor", "acuerdo": float|None,
        "vistas": int, "de": int}}``
    """
    niveles = ["baja", "media", "alta"]
    resultado = {}
    for campo in CAMPOS:
        valor = campos.get(campo)
        if valor in (None, ""):
            resultado[campo] = {"nivel": "sin_valor", "acuerdo": None, "vistas": 0, "de": vistas_totales}
            continue
        elegido = normalize(campo, valor, normalizacion)
        vistas = {e.get("view") for e in evidencia.get(campo, [])
                  if e.get("view") is not None and normalize(campo, e.get("value"), normalizacion) == elegido}
        acuerdo = len(vistas) / vistas_totales if vistas_totales else 0.0
        indice = 2 if acuerdo >= umbral_alta else (1 if acuerdo >= umbral_media else 0)
        if any(a.startswith(campo + ":") for a in alertas):
            indice = max(0, indice - 1)
        resultado[campo] = {"nivel": niveles[indice], "acuerdo": round(acuerdo, 3), "vistas": len(vistas),
                            "de": vistas_totales}
    return resultado


class LectorFacturas:
    """Modelo final: carga la configuración y los pesos una vez y lee documentos.

    Args:
        config: Configuración de la aplicación (``configs/config.yaml``). Se carga si es ``None``.
        ruta_modelo: JSON del modelo; por defecto ``rutas.configuracion_modelo``.
        carpeta_pesos: Dónde se descargan y verifican los pesos; por defecto ``rutas.pesos``.
        carpeta_cache: Caché de lecturas OCR (opcional): acelera releer el mismo archivo.
    """

    def __init__(self, config: dict[str, Any] | None = None, ruta_modelo: str | os.PathLike | None = None,
                 carpeta_pesos: str | os.PathLike | None = None,
                 carpeta_cache: str | os.PathLike | None = None) -> None:
        self.config = config or cargar_configuracion()
        rutas = self.config["rutas"]
        self.ruta_modelo = ruta_proyecto(ruta_modelo or rutas["configuracion_modelo"])
        self.carpeta_pesos = ruta_proyecto(carpeta_pesos or rutas["pesos"])
        self.carpeta_cache = ruta_proyecto(carpeta_cache) if carpeta_cache else None
        self.configuracion_modelo: dict[str, Any] | None = None

    @property
    def cargado(self) -> bool:
        """``True`` después de :meth:`cargar`."""
        return self.configuracion_modelo is not None

    def cargar(self) -> "LectorFacturas":
        """Comprueba Tesseract, lee ``definitivo.json`` y prepara los pesos verificados.

        La primera vez descarga los pesos (~22 MB) desde revisiones fijas de GitHub.

        Raises:
            ErrorModelo: si falta Tesseract, la configuración es inválida o no se pueden obtener los pesos.
        """
        if self.cargado:
            return self
        if not shutil.which("tesseract"):
            raise ErrorModelo("Tesseract no está instalado o no está en el PATH. "
                              "Instálalo (Ubuntu: sudo apt-get install tesseract-ocr) y vuelve a intentar.")
        try:
            crudo = leer_json(self.ruta_modelo)
            with cronometro("Preparación de pesos", LOGGER):
                self.configuracion_modelo = bind_models(crudo, self.carpeta_pesos)
        except ErrorLector as exc:
            raise ErrorModelo(f"Configuración del modelo inválida: {exc}") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise ErrorModelo("No se pudieron descargar los pesos de Tesseract. Revisa la conexión a Internet "
                              "(solo se necesita la primera vez).") from exc
        except (ValueError, KeyError) as exc:
            raise ErrorModelo(f"Los pesos o la configuración no son válidos: {exc}") from exc
        vistas = len(self.configuracion_modelo["ocr"]["ensemble_views"])
        LOGGER.info("Modelo cargado: %d vistas OCR, pesos en %s", vistas, self.carpeta_pesos)
        return self

    def leer(self, ruta: str | os.PathLike, carpeta_salida: str | os.PathLike | None = None) -> ResultadoDocumento:
        """Lee una imagen o un PDF y devuelve los campos de cada página.

        Una página que falla no detiene las demás: queda con ``estado="error"`` y un mensaje.

        Args:
            ruta: Archivo ``.jpg``, ``.jpeg``, ``.png`` o ``.pdf``.
            carpeta_salida: Si se indica, se guardan ahí las páginas del PDF y los resultados.

        Raises:
            ErrorEntrada: si el archivo no es válido.
            ErrorModelo: si el modelo no se puede cargar.
        """
        validado = validar_archivo(ruta, self.config)      # primero la entrada: no cargar el modelo en vano
        self.cargar()
        LOGGER.info("Leyendo %s (%s, %d página(s))", validado.ruta.name, validado.tipo, validado.paginas)
        with tempfile.TemporaryDirectory() as temporal:
            carpeta_paginas = Path(carpeta_salida) / "paginas" if carpeta_salida else Path(temporal)
            paginas = cargar_paginas(validado.ruta, carpeta_paginas, self.config)
            resultados = [self.leer_pagina(p, numero) for numero, p in enumerate(paginas, 1)]
        documento = ResultadoDocumento(str(validado.ruta), resultados, validado.avisos)
        if carpeta_salida:
            documento.guardar(carpeta_salida)
        LOGGER.info("Lectura terminada: %s, %s", validado.ruta.name, documento.estado)
        return documento

    def leer_pagina(self, ruta_imagen: str | os.PathLike, numero: int = 1) -> ResultadoPagina:
        """Lee una sola imagen. Nunca lanza excepción: los errores quedan en el resultado."""
        self.cargar()
        try:
            with cronometro(f"Página {numero}", LOGGER) as tiempo:
                bruto = predict(Path(ruta_imagen), "tesseract", self.configuracion_modelo,
                                self.carpeta_cache)
            return self._a_resultado(bruto, numero, tiempo["segundos"])
        except Exception as exc:  # noqa: BLE001 - una página dañada no debe tumbar el documento
            LOGGER.exception("Falló la lectura de la página %d", numero)
            return ResultadoPagina(pagina=numero, estado="error", error=mensaje_para_usuario(exc),
                                   revision=["No se pudo procesar esta página."])

    def _a_resultado(self, bruto: dict[str, Any], numero: int, segundos: float) -> ResultadoPagina:
        umbrales = self.config.get("confianza", {})
        vistas = len(bruto.get("ocr", {}).get("views", [])) or 1
        confianza = calcular_confianza(bruto["fields"], bruto.get("evidence", {}), bruto.get("alerts", []), vistas,
                                       self.configuracion_modelo["normalization"],
                                       umbrales.get("umbral_alta", 0.6), umbrales.get("umbral_media", 0.3))
        return ResultadoPagina(pagina=numero, estado=bruto.get("status", "ok"), campos=dict(bruto["fields"]),
                               confianza=confianza, alertas=list(bruto.get("alerts", [])),
                               revision=review_notes(bruto), validacion=dict(bruto.get("validation", {})),
                               cobertura=dict(bruto.get("quality", {})), evidencia=bruto.get("evidence", {}),
                               texto=bruto.get("text", ""), segundos=round(segundos, 2),
                               palabras=[{"text": w.get("text", ""), "box": w.get("box"), "line_id": w.get("line_id")}
                                         for w in bruto.get("ocr", {}).get("words", []) if w.get("box")])

    def acerca_de(self) -> dict[str, Any]:
        """Información del modelo para la sección «Acerca de» de la interfaz."""
        ruta_ficha = ruta_proyecto(self.config["rutas"].get("ficha_modelo", "models/ficha_modelo.json"))
        ficha = leer_json(ruta_ficha) if ruta_ficha.is_file() else {}
        modelo = self.configuracion_modelo or leer_json(self.ruta_modelo)
        etapas = [k for k, v in modelo.items() if v is True]
        return {"nombre": ficha.get("modelo", "Resumen contable"), "descripcion": ficha.get("descripcion", ""),
                "vistas_ocr": len(modelo["ocr"]["ensemble_views"]) + (0 if self.cargado else 1),
                "vistas_rescate": len(modelo["ocr"].get("rescue_views", [])), "etapas": etapas,
                "resultados": ficha.get("resultados_desarrollo", {}),
                "metas": {k: v for k, v in self.config["evaluacion"].items() if k.startswith("meta")},
                "fuera_de_alcance": ficha.get("fuera_de_alcance", ["campos escritos a mano"]),
                "uso_previsto": ficha.get("uso_previsto", "")}


def main(argumentos: list[str] | None = None) -> int:
    """Uso: ``python -m src.model factura.pdf --salida outputs/factura``."""
    parser = argparse.ArgumentParser(description="Lee una factura o recibo impreso (imagen o PDF).")
    parser.add_argument("archivo", help="Imagen (.jpg, .png) o PDF")
    parser.add_argument("--salida", default="outputs/lectura", help="Carpeta para resultado.json y campos.csv")
    parser.add_argument("--config", default=None, help="Otro config.yaml (opcional)")
    args = parser.parse_args(argumentos)
    try:
        config = cargar_configuracion(args.config)
        configurar_registro(config)
        resultado = LectorFacturas(config).leer(args.archivo, args.salida)
    except (ErrorEntrada, ErrorModelo, ErrorLector) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    for fila in resultado.tabla():
        print(f"{fila['campo']:<28} {fila['valor']:<20} confianza: {fila['confianza']}")
    print(f"\nEstado: {resultado.estado}. Resultados en {ruta_proyecto(args.salida)}")
    return 0 if resultado.estado != "error" else 1


if __name__ == "__main__":
    sys.exit(main())
