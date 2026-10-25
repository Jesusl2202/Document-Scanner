"""Técnica de comparación aprendida: red neuronal que clasifica las líneas del OCR.

Es la versión liviana de LayoutLMv3 propuesta en la Ficha técnica (Semana 2) y usada en el
diagnóstico de overfitting (Semana 3), ahora evaluada **de extremo a extremo** con la misma
lectura OCR y la misma métrica que el modelo final:

1. Tesseract lee la imagen (vista principal, igual que la línea base M0).
2. Cada línea se describe con su texto (n-gramas de caracteres TF-IDF, con los dígitos
   reemplazados por ``0`` para que la red aprenda formatos y no montos concretos) y su
   posición y forma (coordenadas, ¿contiene un monto o una fecha?, ¿es el monto mayor?).
3. Una red MLP por campo (fecha, subtotal, impuesto, total) estima la probabilidad de que la
   línea contenga el valor. Las etiquetas son **débiles**: una línea es positiva si contiene el
   valor anotado, porque los datasets anotan valores y no líneas.
4. Se elige la línea más probable y se toma de ella el monto (el de más a la derecha) o la fecha.
   Si la probabilidad no supera el umbral, el campo queda vacío.

El entrenamiento registra la pérdida y el F1 de entrenamiento y validación en cada época
(:class:`Historial`) para diagnosticar overfitting, con *early stopping* opcional.
"""
from __future__ import annotations

import copy
import time
from dataclasses import dataclass, field
from typing import Any, Iterable

import numpy as np
import pandas as pd
from scipy import sparse
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import f1_score, log_loss
from sklearn.neural_network import MLPClassifier

from lector_facturas.candidate_rules import AMOUNT, DATE, MONTH_DATE
from lector_facturas.common import FIELDS, normalize
from lector_facturas.geometry import grouped

CAMPOS_APRENDIDOS = ("date", "subtotal", "tax", "total")
MONTOS = ("subtotal", "tax", "total")


# ---------------------------------------------------------------------------------------------
# Líneas, candidatos y etiquetas
# ---------------------------------------------------------------------------------------------


def candidatos(texto: str, campo: str, normalizacion: dict[str, str]) -> list[tuple[str, str, float]]:
    """Valores de la línea que podrían ser ``campo``: ``(texto, normalizado, posición x)``."""
    patrones = (DATE, MONTH_DATE) if campo == "date" else (AMOUNT,)
    salida = []
    for patron in patrones:
        for coincidencia in patron.finditer(texto):
            valor = coincidencia.group().strip()
            normal = normalize(campo, valor, normalizacion)
            if normal:
                salida.append((valor, str(normal), coincidencia.start() / max(1, len(texto))))
    return salida


def lineas_documento(ocr: dict[str, Any], normalizacion: dict[str, str]) -> list[dict[str, Any]]:
    """Líneas visuales del OCR con su posición normalizada y los candidatos de cada campo."""
    ancho = float(ocr.get("width") or 1)
    alto = float(ocr.get("height") or 1)
    filas = grouped({"words": ocr.get("words", [])})
    lineas = []
    for indice, fila in enumerate(filas):
        caja = fila["box"]
        lineas.append({"texto": fila["text"], "indice": indice,
                       "x0": caja[0] / ancho, "y0": caja[1] / alto, "x1": caja[2] / ancho, "y1": caja[3] / alto,
                       "candidatos": {c: candidatos(fila["text"], c, normalizacion) for c in CAMPOS_APRENDIDOS}})
    montos = [float(v[1]) for linea in lineas for v in linea["candidatos"]["total"]
              if _es_numero(v[1])]
    mayor = max(montos) if montos else None
    for linea in lineas:
        valores = [float(v[1]) for v in linea["candidatos"]["total"] if _es_numero(v[1])]
        linea["tiene_mayor"] = float(mayor is not None and mayor in valores)
        linea["posicion_relativa"] = linea["indice"] / max(1, len(lineas) - 1)
    return lineas


def _es_numero(texto: str) -> bool:
    try:
        float(texto)
        return True
    except (TypeError, ValueError):
        return False


