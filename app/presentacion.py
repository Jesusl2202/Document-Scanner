"""Presentación de una lectura como HTML y como archivos para descargar.

Funciones puras (sin Streamlit ni Flask) que usa la versión de Streamlit de la interfaz
(``app/streamlit_app.py``) y que se prueban en ``tests/test_presentacion.py``. Reciben la
respuesta que arma :class:`app.servicio.ServicioLector` y devuelven texto: HTML escapado para
mostrar, CSV y JSON para descargar.

El resaltado de la evidencia no usa JavaScript: el documento y la tabla van en el mismo bloque
y la regla CSS ``:has()`` enciende el recuadro de un campo al pasar por su fila (y al revés).
"""
from __future__ import annotations

import csv
import io
import json
from html import escape
from typing import Any

CAMPOS = ("tax_id", "date", "document_number", "subtotal", "tax", "total")
CONFIANZA = {"alta": "Alta", "media": "Media", "baja": "Baja", "sin_valor": "No detectado"}
CORTO = {"tax_id": "RUC", "date": "Fecha", "document_number": "Número", "subtotal": "Subtotal", "tax": "IVA",
         "total": "Total"}
REPOSITORIO = "https://github.com/Jesusl2202/Document-Scanner"
MARGEN_CAJA = 6          # píxeles alrededor del texto, en la escala de la imagen original

# Hoja de libro con renglones (el mismo dibujo que el favicon de la versión Flask), como imagen para
# que no dependa de que el sanitizador de HTML admita SVG en línea.
ICONO = ('<img class="lf-icono" alt="" src="data:image/svg+xml,%3Csvg xmlns=%27http://www.w3.org/2000/svg%27 '
         'viewBox=%270 0 32 32%27%3E%3Crect x=%276%27 y=%273%27 width=%2720%27 height=%2726%27 rx=%272%27 '
         'fill=%27%23FFFFFF%27 stroke=%27%232F6B4F%27 stroke-width=%272%27/%3E%3Cpath d=%27M10 10h12M10 15h12M10 '
         '20h7%27 stroke=%27%232D50A0%27 stroke-width=%272%27/%3E%3C/svg%3E">')


def _e(texto: Any) -> str:
    return escape("" if texto is None else str(texto), quote=True)


def _coma(numero: float | int) -> str:
    return str(numero).replace(".", ",")


# ---- piezas fijas ---------------------------------------------------------------------------

def html_cabecera() -> str:
    return (f'<header class="lf-cabecera">{ICONO}<div><h1>Lector de Facturas</h1>'
            '<p>Saca el RUC, la fecha, el número, el subtotal, el IVA y el total de una factura impresa, '
            'y te muestra de dónde salió cada valor para que lo revises.</p></div></header>')


def html_consejos(alojamiento: str) -> str:
    """Recomendaciones antes de subir; ``alojamiento`` dice dónde corre esta copia de la app."""
    return ('<section class="lf-consejos"><h2>Para una buena lectura</h2><ul>'
            '<li>Factura o recibo <strong>impreso o digital</strong>. Lo escrito a mano no se reconoce bien: '
            'si un dato está a mano, digítalo tú.</li>'
            '<li>Foto recta, completa y con buena luz; mejor si el comprobante ocupa toda la imagen.</li>'
            '<li>Puedes elegir <strong>varias facturas a la vez</strong>: se leen una tras otra y al final ves una '
            'tabla con todas, con los valores dudosos marcados.</li>'
            f'<li>El archivo solo se usa para esta lectura y se borra al terminar. {_e(alojamiento)}</li>'
            '</ul></section>')


def html_pie(version: str) -> str:
    return ('<div class="lf-pie" role="contentinfo">Proyecto integrador de la Maestría en Inteligencia '
            f'Artificial, Universidad Espíritu Santo. Jesús López y Sebastián Rojas. Versión {_e(version)}. '
            f'<a href="{REPOSITORIO}" target="_blank" rel="noopener">Código y documentación</a></div>')


def html_mensaje(texto: str) -> str:
    return f'<div class="lf-mensaje" role="alert"><p>{_e(texto)}</p></div>'


