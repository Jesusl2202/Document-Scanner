"""Exporta a CSV los hashes de los documentos ya usados en desarrollo y selección.

Lee configs/documentos_revisados.json (id -> SHA-256 de la imagen) y escribe
data/processed/documentos_revisados.csv. No necesita descargar ningún dataset:
solo contiene identificadores y hashes, nunca imágenes ni anotaciones.

Uso, desde la raíz del repositorio:
    python scripts/exportar_documentos_revisados.py
"""
import argparse
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--entrada", default=str(ROOT / "configs/documentos_revisados.json"))
    parser.add_argument("--salida", default=str(ROOT / "data/processed/documentos_revisados.csv"))
    args = parser.parse_args()

    entrada, salida = Path(args.entrada), Path(args.salida)
    if not entrada.is_file():
        raise FileNotFoundError(f"No existe {entrada}")
    registros = json.loads(entrada.read_text(encoding="utf-8"))

    filas = []
    for identificador, sha256 in registros.items():
        # El id tiene la forma <dataset>/<split_origen>/<documento>; el documento puede contener "/".
        dataset, split_origen, documento = identificador.split("/", 2)
        filas.append((dataset, split_origen, documento, sha256))
    filas.sort()

    salida.parent.mkdir(parents=True, exist_ok=True)
    with salida.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(["dataset", "source_split", "document_id", "sha256"])
        writer.writerows(filas)
    print(f"{len(filas)} documentos escritos en {salida}")


if __name__ == "__main__":
    main()
