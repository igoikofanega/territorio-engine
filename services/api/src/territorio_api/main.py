from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from .constants import PROVINCIAS
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


@app.get("/provincias")
async def provincias() -> list[dict]:
    """Provincias con datos, con nombre y si tienen pirámide (para el selector)."""
    async with engine.connect() as conn:
        munis = (
            await conn.execute(
                text("SELECT DISTINCT cod_provincia FROM dim_municipio ORDER BY cod_provincia")
            )
        ).all()
        con_pir = {
            r[0]
            for r in (
                await conn.execute(
                    text("SELECT DISTINCT left(cod_municipio, 2) FROM fact_piramide")
                )
            ).all()
        }
    return [
        {
            "cod": r.cod_provincia,
            "nombre": PROVINCIAS.get(r.cod_provincia, r.cod_provincia),
            "piramide": r.cod_provincia in con_pir,
        }
        for r in munis
    ]


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


@app.get("/poblacion/anios")
async def poblacion_anios() -> list[int]:
    async with engine.connect() as conn:
        rows = (
            await conn.execute(
                text("SELECT DISTINCT anio FROM fact_municipio_anual ORDER BY anio DESC")
            )
        ).all()
    return [r.anio for r in rows]


@app.get("/envejecimiento/anios")
async def envejecimiento_anios() -> list[int]:
    async with engine.connect() as conn:
        rows = (
            await conn.execute(text("SELECT DISTINCT anio FROM fact_piramide ORDER BY anio DESC"))
        ).all()
    return [r.anio for r in rows]


@app.get("/envejecimiento.geojson")
async def envejecimiento(prov: str | None = None, anio: int | None = None) -> dict:
    """Coroplético del índice de envejecimiento (pob 65+ / pob 0-14 × 100) por municipio.

    Se agrega desde `fact_piramide`. Sin `anio` usa el último disponible.
    """
    async with engine.connect() as conn:
        if anio is None:
            anio = (
                await conn.execute(text("SELECT max(anio) FROM fact_piramide"))
            ).scalar_one_or_none()

        where = "WHERE d.cod_provincia = :prov" if prov else ""
        sql = text(f"""
            WITH agg AS (
                SELECT cod_municipio,
                       sum(poblacion) FILTER (WHERE edad_min < 15) AS pob_0_14,
                       sum(poblacion) FILTER (WHERE edad_min >= 65) AS pob_65_mas
                FROM fact_piramide WHERE anio = :anio GROUP BY cod_municipio
            )
            SELECT d.cod_municipio, d.nombre, a.pob_0_14, a.pob_65_mas,
                   round(a.pob_65_mas::numeric / NULLIF(a.pob_0_14, 0) * 100)::int AS indice,
                   ST_AsGeoJSON(ST_SimplifyPreserveTopology(d.geom_4326, 0.001))::json AS geom
            FROM dim_municipio d
            LEFT JOIN agg a ON a.cod_municipio = d.cod_municipio
            {where}
            ORDER BY d.cod_municipio
        """)  # noqa: S608 — `where` es literal fijo, no entrada de usuario
        params = {"anio": anio}
        if prov:
            params["prov"] = prov
        rows = (await conn.execute(sql, params)).all()

    return {
        "type": "FeatureCollection",
        "properties": {"anio": anio},
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "cod_municipio": r.cod_municipio,
                    "nombre": r.nombre,
                    "indice": r.indice,
                },
                "geometry": r.geom,
            }
            for r in rows
        ],
    }


@app.get("/paro/anios")
async def paro_anios() -> list[int]:
    async with engine.connect() as conn:
        rows = (
            await conn.execute(
                text(
                    "SELECT DISTINCT anio FROM fact_municipio_anual "
                    "WHERE paro_media_anual IS NOT NULL ORDER BY anio DESC"
                )
            )
        ).all()
    return [r.anio for r in rows]


