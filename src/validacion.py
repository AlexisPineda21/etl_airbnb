"""
Validaciones post-transformacion (calidad antes de cargar a SQLite/Excel).

Se invoca desde `Transformacion.transformar` cuando `validar_salida=True`. No
modifica datos: solo lee el DataFrame y emite WARNING/ERROR al logger para que
quede trazabilidad si algo no cumple las reglas del EDA.

Por que esta separado de `transformacion.py`
---------------------------------------------
Mantiene la clase de transformacion enfocada en reglas de negocio; las comprobaciones
se pueden reutilizar o ampliar sin inflar un solo archivo.
"""

from __future__ import annotations

import logging
import pandas as pd


def _serie_negativos(serie: pd.Series) -> int:
    num = pd.to_numeric(serie, errors="coerce")
    return int((num < 0).sum())


def validar_listings(df: pd.DataFrame, logger: logging.Logger) -> bool:
    """
    Valida Listings transformado: ids unicos, nulos criticos, precio, categorias.
    Registra WARNING/ERROR segun hallazgos. Retorna True si no hay fallos graves.
    """
    ok = True
    n = len(df)

    if "id" in df.columns:
        dup = df.duplicated(subset=["id"]).sum()
        if dup:
            logger.error("Validacion Listings: aun hay %s filas con id duplicado.", int(dup))
            ok = False
        else:
            logger.info("Validacion Listings: ids unicos (%s registros).", n)
    else:
        logger.error("Validacion Listings: falta columna 'id'.")
        ok = False

    cols_sin_nulos = [
        c
        for c in ("price", "last_review", "reviews_per_month", "host_name")
        if c in df.columns
    ]
    for col in cols_sin_nulos:
        nulos = df[col].isna().sum()
        if nulos:
            logger.error("Validacion Listings: %s valores nulos en '%s'.", int(nulos), col)
            ok = False

    if "price" in df.columns:
        precio = pd.to_numeric(df["price"], errors="coerce")
        if precio.isna().any():
            logger.error(
                "Validacion Listings: %s precios no numericos o nulos.",
                int(precio.isna().sum()),
            )
            ok = False
        neg_p = int((precio < 0).sum())
        if neg_p:
            logger.error("Validacion Listings: %s precios negativos.", neg_p)
            ok = False
        else:
            logger.info(
                "Validacion Listings: precio numerico, sin negativos (min=%s, max=%s).",
                precio.min(),
                precio.max(),
            )

    for col in ("minimum_nights", "availability_365"):
        if col in df.columns:
            neg = _serie_negativos(df[col])
            if neg:
                logger.error("Validacion Listings: %s valores negativos en '%s'.", neg, col)
                ok = False

    esperadas = {
        "price_category": "price",
        "stay_category": "minimum_nights",
        "availability_category": "availability_365",
    }
    for col_cat, col_base in esperadas.items():
        if col_base in df.columns and col_cat not in df.columns:
            logger.error(
                "Validacion Listings: falta columna derivada '%s' (base '%s' existe).",
                col_cat,
                col_base,
            )
            ok = False
        elif col_cat in df.columns:
            vacios = (df[col_cat].isna() | (df[col_cat].astype(str).str.strip() == "")).sum()
            if vacios:
                logger.warning(
                    "Validacion Listings: %s filas sin categoria en '%s'.",
                    int(vacios),
                    col_cat,
                )

    if "last_review" in df.columns and "last_review_ymd" not in df.columns:
        logger.warning("Validacion Listings: falta columna 'last_review_ymd'.")

    if "host_name" in df.columns:
        vacios = df["host_name"].isna().sum()
        if vacios:
            logger.error("Validacion Listings: %s host_name nulos tras imputacion.", int(vacios))
            ok = False

    return ok


def validar_reviews(df: pd.DataFrame, logger: logging.Logger) -> bool:
    ok = True

    if "_id" in df.columns:
        dup = df.duplicated(subset=["_id"]).sum()
        if dup:
            logger.error("Validacion Reviews: %s duplicados por _id.", int(dup))
            ok = False
        else:
            logger.info("Validacion Reviews: _id unicos (%s registros).", len(df))
    else:
        logger.warning("Validacion Reviews: no hay columna '_id'.")

    if "date" in df.columns:
        nulos = df["date"].isna().sum()
        if nulos:
            logger.error("Validacion Reviews: %s fechas nulas en 'date'.", int(nulos))
            ok = False
    else:
        logger.error("Validacion Reviews: falta columna 'date'.")
        ok = False

    derivadas = ("fecha_ymd", "review_year", "review_month", "review_day", "review_quarter")
    if "date" in df.columns:
        faltan = [c for c in derivadas if c not in df.columns]
        if faltan:
            logger.error("Validacion Reviews: faltan columnas derivadas: %s.", faltan)
            ok = False

    return ok


def validar_calendar(df: pd.DataFrame, logger: logging.Logger) -> bool:
    ok = True

    if "_id" in df.columns:
        dup = df.duplicated(subset=["_id"]).sum()
        if dup:
            logger.error("Validacion Calendar: %s duplicados por _id.", int(dup))
            ok = False
        else:
            logger.info("Validacion Calendar: _id unicos (%s registros).", len(df))

    for col in ("minimum_nights", "maximum_nights"):
        if col in df.columns:
            neg = _serie_negativos(df[col])
            if neg:
                logger.warning(
                    "Validacion Calendar: %s valores negativos en '%s' (revisar negocio).",
                    neg,
                    col,
                )

    derivadas = ("fecha_ymd", "cal_year", "cal_month", "cal_day", "cal_quarter")
    if "date" in df.columns:
        faltan = [c for c in derivadas if c not in df.columns]
        if faltan:
            logger.error("Validacion Calendar: faltan columnas derivadas: %s.", faltan)
            ok = False

    return ok


def validar_salida_transformacion(
    dataframes: dict[str, pd.DataFrame],
    logger: logging.Logger,
) -> dict[str, bool]:
    """
    Ejecuta validaciones por coleccion. Retorna mapa nombre_coleccion -> True si paso.

    Listings siempre se valida si esta presente; Reviews y Calendar si vienen en el dict.
    """
    resultados: dict[str, bool] = {}
    logger.info("--- Inicio validacion post-transformacion ---")

    for nombre, df in dataframes.items():
        clave = nombre.lower()
        if clave == "listings":
            resultados[nombre] = validar_listings(df, logger)
        elif clave == "reviews":
            resultados[nombre] = validar_reviews(df, logger)
        elif clave == "calendar":
            resultados[nombre] = validar_calendar(df, logger)

    fallos = [k for k, v in resultados.items() if not v]
    if fallos:
        logger.error("Validacion post-transformacion: fallos en colecciones: %s", fallos)
    else:
        logger.info("--- Validacion post-transformacion: todas las comprobaciones OK ---")

    return resultados
