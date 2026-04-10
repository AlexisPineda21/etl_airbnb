"""Utilidades para crear logs del proyecto."""

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
    """Devuelve el archivo de log compartido por la ejecucion actual."""
    global _LOG_FILE

    ensure_directories()
    if _LOG_FILE is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        _LOG_FILE = LOG_DIR / f"log_{timestamp}.txt"
    return _LOG_FILE


def get_logger(name: str) -> logging.Logger:
    """Configura y retorna un logger reutilizable."""
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

