# results/ — resultados y visualizaciones

Salidas que sí se versionan: figuras, tablas de métricas y reportes. **Nunca** se suben imágenes de facturas, texto OCR, predicciones ni documentos propios: el importador los excluye.

```text
results/
├── figures/
│   ├── desarrollo/        # evolucion_exactitud.png (versiones V1 → resumen contable)
│   ├── eda/               # 01_exploracion.ipynb: particiones, resolución, regiones, cobertura, correlaciones…
│   ├── preprocesamiento/  # 02_preprocesamiento.ipynb: CER frente al tamaño de la imagen
│   ├── optimizacion/      # 04_optimizacion.ipynb: sensibilidad, PDP, importancia, interacciones, costo (⏳)
│   └── evaluacion/        # 05_evaluacion.ipynb: comparación de modelos y errores (⏳)
├── metrics/
│   ├── desarrollo/        # resultados_desarrollo.csv, grupos_test_resumen_contable.csv
│   ├── eda/               # particiones, cobertura, estadísticas, correlaciones, fechas, outliers, incidencias
│   ├── optimizacion/      # (⏳ al importar el ZIP de 04)
│   └── evaluacion/        # (⏳ al importar el ZIP de 05)
└── reports/
    ├── resultados_desarrollo.md   # Mediciones usadas para elegir el modelo, con su contexto
    └── reporte_resultados.md      # Reporte generado a partir de metrics/ (se regenera con un comando)
```

## Qué hay ahora

| Contenido | Origen |
|---|---|
| `figures/eda/`, `metrics/eda/` | Ejecución en Colab de `01_exploracion.ipynb` sobre SROIE y WildReceipt (1.881 documentos de desarrollo). Las tablas se extrajeron de las salidas guardadas del notebook. |
| `figures/preprocesamiento/06_cer_vs_resolucion.png` | Ejecución de `02_preprocesamiento.ipynb` (30 documentos de validación). |
| `figures/desarrollo/`, `metrics/desarrollo/` | Resultados de desarrollo registrados en `reports/resultados_desarrollo.md`. Cada versión se midió en una muestra distinta; no es una evaluación independiente. |
| `reports/reporte_resultados.md` | Generado con `python -m src.evaluate reporte`. Las secciones de optimización y evaluación quedan pendientes hasta importar los ZIP de 04 y 05. |

## Cómo agregar los resultados de 04 y 05

Cuando los notebooks terminen y descargues sus ZIP, desde la raíz del repositorio:

```bash
python -m src.evaluate importar ruta/optimizacion_resultados.zip ruta/evaluacion_<fecha>.zip
```

El comando reconoce de qué notebook viene cada ZIP, copia las figuras a `figures/<tipo>/` y las tablas a `metrics/<tipo>/`, omite predicciones y carpetas privadas, y regenera `reports/reporte_resultados.md`. Después revisa el reporte, completa los ⏳ de [`docs/optimizacion.md`](../docs/optimizacion.md) y sube los cambios.

También sirve para el ZIP de 01 (`figuras_eda.zip`). Para 03, comprime la carpeta `modelado/` que genera el notebook e impórtala con `--tipo modelado`.
