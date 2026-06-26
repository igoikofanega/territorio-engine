from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from .db import engine

app = FastAPI(title="territorio-engine API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/db")
async def health_db() -> dict[str, str]:
    """Comprueba la conexión a PostGIS (prueba de extremo a extremo del stack)."""
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    return {"db": "ok"}


@app.get("/municipios/count")
async def municipios_count() -> dict[str, int]:
    async with engine.connect() as conn:
        total = (await conn.execute(text("SELECT count(*) FROM dim_municipio"))).scalar_one()
    return {"total": total}


@app.get("/municipios.geojson")
async def municipios_geojson(prov: str | None = None) -> dict:
    """Devuelve los municipios como FeatureCollection (geometría simplificada).

    `prov` filtra por código de provincia (2 dígitos). Sin filtro devuelve toda
    España, que es pesado: para el mapa interactivo conviene filtrar.
    """
    where = "WHERE cod_provincia = :prov" if prov else ""
    sql = text(f"""
        SELECT cod_municipio, nombre,
               ST_AsGeoJSON(ST_SimplifyPreserveTopology(geom_4326, 0.001))::json AS geom
        FROM dim_municipio
        {where}
        ORDER BY cod_municipio
    """)  # noqa: S608 — `where` es literal fijo, no entrada de usuario
    async with engine.connect() as conn:
        rows = (await conn.execute(sql, {"prov": prov} if prov else {})).all()
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"cod_municipio": r.cod_municipio, "nombre": r.nombre},
                "geometry": r.geom,
            }
            for r in rows
        ],
    }
