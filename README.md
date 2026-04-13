# ETL Airbnb — Inteligencia de negocios

## Descripcion del proyecto y objetivo

Proceso **ETL** en Python sobre datos de **Airbnb** almacenados en **MongoDB** (fuente obligatoria del taller): extracción a `pandas`, **transformación** según criterios del análisis exploratorio (EDA), **carga** a **SQLite** y exportación a **Excel (.xlsx)**, con **registro en logs** en cada fase.

Objetivos concretos:

- Cumplir el flujo **Extracción → Transformación → Carga** descrito en la guía del curso.
- Documentar hallazgos y decisiones en el notebook `notebooks/exploracion_airbnb.ipynb`.
- Dejar el código ejecutable desde módulos en `src/` (no solo en el notebook).

## Estructura del repositorio

```text
etl_airbnb/
├── logs/                    # Archivos log_YYYYMMDD_HHMM.txt (una corrida por archivo base)
├── notebooks/
│   └── exploracion_airbnb.ipynb
├── output/
│   ├── excel/               # XLSX exportados (Calendar puede partirse en varios archivos)
│   └── sqlite/              # Base SQLite (p. ej. airbnb_transformado.db)
├── src/
│   ├── __init__.py
│   ├── carga.py             # SQLite + XLSX + verificacion de conteos
│   ├── config.py            # Rutas y variables de entorno
│   ├── eda.py               # Funciones EDA y umbrales dinamicos
│   ├── extraccion.py        # MongoDB → DataFrames
│   ├── logger_config.py     # Logs archivo + consola
│   ├── mongo_connection.py
│   ├── transformacion.py    # Limpieza, categorias, derivadas
│   └── validacion.py        # Chequeos post-transformacion
├── .env.example
├── requirements.txt
└── README.md
```

## Instalacion

### 1. Crear entorno virtual (recomendado)

**Windows (PowerShell):**

```powershell
cd ruta\al\proyecto\etl_airbnb
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**Linux / macOS:**

```bash
cd ruta/al/proyecto/etl_airbnb
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Instalar dependencias

```powershell
pip install -r requirements.txt
```

Incluye: `pandas`, `pymongo`, `python-dotenv`, `jupyter`, `matplotlib`, `seaborn`, `openpyxl`.

### 3. Configuracion basica

1. Copiar `.env.example` a `.env` en la **raiz del proyecto** (mismo nivel que `README.md`).
2. Tener **MongoDB** en ejecución con la base cargada (colecciones `Listings`, `Reviews`, `Calendar`).
3. Las carpetas `logs/`, `output/sqlite/`, `output/excel/` se crean solas al ejecutar.

### Variables de entorno segun el PC donde ejecutas

El archivo **`.env` no se sube al repositorio** (cada integrante / cada ordenador tiene el suyo). Debes **revisar y adaptar** estas variables cuando cambies de máquina, de red o de cómo tengas montado MongoDB.

| Variable | Que ajustar | Ejemplo / notas |
|----------|-------------|-----------------|
| **`MONGO_URI`** | Direccion y puerto del servidor MongoDB en **tu** PC o red local. Si Mongo escucha en otro host, puerto o usa autenticacion, cambia aqui. | `mongodb://localhost:27017/` — en otra maquina de la LAN: `mongodb://192.168.1.10:27017/` — con usuario: `mongodb://user:pass@localhost:27017/` |
| **`MONGO_DB`** | Nombre exacto de la **base de datos** donde importaste los CSV (distingue mayusculas segun como la creaste en MongoDB). | Debe coincidir con lo que ves en Compass o `mongosh` (ej. `arbnb_MXN`, `airbnb_ba`). |
| **`MONGO_LISTINGS_COLLECTION`** | Nombre de la coleccion de listings **en tu base**. | Por defecto `Listings`; si la importaste como `listings` en minusculas, pon eso. |
| **`MONGO_REVIEWS_COLLECTION`** | Igual para reseñas. | `Reviews` |
| **`MONGO_CALENDAR_COLLECTION`** | Igual para calendario. | `Calendar` |
| **`LOG_LEVEL`** | Cuanto detalle quieres en consola y en `logs/`. En equipos lentos o corridas largas, `WARNING` reduce ruido; para depurar usa `DEBUG` si el codigo lo soporta o `INFO`. | `INFO` (recomendado), `WARNING`, `ERROR` |
| **`SQLITE_DB_FILENAME`** | Solo el **nombre del archivo** `.db` (la carpeta `output/sqlite/` es fija en el codigo). Cambialo si quieres varias bases en el mismo PC sin sobrescribir. | `airbnb_transformado.db` |
| **`EXCEL_MAX_ROWS_PER_FILE`** | Maximo de filas por archivo **.xlsx** antes de partir en `calendar_part002.xlsx`, etc. En PCs con poca RAM bajar el valor hace exports mas pequeños (y mas archivos). El limite teorico de Excel es ~1.048.576 filas por hoja. | `1000000` para dataset completo; valores bajos solo para pruebas |
| **`SQLITE_TO_SQL_CHUNKSIZE`** | Filas por lote al insertar en SQLite. PCs con poca RAM: bajar (ej. `20000`); con mucha RAM: subir ligeramente puede acelerar. | `50000` por defecto |

