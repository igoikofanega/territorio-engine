"""Comprueba que los modelos SQLAlchemy y las migraciones Alembic no divergen.

`migrations/env.py` usa `Base.metadata` como `target_metadata`. Eso significa que una
columna presente en la base de datos pero ausente del ORM sería propuesta para
**borrarse** en el siguiente `alembic revision --autogenerate` — y con ella, sus datos.

Ya ocurrió: las migraciones 0023 y 0025 añadieron 7 columnas a `fact_municipio_anual`
que nunca se declararon en `models.py`.

Estos tests necesitan una base de datos PostGIS de verdad (los tipos de GeoAlchemy2 no
existen en SQLite), así que se saltan si no hay una disponible. En CI la aporta el
servicio `postgis` del workflow.
"""

from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import OperationalError

from territorio_pipelines.models import Base

URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg2://territorio:territorio@localhost:5544/territorio"
)

# Tablas que crea Alembic, no el modelo de datos.
_AJENAS = {"alembic_version"}

# Tablas que pertenecen a una extensión instalada. Se descubren consultando `pg_depend`
# en vez de mantener una lista a mano, que se quedaría desfasada en cuanto cambie la
# imagen: `imresamu/postgis` trae postgis_tiger_geocoder y postgis_topology, que solos
# aportan ~36 tablas, y además pone `tiger` y `topology` en el search_path, así que
# aparecen al listar. Sin filtro de esquema a propósito: viven fuera de `public`.
_SQL_DE_EXTENSIONES = """
    SELECT c.relname
    FROM pg_class c
    JOIN pg_depend d ON d.objid = c.oid AND d.deptype = 'e'
    WHERE c.relkind IN ('r', 'v', 'm', 'f', 'p')
"""


@pytest.fixture(scope="module")
def bd():
    """(inspector, tablas_del_proyecto) o skip si no hay base de datos."""
    try:
        engine = create_engine(URL)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            de_extensiones = {r[0] for r in conn.execute(text(_SQL_DE_EXTENSIONES))}
    except (OperationalError, Exception) as exc:  # noqa: BLE001 — cualquier fallo = sin BD
        pytest.skip(f"sin base de datos disponible en {URL}: {type(exc).__name__}")
    insp = inspect(engine)
    if not insp.has_table("fact_municipio_anual"):
        pytest.skip("la base de datos existe pero no tiene el esquema aplicado")
    propias = set(insp.get_table_names()) - de_extensiones - _AJENAS
    return insp, propias


@pytest.fixture(scope="module")
def inspector(bd):
    return bd[0]


def test_no_faltan_tablas_del_orm_en_la_bd(inspector):
    reales = set(inspector.get_table_names())
    faltan = set(Base.metadata.tables) - reales
    assert not faltan, f"declaradas en models.py pero sin migración: {sorted(faltan)}"


def test_no_hay_tablas_en_la_bd_ausentes_del_orm(bd):
    _, propias = bd
    huerfanas = propias - set(Base.metadata.tables)
    assert not huerfanas, (
        f"existen en la base de datos pero no en models.py: {sorted(huerfanas)}. "
        "Un autogenerate las propondría para BORRARSE."
    )


def test_no_hay_deriva_de_columnas(inspector):
    problemas = []
    for tabla in sorted(set(Base.metadata.tables) & set(inspector.get_table_names())):
        en_bd = {c["name"] for c in inspector.get_columns(tabla)}
        en_orm = {c.name for c in Base.metadata.tables[tabla].columns}
        if faltan_orm := en_bd - en_orm:
            problemas.append(
                f"{tabla}: {sorted(faltan_orm)} están en la BD pero no en models.py "
                "(un autogenerate las BORRARÍA)"
            )
        if faltan_bd := en_orm - en_bd:
            problemas.append(
                f"{tabla}: {sorted(faltan_bd)} están en models.py pero no en la BD "
                "(falta la migración)"
            )
    assert not problemas, "deriva ORM ↔ Alembic:\n  " + "\n  ".join(problemas)


def test_cod_municipio_es_texto_de_5(inspector):
    """Los ceros a la izquierda importan: `01001` no es `1001`.

    Si alguna tabla lo declarase como entero, perdería silenciosamente los municipios
    de Álava, Albacete y Alicante al hacer el JOIN.
    """
    for tabla in sorted(set(Base.metadata.tables) & set(inspector.get_table_names())):
        for col in inspector.get_columns(tabla):
            if col["name"] == "cod_municipio":
                tipo = str(col["type"]).upper()
                assert "CHAR" in tipo, f"{tabla}.cod_municipio es {tipo}, debería ser texto"
