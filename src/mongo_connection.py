"""Funciones auxiliares para la conexion a MongoDB."""

from __future__ import annotations

from pymongo import MongoClient
from pymongo.database import Database

try:
    from src.config import MONGO_DB, MONGO_URI
except ImportError:
    from config import MONGO_DB, MONGO_URI


def get_mongo_client(uri: str | None = None) -> MongoClient:
    """Crea un cliente de MongoDB con la URI indicada."""
    return MongoClient(uri or MONGO_URI)


def get_database(
    client: MongoClient, database_name: str | None = None
) -> Database:
    """Retorna la base de datos configurada."""
    return client[database_name or MONGO_DB]


def ping_database(client: MongoClient) -> None:
    """Valida que la conexion al servidor MongoDB este activa."""
    client.admin.command("ping")

