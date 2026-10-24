"""Validación en contextos simulados (Workshop S5).

Herramientas que usa ``notebooks/06_validacion_escenarios.ipynb``:

* :func:`muestra_no_revisada`: documentos que **nunca se miraron** durante el desarrollo, para
  medir cómo se comporta el modelo con datos nuevos.
* :data:`ESCENARIOS` y :func:`perturbar_imagen`: degradaciones controladas de la imagen
  (ruido, desenfoque, baja resolución, compresión, rotación, sombra y pérdida de una parte del
  documento) para las pruebas de estrés.
* :func:`detalle_campos`: une las métricas con el nivel de confianza de cada campo y separa
  los errores en **omisiones** y **valores equivocados**; un valor equivocado con confianza
  alta es un **error silencioso**, el más costoso porque la persona que revisa no recibe aviso.
* :func:`exactitud_por_documento`, :func:`calibracion` y :func:`tiempo_revision`: métricas
  del dominio para decidir cómo usar el sistema (revisión completa o guiada por la confianza).

Ninguna función cambia el modelo: todas leen imágenes o resultados ya producidos.
"""
from __future__ import annotations

import hashlib
import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable

import numpy as np
import pandas as pd
from PIL import Image, ImageEnhance, ImageFilter, ImageOps

from lector_facturas.common import FIELDS

from .model import calcular_confianza

# ---------------------------------------------------------------------------------------------
# Muestra de documentos nunca revisados
# ---------------------------------------------------------------------------------------------


