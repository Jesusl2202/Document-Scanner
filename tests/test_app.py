"""Pruebas de la interfaz web (app/) y de las funciones de src/ que usa.

* Presentación, mensajes y «Acerca de»: funciones de ``src.model`` y ``src.utils``.
* Servicio y rutas HTTP: ``app.servicio`` y ``app.app`` con un lector simulado (rápidas, sin OCR).
* Integración: lectura real de los ejemplos sintéticos con Tesseract (se omite si no está
  instalado o si faltan los pesos en ``models/``).
"""
import importlib.util
import io
import json
import py_compile
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from src.model import CAMPOS, LectorFacturas, ResultadoDocumento, ResultadoPagina  # noqa: E402
from src.utils import ErrorEntrada, ErrorModelo, cargar_configuracion, mensaje_para_usuario  # noqa: E402

APP = RAIZ / "app" / "app.py"
HAY_FLASK = importlib.util.find_spec("flask") is not None
EJEMPLOS = RAIZ / "app" / "assets" / "ejemplos"
HAY_TESSERACT = bool(shutil.which("tesseract")) and (RAIZ / "models" / "fast" / "eng.traineddata").is_file() \
    and (RAIZ / "models" / "best" / "eng.traineddata").is_file()


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
    def test_la_app_compila(self):
        for archivo in ("app.py", "servicio.py"):
            py_compile.compile(str(RAIZ / "app" / archivo), doraise=True)

    def test_explicacion_de_alertas(self):
        from app.servicio import explicar_alerta
        alerta = explicar_alerta("total:semantic_conflict")
        self.assertEqual((alerta["campo"], alerta["nivel"]), ("total", "aviso"))
        self.assertIn("revisa", alerta["texto"].lower())
        self.assertEqual(explicar_alerta("tax:structured_selection")["nivel"], "info")
        self.assertEqual(explicar_alerta("date:codigo_nuevo")["nivel"], "aviso")    # desconocida: pide revisar

    def test_detecta_comprobante_electronico_del_sri(self):
        from app.servicio import es_comprobante_electronico
        clave = "1410202601099123456700120020010000045211234567815"
        self.assertTrue(es_comprobante_electronico("CLAVE DE ACCESO:\n" + clave))
        self.assertTrue(es_comprobante_electronico("1410 2026 0109912345670012002001000004521 1234567815"))
        self.assertFalse(es_comprobante_electronico("RUC 0991234567001 TOTAL 42.72"))

    def test_evidencia_busca_el_valor_entre_las_palabras(self):
        from app.servicio import evidencia_principal
        normalizacion = {"date_order": "auto", "decimal_separator": "auto"}
        palabras = [{"text": "Fecha", "box": [10, 10, 60, 30], "line_id": "1"},
                    {"text": "14/10/2026", "box": [70, 10, 170, 30], "line_id": "1"}]
        sin_caja = {"date": [{"value": "14/10/2026", "box": None, "view": 0}]}
        evidencia = evidencia_principal("date", "14/10/2026", sin_caja, normalizacion, palabras)
        self.assertEqual(evidencia["caja"], [70.0, 10.0, 170.0, 30.0])    # el trozo más corto
        self.assertIn("Fecha", evidencia["texto"])
        self.assertIsNone(evidencia_principal("date", None, sin_caja, normalizacion, palabras))


def pagina_simulada(ruta, numero=1):
    """Lo que devolvería LectorFacturas.leer_pagina para la factura de ejemplo."""
    campos = {c: None for c in CAMPOS}
    campos.update(tax_id="0991234567001", date="14/10/2026", subtotal="37.15", tax="5.57", total="42.72")
    confianza = {c: {"nivel": "sin_valor", "acuerdo": None, "vistas": 0, "de": 10} for c in CAMPOS}
    for c in ("tax_id", "date", "subtotal", "tax", "total"):
        confianza[c] = {"nivel": "alta", "acuerdo": 1.0, "vistas": 10, "de": 10}
    return ResultadoPagina(pagina=numero, estado="ok", campos=campos, confianza=confianza,
                           alertas=["total:semantic_selection"], validacion={"amount_balance": "consistent"},
                           evidencia={"total": [{"value": "42.72", "box": [700, 900, 800, 930], "view": 0,
                                                 "text": "TOTAL 42.72"}]},
                           texto="FERRETERIA CLIENTE JUAN PEREZ", segundos=0.1)


