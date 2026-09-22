# Sistema de Extracción y Validación de Datos de Comprobantes de Compra Ecuatorianos

Proyecto integrador de la Maestría en Inteligencia Artificial.

## Descripción

Este proyecto desarrolla un prototipo para extraer y validar automáticamente información de comprobantes de compra ecuatorianos mediante OCR y técnicas de Document AI.

El sistema procesa fotografías o archivos PDF de representaciones impresas de facturas electrónicas (RIDE) y busca estructurar seis campos principales:

- RUC del emisor
- Fecha de emisión
- Número de comprobante
- Subtotal
- IVA
- Total

El flujo general contempla preprocesamiento del documento, OCR, extracción de campos, validación de reglas y generación de una salida estructurada.

## Objetivo general

Desarrollar, durante seis semanas, un pipeline de software que extraiga y valide automáticamente los campos clave de al menos 30 comprobantes de compra ecuatorianos, alcanzando una exactitud mínima de extracción del 70% y aplicando reglas de validación fiscal específicas del SRI.

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
Dataset base para el desarrollo y evaluación inicial del pipeline OCR y de extracción.

Campos especialmente útiles para este proyecto:

- `company`
- `date`
- `address`
- `total`

Referencia:
- ICDAR 2019 Robust Reading Challenge on Scanned Receipts OCR and Information Extraction.
- Recurso de apoyo: https://huggingface.co/datasets/jsdnrs/ICDAR2019-SROIE

### 2. WildReceipt
Dataset complementario para evaluar extracción de información y generalización ante formatos no vistos.

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
Se utilizará principalmente como referencia metodológica para evaluación de facturas y generalización a plantillas no vistas.

Referencia:
- https://github.com/rossumai/docile

### 4. CORD
Dataset complementario / Plan B para revisar parsing de subtotal, impuestos, total e ítems de línea.

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
Se construirá una muestra local de aproximadamente 30 a 50 comprobantes ecuatorianos anonimizados.

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

## Estado del proyecto

Proyecto académico en desarrollo.
