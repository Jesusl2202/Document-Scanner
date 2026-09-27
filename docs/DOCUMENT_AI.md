# Comparador Google Document AI

El proyecto conserva la comparación planteada en Semana 1. El adaptador llama a `DocumentProcessorServiceClient.process_document` y convierte entidades del procesador a los seis campos comunes. No entrena un modelo ni asume qué arquitectura utiliza internamente el servicio.

## Configuración

1. En un proyecto propio de Google Cloud, habilitar Document AI y crear el procesador adecuado. Para recibos evaluar Expense Parser; para facturas evaluar Invoice Parser. Comprobar soporte de idioma, región, límites, esquema y precios en la documentación oficial.
2. Registrar la versión del procesador. Es preferible usar una ruta completa `projects/PROYECTO/locations/REGION/processors/ID/processorVersions/VERSION`, para evitar cambios silenciosos entre corridas.
3. Instalar el extra `pip install -e ".[cloud]"`.
4. Configurar Application Default Credentials según la documentación de Google. No subir archivos de credenciales al repositorio ni incorporarlos al notebook compartido.
5. Establecer la variable de entorno `DOCUMENTAI_PROCESSOR_RESOURCE` o su equivalente en la configuración local.
6. Revisar `google.entity_map`: el mapeo depende del procesador concreto. Un campo que el proveedor no devuelve permanece nulo. No convertir `supplier_name` en `tax_id`.

PowerShell:

```powershell
$env:DOCUMENTAI_PROCESSOR_RESOURCE = "projects/MI_PROYECTO/locations/us/processors/MI_ID/processorVersions/MI_VERSION"
python -m lector_facturas run --engine google --allow-cloud --split validation --limit-per-dataset 20 --out outputs/documentai_v1
```

Linux / Colab, usar `os.environ` sin incluir secretos en celdas compartidas:

```python
import os
os.environ['DOCUMENTAI_PROCESSOR_RESOURCE'] = 'projects/MI_PROYECTO/locations/us/processors/MI_ID/processorVersions/MI_VERSION'
```

## Protocolo de comparación

Ejecutar ambas soluciones sobre el mismo manifiesto, partición, semilla, límite y normalización. El comando `compare` verifica equivalencia de IDs, hashes y referencias. Conservar aciertos, errores, tasa de fallos y duración, no solo F1.

Document AI se usa aquí como solución completa (OCR + entidades). Por tanto, se compara **Tesseract + reglas contra el servicio completo**; no se atribuye toda la diferencia de exactitud al motor OCR. El CER es diagnóstico de transcripción y la extracción mide una tarea distinta.

## Estado

Conector implementado y transformación de entidades comprobada con pruebas unitarias. **No se ejecutó la API con una cuenta real en la preparación del paquete.** Debe validarse después de configurar acceso. Las pruebas unitarias no verifican autenticación, disponibilidad, cobros ni compatibilidad de un procesador concreto.

Fuentes oficiales:

- https://docs.cloud.google.com/document-ai/docs/samples/documentai-process-specialized-document
- https://docs.cloud.google.com/document-ai/docs/processors-list
- https://docs.cloud.google.com/document-ai/docs/authentication
- https://cloud.google.com/document-ai/pricing
