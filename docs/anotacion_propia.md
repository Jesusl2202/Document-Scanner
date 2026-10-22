# Muestra propia y campos no cubiertos

Los seis campos permanecen en la salida del sistema, pero SROIE y WildReceipt no permiten evaluar por sí solos identificador fiscal y número de comprobante. Extraer un patrón no demuestra que sea el valor correcto.

Para las etapas posteriores reservar 30–50 documentos propios de al menos tres emisores como **prueba final**, conforme a Semana 1. Si se necesita ajustar reglas para esos campos, usar documentos de desarrollo distintos; no consumir el conjunto final.

Crear una tabla de referencia revisada por dos integrantes con columnas:

`document_id, image, country, currency, issuer_group, tax_id, date, document_number, subtotal, tax, total, status_tax_id, status_date, status_document_number, status_subtotal, status_tax, status_total, reviewed_by`

Para cada status usar `annotated` (valor legible confirmado), `absent` (ausencia confirmada), `unannotated` (sin revisar) o `ambiguous` (ilegible o múltiples interpretaciones). Un vacío no debe convertirse automáticamente en ausencia.

Usar solo comprobantes **impresos o digitales**. Si la fecha, los montos, el RUC o el número están escritos a mano, el documento queda fuera de la muestra: el sistema no está diseñado para texto manuscrito y medirlo mezclaría dos problemas distintos.

Conservar identificadores como texto para no perder ceros iniciales. Definir moneda y separadores por documento. No convertir nombre del emisor en identificación tributaria. No publicar números o documentos privados sin revisar anonimización y autorización.

El adaptador automático de esta tabla propia queda para la siguiente iteración; actualmente los adaptadores productivos son SROIE y WildReceipt. La extracción de documentos individuales ya funciona con `extract` y permite revisar sus evidencias.


## ZIP de test nuevo para la evaluación aleatoria

En la raíz del ZIP: `anotaciones.jsonl` y una carpeta `imagenes/`. Una línea JSON por factura. Ejemplo de FORMATO, no datos reales de evaluación:

```json
{"id":"factura_001","image":"imagenes/factura_001.png","gold":{"date":{"status":"annotated","value":"21/10/2026"},"subtotal":{"status":"annotated","value":"100.00"},"tax":{"status":"annotated","value":"15.00"},"total":{"status":"annotated","value":"115.00"}}}
```

Sustituye todos los valores por los que realmente se ven en cada imagen y verifica la transcripción manualmente. `annotated` significa valor verificado; `absent` exige `value:null` y significa que realmente no aparece; `unannotated` significa no evaluado. Los campos omitidos quedan no anotados. No declares ausente un dato que simplemente cuesta leer. Usa imágenes PNG/JPEG; para PDF, anota por página tras convertirlas a imágenes. No incluyas documentos usados para ajustar las reglas. El identificador debe ser único, pero renombrar no evita el control por SHA256.

La etiqueta `externas` se informa separada de SROIE/WildReceipt. Su rendimiento no se atribuye a WildReceipt. El porcentaje depende del soporte anotado; para medir los campos débiles, verifica subtotal, impuesto y total cuando sean visibles.
