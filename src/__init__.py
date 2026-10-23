"""Lector de Facturas: extracción y validación de comprobantes con OCR.

Este paquete es la interfaz pública del proyecto. Organiza el código según la
estructura del curso y delega el trabajo pesado en el motor
``src/lector_facturas`` (OCR, consenso y evaluación):

==================  =====================================================
Módulo              Responsabilidad
==================  =====================================================
``utils``           Configuración (YAML y .env), rutas, registro y errores
``data_processing`` Validación de archivos, PDF a imágenes, preprocesamiento,
                    normalización y preparación de los datasets
``model``           Clase :class:`LectorFacturas`: carga del modelo,
                    lectura de documentos y nivel de confianza por campo
``train``           Optimización de la configuración (el modelo no entrena
                    pesos)
``evaluate``        Métricas, evaluación, prueba externa e importación de
                    resultados de los notebooks a ``results/``
==================  =====================================================

Uso mínimo::

    from src.model import LectorFacturas
    lector = LectorFacturas()
    resultado = lector.leer("samples/synthetic_receipt.png")
    print(resultado.campos())
"""
import sys
from pathlib import Path

__version__ = "1.0.0"

# El motor se importa como ``lector_facturas`` en todo el proyecto (notebooks y pruebas).
# Si el paquete no está instalado con ``pip install -e .``, se agrega src/ a la ruta de búsqueda.
_SRC = Path(__file__).resolve().parent
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
