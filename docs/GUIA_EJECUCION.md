# Lector de facturas y comprobantes — avance Semana 2

**Jesús López y Sebastián Rojas · MIAR0545 · Septiembre 2026**

Implementación inicial reproducible de la propuesta de Semana 1. Recibe imágenes o PDF, transcribe con Tesseract, extrae campos con reglas y devuelve JSON con evidencias y alertas. Incluye adaptadores de **SROIE + WildReceipt**, EDA, evaluación por campo y un conector opcional a Google Document AI para la comparación prevista.

## Decisiones conservadas del proyecto

| Componente | Papel en este código |
|---|---|
| SROIE + WildReceipt | Base principal conjunta; adaptadores separados, esquema común, resultados por dataset y agregados. |
| DocILE | Referencia metodológica y plan B. No se descarga ni se convierte automáticamente en este avance. |
| CORD | Apoyo complementario para montos/ítems. No sustituye las bases principales; adaptador pospuesto. |
| Tesseract neuronal LSTM + reglas | Línea base ejecutable en CPU, sin entrenar una red desde cero. |
| Google Document AI | Comparador preentrenado, invocado únicamente si se configura y selecciona explícitamente. |
| OCR + ML clásico / Random Forest | Posible evolución descrita en Semana 1. No reemplaza al comparador Document AI ni se presenta como modelo ya entrenado. |
| GNN, Transformers propios y OCR-free | Análisis bibliográfico y trabajo futuro, sin implementar entrenamientos en este avance. |

**No se atribuye a Document AI una arquitectura interna específica como LayoutLMv3.** La API es un servicio preentrenado y su comportamiento se debe medir. No se garantiza capa gratuita; el código local funciona sin cuenta de nube.

## Qué está implementado

- Importación de las anotaciones de ambas bases sin convertir nombre de empresa en identificador fiscal.
- Manifiesto común con seis campos: `tax_id`, `date`, `document_number`, `subtotal`, `tax`, `total`.
- Estados de referencia: `annotated`, `unannotated`, `ambiguous`; el evaluador también admite `absent` cuando una revisión humana confirme ausencia.
- Separación determinista de entrenamiento/validación dentro del train original, test oficial reservado y cuarentena de duplicados exactos.
- EDA con dimensiones, cobertura por campo, archivos faltantes, cajas problemáticas y duplicados.
- Preprocesamiento en gris y autocontraste sin alterar coordenadas, OCR con caché y evidencia por palabra/línea.
- Extracción inicial con abstención cuando hay candidatos igualmente plausibles.
- Formato de fecha e identificador configurable; cuadre aritmético opcional.
- Exactitud normalizada, precisión, recall, F1, soporte, CER aproximado sensible al orden, latencia y fallos.
- Comparación que exige los mismos documentos, anotaciones y normalización.
- PDF: extracción separada por página; no fusiona automáticamente facturas multipágina.
- Pruebas automatizadas y ejemplos sintéticos claramente identificados.

## 1. Instalar en Windows / VS Code

