# Referencias de datasets

| Dataset | Uso en el proyecto | Campos / etiquetas útiles | Observación |
|---|---|---|---|
| SROIE | Dataset base para OCR y extracción inicial | company, date, address, total | No representa el formato RIDE ecuatoriano |
| WildReceipt | Generalización ante formatos no vistos | Date_value, Subtotal_value, Tax_value, Total_value | Verificar licencia antes de redistribuir |
| DocILE | Referencia metodológica de facturas y generalización | anotaciones KILE/LIR | Requiere seguir el proceso oficial de acceso |
| CORD | Plan B / parsing de subtotal, impuesto, total e ítems | subtotal.subtotal_price, subtotal.tax_price, total.total_price | CC BY 4.0 según el repositorio oficial |
| Muestra RIDE | Evaluación final en Ecuador | ruc_emisor, fecha_emision, numero_comprobante, subtotal, iva, total | Debe anonimizarse |

## Fuentes

### SROIE
- Paper: ICDAR2019 Competition on Scanned Receipt OCR and Information Extraction.
- Dataset de apoyo: https://huggingface.co/datasets/jsdnrs/ICDAR2019-SROIE

### WildReceipt
- Paper: H. Sun, Z. Kuang, X. Yue, C. Lin y W. Zhang, “Spatial Dual-Modality Graph Reasoning for Key Information Extraction”, 2021.
- Implementación / documentación: https://github.com/open-mmlab/mmocr

### DocILE
- Repositorio oficial: https://github.com/rossumai/docile
- El repositorio indica un procedimiento de descarga mediante token.

### CORD
- Repositorio oficial: https://github.com/clovaai/cord
- Licencia: Creative Commons Attribution 4.0.

## Recomendación para samples/

No subir el dataset completo al repositorio.

En `samples/` conviene incluir únicamente:
1. uno o pocos ejemplos cuya redistribución esté permitida;
2. archivos sintéticos creados por el equipo; o
3. ejemplos propios totalmente anonimizados.

Para datasets externos, es preferible documentar la fuente y proporcionar un script o instrucciones de descarga.
