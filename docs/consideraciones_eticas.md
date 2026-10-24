# Consideraciones éticas

**Proyecto:** Lector de Facturas — extracción y validación de datos de facturas y comprobantes de compra con OCR
**Equipo:** Sebastián Rojas y Jesús Antonio López Barahona
**Última actualización:** 21/10/2026

Este documento analiza los riesgos éticos del sistema, qué medidas ya están implementadas en el repositorio y qué límites de uso deben conocer quienes lo usen.

## Contenido

0. [Resumen: el riesgo principal es la privacidad](#0-resumen-el-riesgo-principal-es-la-privacidad)
1. [Análisis de sesgos](#1-análisis-de-sesgos)
2. [Equidad y fairness](#2-equidad-y-fairness)
3. [Privacidad](#3-privacidad)
4. [Transparencia y explicabilidad](#4-transparencia-y-explicabilidad)
5. [Impacto social](#5-impacto-social)
6. [Responsabilidad](#6-responsabilidad)
7. [Uso dual y mal uso](#7-uso-dual-y-mal-uso)
8. [Limitaciones reconocidas](#8-limitaciones-reconocidas)

---

## 0. Resumen: el riesgo principal es la privacidad

El sistema **no toma decisiones sobre personas**: no aprueba créditos, no clasifica clientes ni predice comportamientos. Lee seis datos de un comprobante (identificador fiscal, fecha, número, subtotal, impuesto y total) para que una persona no tenga que copiarlos a mano. Por eso, riesgos que en otros proyectos de IA son centrales, como la discriminación de un grupo demográfico, aquí son bajos.

Después de revisar los ocho puntos, el equipo concluyó que **el riesgo ético más importante es la información personal que contienen las facturas**:

- **Nombres** de clientes, empleados (cajeros, vendedores) y dueños de negocios.
- **Documentos de identidad.** En Ecuador, el RUC de una persona natural es su número de cédula seguido de `001`; el campo `tax_id` que extrae el sistema puede ser, en la práctica, una cédula. En facturas a consumidor final también puede aparecer la cédula del comprador.
- **Direcciones, teléfonos y correos** del emisor y, a veces, del comprador.
- **Fragmentos de tarjetas** de pago (últimos dígitos, tipo de tarjeta, código de autorización).
- **Hábitos de consumo**: qué compró una persona, dónde y cuándo. Por ejemplo, una factura de farmacia puede revelar algo sobre la salud de alguien.

| Dimensión | Nivel de riesgo | Medidas principales |
|---|:-:|---|
| **Privacidad** | **Alto** | Procesamiento local, nada se sube al repositorio, documentos propios anonimizados, salidas tratadas como sensibles (sección 3). |
| Sesgos | Medio | Diferencias por idioma, país y calidad de imagen; métricas por dataset (sección 1). |
| Equidad | Bajo | No hay decisiones sobre personas; se reporta el desempeño por tipo de documento (sección 2). |
| Transparencia | Bajo | Cada campo guarda su evidencia; las reglas se pueden leer (sección 4). |
| Uso dual | Medio | Relacionado con la privacidad: extraer datos personales de facturas ajenas (sección 7). |

## 1. Análisis de sesgos

### 1.1 ¿El dataset tiene sesgos?

Los datos no tienen variables demográficas (edad, género, etnia), así que no hay sesgo demográfico directo. Sí encontramos **sesgos de origen** que afectan qué documentos se leen bien:

| Sesgo | Evidencia | Fuente |
|---|---|---|
| **Geográfico** | SROIE son recibos de Malasia; WildReceipt son imágenes en inglés obtenidas con buscadores. Ninguno tiene comprobantes ecuatorianos ni latinoamericanos. | [Análisis de datos](analisis_datos.md), sección 1 |
| **Idioma** | El OCR usa sobre todo modelos `eng` (solo una de las 10 vistas añade español) y la mayoría de las reglas busca etiquetas en inglés (`TOTAL`, `TAX`, `AMOUNT DUE`). | [Arquitectura](arquitectura.md), sección 3 |
| **Tipo de documento** | Ambos datasets son recibos de comercio minorista; casi no hay facturas formales entre empresas. | Documento de Alcance, sección 3 |
| **Calidad de captura** | El CER mediano de las fotos de WildReceipt (0,48) es más del doble que el de los escaneos de SROIE (0,19). | Línea base de Semana 2 |
| **Formato de fecha** | En 32,3 % de los recibos de SROIE no se distingue día de mes sin saber el país. | [Análisis de datos](analisis_datos.md), sección 5.2 |
| **Escritura** | Los dos datasets y los pesos de Tesseract son de texto **impreso**. Los comprobantes completados a mano (frecuentes en negocios pequeños con talonarios) quedan fuera. | [Análisis de datos](analisis_datos.md), sección 8 |

### 1.2 ¿Cómo afectan las predicciones?

El sistema funcionará peor con:

- Facturas en **español** u otros idiomas con etiquetas que las reglas no conocen, o con letras como `ñ` y tildes.
- **Fotos tomadas con celulares** de baja resolución o con mala luz, frente a escaneos limpios.
- Formatos de **fecha** de un país distinto al configurado.
- Comprobantes con **campos escritos a mano** (fecha, montos o RUC completados con bolígrafo): el OCR no los reconoce de forma confiable.

### 1.3 ¿Quiénes podrían salir perjudicados?

No hay un grupo de personas perjudicado por una decisión del modelo. El perjuicio posible es **operativo**: un negocio pequeño que fotografía sus facturas con un celular sencillo, que recibe facturas en español o que todavía usa talonarios llenados a mano tendrá más campos vacíos o errados y tendrá que corregir más a mano. Es un costo de tiempo, no una exclusión, porque el sistema no reemplaza la revisión humana.

## 2. Equidad y fairness

### 2.1 ¿El modelo trata a todos los grupos de forma equitativa?

Como el sistema no clasifica personas, las métricas clásicas de fairness (paridad demográfica, igualdad de oportunidades) **no aplican**: no hay atributos protegidos ni un resultado favorable o desfavorable para alguien. Lo que sí tiene sentido es revisar si el sistema funciona parecido en **distintos tipos de documento**.

### 2.2 Métricas evaluadas

Usamos el dataset como grupo de comparación (escaneo vs. foto) y reportamos las métricas por separado en vez de solo el promedio:

| Grupo | CER mediano | Exactitud de fecha | Exactitud de total |
|---|---:|---:|---:|
| SROIE (escaneos) | 0,19 | 80,0 % (16/20) | 20,0 % (4/20) |
| WildReceipt (fotos) | 0,48 | 43,8 % (7/16) | 16,7 % (3/18) |

*Línea base de Semana 2 sobre 40 documentos de validación. Es una muestra pequeña: sirve para ver la dirección de la diferencia, no para medirla con precisión.*

La brecha en la lectura de fechas (80 % vs. 44 %) muestra que la calidad de la imagen sí cambia el resultado. La brecha persistió durante el desarrollo: con V6 la fecha se acertó en 80,0 % de SROIE frente a 53,8 % de WildReceipt, y con el modelo actual los campos más débiles siguen siendo subtotal, impuesto y fecha de WildReceipt ([resultados de desarrollo](../results/reports/resultados_desarrollo.md)). La evaluación final lo confirma ([`05_evaluacion.ipynb`](../notebooks/05_evaluacion.ipynb), 100 documentos del test):

| Grupo | Documentos | Exactitud por campo |
|---|---:|---:|
| SROIE (escaneos) | 50 | 89,0 % (IC95 82,0–95,0) |
| WildReceipt (fotos) | 49 | 75,7 % (IC95 66,7–84,5) |
| Imágenes grandes | 33 | 94,2 % |
| Imágenes pequeñas | 33 | 77,0 % |
| OCR limpio (CER bajo) | 33 | 92,9 % |
| OCR con muchos errores (CER alto) | 33 | 68,8 % |

La diferencia entre escaneos y fotos de celular (unos 13 puntos) es la principal brecha del sistema: quien fotografía sus comprobantes con un celular de gama baja o con mala luz obtiene resultados peores. Por eso las alertas y la revisión humana son parte del diseño y no un añadido. Tabla: [`exactitud_por_factor.csv`](../results/metrics/evaluacion/exactitud_por_factor.csv).

### 2.3 Estrategias para reducir la diferencia

- **Ampliar las imágenes pequeñas** a 2.200 px, corregir la iluminación y leer cada documento 10 veces con distintas configuraciones y pesos (más un rescate con binarización local si la lectura es dudosa), pensado justamente para las fotos de baja resolución o con sombras.
- **Una vista en inglés + español**, para reducir el sesgo de idioma con facturas locales.
- **Reportar por dataset y por campo**, para que un promedio alto no esconda un grupo de documentos que funciona mal.
- **Muestra propia** de 30–50 comprobantes de al menos tres emisores para medir el desempeño en facturas reales del contexto local.
- **Reglas configurables por país**: orden de fecha, separador decimal y patrón del identificador fiscal.

## 3. Privacidad

### 3.1 ¿Se usan datos personales o sensibles?

**Sí.** Es el punto más delicado del proyecto, en tres momentos distintos:

| Momento | Qué datos personales pueden aparecer |
|---|---|
| **Datasets públicos** (SROIE, WildReceipt) | Nombres de comercios y de algunos cajeros, direcciones, teléfonos, fragmentos de tarjetas. |
| **Muestra propia** del equipo | Facturas reales: nombre y cédula/RUC del comprador, dirección, correo, lo que se compró. |
| **Uso del sistema** por un usuario | Cualquier factura que el usuario suba, con todos los datos anteriores. |

Además, el sistema guarda en `resultado.json` el **texto completo** leído por el OCR y la posición de cada palabra, no solo los seis campos. Ese archivo contiene todos los datos personales que aparecían en la factura.

### 3.2 ¿Cómo se protege la privacidad?

**Medidas ya implementadas en el repositorio:**

| Medida | Dónde |
|---|---|
| **Procesamiento local.** Tesseract corre en la máquina del usuario; las imágenes no se envían a ningún servicio externo. La única conexión a Internet es para descargar una vez los pesos del modelo. | `README.md`, `frozen_runtime.py` |
| **No se versionan datos.** `.gitignore` excluye el contenido de `data/raw/` y `data/processed/` (salvo su documentación), `datasets/`, `outputs/`, los pesos de `models/`, `cache_ocr/`, `documentos_privados/`, `.env` y archivos de credenciales. | `.gitignore` |
| **No se redistribuyen imágenes** de terceros: cada persona descarga los datasets de la fuente original. | `data/README.md` |
| **El inventario de documentos vistos solo guarda hashes**, no imágenes ni texto. | `data/processed/documentos_revisados.csv` |
| **Los ejemplos del repositorio son sintéticos**, con datos inventados (`RUC 1234567890`). | `samples/` |
| **El notebook de evaluación separa los documentos propios**: los guarda en `documento_privado/` y los **excluye del ZIP** de resultados, junto con la caché de OCR y las predicciones con texto. De la prueba externa solo se exportan métricas. | [`notebooks/05_evaluacion.ipynb`](../notebooks/05_evaluacion.ipynb), secciones 8–10 |
| **Anotación propia con anonimización**: no se publican números ni documentos privados sin revisar anonimización y autorización. | [`docs/anotacion_propia.md`](anotacion_propia.md) |

**Recomendaciones para quien use el sistema:**

1. Tratar `resultado.json`, `campos.csv` y la carpeta de caché como **información confidencial**; borrarlos cuando ya no se necesiten.
2. Si se usa **Google Colab**, tener en cuenta que el archivo se sube a una máquina de Google durante la sesión. Para facturas de terceros es preferible la ejecución local.
3. No subir facturas de otras personas sin una razón legítima (por ejemplo, la contabilidad del propio negocio).
4. Para la muestra propia: tapar o borrar nombres, cédulas, direcciones y datos de tarjetas que no sean los seis campos evaluados, y conservar solo lo necesario.

### 3.3 Cumplimiento de regulaciones

| Norma | Relación con el proyecto | Cómo se atiende |
|---|---|---|
| **Ley Orgánica de Protección de Datos Personales de Ecuador (LOPDP, 2021)** | Aplica al tratamiento de datos de personas en Ecuador, como cédulas y nombres en facturas de la muestra propia. | Minimización (solo seis campos se evalúan), finalidad académica, consentimiento de quienes aportan sus facturas y no publicación. |
| **GDPR (Unión Europea)** | Solo si se procesaran facturas de personas en la UE. Principios útiles: minimización, limitación de la finalidad y del plazo de conservación. | Procesamiento local, sin conservar datos más allá de la sesión salvo que el usuario lo decida. |
| **CCPA (California)** | No aplica directamente (el proyecto no vende ni comparte datos de consumidores). | — |

El proyecto es académico y no constituye una asesoría legal. Un despliegue real tendría que revisar estas obligaciones con un especialista.

## 4. Transparencia y explicabilidad

### 4.1 ¿El modelo es interpretable?

**Sí, en su mayor parte.** El OCR (la red LSTM de Tesseract) es una caja negra, pero la parte que decide qué valor va en cada campo son **reglas legibles** escritas en Python (`consensus.py` y `candidate_rules.py`). Cualquier persona con conocimientos básicos de programación puede leer por qué el sistema eligió un total.

### 4.2 ¿Los usuarios entienden cómo funciona?

Cada campo extraído viene con su **evidencia** en `resultado.json`:

| Evidencia | Ejemplo | Para qué sirve |
|---|---|---|
| `value` | `112.00` | El texto tal como se leyó. |
| `rule` | `visual_label`, `arithmetic_row`, `cash_minus_change` | Qué regla lo encontró. |
| `score` | `8` | Qué tan confiable es esa regla. |
| `box` | `[402, 1310, 512, 1342]` | En qué parte de la imagen está. |
| `view` | `1` | Cuál de las lecturas lo produjo. |
| `alerts` | `total:observed_accounting_selection` | Por qué conviene revisarlo. |
| `accounting_summary` | `{"previous_value": "74.50", "adjustments": {...}}` | Si el resumen contable corrigió un valor, cuál era el anterior y con qué ajustes visibles. |
| `quality` | `lectura_parcial` | Cuántos campos se encontraron; aclara que cobertura no es exactitud. |

### 4.3 Técnicas de explicabilidad

SHAP y LIME están pensados para explicar modelos entrenados que asignan pesos a variables. **Aquí no hacen falta**: el extractor no tiene pesos aprendidos y su explicación es directa (la regla, el texto y la posición). En lugar de una explicación aproximada, el sistema da la explicación exacta de cada decisión. Además, los interruptores `FLAGS` de `consensus.py` permiten apagar un mecanismo y medir cuánto aporta.

## 5. Impacto social

### 5.1 Impacto positivo

- **Menos trabajo repetitivo** para el personal administrativo de pequeñas y medianas empresas, que puede dedicar ese tiempo a revisar en lugar de transcribir.
- **Menos errores de digitación** en montos e identificadores, gracias a las validaciones de formato y de cuadre.
- **Acceso gratuito**: sin licencias ni APIs de pago, una herramienta así está al alcance de negocios pequeños.
- **Base reutilizable** para otros estudiantes o desarrolladores, con código y documentación abiertos.

### 5.2 Impactos negativos posibles

- **Exposición de datos personales** si los resultados se comparten o se guardan sin cuidado (sección 3).
- **Confianza excesiva**: un usuario podría registrar los valores sin revisarlos y arrastrar un error a la contabilidad o a una declaración de impuestos.
- **Desplazamiento de tareas**: en un uso real, la digitación manual podría reducirse. Con la exactitud actual (81 % por campo en la evaluación final) el sistema **asiste** a la persona, no la reemplaza.

### 5.3 ¿Quiénes se benefician y quiénes podrían salir perjudicados?

| Se benefician | Podrían salir perjudicados |
|---|---|
| Personal de contabilidad y digitación de PYMES | Personas cuyos datos aparecen en facturas procesadas sin su conocimiento |
| Dueños de pequeños negocios | Negocios con facturas en formatos poco representados (más correcciones manuales) |
| Estudiantes y desarrolladores que reutilicen el código | Quien confíe en un valor sin revisarlo |

## 6. Responsabilidad

### 6.1 ¿Quién es responsable si el modelo falla?

| Actor | Responsabilidad |
|---|---|
| **Equipo desarrollador** (Sebastián Rojas y Jesús López) | Documentar con honestidad el desempeño y las limitaciones, no exagerar resultados, corregir errores reportados. |
| **Usuario del sistema** | Revisar los valores antes de usarlos, en especial los que tienen alertas, y proteger los datos personales que procese. |
| **Docente / institución** | Evaluar el proyecto en su contexto académico. |

El sistema es un **prototipo académico**. Los valores que entrega son **sugerencias**: la responsabilidad final sobre un registro contable o tributario es de la persona que lo valida.

### 6.2 Mecanismos de accountability

- **Trazabilidad completa**: evidencia por campo, versión del código (hash de cada archivo de `src/`), configuración congelada y SHA-256 de los pesos del modelo guardados en cada ejecución del notebook.
- **El sistema prefiere dejar vacío antes que adivinar**: ante un empate devuelve el campo vacío con alerta, nunca inventa un monto que no leyó y, desde el modelo «resumen contable», **ya no supone que el total es igual al subtotal** cuando no ve un impuesto. Las correcciones del resumen contable y el rescate por confianza conservan el valor anterior y la evidencia.
- **Historial en Git** de todas las versiones del extractor.
- **Resultados reportados tal como salen**: el notebook 05 congela la configuración antes de leer el test y reporta el resultado sin cambiar el modelo para forzar la meta. También declara cuántos documentos del test ya se habían revisado durante el desarrollo.
- **Optimización con regla fijada de antemano**: el notebook 04 solo adopta una configuración nueva si mejora en una muestra de control con un intervalo de confianza favorable. En la práctica, la regla rechazó la mejor configuración de la búsqueda, que ganaba 0,9 pp en optimización pero perdía 3,1 pp en control.

### 6.3 Plan de monitoreo y actualización

1. Publicar cada evaluación tal como sale, aunque quede por debajo de la meta, con su intervalo de confianza y sus resultados por tipo de imagen, como se hizo con la evaluación final ([reporte](../results/reports/reporte_resultados.md)). Medir además la **prueba externa anotada** con la muestra propia.
2. Revisar periódicamente los casos con alertas y los errores reportados por usuarios para encontrar formatos nuevos.
3. Antes de cambiar una regla, medirla en documentos de **desarrollo**, nunca en el test, y registrar el cambio en Git.
4. Ampliar la muestra propia con facturas de nuevos emisores para revisar si el desempeño se mantiene.

## 7. Uso dual y mal uso

### 7.1 ¿Podría usarse con fines maliciosos?

Sí, y el riesgo está ligado a la privacidad:

- **Recolección masiva de datos personales**: procesar facturas ajenas (por ejemplo, filtradas o robadas) para armar una base de nombres, cédulas y hábitos de compra.
- **Apoyo a fraudes**: usar los datos extraídos para preparar facturas falsas con información real de un emisor.
- **Uso como validador fiscal**: presentar la salida del sistema como prueba de que una factura es válida, cuando solo revisa formato.

### 7.2 Salvaguardas implementadas

- El sistema **no genera ni modifica facturas**: solo lee.
- El comando de lectura procesa **un archivo a la vez**; el procesamiento por lotes existe solo para evaluar con los datasets públicos.
- Las validaciones se nombran como **formato** (`valid_format`, `valid_structure`), nunca como "factura válida" o "auténtica".
- No se publican datos personales en el repositorio y los resultados de documentos propios se mantienen fuera de los reportes compartidos.
- La documentación advierte en varios lugares que el sistema **no reemplaza** la verificación ante la autoridad tributaria.

### 7.3 Limitaciones de uso documentadas

**Este sistema no debe usarse para:**

- Procesar facturas de otras personas sin autorización o sin una finalidad legítima.
- Verificar la autenticidad o la validez tributaria de un comprobante.
- Tomar decisiones automáticas (pagos, aprobaciones, declaraciones) sin revisión humana.
- Construir bases de datos de personas a partir de sus facturas.

## 8. Limitaciones reconocidas

### 8.1 ¿En qué casos NO debe usarse?

- Documentos **manuscritos** o comprobantes impresos con **campos completados a mano** (fecha, montos, RUC o número escritos con bolígrafo). El OCR está entrenado con texto impreso y esos valores se leen mal o no se leen; el sistema no lo detecta por sí solo.
- Facturas de **varias páginas** que deban leerse como un solo documento (cada página sale por separado).
- Documentos en idiomas con **otro alfabeto**, porque el modelo OCR es en inglés.
- Cuando se necesita una **certeza legal** sobre el comprobante (para eso están los servicios de la autoridad tributaria y los XML firmados de la factura electrónica).

### 8.2 Advertencias para los usuarios

- La exactitud de la evaluación final es de **81,1 % por campo** (IC95 75,0–86,9 %): 89 % en escaneos y 76 % en fotos de celular. Los documentos de esa muestra ya se habían revisado al mejorar el modelo, así que no es una medida en documentos nuevos: el resultado con facturas propias puede ser menor.
- `tax_id` y `document_number` **no se han podido medir** con los datasets públicos porque no traen esas etiquetas.
- Revisar siempre los campos con alertas, en especial `total:subtotal_no_confirma_total`, `observed_accounting_selection` y `confidence_gap_recovery`.
- Usar solo comprobantes **impresos o digitales**; si algún campo está escrito a mano, digitarlo manualmente.
- Los archivos de salida contienen el texto completo de la factura: **guárdelos con cuidado**.

### 8.3 Casos límite donde el sistema no es confiable

| Caso | Por qué falla |
|---|---|
| Fotos pequeñas, borrosas, inclinadas o con sombras | El OCR comete muchos errores (CER > 0,5 en varias fotos de WildReceipt). |
| Recibos con varios montos iguales (total, efectivo, total redondeado) | Las reglas pueden confundir cuál es el total. |
| Fechas como `05/03/18` sin país configurado | No se sabe si es 5 de marzo o 3 de mayo; queda marcada como ambigua. |
| Recibos sin la palabra "total" o con etiquetas poco comunes | Ninguna regla encuentra el campo. |
| Facturas sin impuesto desglosado | El total queda vacío (`total:subtotal_no_confirma_total`) para que una persona lo confirme. |
| Campos escritos a mano | Tesseract está entrenado con texto impreso; la letra manuscrita produce lecturas erradas o vacías. |
| Descuentos, propinas o cargos que no se leen bien | El resumen contable no cuadra y el sistema conserva los valores leídos con una nota de revisión. |
| Montos como `1.234` | No se sabe si el punto es decimal o de miles; se trata como ambiguo. |

---

### Referencias

- Asamblea Nacional del Ecuador. (2021). *Ley Orgánica de Protección de Datos Personales*. Registro Oficial Suplemento 459, 26 de mayo de 2021.
- Parlamento Europeo y Consejo de la Unión Europea. (2016). *Reglamento (UE) 2016/679 (Reglamento General de Protección de Datos)*.
- Fast.ai. (s. f.). *Practical Data Ethics*. https://ethics.fast.ai/
- Mitchell, M., Wu, S., Zaldivar, A., Barnes, P., Vasserman, L., Hutchinson, B., Spitzer, E., Raji, I. D., y Gebru, T. (2019). Model cards for model reporting. En *Proceedings of the Conference on Fairness, Accountability, and Transparency* (pp. 220–229).

---

**Documentos relacionados:** [Planificación](planificacion.md) · [Análisis de datos](analisis_datos.md) · [Arquitectura](arquitectura.md) · [Optimización](optimizacion.md) · [Manual de usuario](manual_usuario.md)
