"""Pruebas de la capa que usa la interfaz (app/).

La interfaz se apoya en funciones de src/ para mostrar resultados, mensajes de error y la
sección «Acerca de». Estas pruebas verifican esas funciones; la prueba de la propia app se
activa automáticamente cuando exista app/app.py.
"""
import json
import py_compile
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from src.model import CAMPOS, LectorFacturas, ResultadoDocumento, ResultadoPagina  # noqa: E402
from src.utils import ErrorEntrada, ErrorModelo, cargar_configuracion, mensaje_para_usuario  # noqa: E402

APP = RAIZ / "app" / "app.py"


def documento_de_ejemplo():
    campos = {c: None for c in CAMPOS}
    campos.update(date="2026-09-27", subtotal="100.00", tax="12.00", total="112.00")
    confianza = {c: {"nivel": "sin_valor", "acuerdo": None} for c in CAMPOS}
    confianza["total"] = {"nivel": "alta", "acuerdo": 0.9}
    pagina = ResultadoPagina(pagina=1, estado="ok", campos=campos, confianza=confianza,
                             alertas=["total:observed_accounting_selection"], revision=["Revisar el total"],
                             evidencia={"total": [{"value": "112.00", "view": 0}]}, texto="TOTAL 112.00 CLIENTE JUAN")
    return ResultadoDocumento("factura.png", [pagina])


class PresentacionTests(unittest.TestCase):
    def test_tabla_para_mostrar_tiene_los_seis_campos_en_orden(self):
        tabla = documento_de_ejemplo().tabla()
        self.assertEqual([f["clave"] for f in tabla], list(CAMPOS))
        total = next(f for f in tabla if f["clave"] == "total")
        self.assertEqual((total["valor"], total["confianza"]), ("112.00", "alta"))
        self.assertIn("observed_accounting_selection", total["alertas"])
        ruc = next(f for f in tabla if f["clave"] == "tax_id")
        self.assertEqual(ruc["valor"], "No detectado")             # vacío nunca se muestra como cero

    def test_exportar_sin_texto_protege_la_privacidad(self):
        with tempfile.TemporaryDirectory() as carpeta:
            rutas = documento_de_ejemplo().guardar(carpeta, incluir_texto=False)
            contenido = rutas["json"].read_text(encoding="utf-8")
            self.assertNotIn("CLIENTE JUAN", contenido)
            self.assertEqual(json.loads(contenido)["paginas"][0]["campos"]["total"], "112.00")

    def test_estado_del_documento(self):
        documento = documento_de_ejemplo()
        self.assertEqual(documento.estado, "ok")
        documento.paginas.append(ResultadoPagina(pagina=2, estado="error", error="x"))
        self.assertEqual(documento.estado, "parcial")
        with self.assertRaises(IndexError):
            documento.campos(pagina=5)


class MensajesTests(unittest.TestCase):
    def test_mensajes_para_el_usuario_sin_detalles_tecnicos(self):
        self.assertEqual(mensaje_para_usuario(ErrorEntrada("El archivo está vacío.")), "El archivo está vacío.")
        self.assertIn("Tesseract", mensaje_para_usuario(ErrorModelo("Tesseract no está instalado")))
        generico = mensaje_para_usuario(KeyError("ocr"))
        self.assertNotIn("KeyError", generico)
        self.assertIn("inesperado", generico)


class AcercaDeTests(unittest.TestCase):
    def test_informacion_del_modelo_incluye_limitaciones(self):
        info = LectorFacturas(cargar_configuracion()).acerca_de()
        self.assertEqual(info["vistas_ocr"], 10)
        self.assertIn("observed_accounting", info["etapas"])
        self.assertEqual(info["metas"]["meta_exactitud"], 0.70)
        self.assertTrue(any("mano" in x for x in info["fuera_de_alcance"]))


class AppTests(unittest.TestCase):
    @unittest.skipUnless(APP.is_file(), "app/app.py no está disponible")
    def test_la_app_compila(self):
        py_compile.compile(str(APP), doraise=True)


if __name__ == "__main__":
    unittest.main()
