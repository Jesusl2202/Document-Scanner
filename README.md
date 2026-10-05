# Document Scanner — lector de facturas con Tesseract

Proyecto integrador: extracción de fecha, identificador fiscal, número de comprobante, subtotal, impuesto y total desde imágenes o PDF. Usa Tesseract preentrenado en CPU y consenso de cinco lecturas. No entrena pesos ni requiere servicios de pago.

## Empezar en Colab

[Abrir notebook](https://colab.research.google.com/github/Jesusl2202/Document-Scanner/blob/main/notebooks/01_lector_definitivo.ipynb)

Ejecutar las celdas en orden. El notebook descarga el código de este repositorio y registra el commit. Para probar una rama antes de integrarla a main, cambia `RAMA` en la primera celda. La lectura de una imagen/PDF propio está en la sección 5. El test final está activado por defecto (50 documentos por base); desactiva `EVALUAR_TEST_FINAL` si solo quieres leer archivos propios. No hace falta descargar ninguna versión anterior.

## Ejecutar localmente

Requisitos: Python 3.10 o superior y Tesseract instalado y disponible en PATH (`tesseract --version`). En Ubuntu/Colab: `sudo apt-get install tesseract-ocr`. En Windows instalar Tesseract y agregar su carpeta a PATH antes de ejecutar Python.

Desde la raíz del repositorio:

```bash
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# Linux/macOS: source .venv/bin/activate
python -m pip install -r requirements.txt
python scripts/leer_documento.py samples/synthetic_receipt.png --out outputs/ejemplo
python scripts/leer_documento.py mi_factura.pdf --out outputs/mi_factura
```

La primera lectura descarga los pesos ingleses oficiales (unos 4 MB) y verifica su SHA-256. Necesita Internet para esa descarga. Las imágenes se procesan localmente. `resultado.json` conserva texto, cajas, campos y alertas; `campos.csv` conserva una fila por imagen/página. No se fusionan páginas automáticamente. Si aparece `total:from_subtotal`, revisar el total: la ausencia de un impuesto detectado no demuestra que no exista.

## Resultados y meta

La implementación elegida obtuvo 111/153 (72,55 %) en una muestra y 102/149 (68,46 %) al reproducir la extracción sobre el OCR guardado de otra. Son 213/302 (70,53 %) en 120 documentos distintos. Se usaron para seleccionar esta versión: no son una garantía sobre documentos nuevos. El test final independiente está pendiente. La segunda cifra no mide de nuevo tiempo OCR.

Metas: exactitud global >=70 % y procesamiento >=90 %. Fecha/total se evalúan en SROIE; fecha/subtotal/impuesto/total en WildReceipt. Identificador fiscal y número de comprobante requieren una muestra propia. Ver [resultados y limitaciones](docs/resultados.md).

## Estructura

```text
configs/       Configuración fija y hashes de documentos revisados
docs/          Diseño, resultados, datos y anotación propia
notebooks/     Un notebook que utiliza el código de src/
samples/       Imagen/PDF y referencia sintéticos para comprobar la instalación
scripts/       Entrada de lectura, descarga de datos y generador sintético
src/lector_facturas/  OCR, extracción, validación y evaluación
tests/         Pruebas de la implementación activa
```

Una única implementación se expone desde `extraction.py`. `candidate_rules.py` y `consensus.py` son etapas complementarias, no versiones alternativas. Las etapas anteriores siguen disponibles en el historial Git, no como carpetas duplicadas.

## Pruebas

```bash
python -m pip install -e .
python -m unittest discover -s tests -v
```

La instalación editable permite importar el paquete y usar `lector archivo.pdf --out outputs/lectura`. Las pruebas simuladas de OCR verifican el funcionamiento del código, no acreditan su exactitud en documentos reales.

## Documentación

- [Diseño y alcance académico](docs/diseno.md)
- [Resultados medidos](docs/resultados.md)
- [Datos y licencias](docs/datos_y_licencias.md)
- [Anotación de documentos propios](docs/anotacion_propia.md)

No subir datasets, pesos, credenciales, cachés o facturas personales. `.gitignore` excluye sus carpetas habituales. Se conservan únicamente ejemplos sintéticos. La licencia del código del equipo sigue pendiente de elección; no se atribuyen licencias de terceros a los datos.
