# Resultados de desarrollo

Registro de las mediciones que se usaron para **elegir** el modelo. No son la evaluación final: esos documentos se miraron al decidir cambios. La evaluación final se genera con [`notebooks/05_evaluacion.ipynb`](../../notebooks/05_evaluacion.ipynb) y sus tablas se guardan en [`results/metrics/`](../metrics/).

## Modelo actual: resumen contable

Comparación sobre el **mismo OCR archivado** de tres grupos aleatorios del test oficial (con documentos ya revisados permitidos). "Antes" es el lector actual sin contabilidad observada ni rescate por confianza; "Después" es el modelo final. Es una reextracción, no una inferencia nueva ni una validación independiente, y los grupos pueden solaparse: **no se deben sumar sus soportes**.

| Grupo (ejecución) | Antes | Después | Cambios |
|---|---:|---:|---|
| `tesseract_20261022T002345_092851Z` (más reciente) | 183/241 (75,93 %) | 184/241 (76,35 %) | +1, −0 |
| `tesseract_20261021T025614_902596Z` | 188/252 (74,60 %) | 189/252 (75,00 %) | +1, −0 |
| `tesseract_20261021T001258_077632Z` | 347/450 (77,11 %) | 349/450 (77,56 %) | +2, −0 |

- La mejora directa del resumen contable es pequeña y **no demuestra la meta interna del 80 %**. En el grupo más reciente solo mejora el subtotal de WildReceipt (de 21 a 22 de 31, 70,97 %); fecha, impuesto y total no cambian.
- Ningún grupo empeora (0 campos perdidos).
- Factura externa 1 (subtotal 355,20, descuento 17,76, total 412,03): el impuesto pasa de 74,50 a 74,59 con el resumen contable; la fecha 7/12/2014 se conserva. Factura externa 2: se mantienen subtotal 125,00, impuesto 4,75 y total 114,75, con envío 10,00 y descuento 25,00. Son dos comprobantes externos revisados durante el desarrollo: sin referencias humanas verificadas no se les asigna exactitud y no constituyen la muestra propia planificada ([`data/README.md`](../../data/README.md#3-prueba-externa-con-facturas-reales-planificada-no-realizada)).
- Se probaron variantes de ponderación por confianza que cambiaban valores ya establecidos y causaban regresiones; **no se entregan activadas**. La variante final solo rellena campos vacíos con evidencia corroborada en dos vistas.
- 120 pruebas automatizadas del motor aprobadas. La prueba de integración del optimizador con OCR simulado cubre la separación de validación, la exportación y el rechazo de una configuración sin mejora.
- No hay una medición nueva de velocidad desde cero: la caché de OCR se reutiliza durante la búsqueda y el tiempo real depende de Colab.

## Historia de versiones

| Versión | Muestra | Resultado | Nota |
|---|---|---|---|
| Línea base V1 (Semana 2) | 40 documentos de validación | 36/103 (35,0 %) | 56 de los 67 errores fueron omisiones. |
| V5.1 | 60 documentos de validación nueva | 79/153 (51,63 %) | |
| V6 (consenso de Tesseract) | 60 documentos de validación nueva | 96/153 (62,75 %) | SROIE: fecha 80,0 %, total 63,3 %. WildReceipt: fecha 53,8 %, total 73,9 %, subtotal 47,8 %, impuesto 52,4 %. |
| V7 (cinco lecturas) | Validación de la alternativa, 60 documentos | 111/153 (72,55 %) | Usada para seleccionar la versión. |
| V7 (cinco lecturas) | Segunda muestra, reproducción sobre OCR guardado | 102/149 (68,46 %) | |
| V7 (cinco lecturas) | Ambas muestras, sin imágenes repetidas | 213/302 (70,53 %) | Retrospectivo, no independiente. |
| Resumen contable | Tres grupos del test oficial con reutilización | 75,00–77,56 % | Tabla de arriba. |

Las cifras globales solo cubren campos anotados: fecha y total en SROIE; fecha, subtotal, impuesto y total en WildReceipt. Identificador fiscal y número de comprobante no tienen soporte en estas bases.

## Relación con la evaluación final

La optimización de hiperparámetros se hizo en [`04_optimizacion.ipynb`](../../notebooks/04_optimizacion.ipynb) solo con la partición de validación y mantuvo la configuración actual. La evaluación final, en [`05_evaluacion.ipynb`](../../notebooks/05_evaluacion.ipynb) con la configuración fijada antes de leer el test, dio **81,1 %** por campo en 100 documentos ([reporte de resultados](reporte_resultados.md)). Como casi todo el test oficial se revisó durante el desarrollo, esa cifra tampoco es inédita.
