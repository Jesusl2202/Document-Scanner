"""Lógica de la interfaz web, separada de Flask para poder probarla sin servidor.

``ServicioLector`` valida el archivo con los límites de la versión web, lee cada página con
:class:`src.model.LectorFacturas` y arma la respuesta que muestra la página: valores, nivel de
confianza, alertas en lenguaje claro, recuadro de evidencia y una vista previa de la página.

Privacidad: el archivo se guarda solo en una carpeta temporal mientras se lee y se borra al
terminar. La respuesta no incluye el texto OCR completo, solo la línea donde está cada valor.
"""
from __future__ import annotations

import base64
import copy
import io
import json
import tempfile
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps

from src.data_processing import cargar_paginas, validar_archivo
from src.model import CAMPOS, NOMBRES_CAMPOS, LectorFacturas, ResultadoPagina
from src.utils import (ErrorEntrada, ErrorLector, ErrorModelo, cargar_configuracion, leer_json,
                       mensaje_para_usuario, obtener_logger, ruta_proyecto)

from lector_facturas.common import normalize

LOGGER = obtener_logger("app")
CARPETA_EJEMPLOS = Path(__file__).resolve().parent / "assets" / "ejemplos"

# Alertas internas del extractor → explicación para quien revisa. «aviso» pide revisar el valor;
# «info» explica de dónde salió.
ALERTAS: dict[str, tuple[str, str]] = {
    "ambiguous_candidates": ("aviso", "Hay varios valores posibles y ninguno se impone: digítalo desde el documento."),
    "ambiguous_consensus": ("aviso", "Las lecturas no coinciden en un solo valor: compáralo con el documento."),
    "no_candidate": ("aviso", "No se encontró este dato en el documento."),
    "semantic_conflict": ("aviso", "Dos etiquetas del documento compiten por este valor: revisa cuál corresponde."),
    "identifiers_conflict": ("aviso", "El RUC y el número de comprobante podrían estar confundidos entre sí."),
    "focused_recovery_revisar": ("aviso", "Se recuperó con una lectura adicional de esa zona: confírmalo."),
    "focused_disagrees_revisar": ("aviso", "Una lectura adicional de esa zona dio otro valor: confírmalo."),
    "focused_conflict": ("aviso", "Las lecturas adicionales no coinciden: confírmalo."),
    "confidence_gap_recovery": ("aviso", "Se completó con lecturas de menor calidad: confírmalo."),
    "subtotal_no_confirma_total": ("aviso", "El subtotal leído no confirma el total: revisa descuentos o cargos."),
    "from_subtotal": ("aviso", "El total se dedujo del subtotal: confirma impuestos, cargos y descuentos."),
    "partial_failure": ("aviso", "Una de las lecturas adicionales falló."),
    "observed_accounting_selection": ("info", "Ajustado con descuentos o cargos impresos en el documento."),
    "structured_selection": ("info", "Tomado de una etiqueta explícita del documento."),
    "semantic_selection": ("info", "Asociado a su etiqueta por la posición en el documento."),
    "word_geometry_alignment": ("info", "Tomado del número alineado con su etiqueta."),
}

CUADRE = {
    "consistent": ("ok", "Subtotal + IVA = total"),
    "inconsistent_review": ("aviso", "Subtotal + IVA no coincide con el total: puede haber descuentos, propina o "
                                     "cargos, o un monto mal leído."),
    "insufficient_data": ("neutro", "No se puede comprobar el cuadre: falta subtotal, IVA o total."),
    "not_applicable": ("neutro", "El cuadre de montos no está activado."),
}


def explicar_alerta(codigo: str) -> dict[str, str]:
    """``"total:semantic_conflict"`` → campo, nivel y explicación en lenguaje claro."""
    campo, _, tipo = codigo.partition(":")
    if not tipo:
        campo, tipo = "", campo
    nivel, texto = ALERTAS.get(tipo, ("aviso", "Revisa este valor con el documento."))
    return {"codigo": codigo, "campo": campo if campo in CAMPOS else "", "nivel": nivel, "texto": texto}


def vista_previa(ruta: Path, lado_maximo: int = 1400) -> dict[str, Any]:
    """Imagen JPEG reducida (en base64) y tamaño original, para dibujar los recuadros encima."""
    with Image.open(ruta) as abierta:
        imagen = ImageOps.exif_transpose(abierta).convert("RGB")
    ancho, alto = imagen.size
    imagen.thumbnail((lado_maximo, lado_maximo))
    salida = io.BytesIO()
    imagen.save(salida, "JPEG", quality=82)
    return {"imagen": "data:image/jpeg;base64," + base64.b64encode(salida.getvalue()).decode("ascii"),
            "ancho": ancho, "alto": alto}


