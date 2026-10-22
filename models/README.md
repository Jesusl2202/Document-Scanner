# models/ — modelo entrenado

Este proyecto **no entrena pesos**, así que no hay un `best_model.pkl`. El modelo queda definido por tres piezas versionadas por hash:

| Pieza | Dónde | Versionado |
|---|---|---|
| Pesos LSTM de Tesseract: `eng` (`tessdata_fast` y `tessdata_best`) y `spa` (`tessdata_fast`) | `models/fast/` y `models/best/` | **No** (se descargan de revisiones fijas y se verifican por SHA-256 en la primera lectura; Git los ignora) |
| Configuración: vistas OCR, etapas activas, normalización y validaciones | [`configs/definitivo.json`](../configs/definitivo.json) | Sí |
| Código del extractor | [`src/lector_facturas/`](../src/lector_facturas/) | Sí |

## Archivos

| Archivo | Contenido |
|---|---|
| [`ficha_modelo.json`](ficha_modelo.json) | Ficha del **mejor modelo** («resumen contable»): pesos y revisiones, arquitectura VGSL, hash de la configuración y de cada archivo de código, resultados de desarrollo, uso previsto y casos fuera de alcance. |
| `modelo_final.json` *(opcional)* | La misma definición con los resultados de validación de M0–M3; la genera [`03_modelado.ipynb`](../notebooks/03_modelado.ipynb) (sección 9) y se puede copiar aquí. |
| `configuracion_recomendada.json` *(opcional)* | Salida de [`04_optimizacion.ipynb`](../notebooks/04_optimizacion.ipynb); solo se adopta si mejora en la muestra de control. |

## Versiones anteriores

En lugar de `model_v1.pkl`, las versiones anteriores están en el historial de Git:

| Versión | Dónde | Resultado de desarrollo |
|---|---|---|
| V7 (cinco vistas `fast`) | commit `1636f65` | 213/302 (70,53 %), retrospectivo |
| Resumen contable (actual) | rama `main` | 75,0–77,6 % en tres grupos del test con reutilización |

Detalle en [`results/reports/resultados_desarrollo.md`](../results/reports/resultados_desarrollo.md).