def etiquetas(lineas: list[dict[str, Any]], gold: dict[str, dict[str, Any]], normalizacion: dict[str, str]
              ) -> dict[str, np.ndarray | None]:
    """Etiqueta débil por campo: 1 si la línea contiene el valor anotado. ``None`` si el campo no
    está anotado en ese documento (el documento no se usa para entrenar ese campo)."""
    salida: dict[str, np.ndarray | None] = {}
    for campo in CAMPOS_APRENDIDOS:
        referencia = gold.get(campo, {})
        if referencia.get("status") != "annotated":
            salida[campo] = None
            continue
        objetivo = str(normalize(campo, referencia.get("value"), normalizacion))
        salida[campo] = np.array([any(c[1] == objetivo for c in linea["candidatos"][campo]) for linea in lineas],
                                 dtype=np.int8)
    return salida


# ---------------------------------------------------------------------------------------------
# Características
# ---------------------------------------------------------------------------------------------


def _texto_para_tfidf(texto: str) -> str:
    return "".join("0" if ch.isdigit() else ch for ch in texto.lower())


def rasgos_diseno(linea: dict[str, Any], campo: str) -> list[float]:
    """Posición y forma de la línea (12 valores entre 0 y 1)."""
    texto = linea["texto"]
    digitos = sum(ch.isdigit() for ch in texto)
    n_candidatos = len(linea["candidatos"][campo])
    return [linea["x0"], linea["y0"], linea["x1"], linea["y1"], linea["x1"] - linea["x0"], linea["y1"] - linea["y0"],
            linea["posicion_relativa"], digitos / max(1, len(texto)), min(n_candidatos, 3) / 3,
            float(bool(linea["candidatos"]["date"])), float("%" in texto), linea["tiene_mayor"]]


class Caracterizador:
    """TF-IDF de n-gramas de caracteres (2 a 4) + 12 rasgos de diseño, ajustado solo con train."""

    def __init__(self, max_rasgos: int = 3000) -> None:
        self.tfidf = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4), max_features=max_rasgos,
                                     sublinear_tf=True, dtype=np.float32)

    def ajustar(self, textos: Iterable[str]) -> "Caracterizador":
        self.tfidf.fit([_texto_para_tfidf(t) for t in textos])
        return self

    def transformar(self, lineas: list[dict[str, Any]], campo: str) -> sparse.csr_matrix:
        texto = self.tfidf.transform([_texto_para_tfidf(linea["texto"]) for linea in lineas])
        diseno = sparse.csr_matrix(np.array([rasgos_diseno(linea, campo) for linea in lineas], dtype=np.float32))
        return sparse.hstack([texto, diseno], format="csr")


@dataclass
class Conjunto:
    """Matriz de un campo: filas = líneas de los documentos donde el campo está anotado."""

    X: sparse.csr_matrix
    y: np.ndarray
    documento: np.ndarray            # índice del documento de cada línea


def armar_conjunto(documentos: list[dict[str, Any]], campo: str, caracterizador: Caracterizador) -> Conjunto:
    """``documentos``: dicts con ``lineas`` y ``etiquetas`` (de :func:`preparar_documentos`)."""
    bloques, ys, docs = [], [], []
    for i, doc in enumerate(documentos):
        objetivo = doc["etiquetas"].get(campo)
        if objetivo is None or not doc["lineas"]:
            continue
        bloques.append(caracterizador.transformar(doc["lineas"], campo))
        ys.append(objetivo)
        docs.append(np.full(len(objetivo), i))
    if not bloques:
        return Conjunto(sparse.csr_matrix((0, 0)), np.zeros(0, dtype=np.int8), np.zeros(0, dtype=int))
    return Conjunto(sparse.vstack(bloques, format="csr"), np.concatenate(ys), np.concatenate(docs))


def preparar_documentos(filas: list[dict[str, Any]], lecturas: dict[str, dict[str, Any]],
                        normalizacion: dict[str, str]) -> list[dict[str, Any]]:
    """Une cada documento con su lectura OCR, sus líneas y sus etiquetas débiles."""
    documentos = []
    for fila in filas:
        ocr = lecturas.get(fila["id"])
        if ocr is None:
            continue
        lineas = lineas_documento(ocr, normalizacion)
        documentos.append({"id": fila["id"], "dataset": fila["dataset"], "fila": fila, "lineas": lineas,
                           "etiquetas": etiquetas(lineas, fila["gold"], normalizacion)})
    return documentos


