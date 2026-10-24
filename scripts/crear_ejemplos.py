"""Genera los comprobantes sintéticos de ejemplo de la interfaz (app/assets/ejemplos/).

Son documentos inventados, marcados como «EJEMPLO SINTÉTICO — SIN VALIDEZ TRIBUTARIA»: no
contienen datos de personas ni de empresas reales. Sirven para probar la interfaz sin subir
una factura propia y como prueba de humo del despliegue (``tests/test_app.py``).

Uso: ``python scripts/crear_ejemplos.py``
"""
from __future__ import annotations

import json
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

RAIZ = Path(__file__).resolve().parents[1]
DESTINO = RAIZ / "app" / "assets" / "ejemplos"
FUENTES = Path("/usr/share/fonts/truetype")


def fuente(nombre: str, tam: int) -> ImageFont.FreeTypeFont:
    for ruta in (FUENTES / "dejavu" / nombre, FUENTES / "liberation" / nombre):
        if ruta.is_file():
            return ImageFont.truetype(str(ruta), tam)
    return ImageFont.load_default(tam)


def factura_ferreteria() -> tuple[Image.Image, dict]:
    """Factura impresa tamaño media carta, formato parecido al RIDE ecuatoriano."""
    ancho, alto = 1240, 1560
    im = Image.new("RGB", (ancho, alto), "white")
    d = ImageDraw.Draw(im)
    titulo, normal, negrita, chica = (fuente("DejaVuSans-Bold.ttf", 40), fuente("DejaVuSans.ttf", 27),
                                      fuente("DejaVuSans-Bold.ttf", 27), fuente("DejaVuSans.ttf", 21))
    d.text((70, 60), "FERRETERÍA EL TORNILLO", font=titulo, fill="black")
    d.text((70, 115), "EJEMPLO SINTÉTICO - SIN VALIDEZ TRIBUTARIA", font=chica, fill="black")
    d.text((70, 150), "Av. Ejemplo 123 y Calle Ficticia, Guayaquil", font=chica, fill="black")
    d.rectangle((700, 55, 1170, 255), outline="black", width=3)
    d.text((725, 75), "RUC: 0991234567001", font=negrita, fill="black")
    d.text((725, 130), "FACTURA No.", font=titulo, fill="black")
    d.text((725, 190), "001-002-000004521", font=normal, fill="black")
    d.text((70, 300), "Fecha de emisión: 14/10/2026", font=normal, fill="black")
    d.text((70, 345), "Cliente: CONSUMIDOR FINAL", font=normal, fill="black")
    d.line((70, 410, 1170, 410), fill="black", width=2)
    d.text((70, 425), "Cant.", font=negrita, fill="black")
    d.text((200, 425), "Descripción", font=negrita, fill="black")
    d.text((780, 425), "P. unit.", font=negrita, fill="black")
    d.text((1000, 425), "Total", font=negrita, fill="black")
    d.line((70, 470, 1170, 470), fill="black", width=2)
    items = [(2, "Martillo de uña 16 oz", "8.50", "17.00"), (1, "Caja de clavos 2 pulg.", "4.20", "4.20"),
             (3, "Lija de agua N. 120", "0.75", "2.25"), (1, "Flexómetro 5 m", "6.90", "6.90"),
             (2, "Brocha 3 pulg.", "3.40", "6.80")]
    y = 490
    for cant, desc, unit, total in items:
        d.text((90, y), str(cant), font=normal, fill="black")
        d.text((200, y), desc, font=normal, fill="black")
        d.text((780, y), unit, font=normal, fill="black")
        d.text((1000, y), total, font=normal, fill="black")
        y += 55
    d.line((70, y + 10, 1170, y + 10), fill="black", width=2)
    y += 40
    for etiqueta, valor in (("SUBTOTAL", "37.15"), ("IVA 15%", "5.57"), ("TOTAL", "42.72")):
        f = negrita if etiqueta == "TOTAL" else normal
        d.text((700, y), etiqueta, font=f, fill="black")
        d.text((1000, y), valor, font=f, fill="black")
        y += 60
    d.text((70, alto - 120), "Forma de pago: efectivo", font=chica, fill="black")
    d.text((70, alto - 85), "Documento generado para pruebas del Lector de Facturas.", font=chica, fill="black")
    gold = {"tax_id": "0991234567001", "date": "2026-10-14", "document_number": "001-002-000004521",
            "subtotal": "37.15", "tax": "5.57", "total": "42.72"}
    return im, gold


