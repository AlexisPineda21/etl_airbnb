"""
Configuracion central del proyecto ETL.

Carga variables desde `.env` (o `.env.example` si no existe `.env`) para no
incrustar secretos ni rutas en el codigo. Define rutas de logs, salida SQLite/Excel
y parametros de MongoDB usados por extraccion, transformacion y carga.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Raiz del repositorio (directorio padre de `src/`)
BASE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BASE_DIR / ".env"
EXAMPLE_ENV_FILE = BASE_DIR / ".env.example"

if ENV_FILE.exists():
    load_dotenv(ENV_FILE)
elif EXAMPLE_ENV_FILE.exists():
    load_dotenv(EXAMPLE_ENV_FILE)

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
MONGO_DB = os.getenv("MONGO_DB", "airbnb_mx")
COLLECTIONS = {
    "listings": os.getenv("MONGO_LISTINGS_COLLECTION", "Listings"),
    "reviews": os.getenv("MONGO_REVIEWS_COLLECTION", "Reviews"),
    "calendar": os.getenv("MONGO_CALENDAR_COLLECTION", "Calendar"),
}
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

LOG_DIR = BASE_DIR / "logs"
OUTPUT_DIR = BASE_DIR / "output"
SQLITE_DIR = OUTPUT_DIR / "sqlite"
EXCEL_DIR = OUTPUT_DIR / "excel"
# Archivo SQLite por defecto (ruta completa = SQLITE_DIR / SQLITE_DB_FILENAME)
SQLITE_DB_FILENAME = os.getenv("SQLITE_DB_FILENAME", "airbnb_transformado.db")


def ensure_directories() -> None:
    """Crea los directorios base si todavia no existen."""
    for directory in (LOG_DIR, OUTPUT_DIR, SQLITE_DIR, EXCEL_DIR):
        directory.mkdir(parents=True, exist_ok=True)