**Resumen:** en un **PC nuevo** lo minimo suele ser comprobar **`MONGO_URI`** y **`MONGO_DB`** (y que los tres nombres de coleccion coincidan con tu Mongo). El resto puede quedarse como en `.env.example` hasta que necesites afinar rendimiento o rutas de salida.

## Ejecucion del proyecto

Desde la **raíz** del repositorio, con el entorno virtual activado:

| Acción | Comando |
|--------|---------|
| Pipeline **extracción + transformación** (muestra en consola) | `python -m src.transformacion` |
| Pipeline **completo ETL** (incluye SQLite y Excel) | `python -m src.carga` |
| Solo probar extracción (5 filas por colección) | `python -m src.extraccion` |
| EDA en Jupyter | `jupyter notebook notebooks/exploracion_airbnb.ipynb` |

**Nota:** `python -m src.carga` puede tardar mucho y generar archivos grandes porque procesa **todo** el volumen (especialmente Calendar). Para pruebas, puedes usar límites en `Extraccion.extraer_todo(limit_by_collection={...})` desde un script propio.

### Ejemplo de ejecucion del proceso ETL (script corto)

```python
# ejecutar desde la raiz del repo con: python run_etl.py
from src.extraccion import Extraccion
from src.transformacion import Transformacion
from src.carga import Carga

ext = Extraccion()
ext.conectar()
try:
    datos = ext.extraer_todo()  # sin limites = todas las filas
    limpios = Transformacion().transformar(datos, validar_salida=True)
    Carga().ejecutar(limpios)
finally:
    ext.cerrar_conexion()
```

## Manejo de logs (requisito del taller)

- **Archivos:** carpeta `logs/`, nombre `log_YYYYMMDD_HHMM.txt`. Si en el mismo minuto ya existiera un archivo con ese nombre, se añade sufijo `_1`, `_2`, etc., para no sobrescribir.
- **Niveles:** `INFO`, `WARNING`, `ERROR` (según evento).
- **Formato de cada línea:** `fecha y hora | NIVEL | nombre_modulo | mensaje`
- **Scripts que registran eventos:** `extraccion.py`, `transformacion.py`, `carga.py` (todos usan `logger_config.get_logger`).

El mismo archivo de log agrupa normalmente toda una corrida en la que intervienen varias clases, porque el handler de archivo se crea una sola vez por proceso.

## Integrantes del grupo y responsabilidades

| Integrante | Responsabilidades (completar) |
|------------|-------------------------------|
| _Felipe Olaya Benitez_ | _EDA, Transformación y Carga_ |
| _Oscar Alexis Pineda Henao _ | _Extracción, Documentación_ |

_Sustituir la tabla por los datos reales del equipo._

## Contenido adicional util

- **Variables de entorno:** tabla detallada mas arriba (*Variables de entorno segun el PC donde ejecutas*); plantilla en `.env.example`.
- **Consultar SQLite:** [DB Browser for SQLite](https://sqlitebrowser.org/) o `sqlite3` en terminal; tablas en minúsculas (`listings`, `reviews`, `calendar`).
- **Rendimiento:** Calendar supera el límite de filas de Excel; la carga genera `calendar_part001.xlsx`, etc.
- **Calidad:** `validacion.py` comprueba duplicados, nulos críticos y columnas derivadas tras transformar.

## Referencias

- Documentación del taller (entregables ETL, logs, SQLite, informe PDF).
- [MongoDB](https://www.mongodb.com/docs/), [pandas](https://pandas.pydata.org/), [SQLite](https://www.sqlite.org/docs.html).