def recibo_termico() -> tuple[Image.Image, dict]:
    """Recibo angosto de impresora térmica, fotografiado con el celular (inclinación y sombra)."""
    ancho, alto = 620, 1180
    im = Image.new("L", (ancho, alto), 250)
    d = ImageDraw.Draw(im)
    mono, mono_b = fuente("DejaVuSansMono.ttf", 24), fuente("DejaVuSansMono-Bold.ttf", 26)
    lineas = [("CAFETERÍA LA ESQUINA", mono_b), ("EJEMPLO SINTÉTICO", mono), ("RUC 1790012345001", mono),
              ("Quito - Ecuador", mono), ("", mono), ("FACTURA 002-001-000078934", mono),
              ("FECHA: 21/09/2026  10:42", mono), ("--------------------------------", mono),
              ("1 CAPUCCINO GRANDE      3.50", mono), ("2 PAN DE YUCA           2.40", mono),
              ("1 JUGO DE NARANJA       2.25", mono), ("--------------------------------", mono),
              ("SUBTOTAL               8.15", mono), ("IVA 15%                1.22", mono),
              ("TOTAL                  9.37", mono_b), ("EFECTIVO              20.00", mono),
              ("CAMBIO                10.63", mono), ("", mono), ("GRACIAS POR SU COMPRA", mono)]
    y = 50
    for texto, f in lineas:
        d.text((40, y), texto, font=f, fill=25)
        y += 52
    # Simula una foto: fondo de mesa, inclinación leve, sombra lateral, desenfoque y ruido.
    lienzo = Image.new("L", (ancho + 220, alto + 220), 150)
    lienzo.paste(im, (110, 110))
    lienzo = lienzo.rotate(-2.5, resample=Image.BICUBIC, fillcolor=150)
    sombra = Image.linear_gradient("L").rotate(90).resize(lienzo.size)
    lienzo = Image.composite(lienzo, ImageEnhance.Brightness(lienzo).enhance(0.72), sombra)
    lienzo = lienzo.filter(ImageFilter.GaussianBlur(0.8))
    rng = random.Random(7)
    ruido = Image.effect_noise(lienzo.size, 10)
    lienzo = Image.blend(lienzo, ruido, 0.06)
    del rng
    gold = {"tax_id": "1790012345001", "date": "2026-09-21", "document_number": "002-001-000078934",
            "subtotal": "8.15", "tax": "1.22", "total": "9.37"}
    return lienzo.convert("RGB"), gold


def main() -> None:
    DESTINO.mkdir(parents=True, exist_ok=True)
    catalogo = []
    factura, gold_factura = factura_ferreteria()
    factura.save(DESTINO / "factura_impresa.png", optimize=True)
    factura.save(DESTINO / "factura_digital.pdf", resolution=150)
    recibo, gold_recibo = recibo_termico()
    recibo.save(DESTINO / "recibo_fotografiado.jpg", quality=88)
    catalogo += [
        {"id": "factura_impresa", "archivo": "factura_impresa.png", "titulo": "Factura impresa",
         "descripcion": "Escaneo limpio de una factura con RUC, número y desglose de IVA.", "gold": gold_factura},
        {"id": "recibo_fotografiado", "archivo": "recibo_fotografiado.jpg", "titulo": "Recibo fotografiado",
         "descripcion": "Foto de celular inclinada y con sombra; incluye efectivo y cambio.", "gold": gold_recibo},
        {"id": "factura_digital", "archivo": "factura_digital.pdf", "titulo": "Factura en PDF",
         "descripcion": "La misma factura como PDF de una página.", "gold": gold_factura},
    ]
    (DESTINO / "ejemplos.json").write_text(json.dumps({"sinteticos": True, "ejemplos": catalogo},
                                                      ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Ejemplos en", DESTINO)


if __name__ == "__main__":
    main()
