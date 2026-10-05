# Modelo definitivo: alternativa V7 con cinco lecturas

Se conserva el extractor de la alternativa aportada en `06_lector_V7_consenso_(1).ipynb` y su configuración `v7_cinco`. No es el mismo extractor que el notebook anterior llamado V7 evidencia best. No se modificaron sus reglas, votos ni normalización al consolidarlo.

| Muestra | Documentos | Aciertos | Campos | Exactitud |
|---|---:|---:|---:|---:|
| Validación de la alternativa | 60 | 111 | 153 | 72,55 % |
| Segunda muestra: reproducción local sobre su OCR guardado | 60 | 102 | 149 | 68,46 % |
| Ambas muestras, sin imágenes repetidas | 120 | 213 | 302 | 70,53 % |

La segunda medición ejecutó el extractor alternativo sobre las cinco lecturas reales guardadas en el ZIP V7 evidencia best. No volvió a ejecutar Tesseract ni midió nueva latencia. Se comprobó intersección vacía de hashes entre las muestras. Los datos se han usado para seleccionar la implementación: este resultado combinado es retrospectivo, no una evaluación final independiente ni garantía de superar 70 % en nuevos documentos. La primera muestra ya había sido observada en la conversación antes de recibir esta alternativa; no se puede asegurar que su desarrollo haya sido ciego a ella.

En desarrollo, la alternativa reportó 120/151=79,47 %. En la segunda muestra, el extractor V7 evidencia best reportó 95/149=63,76 %; la alternativa obtuvo 102/149 con el mismo OCR. Las tres lecturas best quedaron vacías en los 60 documentos de desarrollo: esa ejecución no permite concluir que esos pesos tengan peor capacidad OCR. El modelo definitivo utiliza los pesos eng comprobados por hash que sí produjeron las lecturas utilizadas.

La inferencia emplea original/PSM6, ampliada/PSM6, Otsu/PSM6, ampliada/PSM3 y ampliada/PSM11. Tesseract preentrenado, CPU y sin entrenamiento. El archivo de pesos se descarga de una revisión oficial fijada; SHA-256: 7d4322bd2a7749724879683fc3912cb542f19906c83bcc1a52132556427170b2.

El código puede asignar un total a partir de un subtotal cuando faltan total e impuesto. Se conserva para reproducir los resultados y se marca `total:from_subtotal`; requiere revisión, porque la ausencia de impuesto detectado no demuestra que no exista. Las coincidencias aritméticas y correcciones de caracteres también son heurísticas. No se garantiza lectura correcta por procesar sin excepción.

La cifra global solo cubre campos anotados: fecha/total en SROIE; fecha/subtotal/impuesto/total en WildReceipt. Identificador fiscal y número de comprobante no tienen soporte suficiente en estas bases para acreditar su precisión.

El notebook final congela esta implementación antes de leer el test. Por defecto toma 50 documentos por base del test oficial, de forma determinista y excluyendo hashes vistos y coincidencias con train. Ejecutar una vez y reportar lo obtenido. Si se usan esos resultados para ajustar reglas, esa muestra deja de ser final independiente. No cambia de modelo para forzar la meta.