def html_espera(nombre: str) -> str:
    return (f'<div class="lf-espera" aria-live="polite"><div class="lf-espera__barra"><span></span></div>'
            f'<p><strong>{_e(nombre)}</strong></p><p>Leyendo el documento con 10 lecturas de Tesseract y '
            'comparando los valores…</p><p class="lf-nota">Suele tardar entre 10 y 40 segundos por página.</p></div>')


# ---- resultado ------------------------------------------------------------------------------

def resumen_lectura(respuesta: dict[str, Any]) -> str:
    """«Lectura completa. 1 página en 5,7 s.»"""
    estados = {"ok": "Lectura completa", "parcial": "Lectura parcial: alguna página falló"}
    paginas = len(respuesta.get("paginas", []))
    cuantas = "1 página" if paginas == 1 else f"{paginas} páginas"
    texto = estados.get(respuesta.get("estado"), "No se pudo leer")
    return f"{texto}. {cuantas} en {_coma(respuesta.get('segundos', 0))} s."


def html_titulo_resultado(respuesta: dict[str, Any]) -> str:
    avisos = "".join(f'<p class="lf-nota">{_e(a)}</p>' for a in respuesta.get("avisos_entrada", []))
    return (f'<div class="lf-titulo"><h2>{_e(respuesta.get("archivo", "Documento"))}</h2>'
            f'<p class="lf-nota">{_e(resumen_lectura(respuesta))}</p>{avisos}</div>')


def _caja(campo: dict[str, Any], vista: dict[str, Any]) -> str:
    x0, y0, x1, y1 = campo["evidencia"]["caja"]
    ancho, alto = float(vista["ancho"]), float(vista["alto"])
    izquierda = max(0.0, (x0 - MARGEN_CAJA) / ancho * 100)
    arriba = max(0.0, (y0 - MARGEN_CAJA) / alto * 100)
    caja_ancho = min(100.0 - izquierda, (x1 - x0 + 2 * MARGEN_CAJA) / ancho * 100)
    caja_alto = min(100.0 - arriba, (y1 - y0 + 2 * MARGEN_CAJA) / alto * 100)
    estilo = f"left:{izquierda:.2f}%;top:{arriba:.2f}%;width:{caja_ancho:.2f}%;height:{caja_alto:.2f}%"
    return (f'<div class="lf-caja" data-campo="{_e(campo["clave"])}" style="{estilo}" '
            f'title="{_e(campo["nombre"])}: {_e(campo["valor"])}">'
            f'<span>{_e(CORTO.get(campo["clave"], ""))}</span></div>')


def _fila(campo: dict[str, Any]) -> str:
    vacio = campo.get("valor") is None
    normalizado = campo.get("normalizado")
    otro_formato = (normalizado and normalizado != campo.get("valor")
                    and not str(normalizado).startswith("AMBIGUOUS"))
    origen = ""
    if campo.get("evidencia") and campo["evidencia"].get("texto"):
        origen = f'<span class="lf-origen">Leído en: «{_e(campo["evidencia"]["texto"])}»</span>'
    if vacio:
        valor = '<span class="lf-valor lf-valor--vacio">No detectado: digítalo desde el documento</span>'
    else:
        valor = f'<span class="lf-valor">{_e(campo["valor"])}</span>'
    if otro_formato:
        etiqueta = "Formato ISO" if campo["clave"] == "date" else "Normalizado"
        valor += f'<span class="lf-valor__iso">{etiqueta}: {_e(normalizado)}</span>'
    for alerta in campo.get("alertas", []):
        clase = "lf-alerta lf-alerta--info" if alerta.get("nivel") == "info" else "lf-alerta"
        valor += f'<span class="{clase}">{_e(alerta.get("texto"))}</span>'
    nivel = campo.get("confianza", "sin_valor")
    sello = f'<span class="lf-sello lf-sello--{_e(nivel)}">{_e(CONFIANZA.get(nivel, nivel))}</span>'
    if not vacio:
        sello += f'<span class="lf-sello__detalle">{_e(campo.get("vistas"))} de {_e(campo.get("de"))} lecturas</span>'
    con_caja = ' class="lf-con-caja" tabindex="0"' if campo.get("evidencia") else ""
    return (f'<tr data-campo="{_e(campo["clave"])}"{con_caja}><td><span class="lf-campo">{_e(campo["nombre"])}</span>'
            f'{origen}</td><td>{valor}</td><td>{sello}</td></tr>')


