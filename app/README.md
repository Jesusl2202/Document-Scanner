# app/ — interfaz de usuario

Interfaz web del lector (en desarrollo), para que cualquier persona pueda probar el modelo con sus propios documentos.

Estructura:

| Archivo | Contenido |
|---|---|
| `app.py` | Aplicación principal; usa `src.model.LectorFacturas` con la configuración de [`configs/config.yaml`](../configs/config.yaml). |
| `requirements.txt` | Dependencias de la app (además de las de la raíz). |
| `assets/` | Imágenes, estilos y comprobantes sintéticos de ejemplo para el botón "Probar con ejemplo". |

Funcionalidades: carga y validación del archivo, procesamiento con indicador de carga, mensajes de error claros, resultados con nivel de confianza y alertas por campo, sección «Acerca de» con métricas y limitaciones, y ejemplos para probar. Solo admite comprobantes impresos o digitales: los **campos escritos a mano no se reconocen de forma confiable**.

La guía de uso está en [`docs/manual_usuario.md`](../docs/manual_usuario.md).