@app.get("/paro.geojson")
async def paro(prov: str | None = None, anio: int | None = None) -> dict:
    """Paro registrado por municipio: total medio anual y por 1.000 habitantes."""
    async with engine.connect() as conn:
        if anio is None:
            anio = (
                await conn.execute(
                    text(
                        "SELECT max(anio) FROM fact_municipio_anual "
                        "WHERE paro_media_anual IS NOT NULL"
                    )
                )
            ).scalar_one_or_none()
        where = "WHERE d.cod_provincia = :prov" if prov else ""
        sql = text(f"""
            SELECT d.cod_municipio, d.nombre, f.paro_media_anual,
                   round(f.paro_media_anual::numeric
                         / NULLIF(f.poblacion_total, 0) * 1000)::int AS paro_1000,
                   ST_AsGeoJSON(ST_SimplifyPreserveTopology(d.geom_4326, 0.001))::json AS geom
            FROM dim_municipio d
            LEFT JOIN fact_municipio_anual f
                   ON f.cod_municipio = d.cod_municipio AND f.anio = :anio
            {where}
            ORDER BY d.cod_municipio
        """)  # noqa: S608 — `where` es literal fijo, no entrada de usuario
        params = {"anio": anio}
        if prov:
            params["prov"] = prov
        rows = (await conn.execute(sql, params)).all()
    return {
        "type": "FeatureCollection",
        "properties": {"anio": anio},
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "cod_municipio": r.cod_municipio,
                    "nombre": r.nombre,
                    "paro_media_anual": r.paro_media_anual,
                    "paro_1000": r.paro_1000,
                },
                "geometry": r.geom,
            }
            for r in rows
        ],
    }


@app.get("/renta/anios")
async def renta_anios() -> list[int]:
    async with engine.connect() as conn:
        rows = (
            await conn.execute(
                text(
                    "SELECT DISTINCT anio FROM fact_municipio_anual "
                    "WHERE renta_neta_media_persona IS NOT NULL ORDER BY anio DESC"
                )
            )
        ).all()
    return [r.anio for r in rows]


@app.get("/renta.geojson")
async def renta(prov: str | None = None, anio: int | None = None) -> dict:
    """Renta neta media por persona (€/año) por municipio (INE ADRH)."""
    async with engine.connect() as conn:
        if anio is None:
            anio = (
                await conn.execute(
                    text(
                        "SELECT max(anio) FROM fact_municipio_anual "
                        "WHERE renta_neta_media_persona IS NOT NULL"
                    )
                )
            ).scalar_one_or_none()
        where = "WHERE d.cod_provincia = :prov" if prov else ""
        sql = text(f"""
            SELECT d.cod_municipio, d.nombre,
                   round(f.renta_neta_media_persona)::int AS renta,
                   ST_AsGeoJSON(ST_SimplifyPreserveTopology(d.geom_4326, 0.001))::json AS geom
            FROM dim_municipio d
            LEFT JOIN fact_municipio_anual f
                   ON f.cod_municipio = d.cod_municipio AND f.anio = :anio
            {where}
            ORDER BY d.cod_municipio
        """)  # noqa: S608 — `where` es literal fijo, no entrada de usuario
        params = {"anio": anio}
        if prov:
            params["prov"] = prov
        rows = (await conn.execute(sql, params)).all()
    return {
        "type": "FeatureCollection",
        "properties": {"anio": anio},
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "cod_municipio": r.cod_municipio,
                    "nombre": r.nombre,
                    "renta": r.renta,
                },
                "geometry": r.geom,
            }
            for r in rows
        ],
    }


@app.get("/alquiler/anios")
async def alquiler_anios() -> list[int]:
    async with engine.connect() as conn:
        rows = (
            await conn.execute(
                text(
                    "SELECT DISTINCT anio FROM fact_municipio_anual "
                    "WHERE alquiler_eur_m2 IS NOT NULL ORDER BY anio DESC"
                )
            )
        ).all()
    return [r.anio for r in rows]


