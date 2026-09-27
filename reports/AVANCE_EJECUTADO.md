# Avance ejecutado — 27 de septiembre de 2026

## Qué se comprobó

Se instaló el paquete Python en modo editable, se ejecutaron 14 pruebas automatizadas y se probó extracción real con Tesseract 5.3.4 sobre ambas bases principales. También se comprobaron imagen y PDF con un comprobante sintético; esos ejemplos no están en las métricas siguientes.

La API Google Document AI **no se ejecutó**: falta configurar una cuenta y procesador propios. Su adaptador y la transformación de entidades están implementados, pero esto no demuestra su desempeño o compatibilidad con una cuenta real. No se entrenó Random Forest ni se cambió la comparación prevista en Semana 1.

## Datos realmente descargados y preparados

| Fuente | Train original | Test original | Total descargado |
|---|---:|---:|---:|
| SROIE v2, distribución Kaggle | 626 | 347 | 973 |
| WildReceipt, distribución MMOCR | 1.267 | 472 | 1.739 |
| Total | 1.893 | 819 | 2.712 |

Estas son cantidades observadas de las distribuciones, no una corrección del tamaño anunciado en los artículos. Las fuentes y SHA256 están en `sroie_source.json` y `wildreceipt_source.json`. Se descartó un espejo alternativo incompleto de SROIE; no aportó documentos a este experimento.

Tras controlar duplicados exactos quedaron **1.517 train, 364 validation, 816 test y 15 en cuarentena**. La exploración de desarrollo comprende 1.881 documentos: 614 SROIE y 1.267 WildReceipt. Los 15 registros duplicados están en cuarentena; las incidencias pueden superponerse (7 también coinciden con imágenes del test original), por lo que no se suman como registros distintos.

Otras incidencias: 16 discordancias de dimensiones anotadas frente a imagen, 2 incidencias de cajas inválidas, 1 línea de caja inválida y 1 lectura con fallback de codificación CP1252. Se registraron, no se corrigieron las coordenadas automáticamente. Ver `eda/incidents.csv`.

## Hallazgos EDA de desarrollo

- SROIE: fecha disponible en 614/614 documentos; total en 613/614.
- WildReceipt: referencia única utilizable de fecha en 1.025/1.267; subtotal en 876/1.267; impuesto en 764/1.267; total en 1.057/1.267.
- Ninguna de las dos fuentes permite evaluar directamente identificador fiscal ni número de comprobante con sus etiquetas estándar.
- Referencias múltiples de un campo se marcan ambiguas. No se agregan impuestos o totales sin una regla de anotación acordada.

## Primera evaluación real del baseline

Se seleccionaron de forma determinista **20 documentos de validación por dataset**, 40 en total. La semilla es 42; no se escogieron a partir de resultados favorables. El test oficial no se utilizó para evaluación o ajuste. Se corrigió una lectura parcial de porcentajes detectada por prueba unitaria y se repitió la corrida completa sobre los mismos 40 documentos. No se usó test para esta corrección. Los resultados siguientes corresponden a la versión entregada.

| Dataset | Campo | Soporte | Exactitud normalizada | F1 |
|---|---|---:|---:|---:|
| SROIE | Fecha | 20 | 80,0% | 0,889 |
| SROIE | Total | 20 | 20,0% | 0,320 |
| WildReceipt | Fecha | 16 | 43,8% | 0,583 |
| WildReceipt | Subtotal | 15 | 20,0% | 0,300 |
| WildReceipt | Impuesto | 14 | 21,4% | 0,273 |
| WildReceipt | Total | 18 | 16,7% | 0,261 |

**40/40 documentos procesados sin error de ejecución; 36/103 valores anotados extraídos correctamente (35,0%).** No se ha alcanzado la meta de exactitud ≥70%. Un JSON generado correctamente no implica que sus valores sean correctos. Esta medición es una línea base inicial que justifica mejorar el extractor y realizar la comparación prevista.

Las diferencias de soporte se deben a disponibilidad/ambigüedad de etiquetas, no a eliminar fallos de extracción. El promedio global tiene distinta composición por fuente; no debe compararse directamente con F1 de publicaciones.

Mediana extremo a extremo sin caché: **0,698 s/documento**; p95: **1,345 s/documento**, en este entorno y estas imágenes. No es una garantía de tiempo en Colab/Windows ni de facturas mayores. CER diagnóstico agregado: **0,307**, sensible al orden de lectura y no equivalente al benchmark oficial. Configuración y entorno acompañan al reporte.

## Lectura técnica y próximos pasos

La cobertura de extracción es baja: hay muchas omisiones. La abstención ante varias fechas/totales y las reglas de cercanía simples limitan el recall. No se atribuyen todos los errores al OCR sin revisar las evidencias individuales.

1. Revisar `baseline_v1/errors.csv` junto con `predictions.jsonl` generado al reproducir la corrida. Separar error de transcripción, etiqueta no reconocida, selección de candidato y normalización.
2. Mejorar reglas con train/desarrollo; conservar la versión baseline y sus resultados. Incorporar proximidad de cajas más robusta, formatos adicionales y evaluación de orientación antes de adoptar un preprocesamiento nuevo.
3. Ejecutar Document AI sobre exactamente los mismos IDs y comparar métricas y fallos. No cambiar automáticamente a Random Forest.
4. Ampliar la evaluación de desarrollo; reservar la muestra propia final y establecer anotación de los campos faltantes.
5. Mantener meta de ≥70% como objetivo pendiente, sin reemplazarla por el resultado observado.

## Cómo reproducir

Descargar las dos distribuciones mediante `scripts/download_data.py`, indicar sus raíces en `prepare`, ejecutar `eda` y:

```bash
python -m lector_facturas run --engine tesseract --split validation --limit-per-dataset 20 --cache artifacts/nueva_cache --out outputs/reproduccion_v1
```

Los archivos `selected_documents.csv` y los hashes permiten verificar la selección. Si cambia la distribución descargada, el entorno, el modelo de idioma, la configuración o el código, los resultados pueden cambiar. Los reportes adjuntos son una ejecución de referencia; el notebook se entrega sin salidas para que registre las de tu equipo.

Los artefactos completos con texto OCR y cajas se generan al ejecutar el proyecto. El ZIP conserva resúmenes y tablas, sin redistribuir imágenes de terceros.
