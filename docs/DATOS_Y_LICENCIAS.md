# Datos, procedencia y condiciones

## Fuentes

| Recurso | Fuente | Uso en este proyecto |
|---|---|---|
| SROIE original | https://rrc.cvc.uab.es/?ch=13 ; artículo https://arxiv.org/abs/2103.10213 | Benchmark de OCR y extracción; cuatro entidades originales. |
| SROIE v2, distribución de trabajo | https://www.kaggle.com/datasets/urbikn/sroie-datasetv2 | Estructura img/box/entities compatible con el adaptador. Se cuentan los archivos descargados; no se fuerza la cifra 1.000 del artículo. |
| WildReceipt | https://download.openmmlab.com/mmocr/data/wildreceipt.tar | Distribución enlazada por la documentación oficial de MMOCR. |
| Formato WildReceipt | https://mmocr.readthedocs.io/en/v1.0.0/_modules/mmocr/datasets/wildreceipt_dataset.html | Nombres de etiquetas y esquema de anotación. |
| DocILE | https://github.com/rossumai/docile | Referencia de evaluación/generalización; no incluido en la ejecución actual. |
| CORD | https://github.com/clovaai/cord | Complemento futuro; no incluido en la evaluación principal actual. |

La descarga de SROIE puede solicitar acceso a Kaggle dependiendo del entorno. No se incluyen credenciales ni se evita ninguna restricción. El script falla con un mensaje claro si la respuesta no es un ZIP válido. Se puede descargar manualmente desde la cuenta del usuario y conservar sus condiciones.

## Descargar desde terminal

Ejecutar desde la raíz del proyecto, después de revisar las condiciones de la fuente:

```bash
python scripts/download_data.py sroie
python scripts/download_data.py wildreceipt
```

La distribución SROIE puede incorporar la carpeta `SROIE2019`: indicar la carpeta que contiene `train` y `test`, por ejemplo:

```bash
python -m lector_facturas prepare --sroie data/raw/sroie_distribution/SROIE2019 --wildreceipt data/raw/wildreceipt
```

Se guardan URL, fecha de descarga, tamaño y SHA256. No se publica una licencia de terceros como propia ni se asume que una licencia del código de un repositorio autoriza todas sus imágenes.

## Qué contiene el ZIP

Código original para este avance, documentación, pruebas, notebook, resúmenes de ejecuciones y ejemplos **sintéticos** propios. No contiene el corpus original de SROIE/WildReceipt ni imágenes de comprobantes privados. Los reportes permiten reproducir el experimento a partir de IDs, fuentes y hashes.

Los ejemplos sintéticos llevan la palabra SYNTHETIC y no sustituyen los samples reales del dataset. Para el anexo de Semana 1, pueden conservarse localmente 5–10 ejemplos reales identificados por sus IDs, sujeto a las condiciones de la fuente; los documentos propios deben anonimizarse.

## Licencias del software

El paquete usa Tesseract y bibliotecas instalables por el usuario. Consultar sus licencias en sus fuentes oficiales; no se redistribuyen sus binarios. No se ha elegido una licencia de publicación para el código de los estudiantes: el equipo debe acordarla antes de publicarlo fuera del contexto académico. Las credenciales y los datos propios quedan fuera de Git por configuración.

## Referencias técnicas

[1] Tesseract OCR, “Command Line Usage,” tessdoc. [En línea]. Disponible: https://tesseract-ocr.github.io/tessdoc/Command-Line-Usage.html. [Consulta: 27-sep-2026].

[2] OpenMMLab, “WildReceiptDataset,” MMOCR 1.0.0. [En línea]. Disponible: https://mmocr.readthedocs.io/en/v1.0.0/_modules/mmocr/datasets/wildreceipt_dataset.html. [Consulta: 27-sep-2026].

[3] Google Cloud, “Process a document using a Specialized processor,” Document AI. [En línea]. Disponible: https://docs.cloud.google.com/document-ai/docs/samples/documentai-process-specialized-document. [Consulta: 27-sep-2026].

[4] Z. Huang et al., “ICDAR2019 Competition on Scanned Receipt OCR and Information Extraction,” 2019. [En línea]. Disponible: https://arxiv.org/abs/2103.10213.

[5] H. Sun et al., “Spatial Dual-Modality Graph Reasoning for Key Information Extraction,” 2021. [En línea]. Disponible: https://arxiv.org/abs/2103.14470.

Estos números son locales al repositorio: al incorporarlos al documento maestro, ajustar la numeración IEEE a su orden de aparición y a la bibliografía existente.
