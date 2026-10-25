# tests/ — pruebas unitarias

188 pruebas con `unittest` (biblioteca estándar). La mayoría simula el OCR, así que corren en segundos y no necesitan Tesseract; las pruebas de integración usan Tesseract real (lectura del recibo sintético, de los ejemplos y de la app de Streamlit de punta a punta) y se omiten si no está disponible. El workflow [`pruebas.yml`](../.github/workflows/pruebas.yml) las ejecuta en cada cambio, junto con `flake8`, una prueba de la app en Debian 13 (el sistema de Streamlit Community Cloud, con Tesseract 5.5) y una prueba de humo de la imagen Docker.

## Cómo ejecutarlas

Desde la raíz del repositorio:

```bash
python -m pip install -r app/requirements.txt                 # lector + interfaz web
python -m pip install -e .                       # hace importable el motor lector_facturas
python -m unittest discover -s tests -v           # todas las pruebas
python -m unittest tests.test_model -v            # un solo archivo
```

Sin instalar el paquete también funciona con `PYTHONPATH=src` (Linux/macOS) o `$env:PYTHONPATH="src"` (PowerShell).

La prueba `IntegracionTesseractTests` se activa sola cuando Tesseract está en el PATH y los pesos están en `models/fast/` y `models/best/` (se descargan con la primera lectura: `python -m src.model samples/synthetic_receipt.png`). Las pruebas de rutas de la app necesitan Flask, y la de punta a punta de la versión de Streamlit, Streamlit (los dos en `app/requirements.txt`).

Estilo (PEP 8) de la interfaz pública y de estas pruebas: `python -m flake8 src tests` (configuración en `.flake8`).

## Qué prueba cada archivo

| Archivo | Pruebas | Qué cubre |
|---|---:|---|
| [`test_data_processing.py`](test_data_processing.py) | 16 | Configuración (YAML, `.env`, errores), validación de archivos (formato, tamaño, imagen dañada o pequeña, páginas de PDF), PDF → imágenes, los 6 preprocesamientos y el retorno de coordenadas, normalización de montos y fechas, localización de datasets y cobertura de etiquetas. |
| [`test_model.py`](test_model.py) | 11 | Carga del modelo (sin Tesseract, sin Internet, una sola carga), lectura con OCR simulado, cuadre de montos, nivel de confianza, que nunca se invente un total, que una página con error no detenga el documento, salidas JSON/CSV y lectura real del recibo sintético. |
| [`test_app.py`](test_app.py) | 21 | Interfaz web: lectura correcta con evidencia y vista previa, sin texto OCR completo en la respuesta (privacidad); entradas inválidas (formato, archivo vacío, imagen dañada o diminuta, sin archivo, más de 10 MB) con mensaje claro; error interno sin detalles técnicos; modelo no disponible; servidor ocupado; página que falla; ejemplos, «Acerca de», alertas en lenguaje claro, aviso de factura electrónica del SRI y lectura real de los tres ejemplos con Tesseract; lectura por lotes (un archivo inválido no detiene el resto, avance, límite de archivos). |
| [`test_presentacion.py`](test_presentacion.py) | 9 | Versión de Streamlit: resumen de la lectura, tabla y descargas del lote, recuadros de evidencia dentro de la imagen, campos vacíos sin «0», confianza, cuadre y avisos, texto OCR escapado, página con error, descargas CSV/JSON solo con los campos, «Cómo funciona»; y la app completa con `streamlit.testing` y Tesseract real (carga, lectura de un ejemplo, «Leer otro documento» y los tres ejemplos como lote). |
| [`test_validation.py`](test_validation.py) | 7 | Muestra de documentos nunca revisados (exclusiones y semilla), escenarios críticos deterministas, tipo de error y errores silenciosos, exactitud por documento, calibración y tiempo de revisión. |
| [`test_line_classifier.py`](test_line_classifier.py) | 4 | Comparador aprendido: candidatos y etiquetas débiles, entrenamiento con historial y *early stopping*, extracción de extremo a extremo y diagnóstico con sensibilidad de umbrales. |
| [`test_consensus.py`](test_consensus.py) | 64 | Extractor y consenso: limpieza de errores del OCR, votos, pagos, filas aritméticas, fechas, etapas del resumen contable. |
| [`test_pipeline.py`](test_pipeline.py) | 25 | Normalización, adaptadores SROIE/WildReceipt, partición sin fugas, evaluación y métricas. |
| [`test_ocr.py`](test_ocr.py) | 18 | Lectura TSV de Tesseract simulada, vistas en paralelo, caché y rescate adaptativo. |
| [`test_preprocessing.py`](test_preprocessing.py) | 7 | Transformaciones de imagen y coordenadas. |
| [`test_frozen_runtime.py`](test_frozen_runtime.py) | 6 | Descarga y verificación por SHA-256 de los pesos y muestra final. |