def css_resaltado() -> str:
    """Reglas que unen cada fila con su recuadro (y al revés) sin JavaScript."""
    reglas = []
    for clave in CAMPOS:
        fila = f'.lf-resultado:has(tr[data-campo="{clave}"]:is(:hover, :focus))'
        caja = f'.lf-resultado:has(.lf-caja[data-campo="{clave}"]:hover)'
        reglas.append(f'{fila} .lf-caja[data-campo="{clave}"], {caja} .lf-caja[data-campo="{clave}"]'
                      '{background:rgba(45,80,160,.32);box-shadow:0 0 0 4px rgba(45,80,160,.25);z-index:2}')
        reglas.append(f'{fila} .lf-caja[data-campo="{clave}"] span, {caja} .lf-caja[data-campo="{clave}"] span'
                      '{display:block}')
        reglas.append(f'{caja} tr[data-campo="{clave}"]{{background:#F2F6FB}}')
    return "<style>" + "\n".join(reglas) + "</style>"


def html_pagina(pagina: dict[str, Any]) -> str:
    """Documento con los recuadros de evidencia junto a la tabla de campos (el «libro»)."""
    vista = pagina.get("vista_previa")
    campos = pagina.get("campos") or []
    documento = '<figure class="lf-documento"><div class="lf-lienzo">'
    if vista:
        documento += f'<img src="{vista["imagen"]}" alt="Página {_e(pagina.get("numero"))} del documento">'
        documento += "".join(_caja(c, vista) for c in campos if c.get("evidencia"))
    documento += ('</div><figcaption class="lf-nota">Los recuadros azules marcan dónde se leyó cada valor. '
                  'Pasa el cursor por una fila para resaltarlo.</figcaption></figure>')

    if pagina.get("estado") != "ok":
        libro = html_mensaje(pagina.get("error") or "No se pudo leer esta página.")
    else:
        filas = "".join(_fila(c) for c in campos)
        libro = ('<table class="lf-tabla"><caption class="lf-oculto">Campos extraídos</caption><thead><tr>'
                 '<th scope="col">Campo</th><th scope="col">Valor leído</th><th scope="col">Confianza</th></tr></thead>'
                 f'<tbody>{filas}</tbody></table>')
        cuadre = pagina.get("cuadre")
        if cuadre:
            marca = "✓ " if cuadre.get("nivel") == "ok" else ""
            libro += f'<p class="lf-cuadre lf-cuadre--{_e(cuadre.get("nivel"))}">{marca}{_e(cuadre.get("texto"))}</p>'
        avisos = list(pagina.get("avisos") or []) + [a.get("texto") for a in pagina.get("alertas") or []]
        if avisos:
            libro += '<div class="lf-avisos">' + "".join(f"<p>{_e(t)}</p>" for t in avisos) + "</div>"
    libro += ('<p class="lf-nota lf-libro__pie">La confianza indica cuántas lecturas del OCR coinciden en el valor '
              '(10 por página, o 12 si la imagen es difícil y se activa el rescate). No reemplaza tu revisión: '
              'compara cada dato con el documento antes de registrarlo.</p>')
    return f'{css_resaltado()}<div class="lf-resultado">{documento}<div class="lf-libro">{libro}</div></div>'


# ---- «Cómo funciona» ------------------------------------------------------------------------

def _cifra(texto: Any) -> str:
    """«81,1 % (IC95 75,0-86,9 %)» → «81,1 %»."""
    return _e(str(texto or "").split(" (")[0])


