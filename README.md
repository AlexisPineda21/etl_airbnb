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

```powershell
Copy-Item .env.example .env
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
