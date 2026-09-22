# Pseudocódigo inicial del pipeline

```text
INICIO

CONFIGURAR:
    campos_objetivo = [
        "ruc_emisor",
        "fecha_emision",
        "numero_comprobante",
        "subtotal",
        "iva",
        "total"
    ]

CARGAR configuración del proyecto

PARA cada documento EN conjunto_de_entrada:

    # 1. Ingesta
    SI documento es PDF:
        convertir páginas a imagen
    SINO:
        cargar imagen

    # 2. Preprocesamiento
    corregir orientación
    corregir perspectiva si es necesario
    convertir a escala de grises
    mejorar contraste
    reducir ruido
    generar imagen_preprocesada

    # 3. OCR
    texto_ocr, cajas_texto = ejecutar_OCR(imagen_preprocesada)

    # 4. Extracción de campos
    ruc_emisor = buscar_RUC(texto_ocr, cajas_texto)
    fecha_emision = buscar_fecha(texto_ocr, cajas_texto)
    numero_comprobante = buscar_numero_comprobante(texto_ocr, cajas_texto)
    subtotal = buscar_subtotal(texto_ocr, cajas_texto)
    iva = buscar_impuesto(texto_ocr, cajas_texto)
    total = buscar_total(texto_ocr, cajas_texto)

    # 5. Normalización
    fecha_emision = normalizar_fecha(fecha_emision)
    subtotal = normalizar_decimal(subtotal)
    iva = normalizar_decimal(iva)
    total = normalizar_decimal(total)

    # 6. Validaciones
    validacion_ruc = validar_RUC_modulo_11(ruc_emisor)

    SI subtotal, iva y total existen:
        validacion_montos = comprobar(
            abs((subtotal + iva) - total) <= tolerancia
        )
    SINO:
        validacion_montos = "NO EVALUABLE"

    validacion_fecha = validar_formato_fecha(fecha_emision)

    # 7. Generar registro estructurado
    resultado = {
        "ruc_emisor": ruc_emisor,
        "fecha_emision": fecha_emision,
        "numero_comprobante": numero_comprobante,
        "subtotal": subtotal,
        "iva": iva,
        "total": total,
        "validacion_ruc": validacion_ruc,
        "validacion_montos": validacion_montos,
        "validacion_fecha": validacion_fecha
    }

    guardar resultado

FIN PARA

# 8. Evaluación
SI existe ground_truth:
    PARA cada campo EN campos_objetivo:
        calcular Accuracy
        calcular Precision
        calcular Recall
        calcular F1

    calcular CER del OCR
    calcular tiempo de procesamiento
    generar reporte de métricas

EXPORTAR resultados a JSON y/o CSV

FIN
```

## Adaptación según dataset

### SROIE
Usar principalmente:
- `date`
- `total`

Los campos `company` y `address` pueden servir como contexto, pero no sustituyen al RUC.

### WildReceipt
Mapeo preliminar:
- `Date_value` -> `fecha_emision`
- `Subtotal_value` -> `subtotal`
- `Tax_value` -> impuesto de referencia
- `Total_value` -> `total`

No asumir que `Tax_value` equivale fiscalmente al IVA ecuatoriano.

### CORD
Mapeo preliminar:
- `subtotal.subtotal_price` -> `subtotal`
- `subtotal.tax_price` -> impuesto de referencia
- `total.total_price` -> `total`

### Muestra RIDE ecuatoriana
Mapeo completo:
- `ruc_emisor`
- `fecha_emision`
- `numero_comprobante`
- `subtotal`
- `iva`
- `total`
