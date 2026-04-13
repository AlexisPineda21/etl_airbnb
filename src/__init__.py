"""
Paquete `src`: pipeline ETL Airbnb (MongoDB -> pandas -> SQLite / Excel).

Expone las clases y utilidades que el taller pide como entregables modulares,
mas el modulo de validacion y el de analisis explorativo reutilizable (`eda`).
"""

from src.carga import Carga
from src.extraccion import Extraccion
from src.logger_config import get_logger
from src.transformacion import Transformacion
from src.validacion import validar_salida_transformacion

__all__ = [
    "Carga",
    "Extraccion",
    "Transformacion",
    "get_logger",
    "validar_salida_transformacion",
]
