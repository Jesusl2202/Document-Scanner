# app/ — interfaz de usuario

⏳ **En construcción.** Aquí irá la aplicación que permite a cualquier persona probar el lector:

| Archivo | Contenido previsto |
|---|---|
| `app.py` | Aplicación principal (Streamlit o Gradio) que llama a `lector_facturas.cli.predict` con la configuración de [`configs/definitivo.json`](../configs/definitivo.json). |
| `requirements.txt` | Dependencias de la app (además de las de la raíz). |
| `assets/` | Imágenes, estilos y comprobantes sintéticos de ejemplo para el botón "Probar con ejemplo". |

Requisitos mínimos del curso: carga y validación del archivo, botón de procesar con indicador de carga, manejo de errores, resultados con nivel de confianza y alertas, sección "Acerca de" con métricas y limitaciones, y ejemplos precargados. La interfaz debe advertir que los **campos escritos a mano no se reconocen de forma confiable**.

La guía de uso se completará en [`docs/manual_usuario.md`](../docs/manual_usuario.md), sección 4.
