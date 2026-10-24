"""Pruebas de src/validation.py (Workshop S5: validación en contextos simulados)."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd
from PIL import Image

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from src import validation as V  # noqa: E402

NORMALIZACION = {"date_order": "auto", "decimal_separator": "auto"}


def fila(ident, dataset="sroie", split="train", sha=None):
    return {"id": ident, "dataset": dataset, "split": split, "sha256": sha or f"h_{ident}", "gold": {}}


class MuestraTests(unittest.TestCase):
    def test_excluye_revisados_y_repetidos(self):
        filas = [fila(f"s{i}") for i in range(10)] + [fila(f"w{i}", "wildreceipt") for i in range(10)]
        filas += [fila("t1", split="test", sha="h_s3"), fila("v1", split="validation")]
        revisados = {"s0": "x", "otro": "h_w1"}
        muestra, plan = V.muestra_no_revisada(filas, revisados, n_por_base=4, semilla=1)
        ids = {f["id"] for f in muestra}
        self.assertEqual(len(muestra), 8)
        self.assertTrue(ids.isdisjoint({"s0", "w1", "s3", "t1", "v1"}))   # revisado, hash revisado, hash en test
        self.assertEqual(plan["exclusiones"], {"ya_revisado": 2, "imagen_en_otra_particion": 1, "imagen_duplicada": 0})
        self.assertEqual(plan["elegibles_por_base"], {"sroie": 8, "wildreceipt": 9})

    def test_misma_semilla_misma_muestra(self):
        filas = [fila(f"s{i}") for i in range(30)]
        a, plan_a = V.muestra_no_revisada(filas, {}, 5, 42)
        b, plan_b = V.muestra_no_revisada(list(reversed(filas)), {}, 5, 42)
        self.assertEqual([f["id"] for f in a], [f["id"] for f in b])
        self.assertEqual(plan_a["firma_muestra"], plan_b["firma_muestra"])


class EscenariosTests(unittest.TestCase):
    def setUp(self):
        self.imagen = Image.new("RGB", (400, 600), "white")
        for x in range(50, 350, 10):
            for y in range(100, 500, 40):
                self.imagen.putpixel((x, y), (0, 0, 0))

    def test_cada_escenario_produce_una_imagen_valida_y_determinista(self):
        for escenario in V.ESCENARIOS:
            with self.subTest(escenario=escenario.etiqueta):
                a = V.perturbar_imagen(self.imagen, escenario, 3)
                b = V.perturbar_imagen(self.imagen, escenario, 3)
                self.assertEqual(a.tobytes(), b.tobytes())
                self.assertEqual(a.mode, "RGB")

    def test_tamanos_esperados(self):
        por_clave = {e.etiqueta: e for e in V.ESCENARIOS}
        self.assertEqual(V.perturbar_imagen(self.imagen, por_clave["resolucion_0.5"]).size, (200, 300))
        self.assertEqual(V.perturbar_imagen(self.imagen, por_clave["recorte_0.2"]).size, (400, 480))
        self.assertGreater(V.perturbar_imagen(self.imagen, por_clave["rotacion_6"]).size[0], 400)
        with self.assertRaises(ValueError):
            V.perturbar_imagen(self.imagen, V.Escenario("magia", 1, "", ""))

    def test_filas_perturbadas_actualizan_imagen_y_hash(self):
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = Path(carpeta) / "a.png"
            self.imagen.save(ruta)
            original = {"id": "sroie/train/a", "image": str(ruta), "sha256": "x", "gold": {"total": 1}}
            nuevas = V.filas_perturbadas([original], V.ESCENARIOS[5], Path(carpeta) / "p")
            self.assertNotEqual(nuevas[0]["image"], str(ruta))
            self.assertEqual((nuevas[0]["width"], nuevas[0]["height"]), (200, 300))
            self.assertNotEqual(nuevas[0]["sha256"], "x")
            self.assertEqual(nuevas[0]["gold"], original["gold"])           # las referencias no cambian


def corrida(carpeta: Path, errores: list[dict], predicciones: list[dict]) -> Path:
    (carpeta / "evaluation").mkdir(parents=True)
    pd.DataFrame(errores).to_csv(carpeta / "evaluation" / "errors.csv", index=False, encoding="utf-8-sig")
    (carpeta / "predictions.jsonl").write_text("\n".join(json.dumps(p) for p in predicciones), encoding="utf-8")
    return carpeta


def prediccion(ident, campos, vistas_por_campo):
    evidencia = {c: [{"value": v, "view": i} for i in range(vistas_por_campo[c])] for c, v in campos.items()}
    return {"id": ident, "status": "ok", "fields": campos, "evidence": evidencia, "alerts": [],
            "ocr": {"views": [{}] * 10}}


class DetalleTests(unittest.TestCase):
    def setUp(self):
        self.temporal = tempfile.TemporaryDirectory()
        errores = [
            {"id": "d1", "dataset": "sroie", "field": "date", "predicted_normalized": "2020-01-02", "correct": 1},
            {"id": "d1", "dataset": "sroie", "field": "total", "predicted_normalized": "9.00", "correct": 0},
            {"id": "d2", "dataset": "sroie", "field": "date", "predicted_normalized": None, "correct": 0},
            {"id": "d2", "dataset": "sroie", "field": "total", "predicted_normalized": "5.00", "correct": 1},
        ]
        predicciones = [prediccion("d1", {"date": "02/01/2020", "total": "9.00"}, {"date": 9, "total": 8}),
                        prediccion("d2", {"date": None, "total": "5.00"}, {"date": 0, "total": 2})]
        self.detalle = V.detalle_campos(corrida(Path(self.temporal.name), errores, predicciones), NORMALIZACION)

    def tearDown(self):
        self.temporal.cleanup()

    def test_tipos_y_errores_silenciosos(self):
        d = self.detalle.set_index(["id", "field"])
        self.assertEqual(d.loc[("d1", "total"), "tipo"], "equivocado")
        self.assertEqual(d.loc[("d1", "total"), "confianza"], "alta")
        self.assertTrue(d.loc[("d1", "total"), "silencioso"])
        self.assertEqual(d.loc[("d2", "date"), "tipo"], "omision")
        self.assertEqual(d.loc[("d2", "total"), "confianza"], "baja")          # 2 de 10 vistas
        resumen = V.resumen_errores(self.detalle)
        self.assertEqual((resumen["exactitud"], resumen["omisiones"], resumen["silenciosos"]), (50.0, 25.0, 25.0))

    def test_por_documento_calibracion_y_tiempos(self):
        por_doc = V.exactitud_por_documento(self.detalle)
        self.assertEqual(por_doc["todo_correcto"], 0.0)
        self.assertAlmostEqual(por_doc["esperado_si_independientes"], 25.0)
        cal = V.calibracion(self.detalle).set_index("confianza")
        self.assertEqual(cal.loc["alta", "campos"], 2)
        tiempos = V.tiempo_revision(self.detalle).set_index("forma de trabajo")
        manual = tiempos.loc["Manual (sin el sistema)", "segundos_por_documento"]
        self.assertAlmostEqual(manual, 2 * V.TIEMPOS_SUPUESTOS["digitar"])
        self.assertLess(tiempos.loc["Revisión completa", "segundos_por_documento"], manual)
        guiada = tiempos.loc["Revisión guiada por la confianza"]
        self.assertEqual(guiada["errores_sin_corregir_por_100_documentos"], 50.0)
        self.assertEqual(len(V.sensibilidad_tiempos(self.detalle)), 3)
        inferior, superior = V.bootstrap_exactitud(self.detalle, repeticiones=200)
        self.assertLessEqual(inferior, 50.0)
        self.assertGreaterEqual(superior, 50.0)


if __name__ == "__main__":
    unittest.main()