def evidencia_principal(campo: str, valor: str | None, evidencia: dict[str, list[dict[str, Any]]],
                        normalizacion: dict[str, str],
                        palabras: list[dict[str, Any]] | None = None) -> dict[str, Any] | None:
    """Recuadro y línea de texto de la lectura que respalda el valor elegido.

    Si la regla que eligió el valor no guardó su posición, se busca el mismo valor entre las
    palabras del OCR principal (una a tres palabras seguidas de la misma línea).
    """
    if valor in (None, ""):
        return None
    elegido = normalize(campo, valor, normalizacion)
    candidatos = [e for e in evidencia.get(campo, [])
                  if e.get("box") and normalize(campo, e.get("value"), normalizacion) == elegido]
    if candidatos:
        mejor = min(candidatos, key=lambda e: (e.get("view") is None, e.get("view") or 0))
        return {"caja": [round(float(v), 1) for v in mejor["box"]], "texto": str(mejor.get("text", ""))[:120]}
    lineas: dict[Any, list[dict[str, Any]]] = {}
    for palabra in palabras or []:
        lineas.setdefault(palabra.get("line_id"), []).append(palabra)
    ordenadas = [sorted(g, key=lambda w: w["box"][0]) for g in lineas.values()]
    for largo in (1, 2, 3):                      # primero el trozo más corto que contiene el valor
        for grupo in ordenadas:
            for inicio in range(len(grupo) - largo + 1):
                trozo = grupo[inicio:inicio + largo]
                for union in (" ", ""):
                    texto = union.join(w["text"] for w in trozo)
                    if normalize(campo, texto, normalizacion) == elegido:
                        caja = [min(w["box"][0] for w in trozo), min(w["box"][1] for w in trozo),
                                max(w["box"][2] for w in trozo), max(w["box"][3] for w in trozo)]
                        linea = " ".join(w["text"] for w in grupo)
                        return {"caja": [round(float(v), 1) for v in caja], "texto": linea[:120]}
    return None


