# results/ — resultados y visualizaciones

Figuras, tablas de métricas y reportes del proyecto. No contiene imágenes de facturas, texto OCR, valores predichos documento por documento ni documentos propios.

```text
results/
├── figures/
│   ├── desarrollo/        # Evolución de la exactitud: línea base V1 → modelo «resumen contable»
│   ├── eda/               # Análisis exploratorio: particiones, resolución, regiones, cobertura, correlaciones, posición de campos
│   ├── preprocesamiento/  # Calidad del OCR (CER) frente al tamaño de la imagen
│   ├── optimizacion/      # Optimización de hiperparámetros (notebook 04)
│   └── evaluacion/        # Evaluación final (notebook 05)
├── metrics/
│   ├── desarrollo/        # Exactitud por versión y por grupo de test
│   ├── eda/               # Particiones, cobertura de etiquetas, estadísticas, correlaciones, formatos de fecha, outliers, incidencias
│   ├── optimizacion/      # Sensibilidad, búsqueda aleatoria, importancia, selección y control antes/después
│   └── evaluacion/        # Test final: cumplimiento de metas, intervalos, línea base (M0–M2), métricas por campo y por factor
└── reports/
    ├── resultados_desarrollo.md   # Mediciones usadas para elegir el modelo, con su contexto
    └── reporte_resultados.md      # Resumen de las métricas de esta carpeta
```

## Origen de cada resultado

| Contenido | Origen |
|---|---|
| `figures/eda/`, `metrics/eda/` | [`01_exploracion.ipynb`](../notebooks/01_exploracion.ipynb) sobre los 1.881 documentos de desarrollo de SROIE y WildReceipt. |
| `figures/preprocesamiento/` | [`02_preprocesamiento.ipynb`](../notebooks/02_preprocesamiento.ipynb), 30 documentos de validación. |
| `figures/desarrollo/`, `metrics/desarrollo/` | Mediciones de desarrollo descritas en [`reports/resultados_desarrollo.md`](reports/resultados_desarrollo.md). Cada versión se midió en una muestra distinta; no es una evaluación independiente. |
| `figures/optimizacion/`, `metrics/optimizacion/` | [`04_optimizacion.ipynb`](../notebooks/04_optimizacion.ipynb): 60 documentos de optimización y 40 de control de la partición de validación. Interpretación en [`docs/optimizacion.md`](../docs/optimizacion.md). |
| `figures/evaluacion/`, `metrics/evaluacion/` | [`05_evaluacion.ipynb`](../notebooks/05_evaluacion.ipynb): 100 documentos del test oficial. `test_final/` guarda la configuración, el entorno y la huella del código evaluado; `M0`–`M2` son las líneas base sobre las mismas lecturas OCR. |
| `reports/reporte_resultados.md` | Generado a partir de `metrics/` con [`src/evaluate.py`](../src/evaluate.py). |

## Figuras principales

![Exactitud por campo y modelo en el test](figures/evaluacion/test_comparacion_modelos.png)

![Evolución de la exactitud durante el desarrollo](figures/desarrollo/evolucion_exactitud.png)