def html_acerca(info: dict[str, Any], alojamiento: str) -> str:
    """Sección «Cómo funciona» a partir de :meth:`ServicioLector.acerca_de`."""
    evaluacion = info.get("evaluacion_final") or {}
    validacion = info.get("validacion") or {}
    limites = info.get("limites") or {}
    partes = [
        "<h2>Qué hace</h2>",
        f'<p>Lee la imagen o el PDF con Tesseract 5 en <strong>{_e(info.get("vistas_ocr"))} versiones distintas de '
        'la misma página</strong> (original, ampliada, binarizada, con corrección de luz, con dos modelos de '
        'Tesseract y en español). Cada versión propone valores para los seis campos y el sistema se queda con el '
        'que más lecturas respaldan, comprobando además que subtotal + IVA = total.</p>',
        '<p>No inventa datos: si un valor no aparece leído en el documento, el campo queda vacío para que lo '
        'digites. Cada valor muestra dónde se leyó.</p>',
    ]
    if evaluacion.get("exactitud_por_campo"):
        metricas = [
            (evaluacion["exactitud_por_campo"],
             f'de los campos correctos en {_e(evaluacion.get("campos_evaluados", ""))} campos de prueba (meta: 70 %)'),
            (evaluacion.get("exactitud_sroie"), "en escaneos (SROIE)"),
            (evaluacion.get("exactitud_wildreceipt"), "en fotos de celular (WildReceipt)"),
        ]
        nuevos = validacion.get("documentos_nuevos") or {}
        if nuevos:
            metricas.append((nuevos.get("exactitud"),
                             f'en {_e(nuevos.get("documentos"))} recibos que nunca se miraron al construir el modelo'))
        tarjetas = "".join(f'<div class="lf-metrica"><strong>{_cifra(v)}</strong><span>{t}</span></div>'
                           for v, t in metricas if v)
        partes += ["<h2>Qué tan bien funciona</h2>", f'<div class="lf-metricas">{tarjetas}</div>',
                   f'<p class="lf-nota">{_e(evaluacion.get("muestra", ""))}</p>']
    escenarios = validacion.get("escenarios") or []
    if escenarios:
        filas = "".join(f"<tr><td>{_e(n)}</td><td>{_e(v)}</td></tr>" for n, v in escenarios)
        partes += ["<h2>Dónde falla</h2>", "<p>Pruebas con imágenes degradadas a propósito (exactitud por campo):</p>",
                   '<table class="lf-tabla-simple"><thead><tr><th>Condición</th><th>Exactitud</th></tr></thead>'
                   f"<tbody>{filas}</tbody></table>"]
    fuera = "".join(f"<li>{_e(x[:1].upper() + x[1:])}.</li>" for x in info.get("fuera_de_alcance") or [])
    partes += [
        "<h2>Cuándo no usarlo</h2>",
        f"<ul>{fuera}<li>Para aprobar pagos o declarar impuestos sin que una persona revise cada valor.</li></ul>",
        "<h2>Privacidad</h2>",
        "<p>El archivo se procesa solo durante la lectura y se borra al terminar: no se guarda ni se envía a otros "
        "servicios. Las descargas CSV y JSON incluyen solo los campos, no el texto completo de la factura.</p>",
        f"<p>{_e(alojamiento)}</p>",
        "<h2>Límites de esta versión</h2>",
        f'<p>Imágenes JPG o PNG y PDF de hasta {_e(limites.get("tamano_maximo_mb"))} MB; los PDF, de hasta '
        f'{_e(limites.get("paginas_maximas_pdf"))} páginas. Cada página se lee como un comprobante separado.</p>',
        f'<p><a href="{REPOSITORIO}" target="_blank" rel="noopener">Código, datos, métricas y documentación del '
        "proyecto</a>.</p>",
    ]
    return '<div class="lf-acerca">' + "".join(partes) + "</div>"


# ---- descargas ------------------------------------------------------------------------------

def nombre_base(respuesta: dict[str, Any]) -> str:
    nombre = str(respuesta.get("archivo") or "documento")
    return nombre.rsplit(".", 1)[0] if "." in nombre else nombre


