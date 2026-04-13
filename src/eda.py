"""
Analisis exploratorio (EDA) compartido entre notebook y transformacion.

Contenido principal
-------------------
- Funciones de exploracion (`analizar_estructura`, nulos, duplicados, outliers,
  precio, negativos) pensadas para Jupyter; usan `IPython.display` si existe.
- Umbrales de categorias **calculados desde los datos** (`calcular_umbrales_categoria`)
  para alinear el ETL con el criterio de cuantiles/IQR del notebook sin duplicar
  constantes magicas.

Por que existe como modulo aparte
----------------------------------
El taller recomienda no dejar la logica solo en el notebook; centralizar aqui permite
importar las mismas reglas en `transformacion.py` y mantener una sola fuente de verdad.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import pandas as pd

HOST_NAME_EMPTY = "empty_hostname"


@dataclass(frozen=True)
class UmbralesCategoria:
    """Umbrales derivados de los datos: cuartiles y techo IQR (como en el EDA)."""

    q1: float
    mediana: float
    q3: float
    limite_superior_iqr: float


def calcular_umbrales_categoria(serie: pd.Series) -> UmbralesCategoria:
    """
    Calcula Q1, mediana, Q3 y limite superior (Q3 + 1.5*IQR) sobre valores numericos.

    Si IQR es 0, el limite superior es el maximo observado (evita rangos vacios).
    """
    datos = pd.to_numeric(serie, errors="coerce").dropna()
    if len(datos) == 0:
        raise ValueError("La serie no tiene valores numericos para calcular umbrales.")

    q1 = float(datos.quantile(0.25))
    q3 = float(datos.quantile(0.75))
    med = float(datos.median())
    iqr = q3 - q1
    lim_sup = float(q3 + 1.5 * iqr) if iqr > 0 else float(datos.max())
    return UmbralesCategoria(q1=q1, mediana=med, q3=q3, limite_superior_iqr=lim_sup)


@dataclass(frozen=True)
class UmbralesListings:
    """Conjunto de umbrales para las tres variables categorizadas en Listings."""

    precio: UmbralesCategoria
    estancia: UmbralesCategoria
    disponibilidad: UmbralesCategoria


def calcular_umbrales_listings(df: pd.DataFrame) -> UmbralesListings:
    """
    Obtiene umbrales desde el propio DataFrame de Listings (mismo criterio que el EDA).

    Requiere columnas `price`, `minimum_nights` y `availability_365`.
    """
    faltan = [c for c in ("price", "minimum_nights", "availability_365") if c not in df.columns]
    if faltan:
        raise ValueError(f"Faltan columnas para umbrales: {faltan}")
    return UmbralesListings(
        precio=calcular_umbrales_categoria(df["price"]),
        estancia=calcular_umbrales_categoria(df["minimum_nights"]),
        disponibilidad=calcular_umbrales_categoria(df["availability_365"]),
    )


def _display(obj: Any) -> None:
    """Usa IPython.display en notebooks; en consola hace print legible."""
    try:
        from IPython.display import display as _ipy_display

        _ipy_display(obj)
    except Exception:
        if hasattr(obj, "to_string"):
            print(obj.to_string())
        else:
            print(obj)


def categoria_precio(precio: float, umbrales: UmbralesCategoria) -> str:
    """Etiqueta de rango de precio segun umbrales calculados sobre los datos."""
    if pd.isna(precio):
        return "Desconocido"
    u = umbrales
    if precio <= u.q1:
        return "Budget"
    if precio <= u.mediana:
        return "Mid-range"
    if precio <= u.q3:
        return "Upper-mid"
    if precio <= u.limite_superior_iqr:
        return "Premium"
    return "Luxury/Outlier"


def categoria_estancia(noches: float, umbrales: UmbralesCategoria) -> str:
    """Etiqueta de tipo de estancia segun minimum_nights y umbrales de datos."""
    if pd.isna(noches):
        return "Desconocido"
    u = umbrales
    if noches <= u.q1:
        return "Short stay"
    if noches <= u.mediana:
        return "Standard stay"
    if noches <= u.q3:
        return "Extended stay"
    if noches <= u.limite_superior_iqr:
        return "Long stay"
    return "Long stay/outlier"


def categoria_disponibilidad(dias: float, umbrales: UmbralesCategoria) -> str:
    """Etiqueta de disponibilidad segun availability_365 y umbrales de datos."""
    if pd.isna(dias):
        return "Desconocido"
    u = umbrales
    if dias <= u.q1:
        return "Low availability"
    if dias <= u.mediana:
        return "Medium availability"
    if dias <= u.q3:
        return "High availability"
    if dias <= u.limite_superior_iqr:
        return "Very high availability"
    return "Very high availability (outlier)"


def analizar_campo_price(
    df: pd.DataFrame,
    col: str = "price",
    nombre_coleccion: str = "",
    muestra_ejemplos: int = 8,
) -> dict[str, Any] | None:
    """
    Analisis exploratorio del campo price (moneda, separadores, texto).
    No modifica el DataFrame.
    """
    titulo = f" - {nombre_coleccion}" if nombre_coleccion else ""
    print(f"\nANÁLISIS DE CAMPO `{col}`{titulo}")
    print("-" * 80)

    if col not in df.columns:
        print(f"   Columna '{col}' no existe.")
        return None

    serie = df[col]
    print(f"   Tipo pandas: {serie.dtype}")
    n_total = len(serie)
    n_nulos = int(serie.isna().sum())
    pct_nulos = 100 * n_nulos / n_total if n_total else 0
    print(f"   Registros: {n_total:,} | Nulos: {n_nulos:,} ({pct_nulos:.2f}%)")

    no_nulo = serie.dropna()
    if len(no_nulo) == 0:
        print("   No hay valores no nulos para analizar.")
        return {"resumen": "sin_datos"}

    num_coerced = pd.to_numeric(serie, errors="coerce")
    n_parse_ok = int(num_coerced.notna().sum())
    n_parse_fail = int((serie.notna() & num_coerced.isna()).sum())
    print("\n   pd.to_numeric(errors='coerce'):")
    print(f"      - Reconocidos como número: {n_parse_ok:,}")
    print(f"      - No nulos que NO convierten: {n_parse_fail:,}")

    str_vals = no_nulo.astype(str).str.strip()

    def _clasificar_formato(s: str) -> str:
        s = str(s).strip()
        if re.search(r"[\$€£¥¢]", s):
            return "simbolo_moneda_en_texto"
        if re.search(r"\b(MXN|USD|EUR|GBP|ARS|COP|CLP)\b", s, re.I):
            return "codigo_moneda_en_texto"
        if re.search(r"[A-Za-z]", s) and not re.match(r"^[-+]?[\d\s,\.eE]+$", s):
            return "texto_u_otro_no_numerico"
        limpio = s.replace(" ", "")
        if re.match(r"^-?\d+$", limpio):
            return "entero_sin_separador_decimal"
        if re.match(r"^-?\d{1,3}(,\d{3})+(\.\d+)?$", limpio):
            return "miles_con_coma_punto_decimal_opcional"
        if re.match(r"^-?\d{1,3}(\.\d{3})+(,\d+)?$", limpio):
            return "miles_con_punto_coma_decimal_opcional"
        if re.match(r"^-?\d+\.\d+$", limpio):
            return "punto_como_decimal"
        if re.match(r"^-?\d+,\d+$", limpio):
            return "coma_como_decimal"
        if re.match(r"^-?[\d\s,\.]+$", limpio):
            return "digitos_con_separadores_mixtos"
        return "otro"

    tiene_simbolo = str_vals.str.contains(r"[\$€£¥¢]", regex=True)
    patrones = str_vals.map(_clasificar_formato)
    dist = patrones.value_counts()
    print("\n   Formato de la representación en texto (no nulos):")
    _display(dist.to_frame("conteo"))
    print(f"   Filas con símbolo $ € £ ¥ ¢ en el texto: {int(tiene_simbolo.sum()):,}")

    if n_parse_fail > 0:
        ejemplos = (
            serie[serie.notna() & num_coerced.isna()].drop_duplicates().head(muestra_ejemplos)
        )
        print(f"\n   Ejemplos que no convierten a número (hasta {muestra_ejemplos}):")
        _display(ejemplos.to_frame(col))

    if num_coerced.notna().any():
        v = num_coerced.dropna()
        print("\n   Estadísticos si se interpretan como número:")
        print(f"      - Mín: {v.min()} | Máx: {v.max()} | Media: {v.mean():.6g}")
        neg = int((v < 0).sum())
        if neg:
            print(f"      - Negativos: {neg:,} (revisar con analizar_valores_negativos)")

    if pd.api.types.is_numeric_dtype(serie):
        print("\n   Nota: la columna ya es numérica; el análisis de 'formato texto' aplica al castear a string.")

    return {
        "dtype": str(serie.dtype),
        "n_parse_ok": n_parse_ok,
        "n_parse_fail": n_parse_fail,
        "distribucion_formato": dist.to_dict(),
    }


def analizar_valores_negativos(
    df: pd.DataFrame,
    columnas: list[str],
    nombre_coleccion: str = "",
) -> dict[str, Any]:
    """Detecta negativos en columnas numéricas o convertibles; imprime resumen."""
    titulo = f" - {nombre_coleccion}" if nombre_coleccion else ""
    print(f"\nVALORES NEGATIVOS{titulo}")
    print("-" * 80)

    resultado: dict[str, Any] = {}
    for col in columnas:
        if col not in df.columns:
            print(f"\n   [{col}] No existe en el DataFrame.")
            resultado[col] = {"error": "columna_inexistente"}
            continue

        num = pd.to_numeric(df[col], errors="coerce")
        valid = num.dropna()
        n_valid = len(valid)
        n_neg = int((valid < 0).sum())
        n_cero = int((valid == 0).sum())
        n_pos = int((valid > 0).sum())
        n_no_convert = int(df[col].notna().sum() - n_valid)

        print(f"\n   Columna: {col}")
        print(f"      - Numéricos válidos: {n_valid:,} | No nulos no convertibles: {n_no_convert:,}")
        print(f"      - Negativos: {n_neg:,} | Ceros: {n_cero:,} | Positivos: {n_pos:,}")
        if n_valid > 0:
            print(f"      - Mínimo: {valid.min()} | Máximo: {valid.max()}")
        if n_neg > 0:
            print("      >>> Hay valores negativos: conviene regla de transformación o limpieza.")
        else:
            print("      >>> Sin valores negativos en valores numéricos válidos.")

        resultado[col] = {
            "n_negativos": n_neg,
            "n_validos": n_valid,
            "min": float(valid.min()) if n_valid else None,
            "max": float(valid.max()) if n_valid else None,
            "requiere_atencion": n_neg > 0,
        }
    return resultado


def analizar_estructura(df: pd.DataFrame, nombre_coleccion: str) -> None:
    """Resumen de estructura: head, dimensiones, tipos, describe."""
    print("\n" + "=" * 80)
    print(f"COLECCIÓN: {nombre_coleccion}")
    print("=" * 80)

    print("\nPRIMERAS FILAS (primeros 5 registros):")
    _display(df.head(5))

    print("\nDIMENSIONES:")
    print(f"   - Filas: {df.shape[0]:,}")
    print(f"   - Columnas: {df.shape[1]}")

    print("\nTIPOS DE DATOS:")
    print("INFO")
    df.info(verbose=False)
    print("TYPES")
    print(df.dtypes)

    print("\nESTADÍSTICAS (Columnas numéricas):")
    _display(df.describe().T)

    print("\nESTADÍSTICAS COMPLETAS (incluye variables categóricas):")
    _display(df.describe(include="all").T)

    cols_no_numericas = df.select_dtypes(
        include=["object", "string", "bool", "datetime64", "str"]
    ).columns
    if len(cols_no_numericas) > 0:
        print(f"\nCOLUMNAS NO NUMÉRICAS ({len(cols_no_numericas)}):")
        for col in cols_no_numericas:
            try:
                unicos = df[col].nunique(dropna=False)
                print(f"   - {col}: {unicos} valores únicos")
                top = df[col].value_counts(dropna=False).head(5)
                print(f"      Principales valores:\n{top.to_dict()}")
            except Exception:
                print(f"   - {col}: Contiene datos complejos o no se puede resumir")


def analizar_valores_nulos(df: pd.DataFrame, nombre_coleccion: str) -> None:
    """Tabla de nulos por columna (solo columnas con al menos un nulo)."""
    print(f"\nVALORES NULOS Y FALTANTES - {nombre_coleccion}:")
    print("-" * 80)

    nulos = df.isnull().sum()
    total_registros = len(df)
    nulos_pct = (nulos / total_registros * 100).round(2)

    df_nulos = pd.DataFrame(
        {
            "Columna": nulos.index,
            "Cantidad de nulos": nulos.values,
            "Porcentaje (%)": nulos_pct.values,
        }
    )

    df_nulos_filtrado = df_nulos[df_nulos["Cantidad de nulos"] > 0].sort_values(
        "Cantidad de nulos", ascending=False
    )

    if len(df_nulos_filtrado) > 0:
        print("   Columnas con valores faltantes:")
        _display(df_nulos_filtrado)
    else:
        print("   Todas las columnas están completas (sin nulos)")


def analizar_duplicados(df: pd.DataFrame, nombre_coleccion: str, col_id: str = "_id") -> None:
    """Duplicados por ID y filas completamente duplicadas."""
    print(f"\nREGISTROS DUPLICADOS - {nombre_coleccion}:")
    print("-" * 80)

    total = len(df)

    unicos = df[col_id].nunique()
    duplicados_id = total - unicos
    pct_duplicados_id = (duplicados_id / total * 100) if total > 0 else 0

    print(f"   1. POR COLUMNA ID ({col_id}):")
    print(f"      - Total de registros: {total:,}")
    print(f"      - Registros únicos: {unicos:,}")
    print(f"      - Duplicados por ID: {duplicados_id:,} ({pct_duplicados_id:.2f}%)")

    filas_duplicadas = df.duplicated().sum()
    pct_filas_dup = (filas_duplicadas / total * 100) if total > 0 else 0

    print("\n   2. FILAS COMPLETAMENTE DUPLICADAS (todas las columnas):")
    print(f"      - Filas duplicadas: {filas_duplicadas:,} ({pct_filas_dup:.2f}%)")

    if duplicados_id == 0 and filas_duplicadas == 0:
        print("\n   Excelente: No hay duplicados en esta colección")


def analizar_outliers(
    df: pd.DataFrame,
    nombre_coleccion: str,
    columnas: list[str] | None = None,
) -> None:
    """Outliers por IQR en columnas numéricas."""
    if columnas is None:
        columnas = df.select_dtypes(include="number").columns.tolist()

    print(f"\nANÁLISIS DE OUTLIERS - {nombre_coleccion}:")
    print("-" * 80)

    if len(columnas) == 0:
        print("   No hay columnas numéricas para analizar")
        return

    for col in columnas:
        if col not in df.columns:
            print(f"   Columna '{col}' no encontrada")
            continue

        datos = pd.to_numeric(df[col], errors="coerce").dropna()

        if len(datos) == 0:
            print(f"\n   {col}: No hay datos numéricos válidos")
            continue

        q1 = datos.quantile(0.25)
        q3 = datos.quantile(0.75)
        iqr = q3 - q1

        if iqr == 0:
            print(f"\n   {col}: IQR = 0, no hay variación suficiente para detectar outliers con este método")
            continue

        limite_inferior = q1 - 1.5 * iqr
        limite_superior = q3 + 1.5 * iqr

        outliers = datos[(datos < limite_inferior) | (datos > limite_superior)]
        pct_outliers = len(outliers) / len(datos) * 100

        print(f"\n   {col}:")
        print(f"      - Mínimo: {datos.min():.2f}")
        print(f"      - Q1 (25%): {q1:.2f}")
        print(f"      - Mediana: {datos.median():.2f}")
        print(f"      - Q3 (75%): {q3:.2f}")
        print(f"      - Máximo: {datos.max():.2f}")
        print(f"      - IQR: {iqr:.2f}")
        print(f"      - Outliers detectados: {len(outliers):,} ({pct_outliers:.2f}%)")
        print(f"      - Rango válido: [{limite_inferior:.2f}, {limite_superior:.2f}]")
