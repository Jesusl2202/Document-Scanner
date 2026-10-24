# src/ — código fuente

El código está en dos capas:

```text
src/
├── __init__.py          # Interfaz pública del proyecto (versión, uso mínimo)
├── data_processing.py   # Validación de entrada, PDF → imágenes, preprocesamiento, normalización, datasets
├── model.py             # Clase LectorFacturas: carga del modelo, lectura, confianza por campo, exportación
├── train.py             # Optimización de la configuración en validación (el modelo no entrena pesos)
├── evaluate.py          # Evaluación en test y prueba externa, importación de resultados y reporte
├── validation.py        # Validación en contextos simulados: datos nuevos, escenarios críticos, costo del error
├── line_classifier.py   # Técnica de comparación aprendida: red MLP que clasifica las líneas del OCR
├── utils.py             # Configuración (config.yaml + .env), rutas relativas, registro, errores
└── lector_facturas/     # Motor: OCR con Tesseract, extractor de reglas y consenso, métricas
```

- **Interfaz pública (`src/*.py`)**: lo que usan la app, los notebooks, los scripts y las pruebas. Sigue PEP 8 (revisado con `flake8`, ver `.flake8`), tiene docstrings, valida entradas, maneja errores con mensajes para el usuario y registra eventos con `logging`.
- **Motor (`src/lector_facturas/`)**: el modelo «resumen contable» tal como se desarrolló y evaluó. La interfaz lo envuelve sin cambiar su comportamiento, para que los resultados de los notebooks sigan siendo reproducibles.

## Uso desde Python

```python
from src.model import LectorFacturas

lector = LectorFacturas()                       # lee configs/config.yaml
resultado = lector.leer("samples/synthetic_receipt.pdf", carpeta_salida="outputs/demo")
print(resultado.estado)                         # ok / parcial / error
for fila in resultado.tabla():                  # campo, valor, confianza y alertas
    print(fila)
print(lector.acerca_de())                       # información para la sección «Acerca de»
```

## Uso desde la terminal

```bash
python -m src.model factura.pdf --salida outputs/factura          # leer un documento
python -m src.evaluate test --datos data/raw --por-base 50          # evaluar en el test oficial
python -m src.evaluate externo --anotaciones muestra_propia.zip     # prueba externa anotada
python -m src.evaluate importar optimizacion_resultados.zip evaluacion_<fecha>.zip
python -m src.evaluate reporte                                       # regenerar results/reports/
python -m src.train --datos data/raw --salida outputs/optimizacion  # optimizar la configuración
```

## Configuración

| Archivo | Qué contiene |
|---|---|
| [`configs/config.yaml`](../configs/config.yaml) | Rutas (relativas a la raíz), límites de entrada, metas, semillas, umbrales de confianza y registro. |
| [`configs/definitivo.json`](../configs/definitivo.json) | El modelo: vistas OCR, etapas activas, normalización y validaciones. |
| `.env` (opcional, copia de [`.env.example`](../.env.example)) | Cambios locales sin editar el YAML: `LECTOR_CONFIG`, `LECTOR_NIVEL_LOG`, `LECTOR_PESOS`, `LECTOR_SALIDAS`. |

## Correspondencia con el motor

| Función pública | Usa |
|---|---|
| `data_processing.validar_archivo`, `cargar_paginas` | `lector_facturas.ocr.render_pdf` |
| `data_processing.preprocesar_imagen` | `lector_facturas.preprocessing.prepare_image` |
| `data_processing.normalizar_*` | `lector_facturas.common.normalize` |
| `data_processing.preparar_datasets` | `lector_facturas.datasets.prepare` |
| `model.LectorFacturas` | `frozen_runtime.bind_models`, `cli.predict`, `consensus.extract` |
| `train.optimizar` | `experiments.optimize_consensus_cached` |
| `evaluate.evaluar_*` | `experiments.run`, `random_known_sample`, `load_external_test`, `evaluation.evaluate` |
| `validation.*` (notebook 06) | `experiments.run` y las salidas de `evaluation.evaluate`; `model.calcular_confianza` |
| `line_classifier.*` (notebook 03, sección 9) | `geometry.grouped`, `candidate_rules.AMOUNT`/`DATE`, `common.normalize`; scikit-learn |

## Nivel de confianza

`model.calcular_confianza` asigna a cada campo `alta`, `media`, `baja` o `sin_valor` según la fracción de vistas OCR que leyeron el valor elegido (umbrales en `config.yaml`). Si el campo tiene una alerta, baja un escalón. **No es una probabilidad calibrada**: indica cuántas lecturas coinciden y sirve para priorizar la revisión.

## Validación y comparación (Workshop S5 y Semana 3)

- [`validation.py`](validation.py): muestra de documentos nunca revisados (`muestra_no_revisada`), escenarios críticos de imagen (`ESCENARIOS`, `perturbar_imagen`), tipo de error y confianza por campo (`detalle_campos`), exactitud por documento, calibración de la confianza y tiempo de revisión estimado. Lo usa [`06_validacion_escenarios.ipynb`](../notebooks/06_validacion_escenarios.ipynb).
- [`line_classifier.py`](line_classifier.py): red MLP por campo sobre las líneas del OCR, con etiquetas débiles, entrenamiento época por época con historial (`entrenar`, `Historial`), *early stopping* con restauración y diagnóstico de overfitting con umbrales explícitos (`cuantificar`, `diagnosticar`, `sensibilidad_umbrales`). Lo usa la sección 9 de [`03_modelado.ipynb`](../notebooks/03_modelado.ipynb).
