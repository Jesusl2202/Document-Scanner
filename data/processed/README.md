# data/processed — datos procesados

Salidas derivadas de `data/raw/`. Para no filtrar contenido de terceros, **solo se versiona lo de esta lista**; el resto de esta carpeta queda excluido por `.gitignore`.

| Archivo | Versionado | Contenido |
|---|---|---|
| `README.md` | sí | Este documento |
| `documentos_revisados.csv` | sí | Inventario de los 350 documentos ya usados en desarrollo y selección: `dataset`, `source_split`, `document_id`, `sha256` |
| `manifest.jsonl`, `manifest_metadata.json`, EDA | no | Se generan al ejecutar el pipeline (ver abajo) |

## documentos_revisados.csv

Contiene 350 documentos del entrenamiento oficial: 179 de SROIE y 171 de WildReceipt. Son los documentos cuya imagen ya se observó mientras se desarrollaba y seleccionaba el extractor, así que **se excluyen de la muestra de test final** (por id y por hash). No contiene imágenes ni anotaciones, solo identificadores y hashes.

Se genera a partir de [`configs/documentos_revisados.json`](../../configs/documentos_revisados.json):

```bash
python scripts/exportar_documentos_revisados.py
```

## Lo que genera el pipeline

El notebook [`01_lector_definitivo.ipynb`](../../notebooks/01_lector_definitivo.ipynb) llama a `prepare()` y `run_eda()` y escribe sus salidas en `outputs/experimentos/<sesión>/`. Si quieres conservarlas junto a los datos, cópialas a esta carpeta; no se subirán a Git.

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
