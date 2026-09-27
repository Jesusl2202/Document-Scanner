# Sistema de Extracción y Validación de Datos de Facturas y Comprobantes de Compra mediante OCR y Document AI

Proyecto integrador de la Maestría en Inteligencia Artificial.

## Descripción

Este proyecto desarrolla un prototipo para extraer y validar
automáticamente información de facturas y comprobantes de compra
mediante OCR y herramientas de Document AI.

El sistema procesa fotografías o archivos PDF y busca estructurar
seis campos principales:

- Identificador fiscal del emisor.
- Fecha de emisión.
- Número de comprobante.
- Subtotal.
- Impuesto.
- Total.

El alcance contempla documentos de distintos formatos y procedencias.
Cuando corresponda a un comprobante ecuatoriano, el identificador
fiscal y el impuesto podrán representar el RUC y el IVA, respectivamente.

La base principal de desarrollo y evaluación combina SROIE y
WildReceipt. Se complementará con una muestra propia de comprobantes
para evaluar la generalización a documentos no utilizados durante
el desarrollo.

El flujo general contempla preprocesamiento, OCR, extracción de
campos, normalización, validaciones configurables y generación de
una salida estructurada.

## Objetivo general

Desarrollar, durante seis semanas y con un equipo de dos integrantes,
un pipeline de software que extraiga y valide automáticamente el
identificador fiscal del emisor, la fecha, el número de comprobante,
el subtotal, el impuesto y el total de facturas o recibos recibidos
como fotografías o archivos PDF.

El proyecto busca evaluar el sistema sobre al menos 30 documentos
de prueba, alcanzar una exactitud de extracción mínima del 70%
y aplicar reglas configurables de validación de negocio.

Estos valores corresponden a objetivos del proyecto y no a resultados
ya alcanzados.
## Arquitectura propuesta

```text
Imagen / PDF
    |
    v
Preprocesamiento
(corrección de perspectiva, contraste, limpieza)
    |
    v
OCR
(Tesseract / Document AI)
    |
    v
Extracción de campos
(regex + reglas + posición del texto)
    |
    v
Validación
(RUC, fecha, subtotal + IVA = total)
    |
    v
Salida estructurada
(JSON / CSV)
    |
    v
Evaluación
(Accuracy, Precision, Recall, F1, CER, tiempo)
```

## Datasets considerados

### 1. SROIE
Forma parte de la base principal junto con WildReceipt. Se utiliza para desarrollar y evaluar el OCR y la extracción de fecha y total, de acuerdo con sus anotaciones disponibles.

Campos especialmente útiles para este proyecto:

- `company`
- `date`
- `address`
- `total`

Referencia:
- ICDAR 2019 Robust Reading Challenge on Scanned Receipts OCR and Information Extraction.
- Recurso de apoyo: https://huggingface.co/datasets/jsdnrs/ICDAR2019-SROIE

### 2. WildReceipt
Forma parte de la base principal junto con SROIE. Aporta variedad de formatos y anotaciones de fecha, subtotal, impuesto y total. Los campos se evalúan únicamente cuando existe una referencia utilizable.

Etiquetas de interés para el proyecto:

- `Date_value`
- `Subtotal_value`
- `Tax_value`
- `Total_value`

Referencia:
- H. Sun et al., *Spatial Dual-Modality Graph Reasoning for Key Information Extraction*, 2021.
- Recurso de apoyo: https://github.com/open-mmlab/mmocr

**Nota:** antes de redistribuir muestras de WildReceipt dentro de este repositorio debe verificarse la licencia específica del dataset.

### 3. DocILE
Se utiliza como referencia metodológica para evaluar generalización entre formatos. Se considera como plan B para ampliar los datos de desarrollo y evaluación si las bases principales resultan insuficientes.

Referencia:
- https://github.com/rossumai/docile

### 4. CORD
Se utiliza como recurso complementario para estudiar la estructura de montos e ítems de línea. No constituye la base principal de evaluación.

