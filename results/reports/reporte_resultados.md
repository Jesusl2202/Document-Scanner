# Reporte de resultados

Resumen de las métricas de `results/metrics/` (actualizado el 24/10/2026).

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
- Tiempo por documento: mediana 7,3 s, p95 12,4 s

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
| sroie | date | 50 | 92 | 0,958 | 0,920 | 0,939 | 46 | 2 | 4 | sí | 0 |
| sroie | total | 50 | 86 | 0,878 | 0,860 | 0,869 | 43 | 6 | 7 | sí | 0 |
| wildreceipt | date | 43 | 79,100 | 0,850 | 0,791 | 0,819 | 34 | 6 | 9 | no | 1 |
| wildreceipt | subtotal | 34 | 73,500 | 0,893 | 0,735 | 0,806 | 25 | 3 | 9 | no | 3 |
| wildreceipt | tax | 27 | 74,100 | 0,909 | 0,741 | 0,816 | 20 | 2 | 7 | no | 2 |
| wildreceipt | total | 40 | 75 | 0,789 | 0,750 | 0,769 | 30 | 8 | 10 | no | 2 |
| ALL | date | 93 | 86 | 0,909 | 0,860 | 0,884 | 80 | 8 | 13 | sí | 0 |
| ALL | subtotal | 34 | 73,500 | 0,893 | 0,735 | 0,806 | 25 | 3 | 9 | no | 3 |
| ALL | tax | 27 | 74,100 | 0,909 | 0,741 | 0,816 | 20 | 2 | 7 | no | 2 |
| ALL | total | 90 | 81,100 | 0,839 | 0,811 | 0,825 | 73 | 14 | 17 | sí | 0 |

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

## Validación en contextos simulados (notebook 06)

### Documentos nunca revisados frente al test (%)

| grupo | exactitud | ic95_inf | ic95_sup | exactitud_test | ic95_inf_test | ic95_sup_test | diferencia_pp |
|---|---|---|---|---|---|---|---|
| todos | 75 | 67,9 | 81,6 | 81,1 | 75 | 86,9 | -6,1 |
| sroie | 86 | 78 | 93 | 89 | 82 | 95 | -3 |
| wildreceipt | 67,4 | 55,8 | 77,6 | 75,7 | 66,7 | 84,5 | -8,3 |

### Exactitud según el nivel de confianza (%)

| confianza | campos | porcentaje_de_campos | exactitud | equivocados | omisiones |
|---|---|---|---|---|---|
| alta | 131 | 53,7 | 95,4 | 4,6 | 0,0 |
| media | 48 | 19,7 | 75 | 25 | 0,0 |
| baja | 41 | 16,8 | 53,7 | 46,3 | 0,0 |
| sin_valor | 24 | 9,8 | 0,0 | 0,0 | 100 |

### Tiempo de revisión estimado por documento

| forma de trabajo | segundos_por_documento | errores_sin_corregir_por_100_documentos | ahorro_vs_manual_% |
|---|---|---|---|
| Manual (sin el sistema) | 22,2 | 0,0 | 0,0 |
| Revisión completa | 11,7 | 0,0 | 47,2 |
| Revisión guiada por la confianza | 7,9 | 6,1 | 64,6 |

### Escenarios críticos

| escenario | campos | exactitud | omisiones | equivocados | silenciosos | procesados | caida_pp | veredicto |
|---|---|---|---|---|---|---|---|---|
| Sin perturbar | 90 | 81,1 | 5,6 | 13,3 | 2,2 | 100 | 0,0 | aceptable |
| Ruido σ = 12 | 90 | 76,7 | 11,1 | 12,2 | 2,2 | 100 | 4,4 | aceptable |
| Ruido σ = 30 | 90 | 48,9 | 33,3 | 17,8 | 2,2 | 100 | 32,2 | falla |
| Desenfoque leve | 90 | 42,2 | 45,6 | 12,2 | 2,2 | 100 | 38,9 | falla |
| Desenfoque fuerte | 90 | 17,8 | 67,8 | 14,4 | 1,1 | 100 | 63,3 | falla |
| Mitad de resolución | 90 | 61,1 | 27,8 | 11,1 | 2,2 | 100 | 20 | falla |
| 30 % de resolución | 90 | 33,3 | 51,1 | 15,6 | 3,3 | 100 | 47,8 | falla |
| JPEG calidad 12 | 90 | 61,1 | 26,7 | 12,2 | 1,1 | 100 | 20 | falla |
| Rotación 6° | 90 | 53,3 | 11,1 | 35,6 | 6,7 | 100 | 27,8 | falla |
| Sombra lateral | 90 | 72,2 | 13,3 | 14,4 | 2,2 | 100 | 8,9 | aceptable |
| Falta el 20 % inferior | 90 | 72,2 | 15,6 | 12,2 | 4,4 | 100 | 8,9 | aceptable |

