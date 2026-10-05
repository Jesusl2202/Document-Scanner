# Diseño y alcance

Proyecto integrador de extracción de seis campos: identificador fiscal, fecha, número de comprobante, subtotal, impuesto y total. Objetivos de evaluación: exactitud global de campos >=70 % y procesamiento >=90 %.

Se eligió Tesseract preentrenado por disponibilidad de tiempo y recursos. No se entrenan pesos. Cada imagen se lee en cinco combinaciones: original/PSM6, ampliada/PSM6, Otsu/PSM6, ampliada/PSM3 y ampliada/PSM11. Las coordenadas vuelven al tamaño original. Los PDF se separan en páginas.

`candidate_rules.py` genera candidatos iniciales; `geometry.py` agrupa palabras; `consensus.py` combina etiquetas, coincidencias entre lecturas y comprobaciones aritméticas. Estos módulos cooperan: no son modelos alternativos entre los que haya que escoger. `extraction.py` expone una única implementación.

No se acreditan curvas de entrenamiento ni overfitting de pesos: solo existe comparación de configuraciones de inferencia y posible sobreajuste de reglas a ejemplos revisados. Para la actividad académica se deben explicar esa distinción y la separación desarrollo/selección/test.

Se conserva la heurística que usa subtotal como total cuando faltan total e impuesto, con alerta `total:from_subtotal`. Requiere revisión. Las validaciones de formato no acreditan validez fiscal; los PDF multipágina no se fusionan automáticamente.

Los resultados anteriores están en `resultados.md`. El historial completo de etapas anteriores permanece en Git; no se mantienen copias de cada implementación dentro de la rama activa.
