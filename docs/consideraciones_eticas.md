# Consideraciones éticas

**Proyecto:** Lector de Facturas — extracción y validación de datos de facturas y comprobantes de compra con OCR
**Equipo:** Sebastián Rojas y Jesús Antonio López Barahona
**Última actualización:** 24/10/2026

Este documento analiza los riesgos éticos del sistema, qué medidas ya están implementadas en el repositorio y qué límites de uso deben conocer quienes lo usen.

## Contenido

0. [Resumen: privacidad y errores contables](#0-resumen-privacidad-y-errores-contables)
1. [Análisis de sesgos](#1-análisis-de-sesgos)
2. [Equidad y fairness](#2-equidad-y-fairness)
3. [Privacidad](#3-privacidad)
4. [Transparencia y explicabilidad](#4-transparencia-y-explicabilidad)
5. [Impacto social y stakeholders](#5-impacto-social-y-stakeholders)
6. [Meta de exactitud y costo del error](#6-meta-de-exactitud-y-costo-del-error)
7. [Responsabilidad](#7-responsabilidad)
8. [Uso dual y mal uso](#8-uso-dual-y-mal-uso)
9. [Limitaciones reconocidas](#9-limitaciones-reconocidas)
10. [Compromiso ético](#10-compromiso-ético)

---

## 0. Resumen: privacidad y errores contables

El sistema **no toma decisiones sobre personas**: no aprueba créditos, no clasifica clientes ni predice comportamientos. Lee seis datos de un comprobante (identificador fiscal, fecha, número, subtotal, impuesto y total) para que una persona no tenga que copiarlos a mano. Por eso, riesgos que en otros proyectos de IA son centrales, como la discriminación de un grupo demográfico, aquí son bajos.

Después de revisar los ocho puntos, el equipo concluyó que hay dos riesgos altos: los **errores en cifras contables** que pasen sin revisión (sección 6) y, sobre todo, **la información personal que contienen las facturas**:

- **Nombres** de clientes, empleados (cajeros, vendedores) y dueños de negocios.
- **Documentos de identidad.** En Ecuador, el RUC de una persona natural es su número de cédula seguido de `001`; el campo `tax_id` que extrae el sistema puede ser, en la práctica, una cédula. En facturas a consumidor final también puede aparecer la cédula del comprador.
- **Direcciones, teléfonos y correos** del emisor y, a veces, del comprador.
- **Fragmentos de tarjetas** de pago (últimos dígitos, tipo de tarjeta, código de autorización).
- **Hábitos de consumo**: qué compró una persona, dónde y cuándo. Por ejemplo, una factura de farmacia puede revelar algo sobre la salud de alguien.

| Dimensión | Nivel de riesgo | Medidas principales |
|---|:-:|---|
| **Privacidad** | **Alto** | Procesamiento local o en una carpeta temporal que se borra; descargas solo con los seis campos; aviso de que la versión publicada corre fuera de Ecuador (sección 3). |
| **Errores contables** | **Alto** | Solo se recomienda con revisión completa: 61,6 % de los documentos nuevos sale con todos sus campos correctos y 2,5 % de los campos son errores silenciosos (sección 6). |
| Sesgos y equidad | Medio | Funciona peor con fotos de celular (67,4 % frente a 86,0 % con escáner en documentos nuevos); se reporta por subgrupo y se toma posición en la sección 2.3. |
| Transparencia | Bajo | Cada campo muestra dónde se leyó y con qué confianza; las reglas se pueden leer (sección 4). |
| Uso dual | Medio | Relacionado con la privacidad: extraer datos personales de facturas ajenas (sección 8). |

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

Con **documentos nunca revisados** la brecha crece ([`06_validacion_escenarios.ipynb`](../notebooks/06_validacion_escenarios.ipynb), sección 7):

| Subgrupo | Exactitud | Omisiones | Errores silenciosos | Campos a revisar por documento |
|---|---:|---:|---:|---:|
| Escáner (SROIE) | 86,0 % | 2,0 % | 2,0 % | 0,7 |
| Celular (WildReceipt) | 67,4 % | 15,3 % | 2,8 % | 1,6 |
| Imagen grande | 88,4 % | 1,4 % | 2,9 % | 0,6 |
| Imagen pequeña | 66,3 % | 13,3 % | 3,1 % | 1,7 |
| OCR limpio | 89,9 % | 1,4 % | 2,9 % | 0,5 |
| OCR con muchos errores | 59,8 % | 19,6 % | 3,1 % | 2,0 |

Y en las pruebas de estrés, las condiciones típicas de una foto de celular barata (desenfoque, baja resolución, compresión por mensajería) son las que más bajan la exactitud: entre 20 y 63 puntos ([escenarios críticos](../results/metrics/validacion/escenarios_criticos.csv)).

### 2.3 Posición: ¿el sistema reduce o aumenta la desigualdad?

**Aumenta la desigualdad en esfuerzo, no en exactitud final, siempre que se use con revisión completa.** Los datos lo muestran así:

- **Aumenta la diferencia de calidad.** Quien digitaliza con un celular obtiene 18,6 puntos menos de exactitud que quien usa escáner, y tiene que revisar con atención el doble de campos dudosos por documento (1,6 frente a 0,7). Un micronegocio sin escáner ahorra menos tiempo que una empresa con escáner y PDF: el beneficio llega más a quien ya tiene mejores medios.
- **No aumenta los errores que pasan sin aviso.** Los errores silenciosos son parecidos entre grupos (2,8 % con celular, 2,0 % con escáner) porque en las imágenes malas el sistema tiende a **dejar el campo vacío** (15,3 % de omisiones con celular) en lugar de inventar. Con revisión completa, la desventaja se traduce en minutos de trabajo, no en registros contables equivocados. La excepción es la foto **torcida**, que sí produce valores equivocados (sección 9.3).
- **Reduce una barrera de acceso.** Es gratuito, corre en CPU y se usa desde el navegador o el celular; la alternativa comercial (servicios de Document AI) tiene costo por página.

Sin revisión humana, el sistema **sí aumentaría** la desigualdad: los negocios con peores medios acumularían más errores. Por eso la revisión completa no es opcional (sección 6).

### 2.4 Estrategias para reducir la diferencia

- **Ampliar las imágenes pequeñas** a 2.200 px, corregir la iluminación y leer cada documento 10 veces con distintas configuraciones y pesos (más un rescate con binarización local si la lectura es dudosa), pensado justamente para las fotos de baja resolución o con sombras.
- **Una vista en inglés + español**, para reducir el sesgo de idioma con facturas locales.
- **Reportar por dataset y por campo**, para que un promedio alto no esconda un grupo de documentos que funciona mal.
- **Indicaciones antes de subir** en la app (foto recta, completa, con buena luz y de cerca), porque las pruebas de estrés muestran que la rotación y el desenfoque son las causas más dañinas.
- **Mejoras técnicas pendientes de evaluar:** enderezar la imagen antes del OCR (la rotación de 6° es el escenario que más valores equivocados produce) y avisar cuando una imagen es demasiado pequeña o borrosa.
- **Muestra propia** de 30–50 comprobantes de al menos tres emisores para medir el desempeño en facturas reales del contexto local ([protocolo](anotacion_propia.md)).
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

### 3.3 Cumplimiento normativo

| Norma | Qué exige para este sistema | Cómo se atiende en el proyecto | Qué faltaría para un uso real |
|---|---|---|---|
| **Ley Orgánica de Protección de Datos Personales** (LOPDP, Registro Oficial Suplemento 459, 26/05/2021) | Base legítima para tratar datos de terceros (RUC de personas naturales, nombres, compras); minimización; seguridad; derechos de acceso, rectificación, eliminación y oposición; notificación de vulneraciones. | Procesamiento local o en una carpeta temporal que se borra; la app no guarda archivos; las descargas solo traen los seis campos; los datos de los datasets públicos no se redistribuyen; el registro de documentos revisados solo guarda hashes. | Definir el responsable del tratamiento y su base legítima (por ejemplo, la obligación contable del propio negocio), informar a los titulares cuando corresponda y fijar plazos de conservación. |
| **Reglamento General de la LOPDP** (Decreto Ejecutivo 904, 06/11/2023) | Ponderación de la base legítima (necesidad, proporcionalidad, impacto, garantías); medidas de seguridad; registro de actividades de tratamiento; delegado de protección de datos cuando aplique; condiciones para transferir datos fuera del país. | La ponderación está hecha en esta sección (finalidad contable acotada, seis campos, sin almacenamiento). La **versión publicada en Streamlit Community Cloud procesa en servidores fuera de Ecuador**: por eso la app lo advierte y pide usar solo facturas propias o los ejemplos; la versión local no transfiere datos. | Para facturas de terceros, desplegar en un servidor propio o en Ecuador, o documentar la transferencia internacional; inscribir el tratamiento en el registro de actividades. |
| **Norma General para la Garantía del Derecho de Protección de Datos Personales en el Uso de Sistemas de IA** (SPDP, Resolución SPDP-SPD-2026-0009-R, reformada por SPDP-SPD-2026-0037-R) | Gestión de riesgos y, cuando aplique, evaluación de impacto antes de desarrollar un sistema de IA que trate datos personales; informar de manera clara sobre el tratamiento automatizado; respetar el derecho a no ser objeto de decisiones basadas solo en valoraciones automatizadas (art. 20 LOPDP); el proveedor debe informar cómo funciona el sistema, sus limitaciones, riesgos previsibles y medidas de control. | El sistema **no decide**: propone valores que una persona confirma (sección 6). Este documento cumple el papel de análisis de riesgos; la ficha del modelo ([`models/ficha_modelo.json`](../models/ficha_modelo.json)), la sección «Cómo funciona» de la app y el [manual](manual_usuario.md) informan funcionamiento, limitaciones y riesgos; la evidencia de cada campo permite explicar el resultado. | Una evaluación de impacto formal firmada por el responsable del tratamiento antes de usarlo con datos de terceros, y una auditoría según el nivel de riesgo. |
| **Comprobantes electrónicos del SRI** (obligación ampliada a casi todos los emisores desde el 29/11/2022, Resolución NAC-DGERCGC22-00000024) | La factura electrónica es un **XML firmado y autorizado por el SRI**; el RIDE impreso es solo su representación. Los datos oficiales del comprobante están en ese XML. | Para facturas electrónicas, **leer el XML es mejor que usar OCR**: trae los campos exactos y se valida con la clave de acceso. La app detecta la clave de acceso de 49 dígitos en la imagen y recomienda usar el XML. El valor del OCR queda en lo que no trae XML: RIDE impresos recibidos sin el archivo, notas de venta y tiquetes de negocios populares, comprobantes del exterior y archivo histórico en papel. | Integrar la lectura del XML autorizado (o su consulta con la clave de acceso) y usar el OCR solo cuando no haya XML. |
| **Leyes laborales** | Aplicarían si la automatización redujera puestos. | El sistema asiste y no reemplaza: con la exactitud medida, toda factura sigue pasando por una persona (sección 6). | Plan de transición y capacitación si se usa a escala. |
| **GDPR, AI Act de la UE, CCPA** | Solo si se trataran datos de personas de esas jurisdicciones o se ofreciera allí. | No aplican al escenario académico descrito. Sus principios (minimización, transparencia, supervisión humana) coinciden con las medidas de este documento. | Reevaluar si cambian el mercado o los usuarios. |

El análisis es de un proyecto académico y no constituye asesoría legal; un despliegue con datos reales requeriría revisión de un especialista.

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

En la interfaz, cada campo muestra además un **recuadro sobre la imagen** donde se leyó, la línea de origen («Leído en») y el **nivel de confianza** (cuántas de las 10 lecturas coinciden). La confianza está razonablemente calibrada para ordenar la revisión: 95,4 % de acierto con confianza alta, 75,0 % con media y 53,7 % con baja en documentos nuevos ([calibración](../results/metrics/validacion/calibracion_confianza.csv)).

### 4.3 Técnicas de explicabilidad

SHAP y LIME están pensados para explicar modelos entrenados que asignan pesos a variables. **Aquí no hacen falta**: el extractor no tiene pesos aprendidos y su explicación es directa (la regla, el texto y la posición). En lugar de una explicación aproximada, el sistema da la explicación exacta de cada decisión. Además, los interruptores `FLAGS` de `consensus.py` permiten apagar un mecanismo y medir cuánto aporta.

## 5. Impacto social y stakeholders

### 5.1 Impacto positivo

- **Menos trabajo repetitivo.** Con documentos nuevos, revisar lo que propone el sistema tomaría unos 11,7 s por documento frente a 22,2 s de digitar sus campos: **47 % menos tiempo de captura** (entre 19 % y 61 % según cuánto tarde verificar un valor). Es una estimación con supuestos explícitos ([`tiempo_revision.csv`](../results/metrics/validacion/tiempo_revision.csv)); el ahorro real debe medirse en un piloto. Como referencia, el Documento de Alcance estimó 2–3 minutos por factura en digitación manual completa (incluye ubicar, abrir y registrar el documento).
- **La revisión se puede ordenar.** Los campos con confianza alta aciertan el 95,4 %, con confianza media el 75,0 % y con baja el 53,7 %: mirar primero los dudosos concentra la atención donde están los errores.
- **Menos errores de digitación** en montos e identificadores, gracias a las validaciones de formato y de cuadre (subtotal + IVA = total) y a que el valor propuesto se compara con el documento en lugar de teclearse.
- **Acceso gratuito**: sin licencias ni APIs de pago, una herramienta así está al alcance de negocios pequeños.
- **Base reutilizable** para otros estudiantes o desarrolladores, con código y documentación abiertos.

### 5.2 Impactos negativos posibles

- **Exposición de datos personales** si los resultados se comparten o se guardan sin cuidado (sección 3).
- **Confianza excesiva**: un usuario podría registrar los valores sin revisarlos. Con documentos nuevos, el 38,4 % de los documentos tiene al menos un campo mal o vacío y el 15,2 % de los campos tiene un valor equivocado: sin revisión, unos 37 valores equivocados por cada 100 facturas llegarían a la contabilidad o a una declaración, y aun revisando solo los campos dudosos pasarían unos 6 (sección 6).
- **Desplazamiento de tareas**: en un uso real, la digitación manual podría reducirse. Con la exactitud actual (81 % por campo en la evaluación final) el sistema **asiste** a la persona, no la reemplaza.

### 5.3 Stakeholders: cómo los afecta, si se consideraron y cómo se protegen

Cada grupo se analiza con las tres preguntas del Workshop de la Semana 4.

| Stakeholder | ¿Cómo lo afecta el sistema? | ¿Se consideró en el diseño? ¿Dónde? | ¿Cómo se protegen sus intereses? |
|---|---|---|---|
| **Operadores de contabilidad y digitación** (usan la app a diario) | **Beneficio:** pasan de digitar seis campos a verificarlos; la estimación de la sección 5.1 es de un ahorro de tiempo por factura con revisión completa. **Riesgo:** sobreconfianza (aceptar valores sin mirar) y ser responsabilizados por un error que el sistema no marcó. | **Sí.** La pantalla de resultado pone la imagen junto a cada valor, con un recuadro donde se leyó, la línea de origen y el nivel de confianza; un campo vacío pide digitar el dato en lugar de mostrar «0»; los errores se explican sin tecnicismos. | La confianza indica qué revisar primero, pero la política es **revisión completa** (sección 6); la app recuerda en cada resultado que no reemplaza la revisión; el [manual](manual_usuario.md) explica qué significa cada nivel y cada aviso. |
| **Contadores y dueños de pymes** (responden por los registros y las declaraciones) | **Beneficio:** menos tiempo de captura y trazabilidad de cada valor. **Riesgo:** que una cifra equivocada llegue a una declaración y genere reprocesos o sanciones. | **Sí.** Métricas por campo, por documento y por tipo de imagen; comprobación de cuadre; aviso de factura electrónica para que usen el XML oficial; la app no exporta nada como «aprobado». | La exactitud real se publica tal como salió, con intervalos y dónde falla (sección 2); la meta de uso se fija con el costo del error (sección 6); el sistema se declara como apoyo y no como validación fiscal. |
| **Emisores** (comercios y proveedores cuyo RUC, razón social y dirección aparecen en el comprobante) | **Beneficio directo:** ninguno; indirecto, menos errores al registrar sus facturas (por ejemplo, RUC mal digitado). **Riesgo:** que sus datos comerciales se procesen o queden guardados sin control. | **En parte.** No se les consultó, pero el diseño evita conservar sus datos: no hay almacenamiento en el servidor y las descargas solo incluyen los seis campos. | Minimización (seis campos), borrado inmediato del archivo, no redistribución de imágenes de los datasets, ejemplos sintéticos en la app y en la documentación. |
| **Clientes y personas naturales** que aparecen en la factura (comprador, cédula, compras) | **Beneficio directo:** ninguno. **Riesgo:** exposición de datos personales y de hábitos de consumo (por ejemplo, una compra en farmacia); en Ecuador, el RUC de una persona natural contiene su cédula. | **Sí, como titulares de datos.** Es el riesgo principal del proyecto (sección 3). | El sistema no extrae el nombre ni la cédula del comprador como campos ni los incluye en las descargas, que solo traen los seis campos. La versión publicada advierte que no se suban facturas de terceros; para ellas, la versión local no transfiere datos. Uso prohibido para armar bases de datos de personas (sección 8). |
| **SRI y auditores** | **Beneficio:** registros más consistentes y trazables. **Riesgo:** recibir datos erróneos o que la herramienta se presente como validación oficial. | **Sí.** Las validaciones se nombran «formato» y «cuadre», nunca «factura válida»; la app remite al XML autorizado cuando detecta una factura electrónica. | Advertencias en la app, el README y el manual; ficha del modelo con su uso previsto y casos fuera de alcance. |
| **Equipo desarrollador e institución** | **Beneficio:** aprendizaje y evidencia reproducible. **Riesgo:** publicar datos de terceros, exagerar resultados o infringir licencias. | **Sí.** Separación de datos por hash, registro de documentos revisados, configuración congelada antes de evaluar, licencias documentadas. | Resultados publicados aunque no favorezcan al modelo (por ejemplo, la configuración rechazada en la optimización), pruebas automáticas en cada cambio, notebooks ejecutados con sus salidas y compromiso firmado (sección 10). |

## 6. Meta de exactitud y costo del error

### 6.1 Qué mide la meta

- **Exactitud por campo** (la meta del proyecto, ≥ 70 %): porcentaje de campos con referencia anotada cuyo valor normalizado coincide exactamente. Un valor equivocado cuenta como error, igual que un campo vacío; un campo sin anotación no cuenta.
- **Exactitud por documento**: porcentaje de documentos con **todos** sus campos anotados correctos. Es la que importa para decidir si una factura se puede registrar sin tocarla.

Con seis campos independientes al 70 %, solo el 0,7⁶ ≈ 12 % de las facturas saldría completa. En los datos públicos cada documento tiene en promedio 2,5 campos anotados, y los errores **no** son independientes (se concentran en las imágenes difíciles):

| Muestra | Exactitud por campo | Documentos con todo correcto | Esperado si fueran independientes |
|---|---:|---:|---:|
| Test (100 documentos, notebook 05) | 81,1 % | 67,7 % | 62,7 % |
| Documentos nunca revisados (100, notebook 06) | 75,0 % | 61,6 % | 54,4 % |

Con los seis campos de una factura ecuatoriana y 75 % por campo, ni siquiera con la correlación observada saldría completa la mayoría de las facturas. **Conclusión: el sistema no sirve para registrar facturas sin revisión, y la meta del 70 % no se plantea para eso.**

### 6.2 Cuánto cuesta cada tipo de error

| Error | Qué pasa | Costo |
|---|---|---|
| **Omisión** (campo vacío) | La persona lo ve y lo digita. | Tiempo: unos 9 s por campo. |
| **Valor equivocado con aviso** (confianza media o baja) | La persona lo revisa con atención y lo corrige. | Tiempo: unos 9 s por campo. |
| **Error silencioso** (valor equivocado con confianza alta) | Si nadie lo revisa, entra a la contabilidad. | Reproceso al conciliar (supuesto: 15 min por error, entre 5 y 60), rectificación de registros y, si llegó a una declaración, una declaración sustitutiva y posibles sanciones. |

Con el salario básico de 2026 (482 USD al mes, unos 3 USD por hora), un error silencioso de 15 minutos cuesta lo mismo que unos 360 campos verificados (2,5 s cada uno).

### 6.3 Qué meta corresponde a cada forma de uso

| Forma de uso | Condición para que valga la pena | Situación medida |
|---|---|---|
| **Asistencia con revisión completa** (la persona verifica cada campo) | Verificar (2,5 s) más corregir los errores (9 s × tasa de error) debe costar menos que digitar (9 s): se cumple con exactitud por campo **≥ 28 %**. La meta del 70 % deja un margen amplio para que el ahorro sea claro y no dependa de supuestos. | **Se cumple.** Ahorro estimado de 47 % del tiempo de captura con documentos nuevos (sección 5.1). |
| **Revisión guiada** (solo se revisan los campos que no tienen confianza alta) | Lo que se ahorra frente a revisar todo debe superar el costo de los errores silenciosos. Con los datos medidos, se ahorran unos 6 minutos por cada 100 facturas y se dejan pasar unos 6 errores: solo compensa si cada error costara menos de 1 minuto. | **No se recomienda.** Con un costo realista por error, sale más caro que revisar todo. |
| **Automatización sin revisión** | El costo esperado de los errores debe ser menor que el de revisar: con 15 min por error, la tasa de error por campo tendría que bajar de 0,3 % (exactitud ≥ 99,7 %), por encima incluso de los servicios comerciales de Document AI (~95 % en facturas limpias). | **No permitido.** |

**Decisión:** la meta del 70 % por campo se mantiene como **mínimo para que el sistema sea útil como asistente con revisión completa**, que es la única forma de uso que el proyecto recomienda. La confianza sirve para ordenar la revisión (primero los campos dudosos), no para saltársela. Los supuestos de tiempo son una estimación (modelo KLM, Card et al., 1980); el piloto de la sección 8 del notebook 06 debe medirlos con usuarios reales.

## 7. Responsabilidad

### 7.1 ¿Quién es responsable si el modelo falla?

| Actor | Responsabilidad |
|---|---|
| **Equipo desarrollador** (Sebastián Rojas y Jesús López) | Documentar con honestidad el desempeño y las limitaciones, no exagerar resultados, corregir errores reportados. |
| **Usuario del sistema** | Revisar los valores antes de usarlos, en especial los que tienen alertas, y proteger los datos personales que procese. |
| **Docente / institución** | Evaluar el proyecto en su contexto académico. |

El sistema es un **prototipo académico**. Los valores que entrega son **sugerencias**: la responsabilidad final sobre un registro contable o tributario es de la persona que lo valida.

### 7.2 Mecanismos de accountability

- **Trazabilidad completa**: evidencia por campo, versión del código (hash de cada archivo de `src/`), configuración congelada y SHA-256 de los pesos del modelo guardados en cada ejecución del notebook.
- **El sistema prefiere dejar vacío antes que adivinar**: ante un empate devuelve el campo vacío con alerta, nunca inventa un monto que no leyó y, desde el modelo «resumen contable», **ya no supone que el total es igual al subtotal** cuando no ve un impuesto. Las correcciones del resumen contable y el rescate por confianza conservan el valor anterior y la evidencia.
- **Historial en Git** de todas las versiones del extractor.
- **Resultados reportados tal como salen**: el notebook 05 congela la configuración antes de leer el test y reporta el resultado sin cambiar el modelo para forzar la meta. También declara cuántos documentos del test ya se habían revisado durante el desarrollo.
- **Optimización con regla fijada de antemano**: el notebook 04 solo adopta una configuración nueva si mejora en una muestra de control con un intervalo de confianza favorable. En la práctica, la regla rechazó la mejor configuración de la búsqueda, que ganaba 0,9 pp en optimización pero perdía 3,1 pp en control.

### 7.3 Plan de monitoreo y actualización

1. Publicar cada evaluación tal como sale, aunque quede por debajo de la meta, con su intervalo de confianza y sus resultados por tipo de imagen, como se hizo con la evaluación final y con los documentos nunca revisados ([reporte](../results/reports/reporte_resultados.md)). Antes de un uso real, medir la **prueba externa** con facturas ecuatorianas anotadas ([protocolo](anotacion_propia.md)).
2. Revisar periódicamente los casos con alertas y los errores reportados por usuarios para encontrar formatos nuevos.
3. Antes de cambiar una regla, medirla en documentos de **desarrollo**, nunca en el test, y registrar el cambio en Git.
4. Ampliar la muestra propia con facturas de nuevos emisores para revisar si el desempeño se mantiene.

### 7.4 Plan de respuesta a incidentes

Incidente de referencia: un total mal extraído llega a un registro contable, o un documento real queda expuesto (en el repositorio, en un enlace compartido o en un registro).

| Etapa | Acciones |
|---|---|
| 1. Detección | Aumento de correcciones o de alertas de cuadre; reporte de un usuario o de un tercero por los [issues](https://github.com/Jesusl2202/Document-Scanner/issues); búsqueda periódica de RUC o nombres en el repositorio. |
| 2. Respuesta inmediata | Suspender el uso del lote o retirar el enlace; avisar al responsable del tratamiento; conservar la evidencia en un lugar protegido. |
| 3. Investigación | Reproducir el caso con el hash del documento y la versión del código (registrados en cada ejecución) y determinar si falló el OCR, una regla o la revisión humana. |
| 4. Corrección | Rectificar los registros afectados y avisar a quienes usaron los datos; ante una exposición de datos personales, cumplir la notificación que exige la LOPDP. |
| 5. Prevención | Agregar un caso sintético equivalente a las pruebas, corregir el control que falló y verificarlo antes de reanudar el uso. |

## 8. Uso dual y mal uso

### 8.1 ¿Podría usarse con fines maliciosos?

Sí, y el riesgo está ligado a la privacidad:

- **Recolección masiva de datos personales**: procesar facturas ajenas (por ejemplo, filtradas o robadas) para armar una base de nombres, cédulas y hábitos de compra.
- **Apoyo a fraudes**: usar los datos extraídos para preparar facturas falsas con información real de un emisor.
- **Uso como validador fiscal**: presentar la salida del sistema como prueba de que una factura es válida, cuando solo revisa formato.

### 8.2 Salvaguardas implementadas

- El sistema **no genera ni modifica facturas**: solo lee.
- El comando de lectura procesa **un archivo a la vez**; el procesamiento por lotes existe solo para evaluar con los datasets públicos.
- Las validaciones se nombran como **formato** (`valid_format`, `valid_structure`), nunca como "factura válida" o "auténtica".
- No se publican datos personales en el repositorio y los resultados de documentos propios se mantienen fuera de los reportes compartidos.
- La documentación advierte en varios lugares que el sistema **no reemplaza** la verificación ante la autoridad tributaria.

### 8.3 Limitaciones de uso documentadas

**Este sistema no debe usarse para:**

- Procesar facturas de otras personas sin autorización o sin una finalidad legítima.
- Verificar la autenticidad o la validez tributaria de un comprobante.
- Tomar decisiones automáticas (pagos, aprobaciones, declaraciones) sin revisión humana.
- Construir bases de datos de personas a partir de sus facturas.

## 9. Limitaciones reconocidas

### 9.1 ¿En qué casos NO debe usarse?

- Documentos **manuscritos** o comprobantes impresos con **campos completados a mano** (fecha, montos, RUC o número escritos con bolígrafo). El OCR está entrenado con texto impreso y esos valores se leen mal o no se leen; el sistema no lo detecta por sí solo.
- Facturas de **varias páginas** que deban leerse como un solo documento (cada página sale por separado).
- Documentos en idiomas con **otro alfabeto**, porque el modelo OCR es en inglés.
- Cuando se necesita una **certeza legal** sobre el comprobante (para eso están los servicios de la autoridad tributaria y los XML firmados de la factura electrónica).

### 9.2 Advertencias para los usuarios

- Con documentos que nunca se revisaron, la exactitud es de **75,0 % por campo** (IC95 67,9–81,6 %): 86 % en escaneos y 67 % en fotos de celular, por debajo de la meta. En el test, ya revisado al mejorar el modelo, es 81,1 %. Con facturas ecuatorianas el resultado puede ser menor.
- `tax_id` y `document_number` **no se han podido medir** con los datasets públicos porque no traen esas etiquetas.
- Revisar siempre los campos con alertas, en especial `total:subtotal_no_confirma_total`, `observed_accounting_selection` y `confidence_gap_recovery`.
- Usar solo comprobantes **impresos o digitales**; si algún campo está escrito a mano, digitarlo manualmente.
- Los archivos de salida contienen el texto completo de la factura: **guárdelos con cuidado**.

### 9.3 Casos límite donde el sistema no es confiable

| Caso | Por qué falla |
|---|---|
| Fotos movidas, desenfocadas, de baja resolución o muy comprimidas | El OCR deja de leer: con desenfoque leve la exactitud cae 39 puntos y con la mitad de resolución, 20 (casi siempre como campos vacíos). |
| Fotos torcidas | Con 6° de inclinación la exactitud cae 28 puntos y aparecen valores equivocados con confianza alta (6,7 % de los campos): es el caso más peligroso. |
| Recibos con varios montos iguales (total, efectivo, total redondeado) | Las reglas pueden confundir cuál es el total. |
| Fechas como `05/03/18` sin país configurado | No se sabe si es 5 de marzo o 3 de mayo; queda marcada como ambigua. |
| Recibos sin la palabra "total" o con etiquetas poco comunes | Ninguna regla encuentra el campo. |
| Facturas sin impuesto desglosado | El total queda vacío (`total:subtotal_no_confirma_total`) para que una persona lo confirme. |
| Campos escritos a mano | Tesseract está entrenado con texto impreso; la letra manuscrita produce lecturas erradas o vacías. |
| Descuentos, propinas o cargos que no se leen bien | El resumen contable no cuadra y el sistema conserva los valores leídos con una nota de revisión. |
| Montos como `1.234` | No se sabe si el punto es decimal o de miles; se trata como ambiguo. |

## 10. Compromiso ético

Como autores de este sistema, nos comprometemos a:

1. **Publicar los resultados tal como salen**, por campo, por documento y por tipo de imagen, con su intervalo de confianza, aunque no favorezcan al modelo, y a no ajustar el modelo mirando los datos con que se evalúa.
2. **Mantener a una persona en la decisión final** sobre cada valor extraído, con el documento y la evidencia a la vista, y a no presentar el sistema como validación tributaria.
3. **Proteger los datos de los comprobantes**: no conservar archivos en el servidor, no publicar imágenes ni textos de facturas reales y usar solo ejemplos sintéticos en las demostraciones públicas.
4. **Advertir con claridad las limitaciones** (campos escritos a mano, fotos de baja calidad, facturas electrónicas que deben leerse desde su XML, campos sin exactitud medida) en la app, el README y el manual.
5. **Atender los reportes de errores o de exposición de datos** por los [issues del repositorio](https://github.com/Jesusl2202/Document-Scanner/issues), siguiendo el plan de respuesta a incidentes de la sección 7.4: suspender el uso afectado, investigar con la versión y el hash del documento, corregir y agregar el caso a las pruebas.
6. **Priorizar a quienes más pueden salir perjudicados**: los negocios que solo cuentan con la cámara de un celular y las personas cuyos datos aparecen en las facturas.

| Integrante | Firma | Fecha |
|---|---|---|
| Jesús Antonio López Barahona | *Jesús Antonio López Barahona* (firma electrónica simple: aceptación al publicar este documento en el repositorio) | 24/10/2026 |
| Sebastián Rojas | *Sebastián Rojas* (firma electrónica simple: aceptación al publicar este documento en el repositorio) | 24/10/2026 |


---

### Referencias

- Asamblea Nacional del Ecuador. (2021). *Ley Orgánica de Protección de Datos Personales*. Registro Oficial Suplemento 459, 26 de mayo de 2021.
- Presidencia de la República del Ecuador. (2023). *Reglamento General a la Ley Orgánica de Protección de Datos Personales* (Decreto Ejecutivo 904, 6 de noviembre de 2023).
- Superintendencia de Protección de Datos Personales. (2026). *Norma General para la Garantía del Derecho de Protección de Datos Personales en el Uso de Sistemas de Inteligencia Artificial* (Resolución SPDP-SPD-2026-0009-R; reformada por la Resolución SPDP-SPD-2026-0037-R).
- Servicio de Rentas Internas. (2022). *Resolución NAC-DGERCGC22-00000024* (emisión de comprobantes electrónicos). Facturación electrónica: <https://www.sri.gob.ec/facturacion-electronica>
- Card, S. K., Moran, T. P., y Newell, A. (1980). The keystroke-level model for user performance time with interactive systems. *Communications of the ACM*, 23(7), 396–410.
- Goddard, K., Roudsari, A., y Wyatt, J. C. (2012). Automation bias: A systematic review of frequency, effect mediators, and mitigators. *Journal of the American Medical Informatics Association*, 19(1), 121–127.
- Parlamento Europeo y Consejo de la Unión Europea. (2016). *Reglamento (UE) 2016/679 (Reglamento General de Protección de Datos)*.
- Fast.ai. (s. f.). *Practical Data Ethics*. https://ethics.fast.ai/
- Mitchell, M., Wu, S., Zaldivar, A., Barnes, P., Vasserman, L., Hutchinson, B., Spitzer, E., Raji, I. D., y Gebru, T. (2019). Model cards for model reporting. En *Proceedings of the Conference on Fairness, Accountability, and Transparency* (pp. 220–229).

---

**Documentos relacionados:** [Planificación](planificacion.md) · [Análisis de datos](analisis_datos.md) · [Arquitectura](arquitectura.md) · [Optimización](optimizacion.md) · [Manual de usuario](manual_usuario.md)
