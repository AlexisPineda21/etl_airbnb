# ETL Airbnb Buenos Aires

Proyecto base para desarrollar el taller de Inteligencia de Negocios sobre los
datasets de Airbnb de la Ciudad Autonoma de Buenos Aires.

## Objetivo

Construir un proceso ETL en Python usando MongoDB como fuente de datos, un EDA
en Jupyter Notebook y una carga final en SQLite y archivos Excel.

## Estructura del proyecto

```text
elt_airbnb/
|-- logs/
|-- notebooks/
|-- output/
|   |-- excel/
|   `-- sqlite/
|-- src/
|   |-- __init__.py
|   |-- carga.py
|   |-- config.py
|   |-- extraccion.py
|   |-- logger_config.py
|   |-- mongo_connection.py
|   `-- transformacion.py
|-- .env.example
|-- .gitignore
|-- README.md
`-- requirements.txt
```

## Instalacion

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Configuracion

1. Crear un archivo `.env` tomando como base `.env.example`.
2. Levantar MongoDB localmente.
3. Importar los datasets fuente en las colecciones `Listings`, `Reviews` y
   `Calendar`.

## Estado inicial del proyecto

- `src/extraccion.py` contiene la base de la clase `Extraccion`.
- `src/config.py` centraliza la configuracion general.
- `src/logger_config.py` crea un archivo de log por ejecucion.
- `src/transformacion.py` y `src/carga.py` quedaron como esqueleto para las
  siguientes fases del trabajo.
