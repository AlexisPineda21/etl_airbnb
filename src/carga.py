"""
Carga (capa ETL): persistencia en SQLite y exportacion XLSX.

Responsabilidad
---------------
Tomar los DataFrames ya transformados y (1) crear/reemplazar tablas en un archivo
SQLite bajo `output/sqlite/`, (2) generar archivos Excel en `output/excel/`,
(3) verificar conteos con `SELECT COUNT(*)` frente a `len(df)`.

Por que se parte Calendar en varios XLSX
-----------------------------------------
Excel limita ~1.048.576 filas por hoja; Calendar supera ese volumen. Se exporta en
`calendar_part001.xlsx`, etc., segun `EXCEL_MAX_ROWS_PER_FILE`. Con `EXCEL_MAX_FILES`
se puede limitar cuantos archivos se generan **por coleccion** (ej. `1` + 2000 filas =
solo una previsualizacion de 2000 filas por tabla).

Por que chunks en to_sql
------------------------
`to_sql(..., chunksize=...)` reduce picos de memoria y transacciones mas estables
en tablas muy grandes.

Logs
----
INFO para rutas y conteos; WARNING al trocear Excel o omitir verificacion; ERROR
si falla SQLite o no coinciden los conteos.
"""

from __future__ import annotations

import json
import math
import os
import re
import sqlite3
from pathlib import Path
from typing import Any

import pandas as pd

try:
    from src.config import EXCEL_DIR, SQLITE_DB_FILENAME, SQLITE_DIR, ensure_directories
    from src.logger_config import get_logger
except ImportError:
    from config import EXCEL_DIR, SQLITE_DB_FILENAME, SQLITE_DIR, ensure_directories
    from logger_config import get_logger

# Limite practico por archivo .xlsx (por debajo del tope de Excel)
EXCEL_MAX_ROWS_PER_FILE = int(os.getenv("EXCEL_MAX_ROWS_PER_FILE", "1000000"))
# Max archivos XLSX por coleccion; vacio o no definido = exportar todos los trozos necesarios
EXCEL_MAX_FILES_RAW = os.getenv("EXCEL_MAX_FILES", "").strip()
EXCEL_MAX_FILES: int | None
if not EXCEL_MAX_FILES_RAW:
    EXCEL_MAX_FILES = None
else:
    _mf = int(EXCEL_MAX_FILES_RAW)
    EXCEL_MAX_FILES = _mf if _mf > 0 else None

SQLITE_CHUNKSIZE = int(os.getenv("SQLITE_TO_SQL_CHUNKSIZE", "50000"))


def _nombre_tabla_sql(nombre_coleccion: str) -> str:
    """Nombre de tabla SQLite seguro: solo letras, numeros y guiones bajos."""
    base = nombre_coleccion.strip().lower()
    base = re.sub(r"[^a-z0-9_]+", "_", base)
    base = re.sub(r"_+", "_", base).strip("_")
    if not base or not base[0].isalpha():
        base = "t_" + base if base else "tabla"
    return base


def _normalizar_valor_complejo(valor: Any) -> Any:
    """Convierte estructuras complejas en tipos serializables por JSON."""
    if isinstance(valor, pd.Timestamp):
        return valor.isoformat()
    if isinstance(valor, dict):
        return {str(k): _normalizar_valor_complejo(v) for k, v in valor.items()}
    if isinstance(valor, (list, tuple, set)):
        return [_normalizar_valor_complejo(v) for v in valor]
    if pd.isna(valor):
        return None
    if hasattr(valor, "item") and not isinstance(valor, (str, bytes)):
        try:
            return valor.item()
        except Exception:
            return valor
    return valor


def _serializar_si_es_complejo(valor: Any) -> Any:
    """Serializa listas/dicts/sets/tuplas a JSON para SQLite y Excel."""
    if isinstance(valor, (list, dict, set, tuple)):
        normalizado = _normalizar_valor_complejo(valor)
        return json.dumps(normalizado, ensure_ascii=False)
    return valor


