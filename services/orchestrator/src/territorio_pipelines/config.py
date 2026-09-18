import os

DEFAULT_ASYNC_URL = "postgresql+asyncpg://territorio:territorio@db:5432/territorio"


def sync_database_url() -> str:
    """URL síncrona (psycopg2) para Alembic y la carga por lotes.

    En docker-compose la variable viene en forma async (asyncpg); aquí la
    convertimos al driver síncrono.
    """
    url = os.environ.get("DATABASE_URL", DEFAULT_ASYNC_URL)
    return url.replace("+asyncpg", "+psycopg2")


def numero_env[N: (int, float)](nombre: str, defecto: N) -> N:
    """Número desde el entorno, con `defecto` si la variable falta **o está vacía**.

    Lo de "vacía" es lo importante. `docker-compose.yml` pasa las variables opcionales
    como `${VAR:-}`, así que si el `.env` no las define llegan al contenedor definidas y
    vacías, y `float(os.environ.get(VAR, "4"))` revienta en vez de usar el 4: el valor por
    defecto de `get` solo cubre la ausencia. Así se rompió la tanda diaria de etiquetado.

    El tipo sale del defecto (`4.0` → float, `0` → int). Un valor que no es un número
    falla nombrando la variable: una errata convertida en silencio en el defecto haría
    creer que el ajuste se aplica.
    """
    crudo = os.environ.get(nombre, "").strip()
    if not crudo:
        return defecto
    try:
        return type(defecto)(crudo)
    except ValueError:
        raise ValueError(f"{nombre}={crudo!r} no es un {type(defecto).__name__} válido") from None
