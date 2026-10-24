# Reporte de resultados

Resumen de las métricas de `results/metrics/` (actualizado el 23/10/2026).

## Desarrollo del modelo

| version | muestra | aciertos | campos | exactitud_pct | independiente |
|---|---|---|---|---|---|
| Línea base V1 | 40 docs de validación | 36 | 103 | 34,95 | no |
| V5.1 | 60 docs de validación | 79 | 153 | 51,63 | no |
| V6 consenso | 60 docs de validación | 96 | 153 | 62,75 | no |
| V7 cinco vistas | 120 docs de selección | 213 | 302 | 70,53 | no |
| Actual sin resumen contable | grupo de test 20261022 (reutilizado) | 183 | 241 | 75,93 | no |
| Resumen contable (final) | grupo de test 20261022 (reutilizado) | 184 | 241 | 76,35 | no |

Mediciones usadas para elegir el modelo; no son una evaluación independiente (ver [`resultados_desarrollo.md`](resultados_desarrollo.md)).

## Datos: cobertura de etiquetas

| dataset | field | documents | annotated | unannotated | ambiguous | cobertura % |
|---|---|---|---|---|---|---|
| sroie | tax_id | 614 | 0 | 614 | 0 | 0,0 |
| sroie | date | 614 | 614 | 0 | 0 | 100 |
| sroie | document_number | 614 | 0 | 614 | 0 | 0,0 |
| sroie | subtotal | 614 | 0 | 614 | 0 | 0,0 |
| sroie | tax | 614 | 0 | 614 | 0 | 0,0 |
| sroie | total | 614 | 613 | 1 | 0 | 99,8 |
| wildreceipt | tax_id | 1267 | 0 | 1267 | 0 | 0,0 |
| wildreceipt | date | 1267 | 1025 | 195 | 47 | 80,9 |
| wildreceipt | document_number | 1267 | 0 | 1267 | 0 | 0,0 |
| wildreceipt | subtotal | 1267 | 876 | 374 | 17 | 69,1 |
| wildreceipt | tax | 1267 | 764 | 414 | 89 | 60,3 |
| wildreceipt | total | 1267 | 1057 | 149 | 61 | 83,4 |

## Optimización de hiperparámetros

- Configuraciones evaluadas: 81
- Decisión: **mantener la configuración actual**
- Cambio de la configuración seleccionada en la muestra de control: -3,06 pp (IC95 -7,07 a 0,00 pp)

Detalle en [`docs/optimizacion.md`](../../docs/optimizacion.md).

## Evaluación final

- Exactitud por campo: **81,1 %** (cumple la meta del 70 %)
- Documentos procesados sin error: **100,0 %** (cumple la meta del 90 %)
- Documentos: 100 · campos evaluados: 244
- Tiempo por documento: mediana 11,2 s, p95 20,7 s

Muestra aleatoria (semilla 42) del test oficial: 50 de sroie, 50 de wildreceipt. La configuración quedó fija antes de leer la muestra. 100 de los 100 documentos ya se habían revisado durante el desarrollo, así que no es una medición inédita.

### Intervalos de confianza (%)

| grupo | exactitud | ic95_inf | ic95_sup |
|---|---|---|---|
| todos | 81,1 | 75 | 86,9 |
| sroie | 89 | 82 | 95 |
| wildreceipt | 75,7 | 66,7 | 84,5 |

### Comparación con la línea base

|  | exactitud % | procesados % | campos |
|---|---|---|---|
| M0 reglas iniciales (1 vista) | 51,6 | 99 | 244 |
| M1 V7 anterior (5 vistas fast) | 63,9 | 100 | 244 |
| M2 actual sin resumen contable | 80,7 | 100 | 244 |
| M3 resumen contable (final) | 81,1 | 100 | 244 |

### Mejora frente a cada línea base (bootstrap pareado)

| comparacion | delta_pp | ic95_inferior_pp | ic95_superior_pp |
|---|---|---|---|
| M0 reglas iniciales (1 vista) → M3 resumen contable (final) | 29,5 | 23,9 | 35,5 |
| M1 V7 anterior (5 vistas fast) → M3 resumen contable (final) | 17,2 | 12 | 22,7 |
| M2 actual sin resumen contable → M3 resumen contable (final) | 0,4 | 0,0 | 1,2 |