Recomendado: **Python 3.11 o 3.12**. Para aproximar el entorno medido, ver `requirements-repro.txt` y `reports/verified_versions.json`; la instalación general usa rangos compatibles. Abrir la carpeta de este proyecto en VS Code y una terminal PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[notebook]"
```

Instalar además el **programa Tesseract**, no solo una biblioteca de Python. Consultar las opciones para Windows en https://tesseract-ocr.github.io/tessdoc/Installation.html. Añadirlo al PATH o establecer `ocr.executable` en `configs/default.json` (en JSON usar `C:/Program Files/Tesseract-OCR/tesseract.exe`).

```powershell
.\.venv\Scripts\python.exe -m lector_facturas doctor
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m lector_facturas extract data/samples/synthetic_receipt.png --out outputs/demo
```

El ejemplo sintético comprueba la instalación; **no acredita desempeño sobre SROIE o WildReceipt**. Su identificador e importes son ficticios.

## 2. Instalar en Google Colab

Subir y descomprimir el ZIP, entrar en la carpeta que contiene este README y ejecutar `notebooks/Avance_Semana2.ipynb`. El notebook contiene las celdas de instalación, rutas, importación, EDA y primera corrida. Los comandos de Linux equivalentes son:

```bash
sudo apt-get update
sudo apt-get install -y tesseract-ocr tesseract-ocr-eng tesseract-ocr-spa
python -m pip install -e ".[notebook]"
python -m lector_facturas doctor
```

`eng` es el idioma inicial para comparar las bases; `eng+spa` requiere ambos paquetes instalados. No cambiar idiomas o PSM usando los resultados de test.

## 3. Colocar las bases

Mantener las imágenes y anotaciones originales. **No mezclar las carpetas de SROIE con las de WildReceipt.**

- SROIE: `data/raw/sroie/train/img/`, `train/box/`, `train/entities/`; estructura equivalente para `test/` si está disponible.
- WildReceipt: `data/raw/wildreceipt/class_list.txt`, `train.txt`, `test.txt`, `image_files/`.
- Los nombres de imágenes de SROIE deben coincidir con los IDs en `.txt` o `.json` de entidades y `.txt` de cajas.
- El adaptador espera la estructura SROIE2019 habitual de la distribución v2; otras distribuciones necesitan reorganizar carpetas, no editar las etiquetas.
- Para las pruebas reales realizadas, consultar `reports/AVANCE_EJECUTADO.md` y la procedencia. No se incluyen las imágenes originales de terceros en este ZIP.

Fuentes y condiciones: `docs/DATOS_Y_LICENCIAS.md`. Una ruta de descarga pública no sustituye verificar condiciones de uso de su distribución.

```bash
python -m lector_facturas prepare --sroie data/raw/sroie --wildreceipt data/raw/wildreceipt
python -m lector_facturas eda
```

Salidas: `data/processed/manifest.jsonl`, `outputs/eda/summary.json`, `coverage.csv`, `incidents.csv`, `documents.csv`, `coverage.png` y `EDA.md`.

Las rutas de imágenes del manifiesto son absolutas: **regenerarlo al cambiar de computadora**. El contenido original no se copia ni se modifica.

## 4. Ejecutar la primera evaluación

```bash
python -m lector_facturas run --engine tesseract --split validation --limit-per-dataset 20 --out outputs/baseline_v1
```

El límite es **por dataset**, no el tamaño del entrenamiento. `0` procesa toda la partición. La selección es reproducible con semilla 42; no escoge ejemplos favorables. Para otra corrida usar otro directorio (`baseline_v2`), evitando sobrescribir resultados.

Archivos por ejecución:

| Archivo | Uso |
|---|---|
| `config.json`, `environment.json` | Configuración, versiones y entorno medidos. |
| `evaluation_manifest.jsonl` | Documentos exactos utilizados y referencias. |
| `predictions.jsonl` | Valores, texto OCR, evidencias, alertas, tiempos y errores por documento. |
| `evaluation/metrics.csv` | Métricas por dataset y campo, más agregados. |
| `evaluation/errors.csv` | Predicción frente a referencia; filtrar `correct == 0`. |
| `evaluation/cer.csv` | Distancia de edición y denominador por documento. |
| `evaluation/summary.json`, `RESULTADOS.md` | Resumen utilizable para el avance. |

Los resultados con caché no se incluyen en la latencia. La primera transcripción guardada conserva su duración, pero una corrida con caché no se presenta como tiempo real extremo a extremo. No presentar exactitud global sin detallar qué campos tienen soporte.

## 5. Comparar con Document AI cuando tengan acceso

Consultar `docs/DOCUMENT_AI.md`. El SDK es opcional:

```bash
python -m pip install -e ".[cloud]"
```

Configurar credenciales ADC y `DOCUMENTAI_PROCESSOR_RESOURCE` con un procesador y versión propios. La nube recibe los documentos seleccionados al ejecutar este comando y puede generar cargos:

```bash
python -m lector_facturas run --engine google --allow-cloud --split validation --limit-per-dataset 20 --out outputs/documentai_v1
python -m lector_facturas compare --a outputs/baseline_v1 --b outputs/documentai_v1 --out outputs/comparacion_v1
```

Usar el mismo manifiesto, semilla, partición y límite. Para recibos elegir un procesador compatible con recibos; para facturas, uno compatible con facturas, y revisar `entity_map` antes de medir. La salida JSON sin entidades no debe confundirse con un extractor funcional: el evaluador reportará omisiones.

## Qué presentar en Semana 2

1. **Ficha de una página:** selección Tesseract + Document AI, justificación, flujo, riesgos y hallazgos reales del EDA. La ficha anterior que proponía sustituir Document AI por Random Forest debe corregirse; ver `docs/TEXTO_PARA_FICHA.md`.
2. **Repositorio:** código, README, notebook y referencias. El PDF de la ficha no exige pegar el código.
3. **Evidencia:** reporte EDA y primera evaluación; declarar tamaño de muestra, partición y limitaciones. No presentar un ensayo como resultado final.
4. **Pendiente de acceso:** ejecución real de Document AI y comparación cuantitativa. El conector implementado no equivale a API validada.

El objetivo de Semana 1 (≥70% de exactitud; ≥90% de procesamiento; al menos 30 documentos de prueba final) **sigue siendo una meta**, no una garantía. La muestra propia de 30–50 documentos debe reservarse para generalización final, sin usarla para diseñar reglas.

## Límites actuales y siguientes iteraciones

Las reglas son iniciales: requieren revisión de errores de desarrollo, en particular formatos de fecha no numéricos, etiquetas diversas, recibos inclinados y varios impuestos/totales. Todavía no hay corrección de perspectiva/rotación, fusión multipágina, validación tributaria por país, interfaz ni integración contable. Los campos fiscales y número de comprobante necesitan anotaciones propias para medirlos; no se fabrican desde otras etiquetas.

El código no entrena modelos ni usa test para elegir reglas. Random Forest sigue en la hoja de ruta si la línea base no generaliza; su incorporación requerirá alineación OCR–etiquetas y evaluación separada del texto de referencia.

## Organización y trabajo en pareja

`docs/ARQUITECTURA_Y_JUSTIFICACION.md` explica las decisiones. Jesús puede liderar adaptadores, EDA y métricas; Sebastián, OCR, integración Document AI y revisión de errores; ambos revisan particiones y la ficha. Es una propuesta de reparto, no una asignación confirmada.

Para llevarlo al repositorio existente, copiar estos archivos en una rama de trabajo y conservar el historial previo. No subir `data/raw`, credenciales ni documentos propios sin anonimizar. No se ha modificado ni publicado tu repositorio remoto desde este paquete.