Campos de interés:

- `menu.nm`
- `menu.price`
- `subtotal.subtotal_price`
- `subtotal.tax_price`
- `total.total_price`

Referencia:
- https://github.com/clovaai/cord

Licencia reportada por el proyecto: CC BY 4.0.

### 5. Muestra propia RIDE
Se reunirá una muestra de aproximadamente 30 a 50 documentos,
procedentes de al menos tres emisores distintos, para la evaluación
final de generalización.

Esta muestra podrá incluir comprobantes ecuatorianos y se mantendrá
separada de los documentos utilizados para ajustar las reglas.

Se revisarán manualmente los seis campos del proyecto, indicando
cuándo un valor está presente, ausente o resulta ilegible o ambiguo.

Los documentos reales no se publicarán sin la anonimización
y autorización correspondientes.

Campos esperados:

- `ruc_emisor`
- `fecha_emision`
- `numero_comprobante`
- `subtotal`
- `iva`
- `total`

Los comprobantes reales no deben publicarse sin anonimización y autorización para su uso.

## Estructura del repositorio

```text
lector_facturas_ecuador/
├── README.md
├── requirements.txt
├── .gitignore
├── LICENSE_NOTES.md
├── src/
│   └── pseudocodigo_pipeline.md
├── samples/
│   └── README.md
└── docs/
    └── datasets.md
```

### Disponibilidad de anotaciones

Los datasets no contienen necesariamente anotaciones de los seis
campos del proyecto.

SROIE permite evaluar directamente fecha y total. WildReceipt
aporta referencias de fecha, subtotal, impuesto y total, según
el documento.

El nombre del comercio no se considera equivalente al identificador
fiscal. Tampoco se supone que estas bases incluyan una etiqueta
estándar de número de comprobante.

Los campos sin anotación se excluyen de las métricas correspondientes;
no se contabilizan automáticamente como aciertos o errores.

## Pseudocódigo

El pseudocódigo inicial se encuentra en:

`src/pseudocodigo_pipeline.md`

## Tecnologías previstas

- Python
- OpenCV
- Tesseract OCR
- pytesseract
- pandas
- expresiones regulares
- Google Colab
- Google Document AI o AWS Textract para comparación puntual

## Métricas

Las principales métricas propuestas son:

- Accuracy por campo
- Precision por campo
- Recall por campo
- F1-score por campo
- Character Error Rate (CER)
- Tiempo de procesamiento por comprobante

## Criterios iniciales de éxito

- Procesar sin errores al menos el 90% de los comprobantes de prueba.
- Alcanzar al menos 70% de exactitud de extracción en los campos clave.
- Implementar pruebas para validación de RUC y cuadre de montos.
- Mantener documentación reproducible del pipeline.

## Autores

- Sebastián Rojas
- Jesús López

## Implementación y documentación técnica

El proyecto se desarrolla de forma incremental durante las seis semanas
del curso. Este README presenta el problema, los objetivos, los datos,
la arquitectura y los criterios de éxito.

Las instrucciones para instalar el entorno y ejecutar el código de
Semana 2 se encuentran en la
[Guía de instalación y ejecución](docs/GUIA_EJECUCION.md).

El diseño inicial puede consultarse en el
[Pseudocódigo del pipeline](src/pseudocodigo_pipeline.md).

La información de las fuentes de datos se encuentra en
[Referencias de datasets](docs/datasets.md).

- [Notebook del avance](notebooks/Avance_Semana2.ipynb)
- [Arquitectura y justificación](docs/ARQUITECTURA_Y_JUSTIFICACION.md)
- [Comparación de técnicas](docs/COMPARATIVA_TECNICAS.md)
- [Descarga y documentación de datos](docs/DATOS_Y_LICENCIAS.md)
- [Reporte de la ejecución de referencia](reports/AVANCE_EJECUTADO.md)
- [Ejemplos sintéticos](data/samples/)

## Estado del proyecto

Proyecto académico en desarrollo.
