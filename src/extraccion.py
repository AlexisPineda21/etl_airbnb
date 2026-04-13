"""
Extraccion (capa ETL): lectura desde MongoDB hacia pandas.

Responsabilidad
---------------
Conectar a la base MongoDB local (fuente obligatoria del taller), leer las
colecciones configuradas y devolver DataFrames en memoria. No transforma datos:
solo materializa documentos como tablas planas para las fases siguientes.

Por que se usa list(cursor)
--------------------------
`find()` devuelve un cursor perezoso; materializar con `list()` carga todos los
documentos de la consulta en RAM. Es coherente con un ETL por lotes sobre un
dataset que cabe en memoria; si el volumen creciera, habria que paginar o usar
chunks (no requerido en el alcance actual del taller).

Logs
----
Se registran conexion exitosa, conteo de documentos por coleccion y cierre.
Errores de conexion se registran con nivel ERROR antes de relanzar la excepcion.
"""

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
    """Gestiona la conexion a MongoDB y la extraccion a DataFrames de pandas."""

    def __init__(
        self,
        mongo_uri: str = MONGO_URI,
        database_name: str = MONGO_DB,
        collections: dict[str, str] | None = None,
    ) -> None:
        self.mongo_uri = mongo_uri
        self.database_name = database_name
        # Clave interna (ej. 'listings') -> nombre real de la coleccion en Mongo
        self.collections = collections or COLLECTIONS
        self.logger = get_logger(self.__class__.__name__)
        self.client = None
        self.database = None

    def conectar(self):
        """
        Abre la conexion con MongoDB y selecciona la base de datos.

        Hace ping al servidor para fallar pronto si no hay conectividad.
        """
        try:
            self.client = get_mongo_client(self.mongo_uri)
            ping_database(self.client)
            self.database = get_database(self.client, self.database_name)
        except Exception as exc:
            self.logger.error(
                "Fallo al conectar con MongoDB (URI base: %s...): %s",
                self.mongo_uri[:40],
                exc,
            )
            raise

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
        """
        Extrae documentos de una coleccion y los convierte en DataFrame.

        El parametro `limit` sirve solo para pruebas rapidas; en produccion debe
        ser None para traer el universo completo.
        """
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

        # ObjectId no es serializable a SQLite/Excel de forma uniforme; se guarda como str
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
        """
        Extrae todas las colecciones definidas en `COLLECTIONS`.

        Las claves del diccionario devuelto son los nombres reales de coleccion
        (p. ej. 'Listings'), para alinear con transformacion y carga.
        """
        dataframes: dict[str, pd.DataFrame] = {}
        limit_by_collection = limit_by_collection or {}

        for _, collection_name in self.collections.items():
            lim = limit_by_collection.get(collection_name)
            if lim is not None:
                self.logger.warning(
                    "Extraccion con limite de %s filas en '%s' (solo para pruebas).",
                    lim,
                    collection_name,
                )
            dataframes[collection_name] = self.extraer_coleccion(
                collection_name=collection_name,
                limit=lim,
            )

        return dataframes

    def cerrar_conexion(self) -> None:
        """Cierra el cliente MongoDB y libera recursos de red."""
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
