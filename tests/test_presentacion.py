"""Pruebas de app/presentacion.py (HTML y descargas de la versión de Streamlit) y de la app de Streamlit.

* Presentación: funciones puras, sin Streamlit ni OCR.
* App de Streamlit: se ejecuta con ``streamlit.testing`` y Tesseract real (se omite si falta
  Streamlit, Tesseract o los pesos en ``models/``).
"""
import csv
import importlib.util
import io
import json
import shutil
import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from app import presentacion as P  # noqa: E402

HAY_STREAMLIT = importlib.util.find_spec("streamlit") is not None
HAY_TESSERACT = bool(shutil.which("tesseract")) and (RAIZ / "models" / "fast" / "eng.traineddata").is_file() \
    and (RAIZ / "models" / "best" / "eng.traineddata").is_file()


def campo(clave, valor, confianza="alta", evidencia=None, alertas=None, normalizado=None):
    return {"clave": clave, "nombre": clave.upper(), "valor": valor, "normalizado": normalizado or valor,
            "confianza": confianza, "vistas": 9 if valor else 0, "de": 10, "evidencia": evidencia,
            "alertas": alertas or []}


def respuesta_de_prueba():
    campos = [
        campo("tax_id", None, "sin_valor"),
        campo("date", "14/10/2026", normalizado="2026-10-14",
              evidencia={"caja": [10, 20, 110, 40], "texto": "Fecha: 14/10/2026"}),
        campo("document_number", "001-002-000004521", "baja"),
        campo("subtotal", "37.15"),
        campo("tax", "5.57"),
        campo("total", "42.72", evidencia={"caja": [300, 900, 400, 930], "texto": "TOTAL 42.72 <b>"},
              alertas=[{"codigo": "total:structured_selection", "nivel": "info",
                        "texto": "Tomado de una etiqueta explícita del documento."}]),
    ]
    pagina = {"numero": 1, "estado": "ok", "segundos": 5.7, "campos": campos,
              "vista_previa": {"imagen": "data:image/jpeg;base64,AAAA", "ancho": 1000, "alto": 1000},
              "cuadre": {"estado": "consistent", "nivel": "ok", "texto": "Subtotal + IVA = total"},
              "avisos": ["Parece una factura electrónica del SRI."], "alertas": []}
    fallida = {"numero": 2, "estado": "error", "error": "No se pudo leer esta página.", "campos": [],
               "vista_previa": None, "cuadre": None}
    return {"archivo": "factura.pdf", "estado": "parcial", "segundos": 12.3, "avisos_entrada": [],
            "paginas": [pagina, fallida]}


class PresentacionTests(unittest.TestCase):
    def test_resumen_en_espanol(self):
        self.assertEqual(P.resumen_lectura(respuesta_de_prueba()),
                         "Lectura parcial: alguna página falló. 2 páginas en 12,3 s.")

    def test_pagina_con_evidencia_confianza_y_avisos(self):
        html = P.html_pagina(respuesta_de_prueba()["paginas"][0])
        self.assertEqual(html.count('class="lf-caja"'), 2)                   # solo los campos con evidencia
        self.assertIn('data-campo="total" style="left:29.40%;top:89.40%', html)
        self.assertIn("No detectado: digítalo desde el documento", html)      # vacío nunca se muestra como cero
        self.assertIn("Formato ISO: 2026-10-14", html)
        self.assertIn('lf-sello--baja">Baja', html)
        self.assertIn("✓ Subtotal + IVA = total", html)
        self.assertIn("factura electrónica del SRI", html)
        self.assertIn("TOTAL 42.72 &lt;b&gt;", html)                          # el texto OCR se escapa
        self.assertIn(':has(tr[data-campo="total"]', html)

    def test_pagina_con_error(self):
        html = P.html_pagina(respuesta_de_prueba()["paginas"][1])
        self.assertIn("lf-mensaje", html)
        self.assertNotIn("<table", html)

    def test_cajas_no_salen_de_la_imagen(self):
        pagina = respuesta_de_prueba()["paginas"][0]
        pagina["campos"][1]["evidencia"]["caja"] = [0, 0, 1000, 1000]
        html = P.html_pagina(pagina)
        self.assertIn('style="left:0.00%;top:0.00%;width:100.00%;height:100.00%"', html)

    def test_descargas_solo_con_los_campos(self):
        respuesta = respuesta_de_prueba()
        datos = json.loads(P.exportar_json(respuesta))
        self.assertEqual(datos["paginas"][0]["campos"]["total"]["valor"], "42.72")
        self.assertEqual(datos["paginas"][0]["campos"]["total"]["alertas"], ["total:structured_selection"])
        self.assertNotIn("base64", P.exportar_json(respuesta))
        texto = P.exportar_csv(respuesta)
        self.assertTrue(texto.startswith("﻿"))
        filas = list(csv.DictReader(io.StringIO(texto.lstrip("﻿"))))
        self.assertEqual(len(filas), 2)
        self.assertEqual((filas[0]["total"], filas[0]["confianza_document_number"], filas[0]["tax_id"]),
                         ("42.72", "baja", ""))
        self.assertEqual(filas[1]["estado"], "error")
        self.assertEqual(P.nombre_base(respuesta), "factura")

    def test_acerca_y_piezas_fijas(self):
        info = {"vistas_ocr": 10, "evaluacion_final": {"exactitud_por_campo": "81,1 % (IC95 75,0-86,9 %)",
                                                       "campos_evaluados": 244},
                "validacion": {"escenarios": [["Ruido σ = 12", "76,7 %"]]},
                "fuera_de_alcance": ["campos escritos a mano"],
                "limites": {"tamano_maximo_mb": 10, "paginas_maximas_pdf": 3}}
        html = P.html_acerca(info, "Alojada en un servidor de prueba.")
        self.assertIn("<strong>81,1 %</strong>", html)
        self.assertIn("Ruido σ = 12", html)
        self.assertIn("Campos escritos a mano.", html)
        self.assertIn("Alojada en un servidor de prueba.", html)
        self.assertIn("Lector de Facturas", P.html_cabecera())
        self.assertIn("&lt;script&gt;", P.html_mensaje("<script>"))


@unittest.skipUnless(HAY_STREAMLIT and HAY_TESSERACT, "Requiere Streamlit, Tesseract y los pesos en models/")
class StreamlitAppTests(unittest.TestCase):
    def setUp(self):
        from streamlit.testing.v1 import AppTest
        self.app = AppTest.from_file(str(RAIZ / "app" / "streamlit_app.py"), default_timeout=300)

    def test_inicio_y_lectura_de_un_ejemplo(self):
        app = self.app.run()
        self.assertFalse(app.exception, app.exception)
        self.assertEqual([t.label for t in app.tabs], ["Leer un documento", "Cómo funciona"])
        app.button(key="ejemplo_factura_impresa").click().run()
        self.assertFalse(app.exception, app.exception)
        respuesta = app.session_state["respuesta"]
        valores = {c["clave"]: c["normalizado"] for c in respuesta["paginas"][0]["campos"]}
        self.assertEqual((valores["subtotal"], valores["tax"], valores["total"]), ("37.15", "5.57", "42.72"))
        self.assertEqual([b.label for b in app.button][-1], "Leer otro documento")
        app.button[-1].click().run()
        self.assertIsNone(app.session_state["respuesta"])


if __name__ == "__main__":
    unittest.main()
