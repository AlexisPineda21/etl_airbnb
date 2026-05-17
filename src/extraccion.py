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

import argparse
from typing import Any

import pandas as pd

try:
    from src.config import COLLECTIONS, EXTRACTION_WINDOW_MONTHS, MONGO_DB, MONGO_URI
    from src.logger_config import get_logger
    from src.mongo_connection import get_database, get_mongo_client, ping_database
except ImportError:
    from config import COLLECTIONS, EXTRACTION_WINDOW_MONTHS, MONGO_DB, MONGO_URI
    from logger_config import get_logger
    from mongo_connection import get_database, get_mongo_client, ping_database


DATE_FIELD_BY_COLLECTION_KEY = {
    "listings": "last_scraped",
    "reviews": "date",
    "calendar": "date",
}


class Extraccion:
    """Gestiona la conexion a MongoDB y la extraccion a DataFrames de pandas."""

    def __init__(
        self,
        mongo_uri: str = MONGO_URI,
        database_name: str = MONGO_DB,
        collections: dict[str, str] | None = None,
        months_back: int = EXTRACTION_WINDOW_MONTHS,
    ) -> None:
        self.mongo_uri = mongo_uri
        self.database_name = database_name
        # Clave interna (ej. 'listings') -> nombre real de la coleccion en Mongo
        self.collections = collections or COLLECTIONS
        self.months_back = max(int(months_back), 0)
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

    def _resolver_campo_fecha(self, collection_name: str) -> str | None:
        """Devuelve el campo fecha asociado a la coleccion configurada."""
        for collection_key, real_collection_name in self.collections.items():
            if real_collection_name.lower() == collection_name.lower():
                return DATE_FIELD_BY_COLLECTION_KEY.get(collection_key.lower())
        return None

    def _agregar_filtro_temporal(
        self,
        collection_name: str,
        query: dict[str, Any] | None = None,
        *,
        months_back: int | None = None,
    ) -> dict[str, Any]:
        """
        Agrega filtro de ventana temporal basado en la fecha maxima de la coleccion.

        Se usa una referencia por coleccion para evitar ventanas vacias cuando el
        dataset historico no llega hasta la fecha actual del equipo.
        """
        base_query = dict(query or {})
        months = self.months_back if months_back is None else max(int(months_back), 0)
        if months <= 0:
            return base_query

        if self.database is None:
            self.conectar()

        date_field = self._resolver_campo_fecha(collection_name)
        if not date_field:
            self.logger.warning(
                "No se encontro campo fecha configurado para '%s'; se omite ventana temporal.",
                collection_name,
            )
            return base_query

        collection = self.database[collection_name]
        reference_doc = collection.find_one(
            {date_field: {"$ne": None}},
            projection={date_field: 1, "_id": 0},
            sort=[(date_field, -1)],
        )
        if not reference_doc or reference_doc.get(date_field) is None:
            self.logger.warning(
                "No hay valores en '%s.%s' para construir ventana temporal; se extrae sin filtro.",
                collection_name,
                date_field,
            )
            return base_query

        reference_date = pd.Timestamp(reference_doc[date_field]).to_pydatetime()
        cutoff_date = (pd.Timestamp(reference_date) - pd.DateOffset(months=months)).to_pydatetime()
        date_filter = {date_field: {"$gte": cutoff_date, "$lte": reference_date}}

        if not base_query:
            final_query = date_filter
        elif date_field in base_query:
            final_query = {**base_query, date_field: {**date_filter[date_field], **base_query[date_field]}}
        else:
            final_query = {"$and": [base_query, date_filter]}

        self.logger.info(
            "Ventana temporal aplicada en '%s' usando '%s': desde %s hasta %s (%s meses).",
            collection_name,
            date_field,
            cutoff_date.date(),
            reference_date.date(),
            months,
        )
        return final_query

    def extraer_todo(
        self,
        limit_by_collection: dict[str, int] | None = None,
        query_by_collection: dict[str, dict[str, Any]] | None = None,
        *,
        months_back: int | None = None,
    ) -> dict[str, pd.DataFrame]:
        """
        Extrae todas las colecciones definidas en `COLLECTIONS`.

        Las claves del diccionario devuelto son los nombres reales de coleccion
        (p. ej. 'Listings'), para alinear con transformacion y carga.
        """
        dataframes: dict[str, pd.DataFrame] = {}
        limit_by_collection = limit_by_collection or {}
        query_by_collection = query_by_collection or {}

        for _, collection_name in self.collections.items():
            lim = limit_by_collection.get(collection_name)
            query = self._agregar_filtro_temporal(
                collection_name,
                query=query_by_collection.get(collection_name),
                months_back=months_back,
            )
            if lim is not None:
                self.logger.warning(
                    "Extraccion con limite de %s filas en '%s' (solo para pruebas).",
                    lim,
                    collection_name,
                )
            dataframes[collection_name] = self.extraer_coleccion(
                collection_name=collection_name,
                query=query,
                limit=lim,
            )

        return dataframes

    def cerrar_conexion(self) -> None:
        """Cierra el cliente MongoDB y libera recursos de red."""
        if self.client is not None:
            self.client.close()
            self.logger.info("Conexion a MongoDB cerrada correctamente.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extrae colecciones Airbnb desde MongoDB.")
    parser.add_argument(
        "--months-back",
        type=int,
        default=EXTRACTION_WINDOW_MONTHS,
        help="Ventana temporal en meses por coleccion, basada en la fecha maxima disponible.",
    )
    args = parser.parse_args()

    extractor = Extraccion(months_back=args.months_back)

    try:
        muestras = extractor.extraer_todo(
            limit_by_collection={"Listings": 5, "Reviews": 5, "Calendar": 5}
        )
        for name, dataframe in muestras.items():
            print(f"{name}: {dataframe.shape}")
    finally:
        extractor.cerrar_conexion()
