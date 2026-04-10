"""Esqueleto inicial para la etapa de carga."""

from __future__ import annotations

from pathlib import Path
import sqlite3

import pandas as pd

try:
    from src.config import EXCEL_DIR, SQLITE_DIR, ensure_directories
    from src.logger_config import get_logger
except ImportError:
    from config import EXCEL_DIR, SQLITE_DIR, ensure_directories
    from logger_config import get_logger


class Carga:
    """Base reutilizable para guardar DataFrames en SQLite y Excel."""

    def __init__(self, sqlite_name: str = "airbnb.sqlite") -> None:
        ensure_directories()
        self.logger = get_logger(self.__class__.__name__)
        self.sqlite_path = SQLITE_DIR / sqlite_name

    def cargar_sqlite(self, dataframes: dict[str, pd.DataFrame]) -> Path:
        """Guarda cada DataFrame en una tabla SQLite con el mismo nombre."""
        with sqlite3.connect(self.sqlite_path) as connection:
            for table_name, dataframe in dataframes.items():
                dataframe.to_sql(
                    table_name.lower(),
                    connection,
                    if_exists="replace",
                    index=False,
                )
                self.logger.info(
                    "Tabla %s cargada en SQLite con %s registros.",
                    table_name,
                    len(dataframe),
                )
        return self.sqlite_path

    def exportar_excel(
        self,
        dataframes: dict[str, pd.DataFrame],
        excel_name: str = "airbnb_transformado.xlsx",
    ) -> Path:
        """Exporta los DataFrames a un archivo Excel, una hoja por coleccion."""
        excel_path = EXCEL_DIR / excel_name
        with pd.ExcelWriter(excel_path) as writer:
            for sheet_name, dataframe in dataframes.items():
                dataframe.to_excel(
                    writer,
                    sheet_name=sheet_name[:31],
                    index=False,
                )
                self.logger.info(
                    "Hoja %s exportada a Excel con %s registros.",
                    sheet_name,
                    len(dataframe),
                )
        return excel_path

