# Datos del proyecto

Descripción de los datos que usa el lector de facturas (OCR con Tesseract + extracción de seis campos). Este documento responde a la sección *Dataset* del README principal y es el punto de partida para reproducir la preparación de datos.

## Contenido de la carpeta

```text
data/
├── README.md                         # Este documento
├── raw/                              # Datos originales (se descargan; NO se versionan)
│   └── README.md                     #   Cómo obtenerlos y qué estructura esperan los scripts
└── processed/                        # Datos procesados
    ├── README.md                     #   Esquema de lo que genera el pipeline y qué se versiona
    └── documentos_revisados.csv      #   Inventario (id + SHA-256) de los 1.461 documentos ya revisados
```

Las imágenes de los datasets **no están en el repositorio**: se descargan con `scripts/download_data.py` y `.gitignore` las excluye. Lo que sí se versiona es la documentación y el inventario de hashes, que no contiene fotografías ni anotaciones.

## Resumen de los datasets

| Dataset | Rol en el proyecto | Documentos | Campos del proyecto con referencia |
|---|---|---|---|
| **SROIE** (ICDAR 2019) | Desarrollo y evaluación | 626 train + 347 test (cifras oficiales) | `date`, `total` |
| **WildReceipt** | Desarrollo y evaluación | 1 268 train + 472 test | `date`, `subtotal`, `tax`, `total` |
| **Ejemplos sintéticos** (`samples/`) | Comprobar la instalación | 1 imagen + 1 PDF | los seis campos (no es evidencia de precisión) |

Los seis campos que el sistema extrae son: `tax_id` (identificador fiscal del emisor), `date`, `document_number`, `subtotal`, `tax` y `total`. **Ninguna de las dos bases públicas anota `tax_id` ni `document_number`**, por lo que su precisión solo puede acreditarse con la muestra propia (ver [`docs/anotacion_propia.md`](../docs/anotacion_propia.md)). Los campos sin anotación quedan fuera de las métricas; no se cuentan como acierto ni como error.

## 1. SROIE