# ---------------------------------------------------------------------------------------------
# Entrenamiento con historial por época
# ---------------------------------------------------------------------------------------------


@dataclass
class Historial:
    """Una fila por época con la pérdida y el F1 (clase positiva) de entrenamiento y validación."""

    nombre: str
    filas: list[dict[str, float]] = field(default_factory=list)

    def registrar(self, **valores: float) -> None:
        self.filas.append(valores)

    def tabla(self) -> pd.DataFrame:
        return pd.DataFrame(self.filas)


@dataclass
class ConfigRed:
    """Hiperparámetros de la red. Cada experimento cambia uno a la vez."""

    capas: tuple[int, ...] = (128,)
    l2: float = 1e-3                  # alpha de scikit-learn
    epocas: int = 40
    paciencia: int | None = 5         # None = sin early stopping
    tasa: float = 1e-3
    lote: int = 256

    def etiqueta(self) -> str:
        es = f"ES{self.paciencia}" if self.paciencia else "sin ES"
        return f"capas={self.capas}, L2={self.l2:g}, {es}"


def _metricas(modelo: MLPClassifier, conjunto: Conjunto) -> tuple[float, float]:
    probabilidad = modelo.predict_proba(conjunto.X)[:, 1]
    perdida = log_loss(conjunto.y, np.clip(probabilidad, 1e-7, 1 - 1e-7), labels=[0, 1])
    return float(perdida), float(f1_score(conjunto.y, probabilidad >= 0.5, zero_division=0))


def entrenar(train: Conjunto, val: Conjunto, config: ConfigRed, semilla: int = 42,
             nombre: str = "") -> tuple[MLPClassifier, Historial]:
    """Entrena una red con ``partial_fit`` época por época, registrando train y validación.

    Con ``paciencia`` se detiene cuando la pérdida de validación no mejora en ese número de
    épocas y devuelve la red de la mejor época (*early stopping* con restauración).
    """
    rng = np.random.default_rng(semilla)
    modelo = MLPClassifier(hidden_layer_sizes=config.capas, alpha=config.l2, learning_rate_init=config.tasa,
                           batch_size=config.lote, random_state=semilla)
    historial = Historial(nombre or config.etiqueta())
    mejor, mejor_perdida, sin_mejora = None, np.inf, 0
    for epoca in range(1, config.epocas + 1):
        inicio = time.perf_counter()
        orden = rng.permutation(train.X.shape[0])
        modelo.partial_fit(train.X[orden], train.y[orden], classes=np.array([0, 1]))
        perdida_train, f1_train = _metricas(modelo, train)
        perdida_val, f1_val = _metricas(modelo, val)
        historial.registrar(epoca=epoca, perdida_train=perdida_train, perdida_val=perdida_val,
                            f1_train=f1_train, f1_val=f1_val, segundos=time.perf_counter() - inicio)
        if perdida_val < mejor_perdida - 1e-6:
            mejor, mejor_perdida, sin_mejora = copy.deepcopy(modelo), perdida_val, 0
        else:
            sin_mejora += 1
            if config.paciencia and sin_mejora >= config.paciencia:
                break
    return (mejor if config.paciencia and mejor is not None else modelo), historial


# ---------------------------------------------------------------------------------------------
# Diagnóstico a partir del historial
# ---------------------------------------------------------------------------------------------


