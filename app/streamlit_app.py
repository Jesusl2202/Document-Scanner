"""Interfaz web del Lector de Facturas con Streamlit (la versión publicada).

Ejecutar desde la raíz del repositorio::

    python -m pip install -r app/requirements.txt
    streamlit run app/streamlit_app.py

Usa el mismo servicio que la versión Flask (:class:`app.servicio.ServicioLector`): mismo modelo,
mismos límites, mismas alertas y mismos mensajes de error. La presentación está en
``app/presentacion.py`` y los estilos en ``app/static/streamlit.css``.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

import streamlit as st  # noqa: E402

import src  # noqa: E402,F401  (hace importable el motor lector_facturas)
from app import presentacion as P  # noqa: E402
from app.servicio import CARPETA_EJEMPLOS, LOGGER, ServicioLector, respuesta_error  # noqa: E402

ALOJAMIENTO = ("Esta demostración corre en Streamlit Community Cloud, fuera de Ecuador: sube facturas tuyas o los "
               "ejemplos, no facturas de otras personas. Para documentos con datos de terceros usa la versión que "
               "se instala en un equipo o servidor propio (instrucciones en el repositorio).")
ESTILOS = Path(__file__).with_name("static") / "streamlit.css"

st.set_page_config(page_title="Lector de Facturas", page_icon="🧾", layout="wide",
                   menu_items={"About": "Lector de Facturas — proyecto integrador de la Maestría en Inteligencia "
                                        f"Artificial, Universidad Espíritu Santo. {P.REPOSITORIO}"})


@st.cache_resource(show_spinner="Preparando el modelo. La primera vez descarga los pesos de Tesseract (unos segundos)…")
def obtener_servicio() -> ServicioLector:
    """Un solo servicio por servidor: carga Tesseract y los pesos una vez y atiende una lectura a la vez."""
    servicio = ServicioLector()
    servicio.lector.cargar()
    return servicio


def estado_inicial() -> None:
    for clave, valor in {"respuesta": None, "error": None, "pagina": 0, "subida": 0}.items():
        st.session_state.setdefault(clave, valor)


def nuevo_documento() -> None:
    st.session_state.respuesta = None
    st.session_state.error = None
    st.session_state.pagina = 0
    st.session_state.subida += 1          # cambia la clave del cargador para vaciarlo


def leer(servicio: ServicioLector, ruta: Path, nombre: str) -> None:
    """Lee el archivo y guarda la respuesta (o el mensaje de error) en la sesión."""
    espera = st.empty()
    espera.html(P.html_espera(nombre))
    try:
        st.session_state.respuesta = servicio.leer(ruta, nombre)
        st.session_state.error = None
        st.session_state.pagina = 0
    except Exception as exc:  # noqa: BLE001 — todo error termina en un mensaje claro
        cuerpo, codigo = respuesta_error(exc)
        if codigo >= 500 and not isinstance(exc, TimeoutError):
            LOGGER.exception("Error en la lectura web de %s", nombre)
        st.session_state.respuesta = None
        st.session_state.error = cuerpo["error"]
    finally:
        espera.empty()
    st.session_state.subida += 1
    st.rerun()


def leer_subida(servicio: ServicioLector, archivo) -> None:
    nombre = Path(archivo.name).name or "documento"
    with tempfile.TemporaryDirectory(prefix="lector_streamlit_") as temporal:
        ruta = Path(temporal) / nombre
        ruta.write_bytes(archivo.getvalue())
        leer(servicio, ruta, nombre)


def vista_inicio(servicio: ServicioLector) -> None:
    if st.session_state.error:
        st.html(P.html_mensaje(st.session_state.error))
    izquierda, derecha = st.columns([1.35, 1], gap="large")
    with izquierda:
        archivo = st.file_uploader("Foto o PDF de la factura", key=f"subida_{st.session_state.subida}",
                                   label_visibility="collapsed")
        if archivo is not None:
            leer_subida(servicio, archivo)
    with derecha:
        st.html(P.html_consejos(ALOJAMIENTO))
        ejemplos = servicio.ejemplos()
        if ejemplos:
            st.html('<p class="lf-subtitulo">O prueba con un ejemplo</p>')
            for ejemplo in ejemplos:
                with st.container(border=True):
                    miniatura, texto = st.columns([1, 4], vertical_alignment="center")
                    ruta = CARPETA_EJEMPLOS / ejemplo["archivo"]
                    with miniatura:
                        if ruta.suffix.lower() == ".pdf":
                            st.html('<p class="lf-ejemplo-texto"><strong style="color:#C4514A">PDF</strong></p>')
                        else:
                            st.image(str(ruta), width=56)
                    with texto:
                        st.html(f'<p class="lf-ejemplo-texto"><strong>{P._e(ejemplo["titulo"])}</strong>'
                                f'{P._e(ejemplo["descripcion"])}</p>')
                        if st.button("Leer este ejemplo", key=f"ejemplo_{ejemplo['id']}"):
                            leer(servicio, ruta, f"Ejemplo: {ejemplo['titulo']}")
            st.html('<p class="lf-nota">Los ejemplos son comprobantes inventados, sin validez tributaria.</p>')


def vista_resultado(respuesta: dict) -> None:
    titulo, csv, json_, otro = st.columns([3, 1, 1, 1.3], vertical_alignment="bottom")
    with titulo:
        st.html(P.html_titulo_resultado(respuesta))
    base = P.nombre_base(respuesta)
    csv.download_button("Descargar CSV", P.exportar_csv(respuesta), f"{base}_campos.csv", "text/csv",
                        use_container_width=True)
    json_.download_button("Descargar JSON", P.exportar_json(respuesta), f"{base}_campos.json", "application/json",
                          use_container_width=True)
    otro.button("Leer otro documento", type="primary", on_click=nuevo_documento, use_container_width=True)
    paginas = respuesta.get("paginas", [])
    if len(paginas) > 1:
        st.session_state.pagina = st.radio(
            "Página", list(range(len(paginas))), format_func=lambda i: f"Página {paginas[i]['numero']}",
            horizontal=True, index=min(st.session_state.pagina, len(paginas) - 1))
    if paginas:
        st.html(P.html_pagina(paginas[min(st.session_state.pagina, len(paginas) - 1)]))


def main() -> None:
    estado_inicial()
    st.html(f"<style>{ESTILOS.read_text(encoding='utf-8')}</style>")
    st.html(P.html_cabecera())
    leer_tab, acerca_tab = st.tabs(["Leer un documento", "Cómo funciona"])
    try:
        servicio = obtener_servicio()
    except Exception as exc:  # noqa: BLE001
        LOGGER.exception("No se pudo preparar el modelo")
        with leer_tab:
            st.html(P.html_mensaje(respuesta_error(exc)[0]["error"]))
        return
    with leer_tab:
        if st.session_state.respuesta:
            vista_resultado(st.session_state.respuesta)
        else:
            vista_inicio(servicio)
    with acerca_tab:
        st.html(P.html_acerca(servicio.acerca_de(), ALOJAMIENTO))
    st.html(P.html_pie(servicio.config["proyecto"].get("version", "")))


main()
