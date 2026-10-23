# Manual de usuario

**Proyecto:** Lector de Facturas — extracción y validación de datos de facturas y comprobantes de compra con OCR
**Equipo:** Sebastián Rojas y Jesús Antonio López Barahona
**Última actualización:** 21/10/2026

Guía para usar el lector: qué documentos acepta, cómo leer una factura, cómo interpretar el resultado y qué hacer cuando algo falla.

> La interfaz web de [`app/`](../app/) está en desarrollo. Mientras tanto, el lector se usa desde Google Colab (sección 2) o desde la terminal (sección 3).

## Contenido

1. [Antes de empezar: qué documentos funcionan](#1-antes-de-empezar-qué-documentos-funcionan)
2. [Leer una factura en Google Colab](#2-leer-una-factura-en-google-colab)
3. [Leer una factura en tu computador](#3-leer-una-factura-en-tu-computador)
4. [Interfaz web](#4-interfaz-web)
5. [Cómo interpretar el resultado](#5-cómo-interpretar-el-resultado)
6. [Solución de problemas](#6-solución-de-problemas)
7. [Preguntas frecuentes](#7-preguntas-frecuentes)
8. [Soporte](#8-soporte)

---

## 1. Antes de empezar: qué documentos funcionan

| ✅ Funciona mejor con | ⚠️ Funciona peor con | ❌ No usar con |
|---|---|---|
| Facturas y recibos **impresos o digitales** (PDF generado por un sistema, ticket térmico, factura electrónica impresa) | Fotos con sombras, inclinadas, borrosas o muy pequeñas | Comprobantes con **campos escritos a mano** (fecha, montos, RUC o número llenados con bolígrafo) |
| Escaneos o fotos nítidas, con el documento completo y de frente | Recibos con varios montos parecidos (total, efectivo, redondeo) | Documentos completamente manuscritos |
| Etiquetas visibles: "TOTAL", "SUBTOTAL", "IVA", "RUC", "Fecha" | Facturas en idiomas con otro alfabeto | Verificar si una factura es auténtica o está autorizada por el SRI |

**Formatos aceptados:** `.jpg`, `.jpeg`, `.png` y `.pdf` (hasta 20 páginas; cada página se lee por separado).

**Consejos para la foto:** buena luz sin flash directo, documento plano y completo, sin dedos sobre los montos, y que el texto se lea bien al hacer zoom.

> **Sobre los campos escritos a mano.** El reconocimiento de Tesseract está entrenado con texto impreso. Si un comprobante tiene la fecha, los montos o el RUC escritos a mano, el sistema puede dejarlos vacíos o, peor, leer un valor equivocado sin darse cuenta. En ese caso digita esos campos manualmente.

## 2. Leer una factura en Google Colab

No necesitas instalar nada.

1. Abre [`notebooks/05_evaluacion.ipynb`](https://colab.research.google.com/github/Jesusl2202/Document-Scanner/blob/main/notebooks/05_evaluacion.ipynb) en Colab (**Entorno de ejecución → CPU** es suficiente).
2. Ejecuta las celdas de la sección **1. Configuración** (instala Tesseract, descarga el código y los pesos verificados). La primera vez tarda unos minutos.
3. Si solo quieres leer tu documento, ejecuta las secciones **1** (configuración y parámetros) y **2** (configuración final) y salta a la sección **9. Leer un documento propio**. No necesitas ejecutar la evaluación del test.
4. En la sección 9 cambia `PROBAR_DOCUMENTO_EXTERNO = True` y ejecuta la celda. Se abrirá el selector de archivos: elige **una** imagen o PDF.
5. Verás cada página, una tabla con los seis campos, el estado de la lectura, los avisos y el texto reconocido.
6. Opcional: si conoces los valores correctos, escríbelos en `RESPUESTAS_CORRECTAS` (siguiente celda) para comparar campo por campo.

Los archivos que subes quedan en una carpeta privada de la sesión de Colab y **no** se incluyen en el ZIP de resultados.

## 3. Leer una factura en tu computador

**Requisitos:** Python 3.10 o superior y Tesseract 5 instalado y disponible en el PATH (`tesseract --version`). En Ubuntu: `sudo apt-get install tesseract-ocr`. En Windows, instala Tesseract (por ejemplo, el instalador de UB Mannheim) y agrega su carpeta al PATH.

```bash
git clone https://github.com/Jesusl2202/Document-Scanner.git
cd Document-Scanner
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# Linux/macOS:        source .venv/bin/activate
python -m pip install -r requirements.txt

# Probar con el recibo sintético del repositorio
python -m src.model samples/synthetic_receipt.png --salida outputs/ejemplo

# Leer tu factura
python -m src.model ruta/a/mi_factura.pdf --salida outputs/mi_factura
```

En la terminal verás cada campo con su **nivel de confianza** (`alta`, `media`, `baja` o `sin_valor`), que indica cuántas de las lecturas OCR coincidieron en ese valor (no es una probabilidad). También funciona el comando anterior, `python scripts/leer_documento.py archivo --out carpeta`, con la misma salida en archivos.

La primera lectura descarga los pesos de Tesseract (`eng` fast y best, `spa`; unos 22 MB) en `models/fast/` y `models/best/` y verifica su SHA-256; necesita Internet solo esa vez. Las imágenes se procesan en tu equipo.

En `outputs/mi_factura/` quedan:

- `campos.csv`: una fila por página con los seis campos y las notas de revisión (se abre en Excel).
- `resultado.json`: todo el detalle (texto OCR, cajas, evidencia de cada campo, validaciones y alertas).
- `paginas/`: las imágenes de cada página si el archivo era un PDF.

## 4. Interfaz web

La interfaz web está en desarrollo en [`app/`](../app/). Usará el mismo modelo que la terminal (`src.model.LectorFacturas`): carga de una imagen o PDF, resultados con nivel de confianza y alertas por campo, sección «Acerca de» con métricas y limitaciones, y ejemplos para probar.

## 5. Cómo interpretar el resultado

### 5.1 Los campos

| Campo | Significado | Formato de salida |
|---|---|---|
| `tax_id` | Identificador fiscal del emisor (RUC en Ecuador) | Texto, tal como aparece |
| `date` | Fecha de emisión | `AAAA-MM-DD`, o `AMBIGUOUS:dd/mm/aaaa` si no se puede saber qué es día y qué es mes |
| `document_number` | Número de comprobante | Texto, tal como aparece (p. ej. `001-002-000123`) |
| `subtotal` | Monto antes de impuesto | Decimal con dos cifras (`100.00`) |
| `tax` | Impuesto (IVA) | Decimal con dos cifras |
| `total` | Total a pagar | Decimal con dos cifras |

Un campo vacío significa **"no se encontró con suficiente evidencia"**, nunca "cero".

### 5.2 Estado de la lectura

| `quality.reading_status` | Qué significa |
|---|---|
| `lectura_por_verificar` | Se encontraron fecha, subtotal, impuesto y total. Igual hay que revisarlos. |
| `lectura_parcial` | Faltan algunos de esos cuatro campos. |
| `sin_campos` | No se encontró ninguno: revisa la calidad de la imagen o si el documento es manuscrito. |

La cobertura **no** es exactitud: un campo encontrado puede estar mal leído.

### 5.3 Validaciones

| Validación | Valores posibles | Qué hacer |
|---|---|---|
| Fecha y montos | `valid_format`, `ambiguous_date_order`, `ambiguous_or_invalid_format` | Revisar los que no digan `valid_format`. |
| Cuadre (`amount_balance`) | `consistent`, `inconsistent_review` | Si no cuadra, revisar descuentos, propinas, cargos o un monto mal leído. |
| RUC (`tax_id`) | `not_configured` por defecto | Para Ecuador se puede configurar el patrón de 13 dígitos en `configs/definitivo.json`. |

`valid_format` significa que el valor tiene la **forma** correcta, no que la factura sea válida ante el SRI.

### 5.4 Avisos de revisión

| Aviso | Qué hacer |
|---|---|
| `total:subtotal_no_confirma_total` | Se vio un subtotal pero no un total ni un impuesto. Escribe el total a mano. |
| `<campo>:observed_accounting_selection` / "Resumen comprobado con descuentos/cargos observados" | El sistema ajustó un monto para que cuadre con descuentos o cargos visibles. Confirma esos ajustes. |
| `<campo>:confidence_gap_recovery` | El campo estaba vacío y se completó con una segunda revisión por confianza. Verifícalo. |
| `<campo>:ambiguous_consensus` | Había dos valores igual de fuertes; se dejó vacío. |
| "Subtotal + impuesto no coincide con total" | Los montos no cuadran: revisa la factura. |
| "Una o varias lecturas OCR fallaron" | Alguna lectura no produjo texto; si muchos campos quedaron vacíos, prueba con una imagen mejor. |

## 6. Solución de problemas

| Problema | Causa probable | Solución |
|---|---|---|
| `No se encontró Tesseract` / `tesseract: command not found` | Tesseract no está instalado o no está en el PATH | Instálalo y abre una terminal nueva; comprueba con `tesseract --version`. En Colab, vuelve a ejecutar la sección 1. |
| `Pesos incompletos` o error al descargar pesos | Sin Internet en la primera ejecución o descarga cortada | Conéctate y vuelve a ejecutar; el archivo dañado se reemplaza solo. |
| `Hash incorrecto de los pesos OCR` | Un archivo de `models/fast/` o `models/best/` fue modificado | Borra esas carpetas y vuelve a ejecutar. |
| `Idiomas Tesseract no instalados: spa` | Se usó un Tesseract del sistema sin los pesos del proyecto | Usa los comandos del repositorio (descargan `spa` en `models/fast/`). |
| El PDF da error de páginas | Tiene más de 20 páginas | Divide el PDF o exporta solo las páginas de la factura. |
| Casi todos los campos vacíos | Foto pequeña, borrosa o con sombras; documento manuscrito | Toma otra foto con más luz y de frente; para campos manuscritos, digítalos. |
| La fecha sale como `AMBIGUOUS:` | Día y mes son ≤ 12 | Configura `date_order: "dmy"` en `configs/definitivo.json` para facturas ecuatorianas. |
| Un monto con punto de miles sale vacío (`1.234`) | No se sabe si el punto es decimal o de miles | Revisa el valor a mano; para facturas locales puedes fijar `decimal_separator`. |
| Tarda mucho | Se leen 10 vistas por página en CPU | Es normal: del orden de 10–30 s por página en Colab (estimado). Las segundas lecturas del mismo archivo usan caché cuando se indica una carpeta de caché. |

## 7. Preguntas frecuentes

**¿Mis facturas se suben a algún servidor?**
En tu computador, no: todo se procesa localmente. En Colab, el archivo se sube a la máquina de Google de tu sesión; para facturas de terceros es preferible la ejecución local.

**¿Puedo confiar en los valores sin revisarlos?**
No. En desarrollo el sistema acierta alrededor de 3 de cada 4 campos. Está pensado para **asistir** a la persona que digita, no para reemplazar la revisión.

**¿Por qué no lee mis campos escritos a mano?**
Porque los modelos de Tesseract están entrenados con texto impreso. Los comprobantes manuscritos están fuera del alcance del proyecto.

**¿Comprueba si la factura es válida ante el SRI?**
No. Solo revisa el formato y si los montos cuadran. Para validez tributaria se debe consultar al SRI o el XML firmado de la factura electrónica.

**¿Por qué el total sale vacío si el recibo dice "TOTAL"?**
Puede haber dos totales igual de fuertes, o el OCR no leyó bien el número. El sistema prefiere dejarlo vacío antes que adivinar.

**¿Por qué el `tax_id` o el número de comprobante pueden salir mal aunque el resto esté bien?**
Los datasets públicos no traen esos campos anotados, así que su exactitud no se ha podido medir todavía; se evalúan con la muestra propia.

**¿Qué hago con `resultado.json` y `campos.csv`?**
Contienen el texto completo de la factura (nombres, direcciones, a veces cédulas). Guárdalos como información confidencial y bórralos cuando no los necesites.

## 8. Soporte

- Reporta problemas o sugerencias en [GitHub Issues](https://github.com/Jesusl2202/Document-Scanner/issues), indicando el sistema operativo, el comando usado y el mensaje de error. **No adjuntes facturas reales**; si hace falta un ejemplo, tapa los datos personales.
- Equipo: Sebastián Rojas y Jesús López (Universidad Espíritu Santo, Maestría en Inteligencia Artificial).

---

**Documentos relacionados:** [Planificación](planificacion.md) · [Análisis de datos](analisis_datos.md) · [Arquitectura](arquitectura.md) · [Optimización](optimizacion.md) · [Consideraciones éticas](consideraciones_eticas.md)
