# ETL Airbnb - Inteligencia de Negocios

## Descripcion

Este proyecto implementa un proceso ETL en Python sobre datos de Airbnb almacenados en MongoDB. El flujo completo incluye:

- extraccion de las colecciones `Listings`, `Reviews` y `Calendar`
- analisis exploratorio en Jupyter Notebook
- transformacion de datos segun hallazgos del EDA
- carga de resultados en SQLite
- exportacion a archivos Excel
- generacion de logs durante todo el proceso

El codigo principal vive en `src/` y el notebook de exploracion esta en `notebooks/exploracion_airbnb.ipynb`.

## Estructura del proyecto

```text
etl_airbnb/
|-- logs/
|-- notebooks/
|   `-- exploracion_airbnb.ipynb
|-- output/
|   |-- excel/
|   `-- sqlite/
|-- src/
|   |-- __init__.py
|   |-- carga.py
|   |-- config.py
|   |-- eda.py
|   |-- extraccion.py
|   |-- logger_config.py
|   |-- mongo_connection.py
|   |-- transformacion.py
|   `-- validacion.py
|-- .env.example
|-- requirements.txt
`-- README.md
```

## Requisitos

- Python 3.10 o superior
- MongoDB en ejecucion
- Base de datos cargada con las colecciones:
  - `Listings`
  - `Reviews`
  - `Calendar`

## Instalacion

### 1. Crear y activar entorno virtual

En PowerShell:

```powershell
Set-Location "C:\ruta\al\proyecto\etl_airbnb"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Si PowerShell bloquea la activacion:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

### 2. Instalar dependencias

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Configurar variables de entorno

Crear `.env` a partir del ejemplo:

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
| **`EXCEL_MAX_ROWS_PER_FILE`** | Maximo de filas por cada archivo **.xlsx** (cada trozo al partir una coleccion grande). | `1000000` para volcar casi todo en pocos archivos; `2000` para trozos pequeños |
| **`EXCEL_MAX_FILES`** | Maximo de archivos **por coleccion** en Excel. **Vacio** = sin limite (se generan todos los `*_partXXX.xlsx` necesarios). Con `1` solo el primer trozo: ideal con pocas filas para **previsualizar** sin llenar el disco. | Preview: `EXCEL_MAX_FILES=1` y `EXCEL_MAX_ROWS_PER_FILE=2000` → un solo `.xlsx` ~2000 filas por tabla (`listings.xlsx`, `reviews.xlsx`, `calendar_part001.xlsx`, etc.) |
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

**Nota:** `python -m src.carga` puede tardar mucho y generar archivos grandes (SQLite sigue cargando **todo** el dataset). Para **solo previsualizar Excel**, pon en `.env` por ejemplo `EXCEL_MAX_FILES=1` y `EXCEL_MAX_ROWS_PER_FILE=2000`. Para acortar tambien la extraccion, usa `Extraccion.extraer_todo(limit_by_collection={...})` en un script propio.

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

Editar `.env` y ajustar como minimo:

```env
MONGO_URI=mongodb://localhost:27017/
MONGO_DB=airbnb_mx
MONGO_LISTINGS_COLLECTION=Listings
MONGO_REVIEWS_COLLECTION=Reviews
MONGO_CALENDAR_COLLECTION=Calendar
LOG_LEVEL=INFO
SQLITE_DB_FILENAME=airbnb_transformado.db
EXCEL_MAX_ROWS_PER_FILE=1000000
SQLITE_TO_SQL_CHUNKSIZE=50000
```

Notas:

- `MONGO_DB` debe coincidir con el nombre real de la base en tu MongoDB.
- Si cambiaste el nombre de alguna coleccion al importar los datos, tambien debes ajustarlo en `.env`.
- El archivo `.env` es local y no debe subirse al repositorio.

## Ejecucion

Todos los comandos se ejecutan desde la raiz del proyecto y con el entorno virtual activado.

### 1. Probar solo la extraccion

Extrae una muestra de 5 registros por coleccion:

```powershell
python -m src.extraccion
```

### 2. Ejecutar extraccion + transformacion

```powershell
python -m src.transformacion
```

Este comando:

- se conecta a MongoDB
- extrae las colecciones completas
- transforma los datos
- ejecuta validaciones post-transformacion

### 3. Ejecutar el ETL completo

```powershell
python -m src.carga
```

Este comando:

- extrae datos desde MongoDB
- transforma los DataFrames
- crea o reemplaza tablas en SQLite
- exporta archivos Excel en `output/excel/`
- verifica que los conteos en SQLite coincidan con los DataFrames

### 4. Ejecutar el notebook de exploracion

```powershell
jupyter notebook notebooks/exploracion_airbnb.ipynb
```

Tambien puedes abrir el notebook directamente en VS Code y seleccionar el kernel de `.venv`.

## Salidas esperadas

### Logs

Se generan en `logs/` con nombre tipo:

```text
log_YYYYMMDD_HHMM.txt
```

### SQLite

La base transformada se guarda en:

```text
output/sqlite/airbnb_transformado.db
```

El nombre exacto depende de `SQLITE_DB_FILENAME`.

### Excel

Los archivos se guardan en:

```text
output/excel/
```

Si una tabla supera el limite configurado en `EXCEL_MAX_ROWS_PER_FILE`, se divide en varios archivos, por ejemplo:

```text
calendar_part001.xlsx
calendar_part002.xlsx
...
```

## Archivos principales

- `src/extraccion.py`: conexion a MongoDB y extraccion a DataFrames.
- `src/eda.py`: funciones de analisis exploratorio reutilizadas por el notebook y la transformacion.
- `src/transformacion.py`: limpieza, enriquecimiento, categorias y columnas derivadas.
- `src/validacion.py`: validaciones de calidad despues de transformar.
- `src/carga.py`: escritura en SQLite, exportacion a Excel y verificacion de conteos.
- `notebooks/exploracion_airbnb.ipynb`: analisis exploratorio, hallazgos y visualizaciones.

## Recomendaciones para la entrega

- Ejecutar primero `python -m src.extraccion` para validar conexion y nombres de coleccion.
- Ejecutar el notebook y revisar que todas las celdas terminen sin error.
- Ejecutar `python -m src.carga` solo cuando la configuracion ya este validada, porque procesa mucho volumen y puede tardar varios minutos.
- Verificar que existan archivos nuevos en `logs/`, `output/sqlite/` y `output/excel/`.

## Integrantes

Completar con los nombres y responsabilidades reales del equipo en el documento final.
