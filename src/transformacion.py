"""Esqueleto inicial para la etapa de transformacion."""

from __future__ import annotations

import pandas as pd

try:
    from src.logger_config import get_logger
except ImportError:
    from logger_config import get_logger


class Transformacion:
    """Base simple para que el equipo continue la fase de transformacion."""

    def __init__(self) -> None:
        self.logger = get_logger(self.__class__.__name__)

    def transformar(
        self, dataframes: dict[str, pd.DataFrame]
    ) -> dict[str, pd.DataFrame]:
        """Retorna los DataFrames sin cambios mientras se implementa la logica."""
        self.logger.warning(
            "La clase Transformacion es un esqueleto inicial y aun no aplica cambios."
        )
        return dataframes

