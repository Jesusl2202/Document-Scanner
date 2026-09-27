# Arquitectura y decisiones justificadas

## Correspondencia con Semana 1

El documento entregado, apartado 3.5, selecciona **la combinación SROIE + WildReceipt**; no WildReceipt solo. El apartado 6.3 incluye Tesseract frente a una API Document AI. Se mantienen esas decisiones. No hace falta entrenar una arquitectura nueva para obtener un primer avance funcional.

La denominación «OCR clásico» de la tabla bibliográfica describe la familia del pipeline; esta implementación usa específicamente el motor **LSTM preentrenado de Tesseract (`--oem 1`)**, no un OCR entrenado por el equipo. Las expresiones regulares son posprocesamiento determinista, no una segunda técnica de IA. La segunda solución elegida es el procesador preentrenado de Document AI.

## Flujo

1. Lectura de anotaciones originales por adaptador.
2. Manifiesto común con identificación de fuente, partición, hash, referencias disponibles e incidencias.
3. EDA de desarrollo y revisión de cobertura: define qué campos se pueden evaluar.
4. Imagen: gris/autocontraste sin mover píxeles. PDF: renderizado por página.
5. Rama A: OCR Tesseract → texto/cajas → reglas de extracción con evidencia y abstención.
6. Rama B: Google Document AI → entidades del procesador → mapeo al mismo esquema de campos.
7. Normalización común y validaciones configurables → JSON.
8. Evaluación sobre los mismos documentos → tablas de soporte, exactitud, F1, errores, CER y tiempos.

El paquete divide módulos por responsabilidad: `datasets`, `eda`, `ocr`, `extraction`, `google_ai`, `evaluation`, `cli`. El notebook orquesta estos módulos; no duplica la lógica ni es requisito para ejecutar en terminal.

## Datos y etiquetas

| Campo común | SROIE | WildReceipt | Evaluación |
|---|---|---|---|
| tax_id | No | No | Anotación propia necesaria. |
| date | date | Date_value | Disponible según documento. |
| document_number | No | No | Anotación propia necesaria. |
| subtotal | No | Subtotal_value | WildReceipt donde haya una referencia única. |
| tax | No | Tax_value | WildReceipt; no se interpreta automáticamente como IVA ecuatoriano. |
| total | total | Total_value | Disponible según documento. |

`company` / `Store_name_value` no se convierten en RUC. El número de comprobante no aparece como categoría estándar WildReceipt. Corregir esas afirmaciones de Semana 1. «25 categorías» suele excluir Ignore; se lee `class_list.txt` real, sin depender de esa cifra.

Cuando hay varios valores anotados de un campo, se marca `ambiguous`, no se selecciona arbitrariamente uno. En próximas iteraciones se puede definir agregación de impuestos si el esquema del documento lo permite. Sin etiqueta no se asume ni acierto ni error.

## Evaluación sin fuga

Se reserva el test oficial. Dentro del train original, un hash de imagen con semilla fija determina train/validation. Duplicados idénticos se ponen en cuarentena; se da prioridad a conservar el test oficial. La separación por hash es un control mínimo: puede haber emisores o plantillas similares entre particiones. La prueba final debería agrupar emisores/plantillas cuando se cuente con esa información.

SROIE y WildReceipt comparten esquema, no necesariamente todos los campos. Se reportan sus resultados por separado. El agregado micro global pondera por instancias anotadas, por lo que no debe presentarse como una comparación equilibrada entre datasets ni como benchmark oficial.

- Exactitud por campo: valores normalizados correctos / documentos con referencia utilizable de ese campo.
- Valor equivocado: un FP y un FN. Valor omitido: FN. Campo sin anotación: fuera del cálculo.
- Fallo de ejecución: no se elimina; afecta procesamiento y extracción de los campos anotados.
- CER: edición Levenshtein / caracteres de referencia; normaliza mayúsculas y espacios. El orden geométrico de cajas puede diferir del orden de lectura, por lo que este CER es diagnóstico, no el oficial del reto.
- Latencia: reloj real extremo a extremo por documento. Las corridas con caché quedan fuera del resumen de latencia.

No se afinan reglas usando test. Después de revisar resultados de validation, los cambios deben versionarse y reevaluarse; el test final permanece intacto.

## Por qué reglas y CPU primero

El plazo es de seis semanas, hay dos integrantes y no se garantiza GPU. Un baseline reproducible permite distinguir errores de OCR, selección del campo y normalización. Las evidencias por línea facilitan diagnosticar errores y justificar cambios. La API sirve como comparador, no como dependencia del funcionamiento local.

## Riesgos controlados y pendientes

- Imágenes faltantes/corruptas: incidencias explícitas y fallos contabilizados.
- Geometría inconsistente: se registra; no se usan cajas para entrenar en esta fase. La corrección de perspectiva queda pendiente porque requeriría transformar también las cajas.
- Fechas/monedas ambiguas: no se infiere país. Se conserva ambigüedad o texto original para comparar.
- Varios totales: abstención y revisión manual, sin elegir el importe más grande por defecto.
- Validación aritmética: no activa si podrían existir descuentos/propinas/cargos. No acredita validez fiscal.
- Servicios externos: configuración y ejecución explícitas, sin credenciales en archivos del proyecto y sin afirmar gratuidad permanente.
- Muestra inicial pequeña: no demuestra generalización; conservar tamaño, IDs, configuración y entorno en cada reporte.

## Continuación semanal

Semana 2: EDA, baseline real y conector comparador. Semanas 3–4: ampliar muestras, revisar errores por fuente, ejecutar Document AI, ajustar reglas sobre desarrollo. Semanas 4–5: decidir si hace falta ML clásico, ampliar idiomas/preprocesamiento, revisar confiabilidad y tiempos. Semana 6: evaluación final independiente con muestra propia, documentación y presentación. Estas etapas deben adaptarse al calendario docente real.
