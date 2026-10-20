# data/raw — datos originales

Aquí se descargan los datasets públicos tal como los distribuye su fuente, sin modificarlos. **Esta carpeta no se versiona**: `.gitignore` excluye todo su contenido salvo este archivo.

## Qué va aquí

| Dataset | Fuente | Archivo descargado |
|---|---|---|
| WildReceipt | <https://download.openmmlab.com/mmocr/data/wildreceipt.tar> | `wildreceipt.tar` (y su contenido extraído) |
| SROIE | <https://www.kaggle.com/datasets/urbikn/sroie-datasetv2> | `sroie_v2.zip` (extraído en `sroie_distribution/`) |

## Cómo descargarlos

Desde la raíz del repositorio:

```bash
python scripts/download_data.py wildreceipt --out data/raw
python scripts/download_data.py sroie --out data/raw
```

- La descarga no se ejecuta al instalar el proyecto; es una acción explícita.
- Kaggle puede exigir sesión. Si el script avisa que no recibió un ZIP, descarga el archivo manualmente con tu cuenta y extráelo dentro de `data/raw/`. El script no intenta eludir ese acceso.
- Cada descarga deja un `<dataset>_download.json` con la URL, el SHA-256, el tamaño en bytes y la fecha UTC. El hash registra qué se descargó; no es una firma oficial ni implica permiso de redistribución.
- Antes de compartir imágenes con terceros, revisa las condiciones de cada fuente (ver [`../README.md`](../README.md#5-licencias-y-condiciones-de-uso)).

## Estructura que esperan los adaptadores

Los adaptadores (`src/lector_facturas/datasets.py`) y el notebook localizan cada base por su contenido, no por un nombre fijo de carpeta:

| Dataset | La raíz es la carpeta que contiene… |
|---|---|
| SROIE | `train/img`, `train/box`, `train/entities` (y, si existe, la misma estructura en `test/`) |
| WildReceipt | `class_list.txt`, `train.txt`, `test.txt` y las imágenes referenciadas por `file_name` |

Si tu descarga quedó en otra ruta, indícala con `DATOS_MANUAL` en la primera celda del notebook o con los argumentos de `prepare`.

## Reglas

- No editar, renombrar ni borrar archivos originales: el manifiesto identifica cada documento por su ruta y su SHA-256.
- No guardar aquí documentos propios o privados. Los comprobantes reales (muestra RIDE) se manejan fuera del repositorio, anonimizados y con autorización; ver [`docs/ANOTACION_PROPIA.md`](../../docs/ANOTACION_PROPIA.md).