def cuantificar(historial: pd.DataFrame, inicio_sobreajuste: float = 0.05, restaurada: bool = False
                ) -> dict[str, float]:
    """Resume una curva en números: mejor época, subida de la pérdida de validación y brechas.

    Con ``restaurada=True`` (early stopping) las métricas «finales» son las de la mejor época,
    que es la red que se conserva.
    """
    historial = historial.reset_index(drop=True)
    mejor = int(historial.perdida_val.idxmin())
    minimo = float(historial.perdida_val.min())
    final = historial.iloc[mejor] if restaurada else historial.iloc[-1]
    encima = historial.index[(historial.perdida_val > minimo * (1 + inicio_sobreajuste)) & (historial.index > mejor)]
    return {"epocas": int(len(historial)), "mejor_epoca": int(historial.epoca.iloc[mejor]),
            "inicio_sobreajuste": int(historial.epoca.loc[encima[0]]) if len(encima) else None,
            "perdida_val_min": minimo, "perdida_train_final": float(final.perdida_train),
            "perdida_val_final": float(final.perdida_val),
            "subida_perdida_val_pct": 100 * (float(final.perdida_val) / minimo - 1),
            "f1_train_final": float(final.f1_train), "f1_val_final": float(final.f1_val),
            "brecha_f1": float(final.f1_train - final.f1_val)}


def diagnosticar(resumen: dict[str, float], subida_max_pct: float = 10.0, brecha_max: float = 0.10,
                 f1_minimo: float = 0.70) -> str:
    """Overfitting si la pérdida de validación sube más de ``subida_max_pct`` sobre su mínimo o la
    brecha de F1 supera ``brecha_max``; underfitting si el F1 de entrenamiento no llega a
    ``f1_minimo`` con una brecha pequeña; adecuado en otro caso."""
    if resumen["subida_perdida_val_pct"] > subida_max_pct or resumen["brecha_f1"] > brecha_max:
        return "overfitting"
    if resumen["f1_train_final"] < f1_minimo and resumen["brecha_f1"] < brecha_max / 2:
        return "underfitting"
    return "adecuado"


def sensibilidad_umbrales(resumenes: dict[str, dict[str, float]], subidas: Iterable[float] = (5, 10, 15, 20),
                          brechas: Iterable[float] = (0.05, 0.10, 0.15)) -> pd.DataFrame:
    """¿Cambia el diagnóstico si se mueven los umbrales? Una fila por modelo y combinación."""
    filas = []
    for nombre, resumen in resumenes.items():
        for subida in subidas:
            for brecha in brechas:
                filas.append({"modelo": nombre, "subida_max_%": subida, "brecha_max_f1": brecha,
                              "diagnostico": diagnosticar(resumen, subida, brecha)})
    return pd.DataFrame(filas)


# ---------------------------------------------------------------------------------------------
# Extracción de extremo a extremo
# ---------------------------------------------------------------------------------------------


@dataclass
class ClasificadorLineas:
    """Una red por campo + el caracterizador compartido. ``umbral`` decide cuándo abstenerse."""

    caracterizador: Caracterizador
    redes: dict[str, MLPClassifier]
    umbral: float = 0.5

    def extraer(self, lineas: list[dict[str, Any]]) -> dict[str, str | None]:
        campos: dict[str, str | None] = {c: None for c in FIELDS}
        if not lineas:
            return campos
        for campo, red in self.redes.items():
            utiles = [linea for linea in lineas if linea["candidatos"][campo]]
            if not utiles:
                continue
            probabilidad = red.predict_proba(self.caracterizador.transformar(utiles, campo))[:, 1]
            mejor = int(np.argmax(probabilidad))
            if probabilidad[mejor] < self.umbral:
                continue
            valores = utiles[mejor]["candidatos"][campo]
            elegido = valores[0] if campo == "date" else max(valores, key=lambda v: v[2])
            campos[campo] = elegido[0]
        return campos

    def predecir(self, documentos: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Predicciones en el formato de ``evaluation.evaluate``."""
        salida = []
        for doc in documentos:
            inicio = time.perf_counter()
            try:
                salida.append({"id": doc["id"], "dataset": doc["dataset"], "fields": self.extraer(doc["lineas"]),
                               "status": "ok", "text": "", "cache_hit": True,
                               "elapsed_seconds": time.perf_counter() - inicio})
            except Exception as exc:  # noqa: BLE001 - un documento no detiene la evaluación
                salida.append({"id": doc["id"], "dataset": doc["dataset"], "fields": {}, "status": "error",
                               "error": str(exc), "text": ""})
        return salida
