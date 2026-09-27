# Análisis comparativo para Semana 2

Se conservan las cinco familias de Semana 1. Esta es una comparación de diseño, no un benchmark ejecutado de cinco modelos.

| Familia | Fortaleza | Datos y recursos | Limitación | Decisión |
|---|---|---|---|---|
| OCR preentrenado + reglas | Trazabilidad de extracción; ejecución local. | Imágenes y modelo de idioma; etiquetas para evaluar, sin entrenamiento nuevo. | Sensible a formatos y errores OCR. | Tesseract LSTM + reglas implementado y evaluado. |
| OCR + ML clásico (CRF / Random Forest) | Aprende patrones de texto, ubicación y contexto. | Regiones etiquetadas y alineación con OCR; CPU posible. | Ingeniería de características y diferencias de etiquetas entre fuentes. | Evolución posible; no entrenado ni elegido como sustituto de la API. |
| Redes de grafos (SDMG-R) | Relaciones espaciales entre regiones. | Construcción del grafo y adaptación del modelo. | Mayor esfuerzo para seis semanas. | Referencia metodológica. |
| Transformers documentales (LayoutLMv3 y afines) | Representaciones preentrenadas y disposición del documento. | Texto, cajas, imagen y etiquetas compatibles; ajuste puede necesitar GPU. | Mayor preparación; transferencia no garantizada. | Referencia bibliográfica, sin fine-tuning en esta fase. |
| OCR-free / generativos (Donut y afines) | Generación de estructuras desde imagen; algunos prescinden de OCR externo. | Checkpoint compatible y recursos de inferencia. | Omisiones o valores incorrectos; validación necesaria. | Comparación cualitativa y trabajo futuro. |

## Soluciones concretas

**Tesseract + reglas** es el baseline local. **Google Document AI** es el servicio preentrenado seleccionado como comparador, conforme a Semana 1. El conector está implementado; su prueba real depende de cuenta y procesador.

No se identifica Document AI como LayoutLMv3 ni como otra arquitectura bibliográfica sin evidencia. Comparar soluciones completas no aísla el efecto del motor OCR.

## Criterios

Problema: imagen no estructurada → seis campos con evidencias y alertas. Datos: SROIE + WildReceipt aportan referencias complementarias. Recursos: CPU, dos integrantes y seis semanas; API acotada cuando exista acceso. Interpretabilidad: texto/cajas y reglas para revisión; la confianza del proveedor no se interpreta como certeza calibrada.

## Evidencia

`reports/AVANCE_EJECUTADO.md` contiene únicamente experimentos ejecutados. No se asignan métricas inventadas a modelos bibliográficos o a la nube. Las referencias técnicas están en `DATOS_Y_LICENCIAS.md`; conservar las referencias verificadas de los modelos en el apartado 2 de Semana 1.
