"""
Configuracion centralizada de logging para el ETL.

Por que existe este modulo
---------------------------
El taller exige que extraccion, transformacion y carga registren eventos en archivos
de texto con niveles INFO / WARNING / ERROR y marca de tiempo. Un solo punto de
configuracion evita duplicar handlers y garantiza el mismo formato en todo el proceso.

Formato del archivo (cumplimiento taller)
------------------------------------------
- Ubicacion: carpeta `logs/` en la raiz del proyecto.
- Nombre base: `log_YYYYMMDD_HHMM.txt` (fecha y hora al iniciar la primera captura
  de logger en la ejecucion). Si en el mismo minuto se generara otro archivo con el
  mismo nombre, se usa un sufijo numerico (`_1`, `_2`, ...) para no sobrescribir.
- Cada linea: `fecha-hora | NIVEL | nombre_logger | mensaje`

Todos los modulos obtienen su logger con `get_logger(__name__)` o
`get_logger(self.__class__.__name__)` para que el nombre identifique la clase.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

try:
    from src.config import LOG_DIR, LOG_LEVEL, ensure_directories
except ImportError:
    from config import LOG_DIR, LOG_LEVEL, ensure_directories

_LOG_FILE: Path | None = None


def _get_log_file() -> Path:
    """
    Resuelve la ruta del archivo de log para la ejecucion actual.

    La primera llamada fija el archivo; las siguientes reutilizan la misma ruta
    para que extraccion, transformacion y carga escriban en un solo log por corrida.
    """
    global _LOG_FILE

    ensure_directories()
    if _LOG_FILE is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        candidate = LOG_DIR / f"log_{timestamp}.txt"
        # Evitar colision si hubo otra ejecucion en el mismo minuto
        path = candidate
        suffix = 0
        while path.exists():
            suffix += 1
            path = LOG_DIR / f"log_{timestamp}_{suffix}.txt"
        _LOG_FILE = path
    return _LOG_FILE


def get_logger(name: str) -> logging.Logger:
    """
    Crea o devuelve un logger con salida a archivo + consola.

    Parameters
    ----------
    name
        Identificador del modulo (aparece en cada linea del log).
    """
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    level = getattr(logging, LOG_LEVEL, logging.INFO)
    logger.setLevel(level)
    logger.propagate = False

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )

    file_handler = logging.FileHandler(_get_log_file(), encoding="utf-8")
    file_handler.setFormatter(formatter)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    return logger
