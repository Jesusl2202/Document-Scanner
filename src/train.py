"""«Entrenamiento» del modelo: optimización de su configuración en validación.

El lector **no entrena pesos**: el OCR usa redes LSTM preentrenadas de Tesseract y la
asignación de campos se hace con reglas y consenso. Lo que sí se ajusta con datos son los
**hiperparámetros del consenso** (peso de la vista principal, puntos por voto, por coincidencia
aproximada y por cuadre de montos). Este script hace esa búsqueda de forma reproducible:

1. Prepara SROIE y WildReceipt y separa la partición ``validation`` en *optimización* y *control*
   (disjuntas por hash y sin imágenes del test oficial).
2. Lee el OCR una sola vez y prueba configuraciones del extractor real sobre esas lecturas.
3. Elige por exactitud macro y compara con la configuración actual en control con un
   bootstrap pareado. **Solo recomienda un cambio si la mejora tiene IC95 > 0 y no empeora el
   peor campo.**

El análisis completo del Workshop S5 (sensibilidad, PDP, importancia e interacciones, con más
hiperparámetros) está en ``notebooks/04_optimizacion.ipynb``.

Uso::

    python -m src.train --datos data/raw --salida outputs/optimizacion
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from lector_facturas.experiments import optimize_consensus_cached

from .data_processing import localizar_datasets, preparar_datasets
from .model import LectorFacturas
from .utils import (ErrorEntrada, ErrorLector, cargar_configuracion, configurar_registro, escribir_json,
                    leer_json, obtener_logger, ruta_proyecto)

LOGGER = obtener_logger("entrenamiento")


def optimizar(filas: list[dict[str, Any]], config_modelo: dict[str, Any], carpeta_salida: str | Path,
              n_optimizacion: int = 30, n_control: int = 20, configuraciones: int = 24,
              semilla: int = 42) -> dict[str, Any]:
    """Busca los hiperparámetros del consenso en validación y decide si adoptarlos.

    Args:
        filas: Manifiesto de :func:`src.data_processing.preparar_datasets`.
        config_modelo: Configuración con pesos ya verificados (``LectorFacturas.configuracion_modelo``).
        carpeta_salida: Carpeta **nueva** para el plan, las lecturas y la selección.
        n_optimizacion, n_control: Documentos por dataset en cada muestra.
        configuraciones: Número de configuraciones a evaluar (incluida la actual).
        semilla: Semilla de las muestras y de la búsqueda.

    Returns:
        Informe con la búsqueda, la mejor configuración, el antes/después en control y la decisión.
    """
    carpeta = ruta_proyecto(carpeta_salida)
    if carpeta.exists():
        raise ErrorEntrada(f"La carpeta {carpeta} ya existe: usa una nueva para no mezclar ejecuciones.")
    LOGGER.info("Optimizando con %d+%d documentos por dataset y %d configuraciones", n_optimizacion, n_control,
                configuraciones)
    try:
        informe = optimize_consensus_cached(filas, config_modelo, carpeta, carpeta.parent / "cache_ocr",
                                            n_opt=n_optimizacion, n_control=n_control, trials=configuraciones,
                                            seed=semilla)
    except ValueError as exc:
        raise ErrorEntrada(f"No se pudo optimizar: {exc}") from exc
    resumen = resumir_informe(informe)
    escribir_json(carpeta / "resumen_optimizacion.json", resumen)
    LOGGER.info("Decisión: %s (Δ control %.2f pp, IC95 inferior %.2f pp)", resumen["decision"],
                resumen["delta_control_pp"], resumen["ic95_inferior_pp"])
    return informe


def resumir_informe(informe: dict[str, Any]) -> dict[str, Any]:
    """Extrae del informe completo lo necesario para ``docs/optimizacion.md``."""
    return {"decision": "adoptar" if informe["adopted"] else "mantener_actual",
            "parametros_seleccionados": informe["best"]["parameters"],
            "macro_optimizacion": informe["best"]["macro"],
            "macro_control_actual": informe["control_base"]["macro"],
            "macro_control_seleccionada": informe["control_candidate"]["macro"],
            "peor_campo_control_actual": informe["control_base"]["minimum"],
            "peor_campo_control_seleccionada": informe["control_candidate"]["minimum"],
            "delta_control_pp": informe["paired"]["delta_pp"],
            "ic95_inferior_pp": informe["paired"]["ic95_inferior_pp"],
            "ic95_superior_pp": informe["paired"]["ic95_superior_pp"],
            "configuraciones_evaluadas": len(informe["search"])}


def guardar_recomendacion(informe: dict[str, Any],
                          destino: str | Path = "models/configuracion_recomendada.json") -> Path:
    """Guarda los parámetros recomendados en el formato que acepta ``05_evaluacion.ipynb``.

    No modifica ``configs/definitivo.json``: adoptar la recomendación es una decisión explícita.
    """
    parametros = informe["config"].get("consensus_parameters", {})
    return escribir_json(destino, {"consensus_parameters": parametros,
                                   "decision": "adoptar" if informe["adopted"] else "mantener_actual"})


def main(argumentos: list[str] | None = None) -> int:
    """Punto de entrada de línea de comandos."""
    parser = argparse.ArgumentParser(description="Optimiza los hiperparámetros del consenso en validación.")
    parser.add_argument("--datos", default=None,
                        help="Carpeta con SROIE y WildReceipt (por defecto rutas.datos_crudos)")
    parser.add_argument("--salida", default="outputs/optimizacion", help="Carpeta nueva para los resultados")
    parser.add_argument("--config", default=None, help="Otro config.yaml (opcional)")
    parser.add_argument("--guardar", action="store_true", help="Escribe models/configuracion_recomendada.json")
    args = parser.parse_args(argumentos)
    try:
        config = cargar_configuracion(args.config)
        configurar_registro(config)
        sroie, wild = localizar_datasets(args.datos or config["rutas"]["datos_crudos"])
        if not (sroie and wild):
            raise ErrorEntrada("No se encontraron SROIE y WildReceipt. Descárgalos con scripts/download_data.py "
                               "(ver data/raw/README.md).")
        lector = LectorFacturas(config).cargar()
        crudo = leer_json(lector.ruta_modelo)
        filas = preparar_datasets(sroie, wild, Path(args.salida).with_name("preparados"), crudo)
        parametros = config.get("optimizacion", {})
        informe = optimizar(filas, lector.configuracion_modelo, args.salida,
                            parametros.get("documentos_optimizacion", 30), parametros.get("documentos_control", 20),
                            parametros.get("configuraciones", 24), config["evaluacion"]["semilla"])
        if args.guardar:
            print("Recomendación guardada en", guardar_recomendacion(informe))
    except ErrorLector as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print(resumir_informe(informe))
    return 0


if __name__ == "__main__":
    sys.exit(main())
