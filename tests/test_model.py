"""Pruebas de src/model.py: carga del modelo, lectura, confianza y manejo de errores.

Las pruebas principales simulan el OCR para ser rápidas y no depender de Tesseract.
La prueba de integración usa Tesseract real y se omite si no está instalado o si los
pesos no están descargados en models/.
"""
import copy
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from src.model import CAMPOS, LectorFacturas, ResultadoDocumento, calcular_confianza  # noqa: E402
from src.utils import ErrorEntrada, ErrorModelo, cargar_configuracion  # noqa: E402

MODELO = json.loads((RAIZ / "configs" / "definitivo.json").read_text(encoding="utf-8"))
MUESTRA_PNG = RAIZ / "samples" / "synthetic_receipt.png"
MUESTRA_PDF = RAIZ / "samples" / "synthetic_receipt.pdf"


def vista(lineas, primaria=False):
    """Lectura OCR simulada: una palabra por token, una fila cada 30 px."""
    palabras = []
    for fila, texto in enumerate(lineas):
        x = 10
        for palabra in texto.split():
            palabras.append({"text": palabra, "box": [x, fila * 30, x + len(palabra) * 10, fila * 30 + 20],
                             "line_id": str(fila), "confidence": 90})
            x += len(palabra) * 10 + 10
    opciones = {"preprocess": "resize", "psm": 6} if primaria else {"preprocess": "otsu", "psm": 6}
    return {"words": palabras, "options": opciones, "text": "\n".join(lineas), "width": 600,
            "height": 30 * len(lineas) + 20}


RECIBO = ["DEMO STORE", "DATE: 27/09/2026", "SUBTOTAL 100.00", "TAX 12.00", "TOTAL 112.00"]


def ocr_simulado(lineas_por_vista):
    vistas = [vista(lineas, i == 0) for i, lineas in enumerate(lineas_por_vista)]
    return dict(vistas[0], views=vistas, cache_hit=False, view_errors=[])


def lector_simulado():
    """LectorFacturas que no necesita Tesseract ni descargar pesos."""
    lector = LectorFacturas(cargar_configuracion())
    with patch("src.model.shutil.which", return_value="/usr/bin/tesseract"), \
            patch("src.model.bind_models", side_effect=lambda config, carpeta: copy.deepcopy(config)):
        lector.cargar()
    return lector


class CargaTests(unittest.TestCase):
    def test_sin_tesseract_da_error_claro(self):
        with patch("src.model.shutil.which", return_value=None):
            with self.assertRaisesRegex(ErrorModelo, "Tesseract no está instalado"):
                LectorFacturas().cargar()

    def test_sin_internet_para_los_pesos_da_error_claro(self):
        import urllib.error
        with patch("src.model.shutil.which", return_value="/usr/bin/tesseract"), \
                patch("src.model.bind_models", side_effect=urllib.error.URLError("sin red")):
            with self.assertRaisesRegex(ErrorModelo, "conexión a Internet"):
                LectorFacturas().cargar()

    def test_carga_una_sola_vez(self):
        lector = lector_simulado()
        self.assertTrue(lector.cargado)
        with patch("src.model.bind_models") as volver_a_cargar:
            lector.cargar()
        volver_a_cargar.assert_not_called()


