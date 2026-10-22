# results/ — resultados y visualizaciones

Salidas de los notebooks que sí se versionan: figuras, tablas de métricas y reportes. **Nunca** se suben imágenes de facturas, texto OCR ni predicciones de documentos propios.

```text
results/
├── figures/
│   ├── eda/                 # 01_exploracion.ipynb (figuras ya incluidas)
│   ├── preprocesamiento/    # 02_preprocesamiento.ipynb
│   ├── optimizacion/        # 04_optimizacion.ipynb (sensibilidad, PDP, importancia, interacciones, costo)
│   └── evaluacion/          # 05_evaluacion.ipynb (comparación de modelos, errores)
├── metrics/                 # Tablas CSV/JSON de 03, 04 y 05
└── reports/
    └── resultados_desarrollo.md   # Mediciones usadas para elegir el modelo
```

## Cómo llenarla

| Notebook | ZIP que descarga | Copiar a |
|---|---|---|
| 01 | `figuras_eda.zip` | `figures/eda/` |
| 02 | carpeta `figuras/` (`cer_por_vista.png`, `06_cer_vs_resolucion.png`) | `figures/preprocesamiento/` |
| 03 | `modelado/` (`ablacion.csv`, `M*/evaluation/metrics.csv`, `modelo_final.json`) y figuras | `metrics/modelado/`, `figures/modelado/`, `models/` |
| 04 | `optimizacion_resultados.zip` | CSV/JSON → `metrics/optimizacion/`; PNG → `figures/optimizacion/` |
| 05 | `evaluacion_<fecha>.zip` | CSV/JSON → `metrics/evaluacion/`; PNG → `figures/evaluacion/` |

Las figuras de `eda/` y `preprocesamiento/06_cer_vs_resolucion.png` salen de la ejecución en Colab de los notebooks 01 y 02 sobre los datos reales. Los demás resultados se agregan al ejecutar 03–05 con el modelo actual.
