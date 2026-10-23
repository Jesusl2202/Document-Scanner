"""Pruebas de src/data_processing.py y de la configuración (src/utils.py).

Cubren las funciones críticas antes del OCR: validar la entrada, convertir PDF,
preprocesar, normalizar y preparar los datasets.
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from src.data_processing import (  # noqa: E402
    cargar_paginas, cobertura_etiquetas, coordenadas_originales, localizar_datasets, normalizar_campo,
    normalizar_fecha, normalizar_monto, preparar_datasets, preprocesar_imagen, resumir_particiones,
    validar_archivo)
from src.utils import ErrorConfiguracion, ErrorEntrada, cargar_configuracion, ruta_proyecto  # noqa: E402

MUESTRA_PNG = RAIZ / "samples" / "synthetic_receipt.png"
MUESTRA_PDF = RAIZ / "samples" / "synthetic_receipt.pdf"


class ConfiguracionTests(unittest.TestCase):
    def test_carga_config_por_defecto_con_rutas_relativas(self):
        config = cargar_configuracion()
        self.assertIn(".pdf", config["entrada"]["extensiones"])
        self.assertFalse(Path(config["rutas"]["configuracion_modelo"]).is_absolute())
        self.assertTrue(ruta_proyecto(config["rutas"]["configuracion_modelo"]).is_file())

    def test_variable_de_entorno_reemplaza_valor(self):
        with patch.dict(os.environ, {"LECTOR_NIVEL_LOG": "DEBUG"}):
            self.assertEqual(cargar_configuracion()["registro"]["nivel"], "DEBUG")

    def test_configuracion_invalida_da_mensaje_claro(self):
        with tempfile.TemporaryDirectory() as carpeta:
            sin_secciones = Path(carpeta) / "config.yaml"
            sin_secciones.write_text("rutas: {}\n", encoding="utf-8")
            with self.assertRaisesRegex(ErrorConfiguracion, "Faltan secciones"):
                cargar_configuracion(sin_secciones)
            negativo = Path(carpeta) / "negativo.yaml"
            texto = (RAIZ / "configs" / "config.yaml").read_text(encoding="utf-8")
            negativo.write_text(texto.replace("tamano_maximo_mb: 20", "tamano_maximo_mb: -1"), encoding="utf-8")
            with self.assertRaisesRegex(ErrorConfiguracion, "tamano_maximo_mb"):
                cargar_configuracion(negativo)
            with self.assertRaises(ErrorConfiguracion):
                cargar_configuracion(Path(carpeta) / "no_existe.yaml")


class ValidacionEntradaTests(unittest.TestCase):
    def setUp(self):
        self.temporal = tempfile.TemporaryDirectory()
        self.carpeta = Path(self.temporal.name)

    def tearDown(self):
        self.temporal.cleanup()

    def test_imagen_y_pdf_validos(self):
        imagen = validar_archivo(MUESTRA_PNG)
        self.assertEqual((imagen.tipo, imagen.paginas), ("imagen", 1))
        self.assertEqual(imagen.dimensiones, (850, 680))
        pdf = validar_archivo(MUESTRA_PDF)
        self.assertEqual((pdf.tipo, pdf.paginas), ("pdf", 1))

    def test_rechaza_archivo_inexistente_vacio_o_de_otro_formato(self):
        with self.assertRaisesRegex(ErrorEntrada, "No se encontró"):
            validar_archivo(self.carpeta / "falta.png")
        vacio = self.carpeta / "vacio.png"
        vacio.write_bytes(b"")
        with self.assertRaisesRegex(ErrorEntrada, "vacío"):
            validar_archivo(vacio)
        texto = self.carpeta / "factura.docx"
        texto.write_text("hola", encoding="utf-8")
        with self.assertRaisesRegex(ErrorEntrada, "no admitido"):
            validar_archivo(texto)

    def test_rechaza_imagen_danada_o_demasiado_pequena(self):
        falsa = self.carpeta / "falsa.jpg"
        falsa.write_bytes(b"esto no es una imagen")
        with self.assertRaisesRegex(ErrorEntrada, "dañada"):
            validar_archivo(falsa)
        pequena = self.carpeta / "pequena.png"
        Image.new("RGB", (60, 400), "white").save(pequena)
        with self.assertRaisesRegex(ErrorEntrada, "lado menor"):
            validar_archivo(pequena)

    def test_respeta_limites_configurables(self):
        config = cargar_configuracion()
        config["entrada"]["paginas_maximas_pdf"] = 0.5
        with self.assertRaisesRegex(ErrorEntrada, "páginas"):
            validar_archivo(MUESTRA_PDF, config)
        config = cargar_configuracion()
        config["entrada"]["tamano_maximo_mb"] = 0.001
        with self.assertRaisesRegex(ErrorEntrada, "MB"):
            validar_archivo(MUESTRA_PNG, config)

    def test_pdf_se_convierte_en_una_imagen_por_pagina(self):
        paginas = cargar_paginas(MUESTRA_PDF, self.carpeta / "paginas")
        self.assertEqual(len(paginas), 1)
        with Image.open(paginas[0]) as imagen:
            self.assertGreater(imagen.size[0], 500)
        self.assertEqual(cargar_paginas(MUESTRA_PNG, self.carpeta), [MUESTRA_PNG])


class PreprocesamientoTests(unittest.TestCase):
    def test_coordenadas_vuelven_a_la_imagen_original(self):
        imagen = Image.new("L", (400, 300), 255)
        opciones = {"target_long_edge": 1200, "max_scale": 3, "border": 20, "max_pixels": 25_000_000}
        salida, transformacion = preprocesar_imagen(imagen, "resize", opciones)
        self.assertEqual(salida.size, (1240, 940))
        caja = [100, 50, 200, 80]
        ampliada = [v * 3 + 20 for v in caja]
        self.assertEqual([round(v, 6) for v in coordenadas_originales(ampliada, transformacion)], caja)

    def test_todos_los_metodos_del_modelo_funcionan(self):
        for metodo in ("original", "resize", "otsu", "illumination", "denoise", "local_binary"):
            with self.subTest(metodo=metodo):
                salida, _ = preprocesar_imagen(MUESTRA_PNG, metodo)
                self.assertGreater(min(salida.size), 100)
        with self.assertRaises(ValueError):
            preprocesar_imagen(MUESTRA_PNG, "magia")


class NormalizacionTests(unittest.TestCase):
    def test_montos(self):
        self.assertEqual(normalizar_monto("1.234,50"), "1234.50")
        self.assertEqual(normalizar_monto("$ 112.00"), "112.00")
        self.assertIsNone(normalizar_monto("1.234"))          # punto de miles o decimal: ambiguo
        self.assertEqual(normalizar_campo("total", "RM 12,30"), "12.30")

    def test_fechas_no_se_adivinan(self):
        self.assertEqual(normalizar_fecha("25/12/2018"), "2018-12-25")
        self.assertTrue(normalizar_fecha("05/03/2018").startswith("AMBIGUOUS:"))
        self.assertEqual(normalizar_fecha("05/03/2018", "dmy"), "2018-03-05")   # Ecuador: día/mes/año
        with self.assertRaises(ValueError):
            normalizar_fecha("05/03/2018", "ymd")

    def test_campo_desconocido(self):
        with self.assertRaises(ValueError):
            normalizar_campo("propina", "1.00")
        self.assertEqual(normalizar_campo("tax_id", " 0991 234 567001 "), "0991234567001")


class DatasetsTests(unittest.TestCase):
    def test_localiza_datasets_por_contenido(self):
        with tempfile.TemporaryDirectory() as carpeta:
            raiz = Path(carpeta)
            for sub in ("x/sroie/train/img", "x/sroie/train/box", "x/sroie/train/entities", "y/wild"):
                (raiz / sub).mkdir(parents=True)
            for nombre in ("class_list.txt", "train.txt", "test.txt"):
                (raiz / "y/wild" / nombre).write_text("", encoding="utf-8")
            self.assertEqual(localizar_datasets(raiz), (raiz / "x/sroie", raiz / "y/wild"))
            self.assertEqual(localizar_datasets(raiz / "no_existe"), (None, None))

    def test_preparar_sin_datasets_falla_con_mensaje(self):
        with self.assertRaisesRegex(ErrorEntrada, "SROIE"):
            preparar_datasets(None, None, "outputs/x", {})

    def test_resumenes_de_particion_y_cobertura(self):
        def fila(dataset, split, fecha):
            gold = {c: {"status": "unannotated", "value": None}
                    for c in ("tax_id", "date", "document_number", "subtotal", "tax", "total")}
            gold["date"] = {"status": "annotated" if fecha else "unannotated", "value": fecha}
            return {"dataset": dataset, "split": split, "gold": gold}
        filas = [fila("sroie", "train", "01/02/2020"), fila("sroie", "validation", None),
                 fila("sroie", "test", "03/04/2020")]
        self.assertEqual(resumir_particiones(filas)[("sroie", "train")], 1)
        cobertura = cobertura_etiquetas(filas)
        self.assertEqual(cobertura[("sroie", "date")], 0.5)       # el test no cuenta
        self.assertEqual(cobertura[("sroie", "total")], 0.0)


if __name__ == "__main__":
    unittest.main()
