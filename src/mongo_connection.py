"""
Conexion a MongoDB: cliente, base de datos y comprobacion de vida.

Se separa de `extraccion.py` para mantener una sola responsabilidad y facilitar
pruebas o cambios de URI sin tocar la logica de lectura de colecciones.
"""

from __future__ import annotations

from pymongo import MongoClient
from pymongo.database import Database

try:
    from src.config import MONGO_DB, MONGO_URI
except ImportError:
    from config import MONGO_DB, MONGO_URI


def get_mongo_client(uri: str | None = None) -> MongoClient:
    """Instancia `MongoClient`; la URI por defecto sale de variables de entorno."""
    return MongoClient(uri or MONGO_URI)


def get_database(
    client: MongoClient, database_name: str | None = None
) -> Database:
    """Selecciona la base de datos por nombre (config o argumento)."""
    return client[database_name or MONGO_DB]


def ping_database(client: MongoClient) -> None:
    """
    Ejecuta comando `ping` contra el cluster.

    Falla con excepcion si el servidor no responde; `Extraccion.conectar` lo
    captura y lo deja registrado en el log como ERROR.
    """
    client.admin.command("ping")