@unittest.skipUnless(HAY_FLASK, "Flask no está instalado (pip install -r app/requirements.txt)")
class RutasTests(unittest.TestCase):
    def setUp(self):
        from app.app import crear_app
        from app.servicio import ServicioLector
        lector = LectorFacturas(cargar_configuracion())
        lector.configuracion_modelo = json.loads((RAIZ / "configs" / "definitivo.json").read_text(encoding="utf-8"))
        lector.leer_pagina = pagina_simulada
        self.servicio = ServicioLector(cargar_configuracion(), lector)
        self.cliente = crear_app(self.servicio, precargar=False).test_client()

    def enviar(self, nombre, contenido):
        return self.cliente.post("/api/leer", data={"archivo": (io.BytesIO(contenido), nombre)},
                                 content_type="multipart/form-data")

    def imagen(self, tamano=(600, 800)):
        salida = io.BytesIO()
        Image.new("RGB", tamano, "white").save(salida, "PNG")
        return salida.getvalue()

    def test_pagina_principal_y_salud(self):
        respuesta = self.cliente.get("/")
        self.assertEqual(respuesta.status_code, 200)
        html = respuesta.get_data(as_text=True)
        self.assertIn("Lector de Facturas", html)
        self.assertIn("escrito a mano", html)                       # limitación visible antes de subir
        self.assertEqual(self.cliente.get("/salud").get_json()["estado"], "ok")

    def test_lectura_correcta(self):
        datos = self.enviar("factura.png", self.imagen()).get_json()
        self.assertEqual(datos["estado"], "ok")
        pagina = datos["paginas"][0]
        total = next(c for c in pagina["campos"] if c["clave"] == "total")
        self.assertEqual((total["valor"], total["confianza"]), ("42.72", "alta"))
        self.assertEqual(total["evidencia"]["caja"], [700.0, 900.0, 800.0, 930.0])
        self.assertTrue(pagina["vista_previa"]["imagen"].startswith("data:image/jpeg;base64,"))
        self.assertEqual(pagina["cuadre"]["nivel"], "ok")
        numero = next(c for c in pagina["campos"] if c["clave"] == "document_number")
        self.assertIsNone(numero["valor"])                          # vacío, nunca «0»
        self.assertNotIn("CLIENTE JUAN", json.dumps(datos))         # no devuelve el texto OCR completo

    def test_entradas_invalidas_con_mensaje_claro(self):
        casos = [("notas.txt", b"hola", "no admitido"), ("vacia.png", b"", "vacío"),
                 ("rota.jpg", b"no es una imagen", "dañada"),
                 ("diminuta.png", self.imagen((40, 300)), "lado menor")]
        for nombre, contenido, texto in casos:
            with self.subTest(nombre=nombre):
                respuesta = self.enviar(nombre, contenido)
                self.assertEqual(respuesta.status_code, 400)
                self.assertIn(texto, respuesta.get_json()["error"])
        sin_archivo = self.cliente.post("/api/leer", data={}, content_type="multipart/form-data")
        self.assertEqual(sin_archivo.status_code, 400)
        self.assertIn("No se recibió", sin_archivo.get_json()["error"])

    def test_archivo_demasiado_grande(self):
        grande = b"0" * int((self.servicio.limites()["tamano_maximo_mb"] + 1.5) * 1024 * 1024)
        respuesta = self.enviar("enorme.png", grande)
        self.assertEqual(respuesta.status_code, 413)
        self.assertIn("MB", respuesta.get_json()["error"])

    def test_error_interno_sin_detalles_tecnicos(self):
        with patch.object(self.servicio, "leer", side_effect=KeyError("ocr_views")), self.assertLogs("lector.app"):
            respuesta = self.enviar("factura.png", self.imagen())
        self.assertEqual(respuesta.status_code, 500)
        self.assertNotIn("KeyError", respuesta.get_json()["error"])
        self.assertIn("inesperado", respuesta.get_json()["error"])

    def test_modelo_no_disponible(self):
        with patch.object(self.servicio.lector, "cargar", side_effect=ErrorModelo("Tesseract no está instalado")), \
                self.assertLogs("lector.app"):
            respuesta = self.enviar("factura.png", self.imagen())
        self.assertEqual(respuesta.status_code, 503)
        self.assertIn("Tesseract", respuesta.get_json()["error"])

    def test_servidor_ocupado(self):
        self.servicio.espera_maxima = 0.05
        self.servicio.turnos.acquire()
        try:
            respuesta = self.enviar("factura.png", self.imagen())
        finally:
            self.servicio.turnos.release()
        self.assertEqual(respuesta.status_code, 503)
        self.assertIn("Espera", respuesta.get_json()["error"])

    def test_pagina_que_falla_no_tumba_el_documento(self):
        self.servicio.lector.leer_pagina = lambda ruta, numero=1: ResultadoPagina(
            pagina=numero, estado="error", error="No se pudo leer esta página.")
        datos = self.enviar("factura.png", self.imagen()).get_json()
        self.assertEqual(datos["estado"], "error")
        self.assertEqual(datos["paginas"][0]["error"], "No se pudo leer esta página.")

    def test_ejemplos_y_acerca(self):
        ejemplos = self.servicio.ejemplos()
        self.assertGreaterEqual(len(ejemplos), 3)
        datos = self.cliente.post(f"/api/ejemplo/{ejemplos[0]['id']}").get_json()
        self.assertEqual(datos["estado"], "ok")
        self.assertEqual(self.cliente.post("/api/ejemplo/no_existe").status_code, 400)
        acerca = self.cliente.get("/api/acerca").get_json()
        self.assertTrue(any("mano" in x for x in acerca["fuera_de_alcance"]))
        self.assertIn("exactitud_por_campo", acerca["evaluacion_final"])
        self.assertEqual(self.cliente.get("/api/no_existe").status_code, 404)


@unittest.skipUnless(HAY_FLASK and HAY_TESSERACT, "Requiere Flask, Tesseract y los pesos en models/")
class IntegracionAppTests(unittest.TestCase):
    def test_los_ejemplos_se_leen_bien(self):
        from app.servicio import ServicioLector
        servicio = ServicioLector()
        catalogo = json.loads((EJEMPLOS / "ejemplos.json").read_text(encoding="utf-8"))["ejemplos"]
        for ejemplo in catalogo:
            with self.subTest(ejemplo=ejemplo["id"]):
                pagina = servicio.leer(EJEMPLOS / ejemplo["archivo"])["paginas"][0]
                leidos = {c["clave"]: c["normalizado"] for c in pagina["campos"]}
                for campo in ("tax_id", "date", "subtotal", "tax", "total"):
                    self.assertEqual(leidos[campo], ejemplo["gold"][campo], campo)
                self.assertEqual(pagina["cuadre"]["estado"], "consistent")


if __name__ == "__main__":
    unittest.main()
