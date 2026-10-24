"""Pruebas de src/line_classifier.py (técnica de comparación aprendida)."""
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from src import line_classifier as LC  # noqa: E402

NORMALIZACION = {"date_order": "auto", "decimal_separator": "auto"}


def ocr(lineas):
    palabras = []
    for fila, texto in enumerate(lineas):
        x = 10
        for palabra in texto.split():
            palabras.append({"text": palabra, "box": [x, 20 + fila * 30, x + 12 * len(palabra), 40 + fila * 30]})
            x += 12 * len(palabra) + 12
    return {"words": palabras, "width": 600, "height": 40 + 30 * len(lineas)}


def documento(i, total, fecha="12/03/2020"):
    lineas = [f"TIENDA {i}", f"FECHA {fecha}", f"ITEM A {total / 2:.2f}", f"CASH {total + 10:.2f}",
              f"TOTAL {total:.2f}"]
    gold = {c: {"status": "unannotated", "value": None} for c in ("tax_id", "document_number", "subtotal", "tax")}
    gold["total"] = {"status": "annotated", "value": f"{total:.2f}"}
    gold["date"] = {"status": "annotated", "value": fecha}
    fila = {"id": f"sroie/train/{i}", "dataset": "sroie", "gold": gold}
    return fila, ocr(lineas)


class LineasTests(unittest.TestCase):
    def test_candidatos_y_etiquetas_debiles(self):
        fila, lectura = documento(1, 25.5)
        lineas = LC.lineas_documento(lectura, NORMALIZACION)
        self.assertEqual(len(lineas), 5)
        self.assertEqual([v[1] for v in LC.candidatos("TOTAL 25.50", "total", NORMALIZACION)], ["25.50"])
        etiq = LC.etiquetas(lineas, fila["gold"], NORMALIZACION)
        self.assertEqual(etiq["total"].tolist(), [0, 0, 0, 0, 1])
        self.assertEqual(int(etiq["date"].sum()), 1)
        self.assertIsNone(etiq["subtotal"])                   # no anotado: no se usa para entrenar
        self.assertEqual(lineas[3]["tiene_mayor"], 1.0)       # CASH es el monto mayor

    def test_caracterizador_reemplaza_digitos(self):
        self.assertEqual(LC._texto_para_tfidf("Total 12.30"), "total 00.00")


class EntrenamientoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        rng = np.random.default_rng(0)
        pares = [documento(i, float(rng.integers(500, 9000)) / 100) for i in range(60)]
        filas = [p[0] for p in pares]
        lecturas = {p[0]["id"]: p[1] for p in pares}
        docs = LC.preparar_documentos(filas, lecturas, NORMALIZACION)
        cls.train, cls.val = docs[:40], docs[40:]
        cls.cz = LC.Caracterizador(max_rasgos=300).ajustar([x["texto"] for d in cls.train for x in d["lineas"]])

    def test_entrena_registra_historial_y_extrae(self):
        a = LC.armar_conjunto(self.train, "total", self.cz)
        b = LC.armar_conjunto(self.val, "total", self.cz)
        red, historial = LC.entrenar(a, b, LC.ConfigRed(capas=(16,), epocas=60, paciencia=10, tasa=0.01), semilla=1)
        tabla = historial.tabla()
        self.assertTrue({"perdida_train", "perdida_val", "f1_train", "f1_val"} <= set(tabla.columns))
        self.assertLessEqual(len(tabla), 60)
        resumen = LC.cuantificar(tabla, restaurada=True)
        self.assertGreater(resumen["f1_val_final"], 0.9)
        self.assertEqual(LC.diagnosticar(resumen), "adecuado")
        redes = {"total": red}
        modelo = LC.ClasificadorLineas(self.cz, redes, umbral=0.5)
        campos = modelo.extraer(self.val[0]["lineas"])
        self.assertEqual(campos["total"], self.val[0]["fila"]["gold"]["total"]["value"])
        self.assertIsNone(campos["date"])                       # sin red para la fecha: queda vacío
        prediccion = modelo.predecir(self.val[:2])
        self.assertEqual(prediccion[0]["status"], "ok")

    def test_diagnostico_y_sensibilidad_de_umbrales(self):
        sobreajuste = {"subida_perdida_val_pct": 40.0, "brecha_f1": 0.2, "f1_train_final": 0.99}
        corto = {"subida_perdida_val_pct": 0.0, "brecha_f1": 0.01, "f1_train_final": 0.5}
        bien = {"subida_perdida_val_pct": 3.0, "brecha_f1": 0.04, "f1_train_final": 0.9}
        self.assertEqual([LC.diagnosticar(r) for r in (sobreajuste, corto, bien)],
                         ["overfitting", "underfitting", "adecuado"])
        tabla = LC.sensibilidad_umbrales({"a": sobreajuste, "b": bien}, subidas=(5, 50), brechas=(0.05, 0.3))
        self.assertEqual(len(tabla), 8)
        self.assertIn("adecuado", set(tabla[tabla.modelo == "a"].diagnostico))   # con umbrales laxos cambia
        self.assertIsInstance(tabla, pd.DataFrame)


if __name__ == "__main__":
    unittest.main()
