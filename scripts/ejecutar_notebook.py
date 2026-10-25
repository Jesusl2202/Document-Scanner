"""Ejecuta un notebook de principio a fin y guarda sus salidas (local o integración continua).

Los notebooks están preparados para Google Colab. Este script los ejecuta con el código del
propio repositorio (``USAR_CODIGO_LOCAL = True``) y con los datos de ``--datos``; al guardar,
deja la celda de configuración con sus valores originales para que el notebook siga abriéndose
igual en Colab.

Uso::

    python scripts/ejecutar_notebook.py notebooks/05_evaluacion.ipynb --datos data/raw

Requiere ``pip install nbclient ipykernel``.
"""
from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path

import nbformat
from nbclient import NotebookClient

RAIZ = Path(__file__).resolve().parents[1]


def parametrizar(fuente: str, valores: dict[str, str]) -> str:
    for variable, valor in valores.items():
        fuente, n = re.subn(rf"^{variable} = .*?(?=\s*#|$)", f"{variable} = {valor}", fuente, count=1, flags=re.M)
        if n != 1:
            raise ValueError(f"No se encontró la variable {variable} en la celda de configuración")
    return fuente


def main(argumentos: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("notebook")
    parser.add_argument("--datos", default="data/raw", help="Carpeta con SROIE y WildReceipt")
    parser.add_argument("--salida", default=None, help="Dónde guardar el notebook ejecutado (por defecto, encima)")
    parser.add_argument("--tiempo-celda", type=int, default=None, help="Segundos máximos por celda (sin límite)")
    args = parser.parse_args(argumentos)

    ruta = Path(args.notebook).resolve()
    nb = nbformat.read(ruta, as_version=4)
    configuracion = next(c for c in nb.cells if c.cell_type == "code" and "USAR_CODIGO_LOCAL = " in c.source)
    original = configuracion.source
    configuracion.source = parametrizar(original, {"USAR_CODIGO_LOCAL": "True", "CODIGO_LOCAL": repr(str(RAIZ)),
                                                   "DATOS_MANUAL": repr(str(Path(args.datos).resolve()))})
    inicio = time.perf_counter()
    cliente = NotebookClient(nb, timeout=args.tiempo_celda, kernel_name="python3",
                             resources={"metadata": {"path": str(ruta.parent)}})
    try:
        cliente.execute()
        estado = 0
    except Exception as exc:  # noqa: BLE001 - se guarda igual el notebook con la celda que falló
        print(f"Falló la ejecución: {exc}", file=sys.stderr)
        estado = 1
    configuracion.source = original
    destino = Path(args.salida) if args.salida else ruta
    nbformat.write(nb, destino)
    minutos = (time.perf_counter() - inicio) / 60
    print(f"{ruta.name}: {'ok' if estado == 0 else 'con errores'} en {minutos:.1f} min -> {destino}")
    return estado


if __name__ == "__main__":
    sys.exit(main())