- **Qué es:** recibos escaneados del reto *ICDAR 2019 Competition on Scanned Receipt OCR and Information Extraction*. El paper de TRIE reporta 626 recibos de entrenamiento y 347 de prueba, con cuatro campos anotados: empresa, fecha, dirección y total.
- **Fuente que usa el proyecto:** distribución en Kaggle, [`urbikn/sroie-datasetv2`](https://www.kaggle.com/datasets/urbikn/sroie-datasetv2). Recurso de apoyo: [`jsdnrs/ICDAR2019-SROIE`](https://huggingface.co/datasets/jsdnrs/ICDAR2019-SROIE) en Hugging Face.
- **Formato esperado por el adaptador** (`src/lector_facturas/datasets.py`): `train|test/img` (imágenes `.jpg/.jpeg/.png`), `train|test/box` (un `.txt` por imagen: ocho coordenadas y el texto de cada región) y `train|test/entities` (JSON con `company`, `date`, `address`, `total`).
- **Campos usados:** `date` y `total`. El nombre del comercio (`company`) **no** se trata como identificador fiscal.
- **Cantidad real en esta distribución:** el adaptador no asume un número fijo; el conteo real queda registrado en `manifest_metadata.json` al preparar los datos (ver [`processed/README.md`](processed/README.md)). Puede diferir de las cifras oficiales.

## 2. WildReceipt

- **Qué es:** recibos fotografiados "en la naturaleza" (distintas perspectivas, pliegues, iluminación). Según el paper original (Sun et al., 2021) son 1 740 imágenes con 68 975 cajas de texto y 25 categorías de información clave (12 claves, 12 valores y *otros*); 1 268 imágenes de entrenamiento y 472 de prueba, con plantillas de prueba no vistas en entrenamiento. Las imágenes se recolectaron con buscadores de imágenes y las anotaron seis expertos.
- **Fuente que usa el proyecto:** archivo `wildreceipt.tar` distribuido por MMOCR: <https://download.openmmlab.com/mmocr/data/wildreceipt.tar>.
- **Formato esperado por el adaptador:** `class_list.txt` (código → etiqueta), `train.txt` y `test.txt` (una línea JSON por imagen con `file_name`, `width`, `height` y `annotations` con `box`, `text`, `label`) e `image_files/`.
- **Etiquetas usadas:** `Date_value` → `date`, `Subtotal_value` → `subtotal`, `Tax_value` → `tax`, `Total_value` → `total`. Si un documento trae varios valores distintos para un campo, se marca `ambiguous` y **no** se suman impuestos ni se elige un total arbitrario.

## 3. Prueba externa con facturas reales (planificada, no realizada)

En la Semana 1 se planificó una muestra propia de 30–50 facturas ecuatorianas (RIDE) de al menos tres emisores, separada de los documentos que sirven para ajustar reglas, porque es la única forma de evaluar `tax_id` y `document_number`. **No se reunió** (motivos en la [planificación](../docs/planificacion.md#53-desviaciones-y-por-qué-ocurrieron)): ninguna cifra del proyecto la incluye. Queda definido el protocolo para hacerla: Cada documento se revisa a mano por dos integrantes y cada campo recibe un estado: `annotated`, `absent`, `unannotated` o `ambiguous` (columnas y criterios en [`docs/anotacion_propia.md`](../docs/anotacion_propia.md)). Solo se incluyen comprobantes **impresos o digitales**: los que tienen campos escritos a mano quedan fuera del alcance.

**Evaluación:** el notebook [`05_evaluacion.ipynb`](../notebooks/05_evaluacion.ipynb) y `python -m src.evaluate externo` ya la evalúan como **prueba externa** a partir de un ZIP con `anotaciones.jsonl` e `imagenes/` (`experiments.load_external_test`), separada de las métricas de SROIE y WildReceipt. La evidencia de generalización del proyecto viene de documentos de SROIE y WildReceipt que nunca se revisaron (sección 6). Los documentos reales **no se publican** sin anonimización y autorización de sus emisores.

## 4. Modelos preentrenados (no son datasets)

El OCR usa pesos oficiales de Tesseract, descargados de revisiones fijas en la primera lectura (`frozen_runtime.bind_models`) y verificados por hash; no se entrena nada. Los pesos no se versionan (quedan en `models/fast/` y `models/best/`, ignoradas por Git).

| Pesos | Revisión | SHA-256 de `eng.traineddata` |
|---|---|---|
| `eng` y `spa` de [`tessdata_fast`](https://github.com/tesseract-ocr/tessdata_fast/tree/87416418657359cb625c412a48b6e1d6d41c29bd) | `87416418` | `7d4322bd2a7749724879683fc3912cb542f19906c83bcc1a52132556427170b2` |
| `eng` de [`tessdata_best`](https://github.com/tesseract-ocr/tessdata_best/tree/e12c65a915945e4c28e237a9b52bc4a8f39a0cec) | `e12c65a9` | `8280aed0782fe27257a68ea10fe7ef324ca0f8d85bd2fd145d1c2b560bcb66ba` |

Tesseract y sus repositorios de pesos se distribuyen con licencia Apache 2.0.

## 5. Licencias y condiciones de uso

| Recurso | Situación |
|---|---|
| SROIE | No se verificó una licencia de redistribución. Revisar las condiciones del reto ICDAR 2019 y de la página de Kaggle antes de compartir imágenes. |
| WildReceipt | La documentación de MMOCR no declara licencia para los datos, y las imágenes provienen de búsquedas en internet. La licencia del software MMOCR no implica una licencia sobre las imágenes. |
| Facturas reales (prueba externa futura) | Datos privados; requieren anonimización y autorización antes de cualquier publicación. |
| Código del equipo | MIT ([`LICENSE`](../LICENSE)). Cubre solo el código y la documentación del equipo, no los datasets. |

Por esta razón el repositorio **no redistribuye** imágenes, anotaciones ni textos de los datasets: cada persona los descarga de su fuente original. El script `download_data.py` guarda en `<dataset>_download.json` la URL, el SHA-256, el tamaño en bytes y la fecha de descarga, y aclara que el hash registra la descarga pero no implica permiso de redistribución.

## 6. Particiones y control de fuga de datos

La preparación (`prepare` en `datasets.py`) construye un manifiesto y asigna cada documento a una partición:

| `split` | Significado |
|---|---|
| `test` | Test oficial de cada dataset. El EDA no explora sus etiquetas y la optimización no lo usa; se reserva para la evaluación (ver la nota sobre documentos ya revisados). |
| `validation` | ~20 % de los documentos de entrenamiento oficial (`validation_fraction = 0.2`), elegido de forma determinista por hash de imagen con `seed = 42`. |
| `train` | Resto del entrenamiento oficial. |
| `quarantine` | Imágenes duplicadas (mismo SHA-256) o presentes también en el test oficial. Se excluyen de la evaluación. |

**Documentos ya revisados.** [`processed/documentos_revisados.csv`](processed/documentos_revisados.csv) registra por id y hash los **1.461** documentos que se miraron durante el desarrollo: 650 de entrenamiento, **809 del test oficial** (337 de SROIE y 472 de WildReceipt) y 2 externos. En la entrega V7 eran 350, todos de entrenamiento; para mejorar los campos débiles se revisaron después grupos aleatorios del test.

Consecuencia: el test oficial **ya no es inédito**. El notebook 05 sigue tomando 50 documentos por base del test (sin duplicados con desarrollo) para medir y comparar versiones y declara cuántos ya se habían revisado. La evidencia de generalización la da el notebook [`06_validacion_escenarios.ipynb`](../notebooks/06_validacion_escenarios.ipynb): 50 documentos por base de la partición `train` que **no figuran en este registro** (nadie miró sus errores al ajustar las reglas) ni comparten imagen con otras particiones. La optimización (notebook 04) usa solo `validation`, separada por hash en optimización y control y sin imágenes del test.

## 7. Limitaciones conocidas de los datos

- **Sin agrupación por emisor:** la partición train/validation se hace por hash de imagen, no por comercio; plantillas del mismo emisor pueden aparecer en ambas y favorecer la validación. Por la misma razón, los documentos nunca revisados del notebook 06 pueden ser de comercios cuyos recibos sí se revisaron: son imágenes nuevas, no necesariamente formatos nuevos.
- **Duplicados:** solo se detectan por SHA-256; imágenes casi idénticas pasan desapercibidas.
- **Cobertura de anotación ≠ exactitud:** que un campo esté anotado no dice nada sobre si el extractor lo lee bien; `coverage.csv` mide cobertura de etiquetas.
- **Sesgo de origen:** ninguna de las dos bases públicas se construyó con comprobantes ecuatorianos y el OCR se ejecuta con el modelo inglés (`eng`). El proyecto apunta también a comprobantes ecuatorianos (RUC, IVA), que ninguna base evaluada representa porque la muestra propia no se reunió. Los resultados en las bases públicas no garantizan el mismo desempeño en esos documentos.
- **Solo texto impreso:** ninguna de las bases contiene comprobantes llenados a mano; el sistema no se evaluó (ni se recomienda) con campos manuscritos.
- **Datos personales:** los recibos pueden mostrar nombres de comercios, direcciones, teléfonos o fragmentos de tarjetas. Por eso no se publican imágenes ni textos transcritos.

## 8. Cómo obtener y preparar los datos

```bash
# WildReceipt (descarga pública directa)
python scripts/download_data.py wildreceipt --out data/raw

# SROIE (Kaggle; si la descarga automática no devuelve un ZIP, bajarlo manualmente con tu cuenta)
python scripts/download_data.py sroie --out data/raw
```

Los notebooks [`01`](../notebooks/01_exploracion.ipynb)–[`05`](../notebooks/05_evaluacion.ipynb) descargan los datos si faltan, preparan el manifiesto y hacen el EDA, el preprocesamiento, el modelado, la optimización y la evaluación. Detalle de las rutas en [`raw/README.md`](raw/README.md) y del esquema de salida en [`processed/README.md`](processed/README.md).

## Referencias

- *ICDAR 2019 Competition on Scanned Receipt OCR and Information Extraction* (SROIE).
- Sun et al., *Spatial Dual-Modality Graph Reasoning for Key Information Extraction*, 2021. <https://arxiv.org/abs/2103.14470>
- Zhang et al., *TRIE: End-to-End Text Reading and Information Extraction for Document Understanding*, 2020. <https://arxiv.org/abs/2005.13118>
- MMOCR, sección *Key Information Extraction*: <https://mmocr.readthedocs.io/en/0.x/datasets/kie.html>
