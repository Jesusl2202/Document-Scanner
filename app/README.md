# app/ — interfaz web

Aplicación web del lector para que cualquier persona pruebe el modelo con sus propios documentos, sin instalar nada. Usa exactamente el mismo modelo que la terminal y los notebooks (`src.model.LectorFacturas` con `configs/definitivo.json`). La guía de uso está en el [manual de usuario](../docs/manual_usuario.md#2-usar-la-aplicación-web).

![Resultado de una lectura](assets/capturas/resultado.png)

## Dos versiones, una sola lógica

| Versión | Para qué | Archivos |
|---|---|---|
| **Streamlit** | Demostración pública en Streamlit Community Cloud; lee un documento o un lote de hasta 20 | [`streamlit_app.py`](streamlit_app.py), [`presentacion.py`](presentacion.py), [`static/streamlit.css`](static/streamlit.css) y, en la raíz, [`packages.txt`](../packages.txt) y [`.streamlit/config.toml`](../.streamlit/config.toml) |
| **Flask + Docker** | Instalación en un equipo o servidor propio, para leer documentos con datos de terceros sin que salgan de él | [`app.py`](app.py), [`templates/index.html`](templates/index.html), [`static/app.js`](static/app.js), [`static/app.css`](static/app.css) y el [`Dockerfile`](../Dockerfile) |

Las dos se apoyan en [`servicio.py`](servicio.py), que no depende de ningún framework web: validación con los límites de la web, una lectura a la vez, lectura por lotes, evidencia de cada campo, alertas en lenguaje claro, aviso de factura electrónica del SRI y mensajes de error. Por eso ambas muestran los mismos resultados y los mismos mensajes.

## Estructura

| Archivo | Contenido |
|---|---|
| [`servicio.py`](servicio.py) | Lógica común, probada en [`tests/test_app.py`](../tests/test_app.py). |
| [`streamlit_app.py`](streamlit_app.py) | Versión de Streamlit: pestañas, carga de uno o varios archivos, ejemplos, avance, resultado de un documento, tabla del lote, descargas y «Cómo funciona». |
| [`presentacion.py`](presentacion.py) | HTML del resultado, de la tabla del lote y de «Cómo funciona», y archivos CSV/JSON de la versión de Streamlit (funciones puras, probadas en [`tests/test_presentacion.py`](../tests/test_presentacion.py)). |
| [`app.py`](app.py) | Versión Flask: rutas, límites de tamaño y manejo de errores HTTP. |
| [`templates/`](templates/), [`static/`](static/) | Página y estilos de la versión Flask, estilos de la de Streamlit y la fuente Atkinson Hyperlegible Next (licencia SIL OFL 1.1), que las dos sirven desde la propia app. |
| [`assets/ejemplos/`](assets/ejemplos/) | Comprobantes **sintéticos** para los ejemplos (generados con [`scripts/crear_ejemplos.py`](../scripts/crear_ejemplos.py)), con sus valores correctos para las pruebas. |
| [`assets/capturas/`](assets/capturas/) | Capturas de pantalla usadas en la documentación. |
| [`requirements.txt`](requirements.txt) | Dependencias del lector (las de la raíz) más Streamlit, Flask y gunicorn. |

## Funcionalidades

| Requisito | Cómo se cumple |
|---|---|
| Carga de imagen o PDF con validación | Arrastrar y soltar o elegir archivo. Se rechazan con un mensaje en español los formatos no admitidos, archivos vacíos, de más de 10 MB o dañados, imágenes demasiado pequeñas y PDF de más de 3 páginas. |
| Procesamiento con indicador de carga | Barra de progreso y aviso del tiempo esperado mientras se hacen las 10 lecturas; en un lote, «Leyendo 3 de 12: archivo». |
| Varios documentos a la vez | Hasta 20 archivos por lote (`documentos_por_lote`). Resultado: tabla con todos los documentos, cada valor marcado por su confianza, cuadre y campos por revisar; un CSV y un JSON con todo; selector para abrir cualquier documento con su evidencia. Un archivo inválido aparece en rojo en la tabla y no detiene el resto. |
| Resultados con confianza y alertas | Seis campos con valor, valor normalizado, línea de origen, nivel de confianza (alta, media, baja, no detectado) y alertas traducidas a lenguaje claro; cuadre subtotal + IVA = total. |
| Explicación de cada valor | Recuadros sobre la imagen que se resaltan al pasar por cada fila. |
| Mensajes de error claros | Cada error dice qué pasó y cómo seguir, sin detalles técnicos. |
| Sección «Cómo funciona» | Métricas de la evaluación, resultados en escenarios degradados, casos en que no debe usarse, privacidad y límites. |
| Ejemplos precargados | Tres comprobantes sintéticos (factura impresa, recibo fotografiado y PDF), uno por uno o los tres juntos como lote. |
| Exportación | CSV y JSON solo con los campos (sin el texto completo de la factura). |
| Accesibilidad | Navegación con teclado, foco visible, fuente de alta legibilidad, diseño adaptable a celular y respeto de «reducir movimiento». |

## Decisiones de diseño

- **Revisar es parte del flujo.** La pantalla de resultado pone el documento junto a los valores para comparar sin cambiar de ventana, y los campos vacíos piden digitar el dato en lugar de mostrar «0».
- **Nada se guarda en el servidor.** El archivo se procesa en una carpeta temporal que se borra al terminar.
- **Lotes que se leen en orden.** Un lote no se reparte en paralelo: cada archivo toma su turno como cualquier otra lectura, así que un lote grande no deja sin servicio a otra persona. El límite de 20 archivos mantiene la espera en unos minutos.
- **La tabla del lote ayuda a revisar todo.** Pone los seis campos de todos los documentos lado a lado, con ámbar y rojo donde la confianza es media o baja y «—» donde no se detectó el valor, para empezar por lo más probable de corregir. No reemplaza la revisión completa recomendada en [consideraciones éticas](../docs/consideraciones_eticas.md).
- **Una lectura a la vez.** Cada página se lee 10 veces y el servidor gratuito tiene hasta 2 CPU; con más lecturas simultáneas todas se volverían lentas. Si hay otra lectura en curso, la nueva espera su turno (hasta 2 minutos) y, si no lo obtiene, se le pide reintentar.
- **Límites propios de la web** (`interfaz` en [`configs/config.yaml`](../configs/config.yaml)): 10 MB y 3 páginas por PDF, frente a 20 MB y 20 páginas en la terminal. Streamlit admite hasta 25 MB para que el límite de 10 MB lo aplique la app con su propio mensaje en español.
- **Aviso de alojamiento.** La demostración pública corre fuera de Ecuador y lo dice en la pantalla de carga y en «Cómo funciona»; para documentos de terceros se indica la versión de instalación propia.
- **Aviso de factura electrónica.** Si el texto muestra la clave de acceso de 49 dígitos, la app recomienda usar el XML autorizado del SRI, que es la fuente oficial de esos datos.
- **Evidencia sin JavaScript en Streamlit.** El documento y la tabla van en el mismo bloque HTML y la regla CSS `:has()` une cada fila con su recuadro.

## Ejecutar

Desde la raíz del repositorio, con Tesseract 5 instalado:

```bash
python -m pip install -r app/requirements.txt
streamlit run app/streamlit_app.py      # versión de Streamlit: http://localhost:8501
python -m app.app                       # versión Flask:        http://127.0.0.1:7860
```

Con Docker (versión Flask, incluye Tesseract 5.3.4 y los pesos verificados):

```bash
docker build -t lector-facturas .
docker run -p 7860:7860 lector-facturas    # http://localhost:7860
```

Rutas de la versión Flask: `GET /` (página), `POST /api/leer` (archivo en el campo `archivo`), `POST /api/ejemplo/<id>`, `GET /api/acerca` y `GET /salud`.

## Despliegue y verificación

- **Streamlit Community Cloud** publica la app desde la rama `main` con el archivo principal `app/streamlit_app.py`; instala Tesseract desde [`packages.txt`](../packages.txt) y las dependencias desde [`requirements.txt`](requirements.txt), y se actualiza sola con cada cambio. Usa Debian 13 con Tesseract 5.5.0 (la evaluación se hizo con 5.3.4; los ejemplos se leen igual con las dos versiones).
- El workflow [`pruebas.yml`](../.github/workflows/pruebas.yml) ejecuta en cada cambio la app de Streamlit de punta a punta con `streamlit.testing` y Tesseract real, en Ubuntu y en Debian 13 instalando igual que Streamlit Community Cloud; además construye la imagen Docker, lee un ejemplo y comprueba los valores, y verifica que un archivo no admitido devuelva un mensaje de error.
