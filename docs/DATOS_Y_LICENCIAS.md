# Datos, fuentes y licencias

SROIE y WildReceipt son las dos bases de evaluación. SROIE aporta fecha/total; WildReceipt fecha/subtotal/impuesto/total. Se evalúan solo referencias anotadas utilizables. Identificador fiscal y número de comprobante necesitan una muestra propia; ver `anotacion_propia.md`.

Descargas empleadas por el adaptador:
- SROIE: https://www.kaggle.com/datasets/urbikn/sroie-datasetv2
- WildReceipt: https://download.openmmlab.com/mmocr/data/wildreceipt.tar
- Tesseract: https://github.com/tesseract-ocr/tesseract
- Pesos ingleses fijados: https://github.com/tesseract-ocr/tessdata_fast/tree/87416418657359cb625c412a48b6e1d6d41c29bd

El script registra procedencia y hashes. Las descargas pueden requerir acceso manual si cambia la fuente. Revisar las condiciones de cada distribución antes de redistribuir imágenes. La licencia del software MMOCR no implica una licencia para todas las imágenes de WildReceipt. No se publica una licencia nueva para el código del equipo: no había una licencia de código acordada en el repositorio anterior.

Los archivos de `samples/` son ejemplos sintéticos del proyecto, no evidencia de precisión en recibos reales. Datasets, pesos, documentos privados, cachés y resultados locales quedan excluidos de Git. Las etiquetas de ejemplo y los hashes de documentos ya revisados no contienen fotografías.

El test oficial se mantiene separado por ID y hash. El notebook congela el lector antes de reservar su muestra final; si se ajustan reglas mirando el test, esa muestra deja de ser independiente.
