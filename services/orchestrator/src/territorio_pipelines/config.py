import os

DEFAULT_ASYNC_URL = "postgresql+asyncpg://territorio:territorio@db:5432/territorio"


def sync_database_url() -> str:
    """URL síncrona (psycopg2) para Alembic y la carga por lotes.

    En docker-compose la variable viene en forma async (asyncpg); aquí la
    convertimos al driver síncrono.
    """
    url = os.environ.get("DATABASE_URL", DEFAULT_ASYNC_URL)
    return url.replace("+asyncpg", "+psycopg2")