def muestra_no_revisada(filas: list[dict[str, Any]], revisados: dict[str, str], n_por_base: int = 50,
                        semilla: int = 42) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Muestra aleatoria de la partición ``train`` con documentos que nadie miró al desarrollar.

    El modelo no se entrena, así que la partición de entrenamiento no se usó para ajustar nada:
    las reglas se ajustaron mirando los documentos de ``configs/documentos_revisados.json`` y los
    hiperparámetros con la partición ``validation``. Se excluyen además las imágenes repetidas
    (mismo SHA-256) en validación, test o cuarentena.

    Returns:
        ``(muestra, plan)``. El plan registra el tamaño del grupo elegible y cada exclusión.
    """
    vistos = set(revisados) | set(revisados.values())
    otras = {f["sha256"] for f in filas if f.get("split") != "train"}
    elegibles: dict[str, dict[str, Any]] = {}
    excluidos = {"ya_revisado": 0, "imagen_en_otra_particion": 0, "imagen_duplicada": 0}
    for fila in sorted(filas, key=lambda f: (f["dataset"], f["id"])):
        if fila.get("split") != "train":
            continue
        if fila["id"] in vistos or fila["sha256"] in vistos:
            excluidos["ya_revisado"] += 1
        elif fila["sha256"] in otras:
            excluidos["imagen_en_otra_particion"] += 1
        elif fila["sha256"] in elegibles:
            excluidos["imagen_duplicada"] += 1
        else:
            elegibles[fila["sha256"]] = fila
    rng = random.Random(semilla)
    muestra, grupo = [], {}
    for base in sorted({f["dataset"] for f in elegibles.values()}):
        candidatos = sorted((f for f in elegibles.values() if f["dataset"] == base), key=lambda f: f["id"])
        grupo[base] = len(candidatos)
        muestra.extend(rng.sample(candidatos, min(n_por_base, len(candidatos))))
    rng.shuffle(muestra)
    firma = hashlib.sha256(json.dumps(sorted((f["id"], f["sha256"]) for f in muestra)).encode()).hexdigest()
    plan = {"semilla": semilla, "particion": "train", "elegibles_por_base": grupo, "exclusiones": excluidos,
            "documentos": len(muestra),
            "por_base": {b: sum(f["dataset"] == b for f in muestra) for b in sorted(grupo)},
            "firma_muestra": firma,
            "nota": "Documentos nunca revisados durante el desarrollo; configuración fija antes de leerlos."}
    return muestra, plan


# ---------------------------------------------------------------------------------------------
# Escenarios críticos (perturbaciones de la imagen)
# ---------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Escenario:
    """Una perturbación con su nivel, en palabras de quien usa el sistema."""

    clave: str
    nivel: float | None
    nombre: str
    simula: str

    @property
    def etiqueta(self) -> str:
        return self.clave if self.nivel is None else f"{self.clave}_{self.nivel:g}"


ESCENARIOS: list[Escenario] = [
    Escenario("referencia", None, "Sin perturbar", "Imagen original"),
    Escenario("ruido", 12, "Ruido σ = 12", "Foto con poca luz o sensor de gama baja"),
    Escenario("ruido", 30, "Ruido σ = 30", "Foto nocturna o muy granulada"),
    Escenario("desenfoque", 1.5, "Desenfoque leve", "Foto ligeramente movida o desenfocada"),
    Escenario("desenfoque", 3.0, "Desenfoque fuerte", "Foto movida"),
    Escenario("resolucion", 0.5, "Mitad de resolución", "Foto tomada de lejos o reenviada reducida"),
    Escenario("resolucion", 0.3, "30 % de resolución", "Captura de pantalla o miniatura"),
    Escenario("jpeg", 12, "JPEG calidad 12", "Imagen recomprimida por mensajería"),
    Escenario("rotacion", 6, "Rotación 6°", "Foto torcida"),
    Escenario("sombra", 0.55, "Sombra lateral", "Iluminación desigual o sombra de la mano"),
    Escenario("recorte", 0.2, "Falta el 20 % inferior", "Comprobante cortado: el pie no aparece"),
]


def perturbar_imagen(imagen: Image.Image, escenario: Escenario, semilla: int = 42) -> Image.Image:
    """Aplica una perturbación determinista (misma semilla → misma imagen)."""
    imagen = ImageOps.exif_transpose(imagen).convert("RGB")
    nivel = escenario.nivel
    if escenario.clave == "referencia":
        return imagen
    if escenario.clave == "ruido":
        arreglo = np.asarray(imagen, dtype=np.float32)
        ruido = np.random.default_rng(semilla).normal(0, nivel, arreglo.shape[:2])[..., None]
        return Image.fromarray(np.clip(arreglo + ruido, 0, 255).astype(np.uint8))
    if escenario.clave == "desenfoque":
        return imagen.filter(ImageFilter.GaussianBlur(nivel))
    if escenario.clave == "resolucion":
        ancho, alto = imagen.size
        return imagen.resize((max(1, round(ancho * nivel)), max(1, round(alto * nivel))), Image.LANCZOS)
    if escenario.clave == "jpeg":
        import io
        salida = io.BytesIO()
        imagen.save(salida, "JPEG", quality=int(nivel))
        salida.seek(0)
        return Image.open(salida).convert("RGB")
    if escenario.clave == "rotacion":
        return imagen.rotate(-nivel, resample=Image.BICUBIC, expand=True, fillcolor=(255, 255, 255))
    if escenario.clave == "sombra":
        ancho, alto = imagen.size
        degradado = Image.linear_gradient("L").rotate(90).resize((ancho, alto))     # oscuro a la izquierda
        oscura = ImageEnhance.Brightness(imagen).enhance(nivel)
        return Image.composite(imagen, oscura, degradado)
    if escenario.clave == "recorte":
        ancho, alto = imagen.size
        return imagen.crop((0, 0, ancho, round(alto * (1 - nivel))))
    raise ValueError(f"Escenario desconocido: {escenario.clave}")


def filas_perturbadas(filas: Iterable[dict[str, Any]], escenario: Escenario, carpeta: str | Path,
                      semilla: int = 42) -> list[dict[str, Any]]:
    """Copia de ``filas`` cuyas imágenes son la versión perturbada (las referencias no cambian)."""
    carpeta = Path(carpeta)
    carpeta.mkdir(parents=True, exist_ok=True)
    salida = []
    for i, fila in enumerate(filas):
        destino = carpeta / f"{hashlib.sha1(fila['id'].encode()).hexdigest()[:16]}.png"
        if not destino.exists():
            with Image.open(fila["image"]) as original:
                perturbar_imagen(original, escenario, semilla + i).save(destino)
        with Image.open(destino) as nueva:
            ancho, alto = nueva.size
        salida.append(dict(fila, image=str(destino), width=ancho, height=alto,
                           sha256=hashlib.sha256(destino.read_bytes()).hexdigest()))
    return salida


# ---------------------------------------------------------------------------------------------
# Detalle por campo: tipo de error y confianza
# ---------------------------------------------------------------------------------------------


def leer_predicciones(carpeta: str | Path) -> dict[str, dict[str, Any]]:
    """``predictions.jsonl`` de una corrida de ``experiments.run``, indexado por documento."""
    ruta = Path(carpeta) / "predictions.jsonl"
    lineas = ruta.read_text(encoding="utf-8").splitlines()
    return {p["id"]: p for p in (json.loads(linea) for linea in lineas if linea.strip())}


def confianza_prediccion(prediccion: dict[str, Any], normalizacion: dict[str, str],
                         umbral_alta: float = 0.6, umbral_media: float = 0.3) -> dict[str, str]:
    """Nivel de confianza de cada campo, igual que en la interfaz (:func:`src.model.calcular_confianza`)."""
    if prediccion.get("status") != "ok":
        return {c: "sin_valor" for c in FIELDS}
    vistas = len(prediccion.get("ocr", {}).get("views", [])) or 1
    niveles = calcular_confianza(prediccion.get("fields", {}), prediccion.get("evidence", {}),
                                 prediccion.get("alerts", []), vistas, normalizacion, umbral_alta, umbral_media)
    return {c: niveles[c]["nivel"] for c in FIELDS}


def detalle_campos(carpeta: str | Path, normalizacion: dict[str, str], umbral_alta: float = 0.6,
                   umbral_media: float = 0.3) -> pd.DataFrame:
    """Una fila por campo anotado: acierto, tipo de error y nivel de confianza.

    ``tipo``: ``correcto``, ``omision`` (el sistema dejó el campo vacío) o ``equivocado``
    (devolvió un valor distinto). ``silencioso`` marca los equivocados con confianza alta.
    """
    carpeta = Path(carpeta)
    errores = pd.read_csv(carpeta / "evaluation" / "errors.csv", encoding="utf-8-sig")
    predicciones = leer_predicciones(carpeta)
    niveles = {i: confianza_prediccion(p, normalizacion, umbral_alta, umbral_media) for i, p in predicciones.items()}
    vacio = errores.predicted_normalized.isna() | (errores.predicted_normalized.astype(str).str.strip() == "")
    errores["tipo"] = np.where(errores.correct == 1, "correcto", np.where(vacio, "omision", "equivocado"))
    errores["confianza"] = [niveles.get(i, {}).get(c, "sin_valor") for i, c in zip(errores.id, errores.field)]
    errores["silencioso"] = (errores.tipo == "equivocado") & (errores.confianza == "alta")
    return errores


def resumen_errores(detalle: pd.DataFrame) -> dict[str, float]:
    """Exactitud y composición de los errores, en porcentaje de los campos anotados."""
    n = len(detalle)
    if n == 0:
        return {"campos": 0}
    return {"campos": n, "exactitud": 100 * (detalle.tipo == "correcto").mean(),
            "omisiones": 100 * (detalle.tipo == "omision").mean(),
            "equivocados": 100 * (detalle.tipo == "equivocado").mean(),
            "silenciosos": 100 * detalle.silencioso.mean()}


def exactitud_por_documento(detalle: pd.DataFrame) -> dict[str, float]:
    """Documentos con **todos** sus campos anotados correctos, y lo que se esperaría si los campos
    fallaran de forma independiente (producto de la exactitud de cada campo)."""
    por_doc = detalle.groupby("id").agg(ok=("correct", "sum"), n=("correct", "size"), dataset=("dataset", "first"))
    exactitud_campo = detalle.groupby(["dataset", "field"]).correct.mean()
    esperado = []
    for doc, campos in detalle.groupby("id"):
        esperado.append(float(np.prod([exactitud_campo[(d, f)] for d, f in zip(campos.dataset, campos.field)])))
    return {"documentos": int(len(por_doc)), "campos_por_documento": float(por_doc.n.mean()),
            "todo_correcto": 100 * float((por_doc.ok == por_doc.n).mean()),
            "esperado_si_independientes": 100 * float(np.mean(esperado)),
            "al_menos_un_error": 100 * float((por_doc.ok < por_doc.n).mean())}


def calibracion(detalle: pd.DataFrame) -> pd.DataFrame:
    """Exactitud por nivel de confianza: ¿la confianza separa los aciertos de los errores?"""
    orden = ["alta", "media", "baja", "sin_valor"]
    filas = []
    for nivel in orden:
        grupo = detalle[detalle.confianza == nivel]
        if len(grupo):
            filas.append({"confianza": nivel, "campos": len(grupo),
                          "porcentaje_de_campos": 100 * len(grupo) / len(detalle),
                          "exactitud": 100 * (grupo.tipo == "correcto").mean(),
                          "equivocados": 100 * (grupo.tipo == "equivocado").mean(),
                          "omisiones": 100 * (grupo.tipo == "omision").mean()})
    return pd.DataFrame(filas)


# ---------------------------------------------------------------------------------------------
# Tiempo de revisión (estimación con supuestos explícitos)
# ---------------------------------------------------------------------------------------------

TIEMPOS_SUPUESTOS = {
    # Segundos por campo. Supuestos de un modelo de tiempos de teclado (KLM, Card, Moran y Newell, 1980)
    # para una persona que digita a ~40 palabras por minuto; se reportan con un análisis de sensibilidad.
    "digitar": 9.0,       # ubicar el dato en la factura, leerlo y teclearlo (~10 caracteres)
    "verificar": 2.5,     # comparar un valor ya escrito con el documento
    "corregir": 9.0,      # borrar y teclear el valor correcto
}


def tiempo_revision(detalle: pd.DataFrame, tiempos: dict[str, float] | None = None) -> pd.DataFrame:
    """Segundos por documento con tres formas de trabajo y los errores que quedan en cada una.

    * **Manual**: digitar todos los campos (sin el sistema).
    * **Revisión completa**: verificar cada valor propuesto; corregir errores y digitar omisiones.
    * **Revisión guiada**: aceptar sin mirar los campos con confianza alta; revisar el resto.
      Los equivocados con confianza alta (errores silenciosos) quedan sin corregir.
    """
    t = dict(TIEMPOS_SUPUESTOS, **(tiempos or {}))
    por_doc = detalle.groupby("id")
    campos = por_doc.size().mean()
    omisiones = por_doc.apply(lambda g: (g.tipo == "omision").sum()).mean()
    equivocados = por_doc.apply(lambda g: (g.tipo == "equivocado").sum()).mean()
    no_alta = por_doc.apply(lambda g: (g.confianza != "alta").sum()).mean()
    corregir_guiada = por_doc.apply(lambda g: ((g.confianza != "alta") & (g.tipo != "correcto")).sum()).mean()
    silenciosos = por_doc.apply(lambda g: g.silencioso.sum()).mean()
    manual = campos * t["digitar"]
    completa = campos * t["verificar"] + equivocados * t["corregir"] + omisiones * t["digitar"]
    guiada = no_alta * t["verificar"] + corregir_guiada * t["corregir"]
    filas = [
        {"forma de trabajo": "Manual (sin el sistema)", "segundos_por_documento": manual,
         "errores_sin_corregir_por_100_documentos": 0.0},
        {"forma de trabajo": "Revisión completa", "segundos_por_documento": completa,
         "errores_sin_corregir_por_100_documentos": 0.0},
        {"forma de trabajo": "Revisión guiada por la confianza", "segundos_por_documento": guiada,
         "errores_sin_corregir_por_100_documentos": 100 * silenciosos},
    ]
    tabla = pd.DataFrame(filas)
    tabla["ahorro_vs_manual_%"] = 100 * (1 - tabla.segundos_por_documento / manual)
    return tabla


def sensibilidad_tiempos(detalle: pd.DataFrame, factores: Iterable[float] = (0.5, 1.0, 2.0)) -> pd.DataFrame:
    """Ahorro de la revisión completa si verificar tarda la mitad, lo mismo o el doble de lo supuesto."""
    filas = []
    for factor in factores:
        tabla = tiempo_revision(detalle, {"verificar": TIEMPOS_SUPUESTOS["verificar"] * factor})
        fila = tabla.set_index("forma de trabajo").loc["Revisión completa"]
        filas.append({"tiempo_verificar_s": TIEMPOS_SUPUESTOS["verificar"] * factor,
                      "segundos_por_documento": fila.segundos_por_documento,
                      "ahorro_vs_manual_%": fila["ahorro_vs_manual_%"]})
    return pd.DataFrame(filas)


def bootstrap_exactitud(detalle: pd.DataFrame, repeticiones: int = 2000, semilla: int = 42) -> tuple[float, float]:
    """Intervalo de confianza al 95 % de la exactitud por campo, remuestreando documentos por dataset."""
    por_doc = detalle.groupby(["dataset", "id"]).correct.agg(["sum", "size"]).reset_index()
    rng = np.random.default_rng(semilla)
    grupos = [g for _, g in por_doc.groupby("dataset")]
    valores = []
    for _ in range(repeticiones):
        muestra = pd.concat([g.iloc[rng.integers(0, len(g), len(g))] for g in grupos])
        valores.append(muestra["sum"].sum() / muestra["size"].sum())
    inferior, superior = np.percentile(valores, [2.5, 97.5])
    return 100 * float(inferior), 100 * float(superior)


def por_subgrupo(detalle: pd.DataFrame, grupos: dict[str, Callable[[pd.DataFrame], pd.Series]]) -> pd.DataFrame:
    """Exactitud, omisiones y errores silenciosos por subgrupo (análisis de equidad)."""
    filas = []
    for factor, asignar in grupos.items():
        etiquetas = asignar(detalle)
        for valor, grupo in detalle.groupby(etiquetas, observed=True):
            filas.append({"factor": factor, "grupo": str(valor), "documentos": grupo.id.nunique(),
                          **{k: v for k, v in resumen_errores(grupo).items()}})
    return pd.DataFrame(filas)