def exportar_json(respuesta: dict[str, Any]) -> str:
    """Solo los campos de cada página (sin imagen ni texto OCR)."""
    limpio = {
        "archivo": respuesta.get("archivo"), "estado": respuesta.get("estado"), "segundos": respuesta.get("segundos"),
        "paginas": [{
            "pagina": p.get("numero"), "estado": p.get("estado"), "error": p.get("error"),
            "cuadre": (p.get("cuadre") or {}).get("estado"),
            "campos": {c["clave"]: {"valor": c.get("valor"), "normalizado": c.get("normalizado"),
                                    "confianza": c.get("confianza"),
                                    "alertas": [a.get("codigo") for a in c.get("alertas", [])]}
                       for c in p.get("campos") or []},
        } for p in respuesta.get("paginas", [])],
    }
    return json.dumps(limpio, ensure_ascii=False, indent=2)


def exportar_csv(respuesta: dict[str, Any]) -> str:
    """Una fila por página: valores y nivel de confianza de los seis campos (UTF-8 con BOM para Excel)."""
    salida = io.StringIO()
    escritor = csv.writer(salida, lineterminator="\r\n")
    escritor.writerow(["pagina", "estado", *CAMPOS, *(f"confianza_{c}" for c in CAMPOS), "cuadre"])
    for pagina in respuesta.get("paginas", []):
        por_clave = {c["clave"]: c for c in pagina.get("campos") or []}
        escritor.writerow([pagina.get("numero"), pagina.get("estado"),
                           *((por_clave.get(c) or {}).get("valor") or "" for c in CAMPOS),
                           *((por_clave.get(c) or {}).get("confianza") or "" for c in CAMPOS),
                           (pagina.get("cuadre") or {}).get("estado") or ""])
    return "﻿" + salida.getvalue()


# ---- lectura por lotes ----------------------------------------------------------------------

POR_REVISAR = ("media", "baja", "sin_valor")


def _duracion(segundos: float) -> str:
    """75.4 → «1 min 15 s»; 12.3 → «12,3 s»."""
    if segundos < 60:
        return f"{_coma(round(segundos, 1))} s"
    minutos, resto = divmod(round(segundos), 60)
    return f"{minutos} min {resto} s" if resto else f"{minutos} min"


def paginas_lote(lote: dict[str, Any]) -> list[dict[str, Any]]:
    """Una fila por página leída (o por archivo que no se pudo leer), en el orden de subida."""
    filas = []
    for documento in lote.get("documentos", []):
        paginas = documento.get("paginas") or []
        if documento.get("estado") == "error" and not paginas:
            filas.append({"archivo": documento.get("archivo"), "pagina": None, "varias": False, "estado": "error",
                          "error": documento.get("error"), "campos": {}, "por_revisar": 0, "cuadre": None})
            continue
        for pagina in paginas:
            campos = {c["clave"]: c for c in pagina.get("campos") or []}
            filas.append({"archivo": documento.get("archivo"), "pagina": pagina.get("numero"),
                          "varias": len(paginas) > 1, "estado": pagina.get("estado"), "error": pagina.get("error"),
                          "campos": campos, "cuadre": pagina.get("cuadre"),
                          "por_revisar": sum(c.get("confianza") in POR_REVISAR for c in campos.values())})
    return filas


def resumen_lote(lote: dict[str, Any]) -> str:
    filas = paginas_lote(lote)
    documentos = len(lote.get("documentos", []))
    leidas = [f for f in filas if f["estado"] == "ok"]
    limpias = sum(f["por_revisar"] == 0 for f in leidas)
    partes = [f"{documentos} {'documento leído' if documentos == 1 else 'documentos leídos'} en "
              f"{_duracion(lote.get('segundos', 0))}."]
    if len(filas) != documentos:
        partes.append(f"{len(filas)} páginas en total.")
    partes.append(f"{limpias} con todos los campos en confianza alta y {len(leidas) - limpias} con campos para "
                  "revisar con atención.")
    fallidas = len(filas) - len(leidas)
    if fallidas:
        partes.append(f"{fallidas} no se {'pudo' if fallidas == 1 else 'pudieron'} leer.")
    return " ".join(partes)


def _celda(campo: dict[str, Any] | None) -> str:
    if not campo or campo.get("valor") is None:
        return '<td class="lf-celda lf-celda--sin_valor" title="No detectado: digítalo">—</td>'
    nivel = campo.get("confianza", "sin_valor")
    titulo = f'Confianza {CONFIANZA.get(nivel, nivel).lower()}: {campo.get("vistas")} de {campo.get("de")} lecturas'
    return f'<td class="lf-celda lf-celda--{_e(nivel)}" title="{_e(titulo)}">{_e(campo["valor"])}</td>'


