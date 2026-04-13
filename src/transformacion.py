"""
Transformacion (capa ETL): limpieza, enriquecimiento y reglas de negocio.

Responsabilidad
---------------
Recibe el diccionario de DataFrames que devuelve `Extraccion` y aplica lo acordado
en el EDA: eliminar filas invalidas (precio nulo, nulos en last_review/reviews
cuando hay Reviews para imputar), deduplicar por `id`, imputar `host_name`,
normalizar precio, alinear `number_of_reviews` con la coleccion Reviews,
recalcular fechas y `reviews_per_month` desde agregados, categorizar con umbrales
dinamicos (`eda.calcular_umbrales_categoria`), y derivar columnas temporales en
Reviews y Calendar.

Por que no esta en el notebook
------------------------------
El taller pide que el proceso ETL formal viva en modulos Python reutilizables;
el notebook sirve para explorar, pero la produccion debe poder ejecutarse sin Jupyter.

Logs y validacion
-----------------
Se usa `get_logger` en cada paso relevante (conteos antes/despues, umbrales,
advertencias). Al final, si `validar_salida=True`, se invoca `validacion.py` para
comprobar duplicados, nulos criticos y columnas derivadas.
"""

from __future__ import annotations

import re
from typing import Any

import numpy as np
import pandas as pd

try:
    from src.eda import (
        HOST_NAME_EMPTY,
        calcular_umbrales_categoria,
        categoria_disponibilidad,
        categoria_estancia,
        categoria_precio,
    )
    from src.logger_config import get_logger
    from src.validacion import validar_salida_transformacion
except ImportError:
    from eda import (
        HOST_NAME_EMPTY,
        calcular_umbrales_categoria,
        categoria_disponibilidad,
        categoria_estancia,
        categoria_precio,
    )
    from logger_config import get_logger
    from validacion import validar_salida_transformacion


def _resolver_dataframe(dataframes: dict[str, pd.DataFrame], nombre: str) -> pd.DataFrame | None:
    """Obtiene una copia del DataFrame por nombre de coleccion (case-insensitive)."""
    for clave, df in dataframes.items():
        if clave.lower() == nombre.lower():
            return df.copy()
    return None


def _normalizar_columna_precio(serie: pd.Series) -> pd.Series:
    """
    Normaliza precios: quita simbolos de moneda, separadores ambiguos y convierte a float.
    Si la columna ya es numerica, solo fuerza conversion segura.
    """
    if pd.api.types.is_numeric_dtype(serie):
        return pd.to_numeric(serie, errors="coerce")

    def _limpiar_celda(val: Any) -> float | np.floating:
        if pd.isna(val):
            return np.nan
        s = str(val).strip()
        s = re.sub(r"[\$€£¥¢]", "", s)
        s = re.sub(r"\s+", "", s)
        s = re.sub(r"(?<=\d),(?=\d{3}(\D|$))", "", s)
        if re.match(r"^-?\d+,\d+$", s):
            s = s.replace(",", ".")
        else:
            s = s.replace(",", "")
        try:
            return float(s)
        except ValueError:
            return np.nan

    return serie.map(_limpiar_celda)


def _fecha_a_estandar(serie: pd.Series) -> pd.Series:
    """Convierte a datetime64 normalizado a medianoche."""
    dt = pd.to_datetime(serie, errors="coerce", utc=False)
    if hasattr(dt.dt, "normalize"):
        return dt.dt.normalize()
    return dt


def _derivar_calendario_temporal(serie_fecha: pd.Series) -> pd.DataFrame:
    """Ano, mes, dia y trimestre a partir de una serie datetime."""
    dt = pd.to_datetime(serie_fecha, errors="coerce")
    return pd.DataFrame(
        {
            "year": dt.dt.year,
            "month": dt.dt.month,
            "day": dt.dt.day,
            "quarter": dt.dt.quarter,
        }
    )


