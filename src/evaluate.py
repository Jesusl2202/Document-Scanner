"""Evaluación del modelo y organización de resultados en ``results/``.

Subcomandos::

    # Test oficial: N documentos por dataset, configuración congelada antes de leer
    python -m src.evaluate test --datos data/raw --por-base 50

    # Prueba externa: ZIP o carpeta con anotaciones.jsonl + imagenes/ (docs/anotacion_propia.md)
    python -m src.evaluate externo --anotaciones mi_muestra.zip

    # Copiar a results/ las tablas y figuras de los ZIP que descargan los notebooks 01–05
    python -m src.evaluate importar optimizacion_resultados.zip evaluacion_2026....zip

    # Regenerar results/reports/reporte_resultados.md con todo lo que haya en results/
    python -m src.evaluate reporte

Las métricas siguen la regla del proyecto: se comparan valores normalizados, un valor
equivocado cuenta como falso positivo y falso negativo, un campo sin anotación no cuenta y un
documento que falla sigue en el denominador.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from lector_facturas.experiments import load_external_test, metrics, random_known_sample, run

from .data_processing import localizar_datasets, preparar_datasets
from .model import LectorFacturas
from .utils import (ErrorEntrada, ErrorLector, cargar_configuracion, configurar_registro, escribir_json,
                    leer_json, obtener_logger, ruta_proyecto)

LOGGER = obtener_logger("evaluacion")
TIPOS_RESULTADO = ("eda", "preprocesamiento", "modelado", "optimizacion", "evaluacion")
DECISIONES = {"mantener_actual": "mantener la configuración actual", "adoptar": "adoptar la configuración seleccionada"}
# Archivos que nunca se copian a results/: pueden contener texto OCR, valores predichos documento por
# documento o datos de documentos propios. RESULTADOS.md es una nota genérica del motor por corrida.
EXCLUIDOS = ("predictions.jsonl", "evaluation_manifest.jsonl", "muestra_test_congelada.jsonl",
             "optimizacion.jsonl", "control.jsonl", "manifest.jsonl", "resultado.json", "errors.csv",
             "RESULTADOS.md")


def cumplimiento_metas(resumen: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    """Compara el resumen de ``evaluation.evaluate`` con las metas de ``config.yaml``."""
    metas = config["evaluacion"]
    exactitud, procesamiento = resumen["micro_exact_match"], resumen["execution_success_rate"]
    return {"exactitud": exactitud, "procesamiento": procesamiento,
            "meta_exactitud": metas["meta_exactitud"], "meta_procesamiento": metas["meta_procesamiento"],
            "cumple_exactitud": exactitud is not None and exactitud >= metas["meta_exactitud"],
            "cumple_procesamiento": procesamiento is not None and procesamiento >= metas["meta_procesamiento"],
            "documentos": resumen["documents"], "campos_evaluados": resumen["evaluated_field_instances"]}


def metricas_por_campo(carpeta_corrida: str | Path, meta_campo: float = 0.80) -> pd.DataFrame:
    """Tabla de exactitud, precisión, recall y F1 por dataset y campo de una corrida de ``run``."""
    tabla = metrics(carpeta_corrida)
    tabla = tabla[tabla.support > 0].copy()
    tabla["cumple_meta_campo"] = tabla.exact_match >= meta_campo
    return tabla


def evaluar_filas(filas: list[dict[str, Any]], lector: LectorFacturas, carpeta_salida: str | Path,
                  config: dict[str, Any], plan: dict[str, Any] | None = None) -> dict[str, Any]:
    """Ejecuta el modelo sobre ``filas`` anotadas y guarda métricas, plan y cumplimiento.

    El plan (configuración, hash del código y firma de la muestra) se escribe **antes** de leer.
    """
    carpeta = ruta_proyecto(carpeta_salida)
    if carpeta.exists():
        raise ErrorEntrada(f"La carpeta {carpeta} ya existe: usa una nueva para cada evaluación.")
    if not filas:
        raise ErrorEntrada("No hay documentos para evaluar.")
    lector.cargar()
    firma = hashlib.sha256(json.dumps(sorted((f["id"], f.get("sha256")) for f in filas)).encode()).hexdigest()
    codigo = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
              for p in sorted(ruta_proyecto("src/lector_facturas").glob("*.py"))}
    escribir_json(carpeta / "plan.json", {**(plan or {}), "documentos": len(filas), "firma_muestra": firma,
                                          "configuracion": leer_json(lector.ruta_modelo), "codigo_sha256": codigo,
                                          "fecha_utc": datetime.now(timezone.utc).isoformat()})
    LOGGER.info("Evaluando %d documentos en %s", len(filas), carpeta)
    corrida = run(filas, lector.configuracion_modelo, carpeta / "corrida", carpeta / "cache_ocr")
    resumen = json.loads((corrida / "evaluation/summary.json").read_text(encoding="utf-8"))
    cumplimiento = cumplimiento_metas(resumen, config)
    tabla = metricas_por_campo(corrida, config["evaluacion"].get("meta_interna_por_campo", 0.80))
    tabla.to_csv(carpeta / "metricas_por_campo.csv", index=False, encoding="utf-8-sig")
    escribir_json(carpeta / "cumplimiento_meta.json", cumplimiento)
    LOGGER.info("Exactitud %.1f %% · procesados %.1f %%", 100 * cumplimiento["exactitud"],
                100 * cumplimiento["procesamiento"])
    return {"cumplimiento": cumplimiento, "metricas": tabla, "carpeta": carpeta}


def evaluar_test(config: dict[str, Any], carpeta_datos: str | Path, carpeta_salida: str | Path,
                 por_base: int | None = None, semilla: int | None = None) -> dict[str, Any]:
    """Evalúa el modelo en una muestra del test oficial de SROIE y WildReceipt.

    Durante el desarrollo se revisó casi todo el test oficial, así que esta medición **no es
    inédita**: el plan registra cuántos documentos de la muestra ya se habían revisado.
    """
    sroie, wild = localizar_datasets(carpeta_datos)
    if not (sroie and wild):
        raise ErrorEntrada("No se encontraron SROIE y WildReceipt (ver data/raw/README.md).")
    lector = LectorFacturas(config).cargar()
    salida = ruta_proyecto(carpeta_salida)
    filas = preparar_datasets(sroie, wild, salida.with_name(salida.name + "_preparados"), leer_json(lector.ruta_modelo))
    por_base = por_base or config["evaluacion"]["documentos_por_base"]
    semilla = config["evaluacion"]["semilla"] if semilla is None else semilla
    muestra, plan = random_known_sample(filas, por_base, seed=semilla)
    revisados = leer_json("configs/documentos_revisados.json")
    vistos = set(revisados) | set(revisados.values())
    plan["ya_revisados_en_desarrollo"] = sum(f["id"] in vistos or f["sha256"] in vistos for f in muestra)
    return evaluar_filas(muestra, lector, salida, config, plan)


def evaluar_externo(config: dict[str, Any], anotaciones: str | Path, carpeta_salida: str | Path) -> dict[str, Any]:
    """Evalúa la muestra propia anotada (ZIP o carpeta con ``anotaciones.jsonl`` e ``imagenes/``).

    Excluye las imágenes que ya se usaron en el desarrollo (por SHA-256).
    """
    origen = ruta_proyecto(anotaciones)
    with tempfile.TemporaryDirectory() as temporal:
        raiz = _extraer_seguro(origen, Path(temporal)) if origen.suffix.lower() == ".zip" else origen
        try:
            raiz = next(p.parent for p in raiz.rglob("anotaciones.jsonl"))
            filas = load_external_test(raiz)
        except StopIteration as exc:
            raise ErrorEntrada("No se encontró anotaciones.jsonl (ver docs/anotacion_propia.md).") from exc
        except (ValueError, FileNotFoundError, KeyError) as exc:
            raise ErrorEntrada(f"Anotaciones inválidas: {exc}") from exc
        vistos = set(leer_json("configs/documentos_revisados.json").values())
        repetidas = [f["id"] for f in filas if f["sha256"] in vistos]
        if repetidas:
            LOGGER.warning("Se excluyen %d imágenes ya usadas en el desarrollo: %s", len(repetidas), repetidas)
        filas = [f for f in filas if f["sha256"] not in vistos]
        return evaluar_filas(filas, LectorFacturas(config), carpeta_salida, config,
                             {"modo": "prueba_externa", "excluidas_por_desarrollo": repetidas})


def _extraer_seguro(zip_path: Path, destino: Path) -> Path:
    """Extrae un ZIP rechazando rutas que salgan de ``destino``."""
    if not zip_path.is_file():
        raise ErrorEntrada(f"No existe el archivo {zip_path}")
    try:
        with zipfile.ZipFile(zip_path) as archivo:
            for item in archivo.infolist():
                if not (destino / item.filename).resolve().is_relative_to(destino.resolve()):
                    raise ErrorEntrada(f"El ZIP contiene una ruta no permitida: {item.filename}")
            archivo.extractall(destino)
    except zipfile.BadZipFile as exc:
        raise ErrorEntrada(f"{zip_path.name} no es un ZIP válido.") from exc
    return destino


def detectar_tipo(carpeta: Path) -> str:
    """Reconoce de qué notebook viene un ZIP de resultados por los archivos que contiene."""
    nombres = {p.name for p in carpeta.rglob("*")}
    if "seleccion.json" in nombres or "sensibilidad.csv" in nombres:
        return "optimizacion"
    if "plan_test.json" in nombres or "cumplimiento_meta.json" in nombres:
        return "evaluacion"
    if "modelo_final.json" in nombres or "ablacion.csv" in nombres:
        return "modelado"
    if "ocr_por_vista_validacion.csv" in nombres or "cer_por_vista.png" in nombres:
        return "preprocesamiento"
    if "01_particiones.png" in nombres or "coverage.csv" in nombres:
        return "eda"
    raise ErrorEntrada("No se reconoce de qué notebook viene este ZIP; indica --tipo.")


def importar_resultados(zip_path: str | Path, tipo: str | None = None,
                        carpeta_resultados: str | Path = "results") -> list[Path]:
    """Copia figuras (``.png``) y tablas (``.csv``/``.json``) de un ZIP de notebook a ``results/``.

    Nunca copia predicciones, manifiestos ni carpetas privadas, porque pueden contener el texto de
    las facturas.

    Returns:
        Rutas de los archivos copiados.
    """
    if tipo is not None and tipo not in TIPOS_RESULTADO:
        raise ErrorEntrada(f"Tipo desconocido: {tipo}. Opciones: {', '.join(TIPOS_RESULTADO)}")
    resultados = ruta_proyecto(carpeta_resultados)
    copiados = []
    with tempfile.TemporaryDirectory() as temporal:
        carpeta = _extraer_seguro(ruta_proyecto(zip_path), Path(temporal))
        tipo = tipo or detectar_tipo(carpeta)
        for archivo in sorted(carpeta.rglob("*")):
            relativo = archivo.relative_to(carpeta)
            if (not archivo.is_file() or archivo.name in EXCLUIDOS or archivo.suffix == ".jsonl"
                    or any(p in ("documento_privado", "cache_ocr", "paginas") for p in relativo.parts)):
                continue
            if archivo.suffix.lower() == ".png":
                destino = resultados / "figures" / tipo / archivo.name
            elif archivo.suffix.lower() in (".csv", ".json", ".md"):
                destino = resultados / "metrics" / tipo / relativo
            else:
                continue
            destino.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(archivo, destino)
            copiados.append(destino)
    LOGGER.info("Importados %d archivos de %s a results/ (%s)", len(copiados), Path(zip_path).name, tipo)
    return copiados


def _numero(valor: float, decimales: int = 1) -> str:
    """Número con coma decimal, como en el resto de la documentación."""
    return f"{valor:.{decimales}f}".replace(".", ",")


def tabla_markdown(tabla: pd.DataFrame, decimales: int = 2) -> str:
    """Convierte un DataFrame en una tabla Markdown sin dependencias extra."""
    def celda(valor: Any) -> str:
        if isinstance(valor, float):
            return str(int(valor)) if valor.is_integer() and abs(valor) >= 1 else _numero(valor, decimales)
        return str(valor)
    columnas = ["" if str(c).startswith("Unnamed") else str(c) for c in tabla.columns]
    filas = ["| " + " | ".join(columnas) + " |", "|" + "---|" * len(columnas)]
    filas += ["| " + " | ".join(celda(v) for v in fila) + " |" for fila in tabla.itertuples(index=False)]
    return "\n".join(filas)


def generar_reporte(carpeta_resultados: str | Path = "results") -> Path:
    """Escribe ``results/reports/reporte_resultados.md`` con todo lo que haya en ``results/metrics``.

    Las secciones sin datos quedan marcadas como pendientes en lugar de inventar cifras.
    """
    resultados = ruta_proyecto(carpeta_resultados)
    metricas = resultados / "metrics"
    partes = ["# Reporte de resultados", "",
              f"Resumen de las métricas de `results/metrics/` "
              f"(actualizado el {datetime.now().strftime('%d/%m/%Y')}).", ""]

    desarrollo = metricas / "desarrollo" / "resultados_desarrollo.csv"
    if desarrollo.is_file():
        partes += ["## Desarrollo del modelo", "", tabla_markdown(pd.read_csv(desarrollo)), "",
                   "Mediciones usadas para elegir el modelo; no son una evaluación independiente "
                   "(ver [`resultados_desarrollo.md`](resultados_desarrollo.md)).", ""]

    cobertura = metricas / "eda" / "cobertura_etiquetas.csv"
    if cobertura.is_file():
        partes += ["## Datos: cobertura de etiquetas", "", tabla_markdown(pd.read_csv(cobertura), 1), ""]

    seleccion = next(iter(sorted((metricas / "optimizacion").rglob("seleccion.json"))), None) \
        if (metricas / "optimizacion").is_dir() else None
    if seleccion:
        datos = json.loads(seleccion.read_text(encoding="utf-8"))
        control = datos.get("control", {})
        decision = datos.get("recomendada", {}).get("decision", datos.get("decision", "?"))
        partes += ["## Optimización de hiperparámetros", "",
                   f"- Configuraciones evaluadas: {datos.get('n_busqueda', '?')}",
                   f"- Decisión: **{DECISIONES.get(decision, decision)}**",
                   f"- Cambio de la configuración seleccionada en la muestra de control: "
                   f"{_numero(control.get('delta_pp', float('nan')), 2)} pp "
                   f"(IC95 {_numero(control.get('ic95_inferior_pp', float('nan')), 2)} a "
                   f"{_numero(control.get('ic95_superior_pp', float('nan')), 2)} pp)", "",
                   "Detalle en [`docs/optimizacion.md`](../../docs/optimizacion.md).", ""]

    evaluacion = metricas / "evaluacion"
    cumplimiento = (next(iter(sorted(evaluacion.rglob("cumplimiento_meta.json"))), None)
                    if evaluacion.is_dir() else None)
    if cumplimiento:
        c = json.loads(cumplimiento.read_text(encoding="utf-8"))
        partes += ["## Evaluación final", ""]
        cumple = c.get("cumple_exactitud_70", c.get("cumple_exactitud"))
        partes += [f"- Exactitud por campo: **{_numero(100 * c['exactitud'])} %** "
                   f"({'cumple' if cumple else 'no cumple'} la meta del 70 %)",
                   f"- Documentos procesados sin error: **{_numero(100 * c['procesamiento'])} %** "
                   f"({'cumple' if c.get('cumple_procesamiento_90', c.get('cumple_procesamiento')) else 'no cumple'}"
                   " la meta del 90 %)",
                   f"- Documentos: {c.get('documentos')} · campos evaluados: {c.get('campos_evaluados')}"]
        if c.get("mediana_s_por_documento") is not None:
            partes.append(f"- Tiempo por documento: mediana {_numero(c['mediana_s_por_documento'])} s, "
                          f"p95 {_numero(c['p95_s_por_documento'])} s")
        plan = next(iter(sorted(evaluacion.rglob("plan_test.json"))), None)
        if plan:
            p = json.loads(plan.read_text(encoding="utf-8"))
            partes += ["", f"Muestra aleatoria (semilla {p.get('seed')}) del test oficial: "
                       f"{', '.join(f'{v} de {k}' for k, v in p.get('by_dataset', {}).items())}. La configuración "
                       "quedó fija antes de leer la muestra. "
                       f"{p.get('ya_revisados_en_desarrollo', '?')} de los {p.get('documents', '?')} documentos "
                       "ya se habían revisado durante el desarrollo, así que no es una medición inédita."]
        partes.append("")
        for nombre, titulo in (("intervalos_confianza.csv", "Intervalos de confianza (%)"),
                               ("comparacion_modelos.csv", "Comparación con la línea base"),
                               ("deltas_bootstrap.csv", "Mejora frente a cada línea base (bootstrap pareado)"),
                               ("metricas_por_campo.csv", "Métricas por campo"),
                               ("exactitud_por_factor.csv", "Dónde funciona bien y dónde no"),
                               ("metricas_prueba_externa.csv", "Prueba externa")):
            archivo = next(iter(sorted(evaluacion.rglob(nombre))), None)
            if archivo:
                tabla = pd.read_csv(archivo, encoding="utf-8-sig").replace({True: "sí", False: "no"})
                partes += [f"### {titulo}", "", tabla_markdown(tabla.drop(columns=["nota"], errors="ignore"), 1), ""]

    figuras = sorted((resultados / "figures").rglob("*.png"))
    partes += ["## Figuras", ""]
    enlaces = [f"- [`{f.relative_to(resultados)}`](../{f.relative_to(resultados).as_posix()})" for f in figuras]
    partes += enlaces or ["Ninguna."]
    destino = resultados / "reports" / "reporte_resultados.md"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text("\n".join(partes) + "\n", encoding="utf-8")
    return destino


def main(argumentos: list[str] | None = None) -> int:
    """Punto de entrada de línea de comandos."""
    parser = argparse.ArgumentParser(description="Evaluación del lector y organización de resultados.")
    parser.add_argument("--config", default=None, help="Otro config.yaml (opcional)")
    sub = parser.add_subparsers(dest="comando", required=True)
    test = sub.add_parser("test", help="Evaluar en el test oficial de SROIE y WildReceipt")
    test.add_argument("--datos", default=None, help="Carpeta con los datasets (por defecto rutas.datos_crudos)")
    test.add_argument("--por-base", type=int, default=None, help="Documentos por dataset")
    test.add_argument("--semilla", type=int, default=None)
    test.add_argument("--salida", default=None, help="Carpeta nueva (por defecto outputs/evaluacion_<fecha>)")
    externo = sub.add_parser("externo", help="Evaluar la muestra propia anotada")
    externo.add_argument("--anotaciones", required=True, help="ZIP o carpeta con anotaciones.jsonl e imagenes/")
    externo.add_argument("--salida", default=None)
    importar = sub.add_parser("importar", help="Copiar a results/ los ZIP de los notebooks")
    importar.add_argument("zips", nargs="+")
    importar.add_argument("--tipo", choices=TIPOS_RESULTADO, default=None)
    sub.add_parser("reporte", help="Regenerar results/reports/reporte_resultados.md")
    args = parser.parse_args(argumentos)
    sello = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    try:
        config = cargar_configuracion(args.config)
        configurar_registro(config)
        if args.comando == "test":
            r = evaluar_test(config, args.datos or config["rutas"]["datos_crudos"],
                             args.salida or f"{config['rutas']['salidas']}/evaluacion_{sello}", args.por_base,
                             args.semilla)
            print(json.dumps(r["cumplimiento"], ensure_ascii=False, indent=2))
        elif args.comando == "externo":
            salida = args.salida or f"{config['rutas']['salidas']}/externo_{sello}"
            r = evaluar_externo(config, args.anotaciones, salida)
            print(json.dumps(r["cumplimiento"], ensure_ascii=False, indent=2))
        elif args.comando == "importar":
            for zip_path in args.zips:
                copiados = importar_resultados(zip_path, args.tipo, config["rutas"]["resultados"])
                print(f"{zip_path}: {len(copiados)} archivos copiados a results/")
            print("Reporte actualizado:", generar_reporte(config["rutas"]["resultados"]))
        else:
            print("Reporte:", generar_reporte(config["rutas"]["resultados"]))
    except ErrorLector as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