### Resultados por subgrupo

| factor | grupo | documentos | campos | exactitud | omisiones | equivocados | silenciosos | campos_a_revisar_por_doc |
|---|---|---|---|---|---|---|---|---|
| captura | celular (WildReceipt) | 49 | 144 | 67,4 | 15,3 | 17,4 | 2,8 | 1,6 |
| captura | escáner (SROIE) | 50 | 100 | 86 | 2 | 12 | 2 | 0,7 |
| tamaño de imagen | pequeña | 33 | 98 | 66,3 | 13,3 | 20,4 | 3,1 | 1,7 |
| tamaño de imagen | mediana | 33 | 77 | 74,0 | 13,0 | 13,0 | 1,3 | 1,1 |
| tamaño de imagen | grande | 33 | 69 | 88,4 | 1,4 | 10,1 | 2,9 | 0,6 |
| calidad del OCR | OCR limpio | 33 | 69 | 89,9 | 1,4 | 8,7 | 2,9 | 0,5 |
| calidad del OCR | OCR medio | 33 | 78 | 80,8 | 5,1 | 14,1 | 1,3 | 0,9 |
| calidad del OCR | OCR con muchos errores | 33 | 97 | 59,8 | 19,6 | 20,6 | 3,1 | 2,0 |

Documentos con todos sus campos correctos: **61,6 %** (si los campos fallaran de forma independiente se esperaría 54,4 %).

## Comparación con una técnica aprendida (notebook 03)

| modelo | lectura OCR | exactitud | ic95 |
|---|---|---|---|
| M0 reglas iniciales (1 vista) | 1 vista | 51,9 | — |
| Red MLP sobre líneas (capas=(128,), L2=0.01, ES5) | 1 vista | 57,4 | 56.1 – 58.8 (5 semillas) |
| M3 resumen contable (final) | 10 vistas | 81,1 | 75,0 – 86,9 (bootstrap, notebook 05) |

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
- [`figures/modelado/ablacion.png`](../figures/modelado/ablacion.png)
- [`figures/modelado/comparacion_modelos.png`](../figures/modelado/comparacion_modelos.png)
- [`figures/modelado/ml_curvas_aprendizaje_validacion.png`](../figures/modelado/ml_curvas_aprendizaje_validacion.png)
- [`figures/modelado/ml_curvas_escalera.png`](../figures/modelado/ml_curvas_escalera.png)
- [`figures/optimizacion/exactitud_vs_costo.png`](../figures/optimizacion/exactitud_vs_costo.png)
- [`figures/optimizacion/importancia.png`](../figures/optimizacion/importancia.png)
- [`figures/optimizacion/interaccion_grilla.png`](../figures/optimizacion/interaccion_grilla.png)
- [`figures/optimizacion/interacciones_pdp2d.png`](../figures/optimizacion/interacciones_pdp2d.png)
- [`figures/optimizacion/pdp.png`](../figures/optimizacion/pdp.png)
- [`figures/optimizacion/sensibilidad.png`](../figures/optimizacion/sensibilidad.png)
- [`figures/preprocesamiento/06_cer_vs_resolucion.png`](../figures/preprocesamiento/06_cer_vs_resolucion.png)
- [`figures/preprocesamiento/cer_por_vista.png`](../figures/preprocesamiento/cer_por_vista.png)
- [`figures/validacion/calibracion_confianza.png`](../figures/validacion/calibracion_confianza.png)
- [`figures/validacion/escenarios_criticos.png`](../figures/validacion/escenarios_criticos.png)
- [`figures/validacion/escenarios_ejemplo.png`](../figures/validacion/escenarios_ejemplo.png)
