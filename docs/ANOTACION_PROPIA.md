# Muestra propia y campos no cubiertos

Los seis campos permanecen en la salida del sistema, pero SROIE y WildReceipt no permiten evaluar por sí solos identificador fiscal y número de comprobante. Extraer un patrón no demuestra que sea el valor correcto.

Para las etapas posteriores reservar 30–50 documentos propios de al menos tres emisores como **prueba final**, conforme a Semana 1. Si se necesita ajustar reglas para esos campos, usar documentos de desarrollo distintos; no consumir el conjunto final.

Crear una tabla de referencia revisada por dos integrantes con columnas:

`document_id, image, country, currency, issuer_group, tax_id, date, document_number, subtotal, tax, total, status_tax_id, status_date, status_document_number, status_subtotal, status_tax, status_total, reviewed_by`

Para cada status usar `annotated` (valor legible confirmado), `absent` (ausencia confirmada), `unannotated` (sin revisar) o `ambiguous` (ilegible o múltiples interpretaciones). Un vacío no debe convertirse automáticamente en ausencia.

Conservar identificadores como texto para no perder ceros iniciales. Definir moneda y separadores por documento. No convertir nombre del emisor en identificación tributaria. No publicar números o documentos privados sin revisar anonimización y autorización.

El adaptador automático de esta tabla propia queda para la siguiente iteración; actualmente los adaptadores productivos son SROIE y WildReceipt. La extracción de documentos individuales ya funciona con `extract` y permite revisar sus evidencias.