class Transformacion:
    """
    Pipeline de transformacion sobre el diccionario devuelto por `Extraccion`.

    Devuelve el mismo mapa de nombres de coleccion → DataFrame, listo para `Carga`.
    Los pasos intermedios (merge con agregados de Reviews, categorias, fechas)
    quedan descritos en el docstring del modulo y en los logs (INFO/WARNING/ERROR).
    """

    def __init__(self) -> None:
        self.logger = get_logger(self.__class__.__name__)

    def transformar(
        self,
        dataframes: dict[str, pd.DataFrame],
        *,
        validar_salida: bool = True,
    ) -> dict[str, pd.DataFrame]:
        """
        Ejecuta la pipeline de transformacion sobre Listings, Reviews y Calendar.

        Parameters
        ----------
        dataframes :
            Mapa nombre_coleccion -> DataFrame (p. ej. 'Listings', 'Reviews', 'Calendar').
        validar_salida :
            Si True, ejecuta validaciones post-transformacion (duplicados, nulos criticos,
            negativos, precio, columnas derivadas) y registra el resultado en el log.

        Returns
        -------
        dict[str, pd.DataFrame]
            Mismas claves de entrada con datos transformados.
        """
        self.logger.info("Inicio de transformacion. Colecciones recibidas: %s", list(dataframes.keys()))

        df_listings = _resolver_dataframe(dataframes, "Listings")
        df_reviews = _resolver_dataframe(dataframes, "Reviews")
        df_calendar = _resolver_dataframe(dataframes, "Calendar")

        if df_listings is None:
            self.logger.error("No se encontro la coleccion Listings en el diccionario de entrada.")
            raise ValueError("Se requiere la coleccion Listings.")

        n_antes_listings = len(df_listings)
        df_listings = self._transformar_listings(df_listings, df_reviews)
        self.logger.info(
            "Listings: registros antes=%s, despues=%s (limpieza e imputaciones).",
            n_antes_listings,
            len(df_listings),
        )

        if df_reviews is not None:
            n_antes_r = len(df_reviews)
            df_reviews = self._transformar_reviews(df_reviews)
            self.logger.info("Reviews: registros antes=%s, despues=%s.", n_antes_r, len(df_reviews))
        else:
            self.logger.warning("Reviews ausente: se omite transformacion de reseñas.")

        if df_calendar is not None:
            n_antes_c = len(df_calendar)
            df_calendar = self._transformar_calendar(df_calendar)
            self.logger.info("Calendar: registros antes=%s, despues=%s.", n_antes_c, len(df_calendar))
        else:
            self.logger.warning("Calendar ausente: se omite transformacion de calendario.")

        resultado: dict[str, pd.DataFrame] = {}
        for nombre_original, _ in dataframes.items():
            clave_lower = nombre_original.lower()
            if clave_lower == "listings":
                resultado[nombre_original] = df_listings
            elif clave_lower == "reviews" and df_reviews is not None:
                resultado[nombre_original] = df_reviews
            elif clave_lower == "calendar" and df_calendar is not None:
                resultado[nombre_original] = df_calendar

        self.logger.info("Transformacion finalizada. Colecciones de salida: %s", list(resultado.keys()))

        if validar_salida:
            validar_salida_transformacion(resultado, self.logger)

        return resultado


    def _agregar_reviews_por_listing(self, reviews: pd.DataFrame) -> pd.DataFrame:
        """Agrega por listing_id: ultima fecha, primera fecha, conteo y reviews_per_month."""
        if reviews.empty or "listing_id" not in reviews.columns or "date" not in reviews.columns:
            self.logger.warning("Reviews sin columnas listing_id/date; no se puede agregar por listing.")
            return pd.DataFrame()

        r = reviews.copy()
        r["date"] = pd.to_datetime(r["date"], errors="coerce")
        r = r.dropna(subset=["listing_id", "date"])

        filas: list[dict[str, Any]] = []
        for lid, grp in r.groupby("listing_id"):
            fechas = grp["date"].sort_values()
            last = fechas.max()
            first = fechas.min()
            n = int(len(fechas))
            dias = (last - first).days
            meses = max(dias / 30.44, 1.0) if dias >= 1 else 1.0
            rpm = n / meses
            filas.append(
                {
                    "listing_id": lid,
                    "lr_from_reviews": last,
                    "first_review": first,
                    "review_count_agg": n,
                    "rpm_from_reviews": rpm,
                }
            )

        out = pd.DataFrame(filas)
        self.logger.info("Agregacion Reviews: %s listings con al menos una reseña.", len(out))
        return out

    def _alinear_number_of_reviews(self, listings: pd.DataFrame, reviews: pd.DataFrame) -> pd.Series:
        """
        Regla EDA: si number_of_reviews==0 y el conteo en Reviews es distinto de 0, usar conteo;
        si number_of_reviews>0, mantener el valor del listing.
        """
        if reviews.empty or "listing_id" not in reviews.columns:
            return listings["number_of_reviews"]

        conteos = reviews.groupby("listing_id").size()

        def _fila(row: pd.Series) -> int:
            lid = row["id"]
            tbl = row["number_of_reviews"]
            try:
                cnt = int(conteos[lid]) if lid in conteos.index else 0
            except Exception:
                cnt = 0
            try:
                t = int(tbl) if not pd.isna(tbl) else 0
            except Exception:
                t = 0
            if t == 0 and cnt != 0:
                return cnt
            return t

        return listings.apply(_fila, axis=1)

    def _merge_listings_con_reviews_agg(self, df: pd.DataFrame, agg: pd.DataFrame) -> pd.DataFrame:
        """Imputa last_review y reviews_per_month desde agregados de Reviews."""
        if agg is None or agg.empty:
            return df

        merged = df.merge(agg, how="left", left_on="id", right_on="listing_id")
        merged = merged.drop(columns=["listing_id"], errors="ignore")

        if "lr_from_reviews" in merged.columns:
            if "last_review" in merged.columns:
                merged["last_review"] = merged["last_review"].combine_first(merged["lr_from_reviews"])
            else:
                merged["last_review"] = merged["lr_from_reviews"]
            merged["last_review"] = _fecha_a_estandar(merged["last_review"])
            merged = merged.drop(columns=["lr_from_reviews"], errors="ignore")

        if "rpm_from_reviews" in merged.columns:
            if "reviews_per_month" in merged.columns:
                merged["reviews_per_month"] = merged["reviews_per_month"].combine_first(
                    merged["rpm_from_reviews"]
                )
            else:
                merged["reviews_per_month"] = merged["rpm_from_reviews"]
            merged = merged.drop(columns=["rpm_from_reviews"], errors="ignore")

        merged = merged.drop(columns=["first_review", "review_count_agg"], errors="ignore")
        return merged

    def _transformar_listings(self, df: pd.DataFrame, reviews: pd.DataFrame | None) -> pd.DataFrame:
        """Limpieza de nulos/duplicados, precio, fechas, imputaciones desde Reviews y categorias."""
        self.logger.info("Transformando Listings: forma inicial %s.", df.shape)

        if "price" in df.columns:
            n_antes = len(df)
            df = df.dropna(subset=["price"])
            self.logger.info("Listings: eliminadas %s filas con price nulo.", n_antes - len(df))

        if "id" in df.columns:
            dup_mask = df.duplicated(subset=["id"], keep=False)
            dup = int(dup_mask.sum())
            if dup:
                self.logger.warning(
                    "Listings: %s filas con id duplicado; se conserva la primera aparicion.", dup
                )
            df = df.drop_duplicates(subset=["id"], keep="first")

        if "host_name" in df.columns:
            df["host_name"] = df["host_name"].fillna(HOST_NAME_EMPTY)

        if "price" in df.columns:
            df["price"] = _normalizar_columna_precio(df["price"])

        if "last_review" in df.columns:
            df["last_review"] = _fecha_a_estandar(df["last_review"])

        agg = pd.DataFrame()
        if reviews is not None and not reviews.empty:
            agg = self._agregar_reviews_por_listing(reviews)
            df = self._merge_listings_con_reviews_agg(df, agg)

        if reviews is not None and not reviews.empty and "number_of_reviews" in df.columns and "id" in df.columns:
            df["number_of_reviews"] = self._alinear_number_of_reviews(df, reviews)

        if "last_review" in df.columns and "reviews_per_month" in df.columns:
            if reviews is not None and not reviews.empty:
                n_pre = len(df)
                df = df.dropna(subset=["last_review", "reviews_per_month"])
                self.logger.info(
                    "Listings: eliminadas %s filas con last_review o reviews_per_month nulos.",
                    n_pre - len(df),
                )
            else:
                self.logger.warning(
                    "Sin coleccion Reviews no se imputan last_review/reviews_per_month; "
                    "no se eliminan filas por esos nulos."
                )

        # Categorias: umbrales Q1, mediana, Q3 e IQR desde el propio DataFrame (eda.calcular_umbrales_categoria)
        if "price" in df.columns:
            try:
                u_precio = calcular_umbrales_categoria(df["price"])
                self.logger.info(
                    "Umbrales precio (desde datos): q1=%s, mediana=%s, q3=%s, limite_IQR=%s",
                    u_precio.q1,
                    u_precio.mediana,
                    u_precio.q3,
                    u_precio.limite_superior_iqr,
                )
                df["price_category"] = df["price"].map(lambda p: categoria_precio(p, u_precio))
            except ValueError as exc:
                self.logger.warning("No se asignan categorias de precio: %s", exc)
        if "minimum_nights" in df.columns:
            try:
                u_noches = calcular_umbrales_categoria(df["minimum_nights"])
                self.logger.info(
                    "Umbrales estancia (desde datos): q1=%s, mediana=%s, q3=%s, limite_IQR=%s",
                    u_noches.q1,
                    u_noches.mediana,
                    u_noches.q3,
                    u_noches.limite_superior_iqr,
                )
                df["stay_category"] = pd.to_numeric(df["minimum_nights"], errors="coerce").map(
                    lambda x: categoria_estancia(x, u_noches)
                )
            except ValueError as exc:
                self.logger.warning("No se asignan categorias de estancia: %s", exc)
        if "availability_365" in df.columns:
            try:
                u_avail = calcular_umbrales_categoria(df["availability_365"])
                self.logger.info(
                    "Umbrales disponibilidad (desde datos): q1=%s, mediana=%s, q3=%s, limite_IQR=%s",
                    u_avail.q1,
                    u_avail.mediana,
                    u_avail.q3,
                    u_avail.limite_superior_iqr,
                )
                df["availability_category"] = pd.to_numeric(df["availability_365"], errors="coerce").map(
                    lambda x: categoria_disponibilidad(x, u_avail)
                )
            except ValueError as exc:
                self.logger.warning("No se asignan categorias de disponibilidad: %s", exc)

        self.logger.info(
            "Listings: no hay campos anidados tipo amenities/host en el esquema cargado; "
            "no se aplica expansion de estructuras."
        )

        if "last_review" in df.columns:
            df["last_review_ymd"] = pd.to_datetime(df["last_review"], errors="coerce").dt.strftime("%Y-%m-%d")

        return df

    def _transformar_reviews(self, df: pd.DataFrame) -> pd.DataFrame:
        """Fechas estandar, derivadas temporales, duplicados por _id."""
        self.logger.info("Transformando Reviews.")

        if "_id" in df.columns:
            dup = int(df.duplicated(subset=["_id"]).sum())
            if dup:
                self.logger.warning("Reviews: %s duplicados por _id eliminados.", dup)
            df = df.drop_duplicates(subset=["_id"], keep="first")

        if "date" in df.columns:
            df["date"] = _fecha_a_estandar(df["date"])
            df["fecha_ymd"] = pd.to_datetime(df["date"], errors="coerce").dt.strftime("%Y-%m-%d")
            deriv = _derivar_calendario_temporal(df["date"])
            df["review_year"] = deriv["year"]
            df["review_month"] = deriv["month"]
            df["review_day"] = deriv["day"]
            df["review_quarter"] = deriv["quarter"]

        return df

    def _transformar_calendar(self, df: pd.DataFrame) -> pd.DataFrame:
        """Fechas estandar, derivadas, duplicados, advertencias por noches negativas."""
        self.logger.info("Transformando Calendar.")

        if "_id" in df.columns:
            dup = int(df.duplicated(subset=["_id"]).sum())
            if dup:
                self.logger.warning("Calendar: %s duplicados por _id eliminados.", dup)
            df = df.drop_duplicates(subset=["_id"], keep="first")

        if "date" in df.columns:
            df["date"] = _fecha_a_estandar(df["date"])
            df["fecha_ymd"] = pd.to_datetime(df["date"], errors="coerce").dt.strftime("%Y-%m-%d")
            deriv = _derivar_calendario_temporal(df["date"])
            df["cal_year"] = deriv["year"]
            df["cal_month"] = deriv["month"]
            df["cal_day"] = deriv["day"]
            df["cal_quarter"] = deriv["quarter"]

        for col in ("minimum_nights", "maximum_nights"):
            if col in df.columns:
                neg = int((pd.to_numeric(df[col], errors="coerce") < 0).sum())
                if neg:
                    self.logger.warning(
                        "Calendar: %s valores negativos en %s (se conservan; revisar en negocio).",
                        neg,
                        col,
                    )

        return df


if __name__ == "__main__":
    try:
        from src.extraccion import Extraccion
    except ImportError:
        from extraccion import Extraccion

    ext = Extraccion()
    try:
        ext.conectar()
        # Sin limit_by_collection: se extraen todos los documentos de cada coleccion (comportamiento de produccion).
        # Para una prueba rapida con muestra, usar p. ej. extraer_todo(limit_by_collection={"Listings": 500, ...}).
        datos = ext.extraer_todo()
        transformador = Transformacion()
        limpios = transformador.transformar(datos)
        for nombre, df in limpios.items():
            print(f"{nombre}: {df.shape}")
    finally:
        ext.cerrar_conexion()
