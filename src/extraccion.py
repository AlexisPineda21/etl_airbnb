from __future__ import annotations

from typing import Any

import pandas as pd

try:
    from src.config import COLLECTIONS, MONGO_DB, MONGO_URI
    from src.logger_config import get_logger
    from src.mongo_connection import get_database, get_mongo_client, ping_database
except ImportError:
    from config import COLLECTIONS, MONGO_DB, MONGO_URI
    from logger_config import get_logger
    from mongo_connection import get_database, get_mongo_client, ping_database


class Extraccion:
    """Gestiona la conexion a MongoDB y la extraccion a DataFrames."""

    def __init__(
        self,
        mongo_uri: str = MONGO_URI,
        database_name: str = MONGO_DB,
        collections: dict[str, str] | None = None,
    ) -> None:
        self.mongo_uri = mongo_uri
        self.database_name = database_name
        self.collections = collections or COLLECTIONS
        self.logger = get_logger(self.__class__.__name__)
        self.client = None
        self.database = None

    def conectar(self):
        """Abre la conexion con MongoDB y selecciona la base de datos."""
        self.client = get_mongo_client(self.mongo_uri)
        ping_database(self.client)
        self.database = get_database(self.client, self.database_name)
        self.logger.info(
            "Conexion exitosa a MongoDB. Base de datos seleccionada: %s",
            self.database_name,
        )
        return self.database

    def extraer_coleccion(
        self,
        collection_name: str,
        query: dict[str, Any] | None = None,
        projection: dict[str, int] | None = None,
        limit: int | None = None,
    ) -> pd.DataFrame:
        """Extrae una coleccion y la convierte en un DataFrame de pandas."""
        if self.database is None:
            self.conectar()

        query = query or {}
        collection = self.database[collection_name]
        total_documents = collection.count_documents(query)
        cursor = collection.find(query, projection)

        if limit is not None:
            cursor = cursor.limit(limit)

        records = list(cursor)
        dataframe = pd.DataFrame(records)

        if "_id" in dataframe.columns:
            dataframe["_id"] = dataframe["_id"].astype(str)

        self.logger.info(
            "Coleccion %s extraida correctamente. Registros encontrados: %s. "
            "Registros cargados en DataFrame: %s.",
            collection_name,
            total_documents,
            len(dataframe),
        )
        return dataframe

    def extraer_todo(
        self, limit_by_collection: dict[str, int] | None = None
    ) -> dict[str, pd.DataFrame]:
        """Extrae todas las colecciones configuradas."""
        dataframes: dict[str, pd.DataFrame] = {}
        limit_by_collection = limit_by_collection or {}

        for _, collection_name in self.collections.items():
            dataframes[collection_name] = self.extraer_coleccion(
                collection_name=collection_name,
                limit=limit_by_collection.get(collection_name),
            )

        return dataframes

    def cerrar_conexion(self) -> None:
        """Cierra la conexion con MongoDB."""
        if self.client is not None:
            self.client.close()
            self.logger.info("Conexion a MongoDB cerrada correctamente.")


if __name__ == "__main__":
    extractor = Extraccion()

    try:
        muestras = extractor.extraer_todo(
            limit_by_collection={"Listings": 5, "Reviews": 5, "Calendar": 5}
        )
        for name, dataframe in muestras.items():
            print(f"{name}: {dataframe.shape}")
    finally:
        extractor.cerrar_conexion()