def _preparar_dataframe_para_salida(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """
    Devuelve una copia segura para SQLite/Excel.

    Se serializan solo las columnas object que contengan estructuras complejas
    (listas, diccionarios, sets o tuplas). Esto evita errores de binding en
    SQLite sin alterar el DataFrame original de transformacion.
    """
    preparado = df.copy()
    columnas_serializadas: list[str] = []

    for col in preparado.select_dtypes(include=["object"]).columns:
        mascara_complejos = preparado[col].map(
            lambda v: isinstance(v, (list, dict, set, tuple))
        )
        if bool(mascara_complejos.any()):
            preparado[col] = preparado[col].map(_serializar_si_es_complejo)
            columnas_serializadas.append(col)

    return preparado, columnas_serializadas


class Carga:
    """
    Orquesta escritura SQLite, export Excel y comprobacion de filas.

    Usa `get_logger` para cumplir el requisito de logs en la fase de carga del taller.
    """

    def __init__(
        self,
        sqlite_path: Path | str | None = None,
        directorio_excel: Path | None = None,
    ) -> None:
        ensure_directories()
        self.logger = get_logger(self.__class__.__name__)
        if sqlite_path is None:
            self.sqlite_path = SQLITE_DIR / SQLITE_DB_FILENAME
        else:
            self.sqlite_path = Path(sqlite_path)
        self.directorio_excel = directorio_excel if directorio_excel is not None else EXCEL_DIR
        self.directorio_excel.mkdir(parents=True, exist_ok=True)

    def cargar_sqlite(self, dataframes: dict[str, pd.DataFrame]) -> Path:
        """
        Crea o reemplaza tablas en la base SQLite (una por coleccion).

        Usa insercion por lotes para tablas grandes. Activa WAL para mejor rendimiento.
        """
        self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        self.logger.info("Inicio carga SQLite en %s", self.sqlite_path)

        conn = sqlite3.connect(self.sqlite_path)
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")

            for nombre_original, df in dataframes.items():
                tabla = _nombre_tabla_sql(nombre_original)
                df_salida, columnas_serializadas = _preparar_dataframe_para_salida(df)
                filas = len(df)
                self.logger.info(
                    "Insertando tabla '%s' (%s registros, columnas=%s)...",
                    tabla,
                    filas,
                    len(df.columns),
                )
                if columnas_serializadas:
                    self.logger.info(
                        "SQLite: columnas serializadas en '%s' por contener estructuras complejas: %s",
                        tabla,
                        columnas_serializadas,
                    )
                df_salida.to_sql(
                    tabla,
                    conn,
                    if_exists="replace",
                    index=False,
                    chunksize=SQLITE_CHUNKSIZE,
                )
                self.logger.info(
                    "SQLite: tabla '%s' escrita (%s filas).",
                    tabla,
                    filas,
                )
            conn.commit()
        except Exception as exc:
            self.logger.exception("Error durante carga SQLite: %s", exc)
            conn.rollback()
            raise
        finally:
            conn.close()

        self.logger.info("Carga SQLite finalizada: %s", self.sqlite_path)
        return self.sqlite_path

    def exportar_xlsx(self, dataframes: dict[str, pd.DataFrame]) -> list[Path]:
        """
        Exporta cada coleccion a uno o varios archivos XLSX en `directorio_excel`.

        Si una tabla supera EXCEL_MAX_ROWS_PER_FILE, se generan varios archivos
        `nombre_part001.xlsx`, etc., salvo que `EXCEL_MAX_FILES` limite cuantos
        trozos se escriben (util para previsualizar sin llenar el disco).
        """
        rutas: list[Path] = []
        self.logger.info(
            "Inicio exportacion Excel (max %s filas por archivo; max archivos por coleccion=%s).",
            EXCEL_MAX_ROWS_PER_FILE,
            EXCEL_MAX_FILES if EXCEL_MAX_FILES is not None else "sin limite",
        )

        for nombre_original, df in dataframes.items():
            base = _nombre_tabla_sql(nombre_original)
            df_salida, columnas_serializadas = _preparar_dataframe_para_salida(df)
            n = len(df)
            if columnas_serializadas:
                self.logger.info(
                    "Excel: columnas serializadas en '%s' por contener estructuras complejas: %s",
                    base,
                    columnas_serializadas,
                )
            if n == 0:
                path = self.directorio_excel / f"{base}.xlsx"
                pd.DataFrame().to_excel(path, index=False, engine="openpyxl")
                rutas.append(path)
                self.logger.warning("Excel: %s vacio; archivo creado sin filas de datos.", path.name)
                continue

            if n <= EXCEL_MAX_ROWS_PER_FILE:
                path = self.directorio_excel / f"{base}.xlsx"
                df_salida.to_excel(path, index=False, engine="openpyxl")
                rutas.append(path)
                self.logger.info("Excel: %s (%s filas).", path.name, n)
            else:
                partes_totales = math.ceil(n / EXCEL_MAX_ROWS_PER_FILE)
                partes = (
                    min(partes_totales, EXCEL_MAX_FILES)
                    if EXCEL_MAX_FILES is not None
                    else partes_totales
                )
                if partes < partes_totales:
                    filas_exportadas = min(n, partes * EXCEL_MAX_ROWS_PER_FILE)
                    self.logger.warning(
                        "Excel: '%s' tiene %s filas (%s archivos posibles); "
                        "por EXCEL_MAX_FILES=%s solo se exportan %s archivo(s) (~%s filas; %s omitidas).",
                        base,
                        n,
                        partes_totales,
                        EXCEL_MAX_FILES,
                        partes,
                        filas_exportadas,
                        n - filas_exportadas,
                    )
                else:
                    self.logger.warning(
                        "Excel: '%s' tiene %s filas; se divide en %s archivos (limite hoja Excel).",
                        base,
                        n,
                        partes,
                    )
                for p in range(partes):
                    ini = p * EXCEL_MAX_ROWS_PER_FILE
                    fin = min(ini + EXCEL_MAX_ROWS_PER_FILE, n)
                    trozo = df_salida.iloc[ini:fin]
                    path = self.directorio_excel / f"{base}_part{p + 1:03d}.xlsx"
                    trozo.to_excel(path, index=False, engine="openpyxl")
                    rutas.append(path)
                    self.logger.info(
                        "Excel: %s (filas %s-%s, total trozo=%s).",
                        path.name,
                        ini + 1,
                        fin,
                        len(trozo),
                    )

        self.logger.info("Exportacion Excel: %s archivo(s) generado(s).", len(rutas))
        return rutas

    def verificar_carga_sqlite(self, dataframes: dict[str, pd.DataFrame]) -> bool:
        """
        Comprueba que el numero de filas en SQLite coincide con cada DataFrame fuente.
        """
        self.logger.info("Verificacion: conteos en SQLite vs DataFrames.")
        if not self.sqlite_path.exists():
            self.logger.error("No existe el archivo SQLite: %s", self.sqlite_path)
            return False

        conn = sqlite3.connect(self.sqlite_path)
        todo_ok = True
        try:
            for nombre_original, df in dataframes.items():
                tabla = _nombre_tabla_sql(nombre_original)
                esperado = len(df)
                try:
                    cur = conn.execute(f'SELECT COUNT(*) AS c FROM "{tabla}"')
                    fila = cur.fetchone()
                    obtenido = int(fila[0]) if fila else 0
                except sqlite3.Error as exc:
                    self.logger.error(
                        "Verificacion: no se pudo leer la tabla '%s': %s",
                        tabla,
                        exc,
                    )
                    todo_ok = False
                    continue

                if obtenido == esperado:
                    self.logger.info(
                        "OK tabla '%s': %s filas (coincide con DataFrame).",
                        tabla,
                        obtenido,
                    )
                else:
                    self.logger.error(
                        "FALLO tabla '%s': SQLite tiene %s filas, se esperaban %s.",
                        tabla,
                        obtenido,
                        esperado,
                    )
                    todo_ok = False
        finally:
            conn.close()

        if todo_ok:
            self.logger.info("Verificacion SQLite: todas las tablas coinciden con los DataFrames.")
        else:
            self.logger.error("Verificacion SQLite: hay discrepancias de conteo.")

        return todo_ok

    def ejecutar(
        self,
        dataframes: dict[str, pd.DataFrame],
        *,
        sqlite: bool = True,
        excel: bool = True,
        verificar: bool = True,
    ) -> dict[str, Any]:
        """
        Ejecuta carga SQLite, exportacion XLSX y verificacion segun flags.

        Returns
        -------
        dict
            sqlite_path, rutas_excel, verificacion_ok
        """
        resultado: dict[str, Any] = {
            "sqlite_path": None,
            "rutas_excel": [],
            "verificacion_ok": None,
        }

        if sqlite:
            resultado["sqlite_path"] = self.cargar_sqlite(dataframes)

        if excel:
            resultado["rutas_excel"] = self.exportar_xlsx(dataframes)

        if verificar and sqlite:
            resultado["verificacion_ok"] = self.verificar_carga_sqlite(dataframes)
        elif verificar and not sqlite:
            self.logger.warning("Verificacion omitida: no se cargo SQLite en esta ejecucion.")
            resultado["verificacion_ok"] = None

        return resultado


if __name__ == "__main__":
    try:
        from src.extraccion import Extraccion
        from src.transformacion import Transformacion
    except ImportError:
        from extraccion import Extraccion
        from transformacion import Transformacion

    ext = Extraccion()
    try:
        ext.conectar()
        datos = ext.extraer_todo()
        limpios = Transformacion().transformar(datos)
        carga = Carga()
        salida = carga.ejecutar(limpios)
        print("SQLite:", salida["sqlite_path"])
        print("Excel:  ", len(salida["rutas_excel"]), "archivo(s)")
        print("Verificacion OK:", salida["verificacion_ok"])
    finally:
        ext.cerrar_conexion()