class ServicioLector:
    """Envuelve el modelo para la web: límites, una lectura a la vez y respuesta lista para mostrar."""

    def __init__(self, config: dict[str, Any] | None = None, lector: LectorFacturas | None = None) -> None:
        self.config = config or cargar_configuracion()
        web = self.config.get("interfaz", {})
        self.config_web = copy.deepcopy(self.config)
        self.config_web["entrada"]["tamano_maximo_mb"] = web.get("tamano_maximo_mb", 10)
        self.config_web["entrada"]["paginas_maximas_pdf"] = web.get("paginas_maximas_pdf", 3)
        self.lector = lector or LectorFacturas(self.config)
        self.turnos = threading.BoundedSemaphore(web.get("lecturas_simultaneas", 1))
        self.espera_maxima = float(web.get("espera_maxima_s", 120))

    # ---- información estática -------------------------------------------------------------
    def limites(self) -> dict[str, Any]:
        entrada = self.config_web["entrada"]
        return {"extensiones": entrada["extensiones"], "tamano_maximo_mb": entrada["tamano_maximo_mb"],
                "paginas_maximas_pdf": entrada["paginas_maximas_pdf"],
                "dimension_minima_px": entrada["dimension_minima_px"]}

    def ejemplos(self) -> list[dict[str, Any]]:
        catalogo = CARPETA_EJEMPLOS / "ejemplos.json"
        if not catalogo.is_file():
            return []
        return [{k: e[k] for k in ("id", "archivo", "titulo", "descripcion")}
                for e in json.loads(catalogo.read_text(encoding="utf-8"))["ejemplos"]]

    def ruta_ejemplo(self, identificador: str) -> Path:
        for ejemplo in self.ejemplos():
            if ejemplo["id"] == identificador:
                return CARPETA_EJEMPLOS / ejemplo["archivo"]
        raise ErrorEntrada("Ese ejemplo no existe.")

    def acerca_de(self) -> dict[str, Any]:
        info = self.lector.acerca_de()
        ficha_ruta = ruta_proyecto(self.config["rutas"].get("ficha_modelo", "models/ficha_modelo.json"))
        ficha = leer_json(ficha_ruta) if ficha_ruta.is_file() else {}
        info["evaluacion_final"] = ficha.get("evaluacion_final", {})
        info["validacion"] = ficha.get("validacion", {})
        info["campos"] = [{"clave": c, "nombre": NOMBRES_CAMPOS[c]} for c in CAMPOS]
        info["limites"] = self.limites()
        return info

    # ---- lectura ----------------------------------------------------------------------------
    def leer(self, ruta: str | Path, nombre_original: str | None = None) -> dict[str, Any]:
        """Lee un archivo y devuelve la respuesta para la página.

        Raises:
            ErrorEntrada: archivo inválido (mensaje para el usuario).
            ErrorModelo: el modelo no está disponible.
            TimeoutError: el servidor está ocupado con otras lecturas.
        """
        identificador = uuid.uuid4().hex[:8]
        nombre = nombre_original or Path(ruta).name
        validado = validar_archivo(ruta, self.config_web)     # antes de esperar turno o cargar el modelo
        if not self.turnos.acquire(timeout=self.espera_maxima):
            raise TimeoutError("El servidor está ocupado con otras lecturas.")
        inicio = time.perf_counter()
        try:
            self.lector.cargar()
            with tempfile.TemporaryDirectory(prefix="lector_web_") as temporal:
                paginas = cargar_paginas(validado.ruta, Path(temporal), self.config_web)
                resultado = [self._pagina(self.lector.leer_pagina(p, n), p) for n, p in enumerate(paginas, 1)]
        finally:
            self.turnos.release()
        segundos = round(time.perf_counter() - inicio, 1)
        estados = {p["estado"] for p in resultado}
        estado = "ok" if estados == {"ok"} else ("error" if estados == {"error"} else "parcial")
        LOGGER.info("Lectura web %s: %s, %d página(s), %.1f s", identificador, estado, len(resultado), segundos)
        return {"id": identificador, "archivo": nombre, "tipo": validado.tipo, "estado": estado,
                "segundos": segundos, "avisos_entrada": list(validado.avisos), "paginas": resultado}

    def _pagina(self, pagina: ResultadoPagina, ruta_imagen: Path) -> dict[str, Any]:
        datos: dict[str, Any] = {"numero": pagina.pagina, "estado": pagina.estado, "segundos": pagina.segundos}
        try:
            datos["vista_previa"] = vista_previa(ruta_imagen)
        except OSError:
            datos["vista_previa"] = None
        if pagina.estado != "ok":
            datos.update(error=pagina.error or "No se pudo leer esta página.", campos=[], alertas=[], cuadre=None)
            return datos
        normalizacion = (self.lector.configuracion_modelo or {}).get("normalization", {})
        alertas = [explicar_alerta(a) for a in pagina.alertas]
        campos = []
        for clave in CAMPOS:
            valor = pagina.campos.get(clave)
            confianza = pagina.confianza.get(clave, {})
            campos.append({
                "clave": clave, "nombre": NOMBRES_CAMPOS[clave],
                "valor": valor if valor not in (None, "") else None,
                "normalizado": normalize(clave, valor, normalizacion) if valor not in (None, "") else None,
                "confianza": confianza.get("nivel", "sin_valor"),
                "vistas": confianza.get("vistas", 0), "de": confianza.get("de", 0),
                "evidencia": evidencia_principal(clave, valor, pagina.evidencia, normalizacion,
                                                 pagina.palabras),
                "alertas": [a for a in alertas if a["campo"] == clave],
            })
        balance = pagina.validacion.get("amount_balance", "not_applicable")
        nivel, texto = CUADRE.get(balance, CUADRE["not_applicable"])
        fecha = pagina.validacion.get("date")
        avisos = []
        if fecha == "ambiguous_date_order":
            avisos.append("La fecha admite dos lecturas (día/mes o mes/día): confírmala con el documento.")
        encontrados = sum(c["valor"] is not None for c in campos)
        if encontrados == 0:
            avisos.append("No se encontró ningún campo. ¿Es una factura impresa y legible? Prueba con una foto más "
                          "cercana, recta y con buena luz.")
        datos.update(campos=campos, encontrados=encontrados,
                     alertas=[a for a in alertas if not a["campo"]],
                     cuadre={"estado": balance, "nivel": nivel, "texto": texto},
                     avisos=avisos, revision=list(pagina.revision))
        return datos


def respuesta_error(exc: BaseException) -> tuple[dict[str, Any], int]:
    """Mensaje para el usuario y código HTTP según el tipo de error."""
    if isinstance(exc, ErrorEntrada):
        return {"error": str(exc), "tipo": "entrada"}, 400
    if isinstance(exc, TimeoutError):
        return {"error": "El servidor está atendiendo otras lecturas. Espera unos segundos y vuelve a intentar.",
                "tipo": "ocupado"}, 503
    if isinstance(exc, ErrorModelo):
        return {"error": str(exc), "tipo": "modelo"}, 503
    if isinstance(exc, ErrorLector):
        return {"error": str(exc), "tipo": "lector"}, 500
    return {"error": mensaje_para_usuario(exc).replace(" Revisa el registro para más detalles.", "")
            + " Intenta con otro archivo o vuelve a intentar.", "tipo": "inesperado"}, 500