@app.get("/alquiler.geojson")
async def alquiler(prov: str | None = None, anio: int | None = None) -> dict:
    """Precio medio del alquiler (€/m²·mes) por municipio (SERPAVI)."""
    async with engine.connect() as conn:
        if anio is None:
            anio = (
                await conn.execute(
                    text(
                        "SELECT max(anio) FROM fact_municipio_anual "
                        "WHERE alquiler_eur_m2 IS NOT NULL"
                    )
                )
            ).scalar_one_or_none()
        where = "WHERE d.cod_provincia = :prov" if prov else ""
        sql = text(f"""
            SELECT d.cod_municipio, d.nombre, f.alquiler_eur_m2 AS alquiler,
                   ST_AsGeoJSON(ST_SimplifyPreserveTopology(d.geom_4326, 0.001))::json AS geom
            FROM dim_municipio d
            LEFT JOIN fact_municipio_anual f
                   ON f.cod_municipio = d.cod_municipio AND f.anio = :anio
            {where}
            ORDER BY d.cod_municipio
        """)  # noqa: S608 — `where` es literal fijo, no entrada de usuario
        params = {"anio": anio}
        if prov:
            params["prov"] = prov
        rows = (await conn.execute(sql, params)).all()
    return {
        "type": "FeatureCollection",
        "properties": {"anio": anio},
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "cod_municipio": r.cod_municipio,
                    "nombre": r.nombre,
                    "alquiler": r.alquiler,
                },
                "geometry": r.geom,
            }
            for r in rows
        ],
    }


@app.get("/indice.geojson")
async def indice(prov: str | None = None) -> dict:
    """Índice "¿dónde vivir?" (0-100) + percentiles por componente (explicabilidad)."""
    async with engine.connect() as conn:
        anio = (
            await conn.execute(text("SELECT max(anio) FROM indice_municipio"))
        ).scalar_one_or_none()
        where = "WHERE d.cod_provincia = :prov" if prov else ""
        sql = text(f"""
            SELECT d.cod_municipio, d.nombre, i.score,
                   i.c_renta, i.c_paro, i.c_alquiler, i.c_envejecimiento,
                   ST_AsGeoJSON(ST_SimplifyPreserveTopology(d.geom_4326, 0.001))::json AS geom
            FROM dim_municipio d
            LEFT JOIN indice_municipio i
                   ON i.cod_municipio = d.cod_municipio AND i.anio = :anio
            {where}
            ORDER BY d.cod_municipio
        """)  # noqa: S608 — `where` es literal fijo, no entrada de usuario
        params = {"anio": anio}
        if prov:
            params["prov"] = prov
        rows = (await conn.execute(sql, params)).all()
    return {
        "type": "FeatureCollection",
        "properties": {"anio": anio},
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "cod_municipio": r.cod_municipio,
                    "nombre": r.nombre,
                    "score": r.score,
                    "c_renta": r.c_renta,
                    "c_paro": r.c_paro,
                    "c_alquiler": r.c_alquiler,
                    "c_envejecimiento": r.c_envejecimiento,
                },
                "geometry": r.geom,
            }
            for r in rows
        ],
    }


@app.get("/clima.geojson")
async def clima(prov: str | None = None) -> dict:
    """Clima por municipio: temperatura media anual (°C) y precipitación (mm)."""
    async with engine.connect() as conn:
        anio = (
            await conn.execute(
                text(
                    "SELECT max(anio) FROM fact_municipio_anual WHERE temp_media_anual IS NOT NULL"
                )
            )
        ).scalar_one_or_none()
        where = "WHERE d.cod_provincia = :prov" if prov else ""
        sql = text(f"""
            SELECT d.cod_municipio, d.nombre,
                   f.temp_media_anual AS temp, f.precip_anual_mm AS precip,
                   ST_AsGeoJSON(ST_SimplifyPreserveTopology(d.geom_4326, 0.001))::json AS geom
            FROM dim_municipio d
            LEFT JOIN fact_municipio_anual f
                   ON f.cod_municipio = d.cod_municipio AND f.anio = :anio
            {where}
            ORDER BY d.cod_municipio
        """)  # noqa: S608 — `where` es literal fijo, no entrada de usuario
        params = {"anio": anio}
        if prov:
            params["prov"] = prov
        rows = (await conn.execute(sql, params)).all()
    return {
        "type": "FeatureCollection",
        "properties": {"anio": anio},
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "cod_municipio": r.cod_municipio,
                    "nombre": r.nombre,
                    "temp": r.temp,
                    "precip": r.precip,
                },
                "geometry": r.geom,
            }
            for r in rows
        ],
    }


