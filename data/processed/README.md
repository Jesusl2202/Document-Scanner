# data/processed — datos procesados

Salidas derivadas de `data/raw/`. Para no filtrar contenido de terceros, **solo se versiona lo de esta lista**; el resto de esta carpeta queda excluido por `.gitignore`.

| Archivo | Versionado | Contenido |
|---|---|---|
| `README.md` | sí | Este documento |
| `documentos_revisados.csv` | sí | Inventario de los 1.461 documentos ya revisados durante el desarrollo: `dataset`, `source_split`, `document_id`, `sha256` |
| `manifest.jsonl`, `manifest_metadata.json`, EDA | no | Se generan al ejecutar el pipeline (ver abajo) |

## documentos_revisados.csv

Contiene los 1.461 documentos cuya imagen ya se observó mientras se desarrollaba y seleccionaba el extractor:

| Dataset | Partición de origen | Documentos |
|---|---|---:|
| SROIE | train | 329 |
| SROIE | test | 337 |
| WildReceipt | train | 321 |
| WildReceipt | test | 472 |
| Externos | development / printed_reviewed | 2 |

Sirve para declarar con honestidad qué evaluaciones no son inéditas (el notebook 05 informa cuántos documentos de su muestra ya estaban aquí) y para excluir esas imágenes de la prueba externa. No contiene imágenes ni anotaciones, solo identificadores y hashes; el documento externo `printed_reviewed` no tiene `document_id`.

Se genera a partir de [`configs/documentos_revisados.json`](../../configs/documentos_revisados.json):

```bash
python scripts/exportar_documentos_revisados.py
```

## Lo que genera el pipeline

Los notebooks de [`notebooks/`](../../notebooks/) llaman a `prepare()` (todos) y `run_eda()` ([`01_exploracion.ipynb`](../../notebooks/01_exploracion.ipynb)) y escriben sus salidas en `outputs/experimentos/notebooks/` (o en Drive con `USAR_DRIVE = True`). Si quieres conservarlas junto a los datos, cópialas a esta carpeta; no se subirán a Git.

### manifest.jsonl (una línea JSON por documento)

| Campo | Descripción |
|---|---|
| `id` | `<dataset>/<split_origen>/<documento>` |
| `dataset` | `sroie` o `wildreceipt` |
| `source_split` | `train` o `test`, según la fuente |
| `split` | Partición del proyecto: `train`, `validation`, `test` o `quarantine` |
| `image` | Ruta absoluta de la imagen en la máquina que preparó los datos |
| `sha256`, `width`, `height` | Hash y dimensiones de la imagen (`null` si no se pudo leer) |
| `gold` | Referencia por campo: `{status, value}` para `tax_id`, `date`, `document_number`, `subtotal`, `tax`, `total` |
| `regions` | Lista de `{box, text, label}` con las regiones de texto anotadas |
| `issues` | Incidencias detectadas, p. ej. `missing_entities`, `invalid_box`, `duplicate_image_hash`, `duplicate_in_official_test` |

`gold.status` toma uno de estos valores:

- `annotated`: hay un valor de referencia utilizable.
- `unannotated`: el dataset no anota ese campo para el documento (no equivale a ausencia).
- `ambiguous`: hay varios valores distintos; se guardan en `candidates` y el campo se excluye de las métricas.
- `absent`: ausencia confirmada (solo aplicable a la muestra propia).

`manifest_metadata.json` registra la semilla (`42`), `validation_fraction` (`0.2`), las rutas de origen, el total de documentos y una nota sobre el método de partición.

### EDA (`run_eda`)

| Archivo | Contenido |
|---|---|
| `documents.csv` | Inventario de desarrollo: id, dataset, split, dimensiones, número de regiones, legibilidad |
| `coverage.csv` | Por dataset y campo: documentos, anotados, no anotados, ambiguos y cobertura |
| `incidents.csv` | Una fila por incidencia (id, dataset, split, issue) |
| `summary.json`, `EDA.md`, `coverage.png` | Resumen, informe en texto y gráfico de cobertura |

El EDA se calcula solo sobre `train` y `validation`. Del test oficial únicamente se inventarían integridad y duplicados; no se exploran sus etiquetas.

## Reproducir

1. Descargar los datos: ver [`../raw/README.md`](../raw/README.md).
2. Ejecutar el notebook de principio a fin (Colab o local, con Tesseract instalado).
3. Para regenerar solo el inventario de hashes: `python scripts/exportar_documentos_revisados.py`.