### Métricas por campo

| dataset | field | support | exact_match | precision | recall | f1 | tp | fp | fn | meta_80 | faltan_para_80 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| sroie | date | 50 | 92 | 1,0 | 0,9 | 0,9 | 46 | 2 | 4 | sí | 0 |
| sroie | total | 50 | 86 | 0,9 | 0,9 | 0,9 | 43 | 6 | 7 | sí | 0 |
| wildreceipt | date | 43 | 79,1 | 0,8 | 0,8 | 0,8 | 34 | 6 | 9 | no | 1 |
| wildreceipt | subtotal | 34 | 73,5 | 0,9 | 0,7 | 0,8 | 25 | 3 | 9 | no | 3 |
| wildreceipt | tax | 27 | 74,1 | 0,9 | 0,7 | 0,8 | 20 | 2 | 7 | no | 2 |
| wildreceipt | total | 40 | 75 | 0,8 | 0,8 | 0,8 | 30 | 8 | 10 | no | 2 |
| ALL | date | 93 | 86 | 0,9 | 0,9 | 0,9 | 80 | 8 | 13 | sí | 0 |
| ALL | subtotal | 34 | 73,5 | 0,9 | 0,7 | 0,8 | 25 | 3 | 9 | no | 3 |
| ALL | tax | 27 | 74,1 | 0,9 | 0,7 | 0,8 | 20 | 2 | 7 | no | 2 |
| ALL | total | 90 | 81,1 | 0,8 | 0,8 | 0,8 | 73 | 14 | 17 | sí | 0 |

### Dónde funciona bien y dónde no

| factor | grupo | documentos | exactitud % |
|---|---|---|---|
| dataset | sroie | 50 | 89 |
| dataset | wildreceipt | 49 | 75,7 |
| tamaño | pequeña | 33 | 77 |
| tamaño | mediana | 33 | 74,7 |
| tamaño | grande | 33 | 94,2 |
| calidad OCR | CER bajo | 33 | 92,9 |
| calidad OCR | CER medio | 33 | 85,2 |
| calidad OCR | CER alto | 33 | 68,8 |

## Figuras

- [`figures/desarrollo/evolucion_exactitud.png`](../figures/desarrollo/evolucion_exactitud.png)
- [`figures/eda/01_particiones.png`](../figures/eda/01_particiones.png)
- [`figures/eda/02_resolucion.png`](../figures/eda/02_resolucion.png)
- [`figures/eda/03_regiones.png`](../figures/eda/03_regiones.png)
- [`figures/eda/04_cobertura.png`](../figures/eda/04_cobertura.png)
- [`figures/eda/08_correlaciones.png`](../figures/eda/08_correlaciones.png)
- [`figures/eda/ejemplos_regiones.png`](../figures/eda/ejemplos_regiones.png)
- [`figures/eda/posicion_campos.png`](../figures/eda/posicion_campos.png)
- [`figures/eda/razon_impuesto_subtotal.png`](../figures/eda/razon_impuesto_subtotal.png)
- [`figures/evaluacion/07_errores_linea_base.png`](../figures/evaluacion/07_errores_linea_base.png)
- [`figures/evaluacion/test_comparacion_modelos.png`](../figures/evaluacion/test_comparacion_modelos.png)
- [`figures/optimizacion/exactitud_vs_costo.png`](../figures/optimizacion/exactitud_vs_costo.png)
- [`figures/optimizacion/importancia.png`](../figures/optimizacion/importancia.png)
- [`figures/optimizacion/interaccion_grilla.png`](../figures/optimizacion/interaccion_grilla.png)
- [`figures/optimizacion/interacciones_pdp2d.png`](../figures/optimizacion/interacciones_pdp2d.png)
- [`figures/optimizacion/pdp.png`](../figures/optimizacion/pdp.png)
- [`figures/optimizacion/sensibilidad.png`](../figures/optimizacion/sensibilidad.png)
- [`figures/preprocesamiento/06_cer_vs_resolucion.png`](../figures/preprocesamiento/06_cer_vs_resolucion.png)