@app.get("/futuro.geojson")
async def futuro(prov: str | None = None) -> dict:
    """Proyección demográfica: cambio % a horizonte y trayectoria por municipio."""
    where = "WHERE d.cod_provincia = :prov" if prov else ""
    sql = text(f"""
        SELECT d.cod_municipio, d.nombre, p.cambio_pct, p.trayectoria,
               p.pob_base, p.pob_proyectada, p.anio_horizonte,
               ST_AsGeoJSON(ST_SimplifyPreserveTopology(d.geom_4326, 0.001))::json AS geom
        FROM dim_municipio d
        LEFT JOIN proyeccion_municipio p ON p.cod_municipio = d.cod_municipio
        {where}
        ORDER BY d.cod_municipio
    """)  # noqa: S608 — `where` es literal fijo, no entrada de usuario
    async with engine.connect() as conn:
        rows = (await conn.execute(sql, {"prov": prov} if prov else {})).all()
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "cod_municipio": r.cod_municipio,
                    "nombre": r.nombre,
                    "cambio_pct": r.cambio_pct,
                    "trayectoria": r.trayectoria,
                    "pob_base": r.pob_base,
                    "pob_proyectada": r.pob_proyectada,
                    "anio_horizonte": r.anio_horizonte,
                },
                "geometry": r.geom,
            }
            for r in rows
        ],
    }


@app.get("/futuro-cohorte.geojson")
async def futuro_cohorte(prov: str | None = None) -> dict:
    """Proyección v2 (cohorte-componente Hamilton-Perry). Solo provincias con pirámide."""
    where = "WHERE d.cod_provincia = :prov" if prov else ""
    sql = text(f"""
        SELECT d.cod_municipio, d.nombre, p.cambio_pct, p.trayectoria,
               p.pob_base, p.pob_proyectada, p.anio_horizonte,
               ST_AsGeoJSON(ST_SimplifyPreserveTopology(d.geom_4326, 0.001))::json AS geom
        FROM dim_municipio d
        LEFT JOIN proyeccion_cohorte p ON p.cod_municipio = d.cod_municipio
        {where}
        ORDER BY d.cod_municipio
    """)  # noqa: S608 — `where` es literal fijo, no entrada de usuario
    async with engine.connect() as conn:
        rows = (await conn.execute(sql, {"prov": prov} if prov else {})).all()
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "cod_municipio": r.cod_municipio,
                    "nombre": r.nombre,
                    "cambio_pct": r.cambio_pct,
                    "trayectoria": r.trayectoria,
                    "pob_base": r.pob_base,
                    "pob_proyectada": r.pob_proyectada,
                    "anio_horizonte": r.anio_horizonte,
                },
                "geometry": r.geom,
            }
            for r in rows
        ],
    }


@app.get("/coropleta.geojson")
async def coropleta(prov: str | None = None, anio: int | None = None) -> dict:
    """Coroplético: geometría + población (y densidad) por municipio para un año.

    Sin `anio` usa el último disponible. `prov` filtra por provincia (recomendado
    para el mapa interactivo).
    """
    async with engine.connect() as conn:
        if anio is None:
            anio = (
                await conn.execute(text("SELECT max(anio) FROM fact_municipio_anual"))
            ).scalar_one_or_none()

        where = "WHERE d.cod_provincia = :prov" if prov else ""
        sql = text(f"""
            SELECT d.cod_municipio, d.nombre, f.poblacion_total,
                   round(f.poblacion_total / NULLIF(d.superficie_km2, 0))::int AS densidad,
                   ST_AsGeoJSON(ST_SimplifyPreserveTopology(d.geom_4326, 0.001))::json AS geom
            FROM dim_municipio d
            LEFT JOIN fact_municipio_anual f
                   ON f.cod_municipio = d.cod_municipio AND f.anio = :anio
            {where}
            ORDER BY d.cod_municipio
        """)  # noqa: S608 — `where` es literal fijo, no entrada de usuario
        params = {"anio": anio}
        if prov:
            params["prov"] = prov
        rows = (await conn.execute(sql, params)).all()

    return {
        "type": "FeatureCollection",
        "properties": {"anio": anio},
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "cod_municipio": r.cod_municipio,
                    "nombre": r.nombre,
                    "poblacion_total": r.poblacion_total,
                    "densidad": r.densidad,
                },
                "geometry": r.geom,
            }
            for r in rows
        ],
    }
