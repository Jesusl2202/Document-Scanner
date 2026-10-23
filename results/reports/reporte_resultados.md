# Reporte de resultados

Resumen de las métricas de `results/metrics/` (actualizado el 22/10/2026).

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
- [`figures/preprocesamiento/06_cer_vs_resolucion.png`](../figures/preprocesamiento/06_cer_vs_resolucion.png)