class LecturaSimuladaTests(unittest.TestCase):
    def setUp(self):
        self.lector = lector_simulado()

    def leer(self, ocr, archivo=MUESTRA_PNG, salida=None):
        with patch("lector_facturas.cli.transcribe", return_value=ocr):
            return self.lector.leer(archivo, salida)

    def test_extrae_los_campos_y_cuadra_los_montos(self):
        resultado = self.leer(ocr_simulado([RECIBO, RECIBO, RECIBO]))
        campos = resultado.campos()
        self.assertEqual((campos["subtotal"], campos["tax"], campos["total"]), ("100.00", "12.00", "112.00"))
        self.assertEqual(resultado.estado, "ok")
        self.assertEqual(resultado.paginas[0].validacion["amount_balance"], "consistent")
        self.assertEqual(set(resultado.paginas[0].confianza), set(CAMPOS))

    def test_confianza_alta_cuando_todas_las_vistas_coinciden(self):
        pagina = self.leer(ocr_simulado([RECIBO, RECIBO, RECIBO])).paginas[0]
        self.assertEqual(pagina.confianza["total"]["nivel"], "alta")
        self.assertEqual(pagina.confianza["total"]["vistas"], 3)
        self.assertEqual(pagina.confianza["document_number"]["nivel"], "sin_valor")

    def test_nunca_inventa_un_total_que_no_se_leyo(self):
        sin_total = ["DEMO STORE", "SUBTOTAL 100.00"]
        campos = self.leer(ocr_simulado([sin_total, sin_total])).campos()
        self.assertIsNone(campos["total"])          # ya no supone total = subtotal

    def test_una_pagina_que_falla_no_detiene_el_documento(self):
        with patch("lector_facturas.cli.transcribe", side_effect=RuntimeError("Ninguna lectura OCR útil")), \
                self.assertLogs("lector.modelo", level="ERROR"):
            resultado = self.lector.leer(MUESTRA_PNG)
        self.assertEqual(resultado.estado, "error")
        self.assertIn("error inesperado", resultado.paginas[0].error)

    def test_pdf_y_archivos_de_salida(self):
        with tempfile.TemporaryDirectory() as carpeta:
            resultado = self.leer(ocr_simulado([RECIBO, RECIBO]), MUESTRA_PDF, Path(carpeta) / "salida")
            self.assertEqual(len(resultado.paginas), 1)
            csv = (Path(carpeta) / "salida" / "campos.csv").read_text(encoding="utf-8-sig")
            self.assertIn("100.00,12.00,112.00", csv)
            datos = json.loads((Path(carpeta) / "salida" / "resultado.json").read_text(encoding="utf-8"))
            self.assertEqual(datos["paginas"][0]["campos"]["total"], "112.00")

    def test_entrada_invalida_se_rechaza_antes_del_ocr(self):
        with tempfile.TemporaryDirectory() as carpeta:
            archivo = Path(carpeta) / "notas.txt"
            archivo.write_text("x", encoding="utf-8")
            with patch("lector_facturas.cli.transcribe") as ocr:
                with self.assertRaises(ErrorEntrada):
                    self.lector.leer(archivo)
            ocr.assert_not_called()


class ConfianzaTests(unittest.TestCase):
    NORMALIZACION = {"date_order": "auto", "decimal_separator": "auto"}

    def test_niveles_segun_acuerdo_entre_vistas_y_alertas(self):
        evidencia = {"total": [{"value": "112.00", "view": v} for v in range(2)] + [{"value": "11.20", "view": 2}],
                     "tax": [{"value": "12,00", "view": 0}]}
        campos = {c: None for c in CAMPOS}
        campos.update(total="112.00", tax="12.00")
        resultado = calcular_confianza(campos, evidencia, [], 10, self.NORMALIZACION)
        self.assertEqual((resultado["total"]["nivel"], resultado["total"]["acuerdo"]), ("baja", 0.2))
        resultado = calcular_confianza(campos, evidencia, [], 3, self.NORMALIZACION)
        self.assertEqual(resultado["total"]["nivel"], "alta")            # 2 de 3 vistas
        self.assertEqual(resultado["tax"]["nivel"], "media")             # 12,00 y 12.00 son el mismo valor
        con_alerta = calcular_confianza(campos, evidencia, ["total:observed_accounting_selection"], 3,
                                        self.NORMALIZACION)
        self.assertEqual(con_alerta["total"]["nivel"], "media")          # una alerta baja un escalón


@unittest.skipUnless(shutil.which("tesseract") and (RAIZ / "models" / "fast" / "eng.traineddata").is_file()
                     and (RAIZ / "models" / "best" / "eng.traineddata").is_file(),
                     "Requiere Tesseract y los pesos en models/ (se descargan con la primera lectura)")
class IntegracionTesseractTests(unittest.TestCase):
    def test_lee_el_recibo_sintetico_completo(self):
        gold = json.loads((RAIZ / "samples" / "synthetic_gold.json").read_text(encoding="utf-8"))["fields"]
        resultado = LectorFacturas().leer(MUESTRA_PNG)
        self.assertEqual(resultado.campos(), gold)
        self.assertIsInstance(resultado, ResultadoDocumento)


if __name__ == "__main__":
    unittest.main()