def html_lote(lote: dict[str, Any]) -> str:
    """Resumen y tabla de todos los documentos del lote, con cada valor marcado por su confianza."""
    encabezado = "".join(f'<th scope="col">{_e(CORTO[c])}</th>' for c in CAMPOS)
    filas = []
    for numero, fila in enumerate(paginas_lote(lote), 1):
        nombre = _e(fila["archivo"]) + (f' <span class="lf-nota">(página {fila["pagina"]})</span>'
                                        if fila["varias"] else "")
        if fila["estado"] != "ok":
            filas.append(f'<tr class="lf-fila-error"><td>{numero}</td><td>{nombre}</td>'
                         f'<td colspan="{len(CAMPOS) + 2}">{_e(fila["error"] or "No se pudo leer.")}</td></tr>')
            continue
        cuadre = fila.get("cuadre") or {}
        marca = {"ok": "✓", "aviso": "Revisar"}.get(cuadre.get("nivel"), "—")
        revisar = fila["por_revisar"]
        filas.append(f'<tr><td>{numero}</td><td>{nombre}</td>'
                     + "".join(_celda(fila["campos"].get(c)) for c in CAMPOS)
                     + f'<td class="lf-cuadre-celda lf-cuadre-celda--{_e(cuadre.get("nivel", "neutro"))}" '
                       f'title="{_e(cuadre.get("texto", ""))}">{marca}</td>'
                     + f'<td class="lf-revisar">{revisar if revisar else "—"}</td></tr>')
    leyenda = ('<p class="lf-leyenda"><span class="lf-celda lf-celda--alta">Alta</span>'
               '<span class="lf-celda lf-celda--media">Media</span><span class="lf-celda lf-celda--baja">Baja</span>'
               '<span class="lf-celda lf-celda--sin_valor">— No detectado</span></p>')
    return ('<div class="lf-lote">'
            f'<p class="lf-lote__resumen">{_e(resumen_lote(lote))}</p>'
            '<p class="lf-nota">Compara todos los valores con su documento: los marcados en ámbar o rojo tienen más '
            'probabilidad de error y los vacíos hay que digitarlos. Elige un documento debajo de la tabla para ver '
            f'de dónde salió cada valor.</p>{leyenda}'
            '<div class="lf-lote__marco"><table class="lf-tabla lf-tabla-lote"><caption class="lf-oculto">Campos de '
            f'todos los documentos</caption><thead><tr><th scope="col">#</th><th scope="col">Documento</th>{encabezado}'
            '<th scope="col">Cuadre</th><th scope="col">Por revisar</th></tr></thead>'
            f'<tbody>{"".join(filas)}</tbody></table></div></div>')


def exportar_csv_lote(lote: dict[str, Any]) -> str:
    """Una fila por página de cada documento, con el nombre del archivo (UTF-8 con BOM para Excel)."""
    salida = io.StringIO()
    escritor = csv.writer(salida, lineterminator="\r\n")
    escritor.writerow(["archivo", "pagina", "estado", *CAMPOS, *(f"confianza_{c}" for c in CAMPOS), "cuadre",
                       "error"])
    for fila in paginas_lote(lote):
        escritor.writerow([fila["archivo"], fila["pagina"] or "", fila["estado"],
                           *((fila["campos"].get(c) or {}).get("valor") or "" for c in CAMPOS),
                           *((fila["campos"].get(c) or {}).get("confianza") or "" for c in CAMPOS),
                           (fila.get("cuadre") or {}).get("estado") or "", fila.get("error") or ""])
    return "﻿" + salida.getvalue()


def exportar_json_lote(lote: dict[str, Any]) -> str:
    documentos = [json.loads(exportar_json(d)) if d.get("paginas") else
                  {"archivo": d.get("archivo"), "estado": d.get("estado"), "error": d.get("error"), "paginas": []}
                  for d in lote.get("documentos", [])]
    return json.dumps({"segundos": lote.get("segundos"), "documentos": documentos}, ensure_ascii=False, indent=2)
