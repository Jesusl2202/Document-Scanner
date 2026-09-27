# Texto actualizado para la ficha de Semana 2

**Usar este contenido para corregir la ficha anterior: no se sustituye Document AI por Random Forest.** Ajustar en Word a una página según la plantilla docente; este archivo es contenido editable, no una ficha diagramada.

**Autores:** Sebastián Rojas y Jesús López. **Fecha:** 27 de septiembre de 2026.
**Proyecto:** Sistema de Extracción y Validación de Datos de Facturas y Comprobantes de Compra mediante OCR y Document AI.

**Técnicas seleccionadas.** (1) OCR neuronal LSTM preentrenado con Tesseract, seguido de reglas de extracción como línea base. (2) Procesador documental preentrenado Google Document AI, como solución de comparación. Las reglas son posprocesamiento; no se cuentan como otra técnica de IA. No se entrenará una red desde cero ni se atribuye una arquitectura interna específica al servicio comercial.

**Justificación.** Problema: las entradas son imágenes/PDF no estructurados; la salida contiene identificador fiscal, fecha, número de comprobante, subtotal, impuesto y total. El análisis comparativo de cinco familias conserva el enfoque aplicado de Semana 1. Datos/recursos: la combinación principal SROIE + WildReceipt permite evaluar campos complementarios. El EDA ejecutado comprende 1.881 documentos de desarrollo tras controlar duplicados; los identificadores fiscales y números de comprobante carecen de anotación estándar. El baseline funciona en CPU y la API requiere acceso propio. Interpretabilidad: se conservan texto, cajas, reglas o entidades y alertas para revisar errores; las puntuaciones no se interpretan como certeza calibrada.

**Arquitectura y EDA.** Imagen/PDF → preprocesamiento/renderizado → Tesseract y reglas / Document AI → esquema común → normalización y controles configurables → JSON y evaluación. El EDA registra cobertura, geometría, codificación y duplicados; el test oficial queda reservado. En la prueba inicial de 20 documentos por fuente, Tesseract procesó 40/40 sin errores, con 36/103 valores anotados correctos (35,0%); la meta ≥70% sigue pendiente. Evidencias: `reports/eda/EDA.md`, `reports/AVANCE_EJECUTADO.md` y `docs/COMPARATIVA_TECNICAS.md`. La API está integrada en código, pero su evaluación real aún no se ha ejecutado.

**Riesgos y mitigación.** La variación de formato, las omisiones OCR y las referencias ambiguas limitan la extracción. Se revisarán errores por fuente y se ajustarán reglas solo con desarrollo; los campos sin etiqueta requerirán anotación propia independiente de la prueba final.

**Conclusión.** Se conserva Tesseract frente a Document AI y se fundamenta la siguiente iteración en el EDA y la línea base medidos.
