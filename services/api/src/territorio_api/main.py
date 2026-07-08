from fastapi import FastAPI, HTTPException
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


@app.get("/resumen")
async def resumen(prov: str | None = None) -> dict:
    """Panel-resumen (España o una provincia): agregados, rankings y distribución."""
    filtro = "WHERE d.cod_provincia = :prov" if prov else ""
    p = {"prov": prov} if prov else {}

    async def top(orden: str, extra_join: str = "", extra_where: str = "", campo: str = "") -> list:
        sel = f", {campo}" if campo else ""
        sql = text(f"""
            SELECT d.cod_municipio AS cod, d.nombre {sel}
            FROM dim_municipio d {extra_join}
            {filtro} {("AND " + extra_where) if (filtro and extra_where) else (("WHERE " + extra_where) if extra_where else "")}
            ORDER BY {orden} LIMIT 6
        """)  # noqa: S608 — fragmentos literales fijos, `prov` va parametrizado
        async with engine.connect() as conn:
            return (await conn.execute(sql, p)).all()

    anio_idx = "(SELECT max(anio) FROM indice_municipio)"
    async with engine.connect() as conn:
        agg = (
            await conn.execute(
                text(f"""
                    SELECT count(*) AS n,
                           sum(f.poblacion_total) AS pob,
                           round(avg(i.score)::numeric, 1) AS indice_medio
                    FROM dim_municipio d
                    LEFT JOIN indice_municipio i
                           ON i.cod_municipio = d.cod_municipio AND i.anio = {anio_idx}
                    LEFT JOIN fact_municipio_anual f
                           ON f.cod_municipio = d.cod_municipio
                          AND f.anio = (SELECT max(anio) FROM fact_municipio_anual
                                        WHERE poblacion_total IS NOT NULL)
                    {filtro}
                """),  # noqa: S608
                p,
            )
        ).one()
        ext_medio = (
            await conn.execute(
                text(f"""
                    SELECT round(avg(f.pct_extranjeros)::numeric, 1) AS m
                    FROM fact_municipio_anual f JOIN dim_municipio d USING (cod_municipio)
                    WHERE f.anio = (SELECT max(anio) FROM fact_municipio_anual
                                    WHERE pct_extranjeros IS NOT NULL)
                    {("AND d.cod_provincia = :prov") if prov else ""}
                """),  # noqa: S608
                p,
            )
        ).scalar_one_or_none()
        riesgo = dict(
            (r.nivel, r.n)
            for r in (
                await conn.execute(
                    text(f"""
                        SELECT r.nivel, count(*) AS n
                        FROM riesgo_municipio r JOIN dim_municipio d USING (cod_municipio)
                        {filtro} GROUP BY r.nivel
                    """),  # noqa: S608
                    p,
                )
            ).all()
        )
        giros = dict(
            (r.tipo, r.n)
            for r in (
                await conn.execute(
                    text(f"""
                        SELECT i.tipo, count(*) AS n
                        FROM inflexion_municipio i JOIN dim_municipio d USING (cod_municipio)
                        {filtro} GROUP BY i.tipo
                    """),  # noqa: S608
                    p,
                )
            ).all()
        )
        # distribución del índice en tramos de 20
        dist = (
            await conn.execute(
                text(f"""
                    SELECT width_bucket(i.score, 0, 100, 5) AS tramo, count(*) AS n
                    FROM indice_municipio i JOIN dim_municipio d USING (cod_municipio)
                    WHERE i.anio = {anio_idx} {("AND d.cod_provincia = :prov") if prov else ""}
                    GROUP BY tramo ORDER BY tramo
                """),  # noqa: S608
                p,
            )
        ).all()

    def fmt(rows, campo):
        return [
            {"cod": r.cod, "nombre": r.nombre, "valor": getattr(r, campo)}
            for r in rows
            if getattr(r, campo) is not None
        ][:5]

    join_i = f"JOIN indice_municipio i ON i.cod_municipio = d.cod_municipio AND i.anio = {anio_idx}"
    mejor_indice = await top("i.score DESC NULLS LAST", join_i, campo="i.score AS score")
    peor_riesgo = await top(
        "r.prob DESC NULLS LAST",
        "JOIN riesgo_municipio r ON r.cod_municipio = d.cod_municipio",
        campo="r.prob AS prob",
    )
    mas_crecen = await top(
        "p.cambio_pct DESC NULLS LAST",
        "JOIN prediccion_ml p ON p.cod_municipio = d.cod_municipio",
        campo="p.cambio_pct AS cambio",
    )
    remontan = await top(
        "inf.magnitud DESC NULLS LAST",
        "JOIN inflexion_municipio inf ON inf.cod_municipio = d.cod_municipio",
        "inf.tipo = 'remonta'",
        campo="inf.anio_inflexion AS anio",
    )

    return {
        "ambito": PROVINCIAS.get(prov, prov) if prov else "España",
        "n_municipios": agg.n,
        "poblacion": agg.pob,
        "indice_medio": float(agg.indice_medio) if agg.indice_medio is not None else None,
        "extranjeros_medio": float(ext_medio) if ext_medio is not None else None,
        "riesgo": {k: riesgo.get(k, 0) for k in ("verde", "ambar", "rojo")},
        "giros": {
            "remonta": giros.get("remonta", 0),
            "se_hunde": giros.get("se hunde", 0) + giros.get("acelera caída", 0),
        },
        "distribucion_indice": [{"tramo": r.tramo, "n": r.n} for r in dist if r.tramo],
        "rankings": {
            "mejor_indice": fmt(mejor_indice, "score"),
            "mayor_riesgo": [
                {"cod": r.cod, "nombre": r.nombre, "valor": round(r.prob * 100, 1)}
                for r in peor_riesgo
                if r.prob is not None
            ][:5],
            "mas_crecen": fmt(mas_crecen, "cambio"),
            "remontan": fmt(remontan, "anio"),
        },
    }


@app.get("/municipios/count")
async def municipios_count() -> dict[str, int]:
    async with engine.connect() as conn:
        total = (await conn.execute(text("SELECT count(*) FROM dim_municipio"))).scalar_one()
    return {"total": total}


@app.get("/buscar")
async def buscar(q: str, limit: int = 12) -> list[dict]:
    """Busca municipios por nombre (prefijo primero, luego contiene). Case/acento-insensible."""
    q = q.strip()
    if len(q) < 2:
        return []
    limit = max(1, min(limit, 50))
    async with engine.connect() as conn:
        rows = (
            await conn.execute(
                text("""
                    SELECT cod_municipio, nombre, cod_provincia
                    FROM dim_municipio,
                         LATERAL (SELECT f_unaccent(lower(:qq)) AS q) q
                    WHERE f_unaccent(lower(nombre)) LIKE '%' || q.q || '%'
                    ORDER BY (f_unaccent(lower(nombre)) LIKE q.q || '%') DESC,
                             length(nombre), nombre
                    LIMIT :lim
                """),
                {"qq": q, "lim": limit},
            )
        ).all()
    return [
        {
            "cod": r.cod_municipio,
            "nombre": r.nombre,
            "provincia": PROVINCIAS.get(r.cod_provincia, r.cod_provincia),
            "cod_provincia": r.cod_provincia,
        }
        for r in rows
    ]


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


@app.get("/extranjeros/anios")
async def extranjeros_anios() -> list[int]:
    async with engine.connect() as conn:
        rows = (
            await conn.execute(
                text(
                    "SELECT DISTINCT anio FROM fact_municipio_anual "
                    "WHERE pct_extranjeros IS NOT NULL ORDER BY anio DESC"
                )
            )
        ).all()
    return [r.anio for r in rows]


@app.get("/extranjeros.geojson")
async def extranjeros(prov: str | None = None, anio: int | None = None) -> dict:
    """Porcentaje de población extranjera por municipio (INE padrón por nacionalidad)."""
    async with engine.connect() as conn:
        if anio is None:
            anio = (
                await conn.execute(
                    text(
                        "SELECT max(anio) FROM fact_municipio_anual "
                        "WHERE pct_extranjeros IS NOT NULL"
                    )
                )
            ).scalar_one_or_none()
        where = "WHERE d.cod_provincia = :prov" if prov else ""
        sql = text(f"""
            SELECT d.cod_municipio, d.nombre, f.pct_extranjeros, f.poblacion_extranjera,
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
                    "pct_extranjeros": r.pct_extranjeros,
                    "poblacion_extranjera": r.poblacion_extranjera,
                },
                "geometry": r.geom,
            }
            for r in rows
        ],
    }


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
                   i.c_renta, i.c_paro, i.c_alquiler, i.c_envejecimiento, i.c_servicios,
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
                    "c_servicios": r.c_servicios,
                },
                "geometry": r.geom,
            }
            for r in rows
        ],
    }


@app.get("/riesgo.geojson")
async def riesgo(prov: str | None = None) -> dict:
    """Semáforo de despoblación: probabilidad calibrada de pérdida fuerte a 5 años."""
    where = "WHERE d.cod_provincia = :prov" if prov else ""
    sql = text(f"""
        SELECT d.cod_municipio, d.nombre, r.prob, r.nivel,
               ST_AsGeoJSON(ST_SimplifyPreserveTopology(d.geom_4326, 0.001))::json AS geom
        FROM dim_municipio d
        LEFT JOIN riesgo_municipio r ON r.cod_municipio = d.cod_municipio
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
                    "prob": round(r.prob * 100, 1) if r.prob is not None else None,
                    "nivel": r.nivel,
                },
                "geometry": r.geom,
            }
            for r in rows
        ],
    }


@app.get("/lisa.geojson")
async def lisa(var: str = "crecimiento", prov: str | None = None) -> dict:
    """Hot spots LISA (Moran local): clusters espaciales significativos de una variable."""
    if var not in ("crecimiento", "renta"):
        raise HTTPException(status_code=400, detail="var debe ser 'crecimiento' o 'renta'")
    where = "AND d.cod_provincia = :prov" if prov else ""
    sql = text(f"""
        SELECT d.cod_municipio, d.nombre, l.valor, l.categoria, l.p,
               ST_AsGeoJSON(ST_SimplifyPreserveTopology(d.geom_4326, 0.001))::json AS geom
        FROM dim_municipio d
        LEFT JOIN lisa_municipio l
               ON l.cod_municipio = d.cod_municipio AND l.variable = :var
        WHERE true {where}
        ORDER BY d.cod_municipio
    """)  # noqa: S608 — `where` es literal fijo, no entrada de usuario
    params: dict = {"var": var}
    if prov:
        params["prov"] = prov
    async with engine.connect() as conn:
        rows = (await conn.execute(sql, params)).all()
    return {
        "type": "FeatureCollection",
        "properties": {"variable": var},
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "cod_municipio": r.cod_municipio,
                    "nombre": r.nombre,
                    "valor": r.valor,
                    "categoria": r.categoria,
                    "p": r.p,
                },
                "geometry": r.geom,
            }
            for r in rows
        ],
    }


@app.get("/fibra.geojson")
async def fibra(prov: str | None = None) -> dict:
    """Cobertura de banda ancha por municipio: % hogares con fibra (FTTH), ≥100 Mbps y 5G."""
    where = "WHERE d.cod_provincia = :prov" if prov else ""
    sql = text(f"""
        SELECT d.cod_municipio, d.nombre, c.pct_fibra, c.pct_100mbps, c.pct_5g,
               ST_AsGeoJSON(ST_SimplifyPreserveTopology(d.geom_4326, 0.001))::json AS geom
        FROM dim_municipio d
        LEFT JOIN municipio_conectividad c ON c.cod_municipio = d.cod_municipio
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
                    "pct_fibra": r.pct_fibra,
                    "pct_100mbps": r.pct_100mbps,
                    "pct_5g": r.pct_5g,
                },
                "geometry": r.geom,
            }
            for r in rows
        ],
    }


@app.get("/aislamiento.geojson")
async def aislamiento(prov: str | None = None) -> dict:
    """Aislamiento: km al municipio con sanidad más cercano y a la capital de provincia."""
    where = "WHERE d.cod_provincia = :prov" if prov else ""
    sql = text(f"""
        SELECT d.cod_municipio, d.nombre, a.km_salud, a.km_educacion, a.km_capital,
               ST_AsGeoJSON(ST_SimplifyPreserveTopology(d.geom_4326, 0.001))::json AS geom
        FROM dim_municipio d
        LEFT JOIN municipio_aislamiento a ON a.cod_municipio = d.cod_municipio
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
                    "km_salud": r.km_salud,
                    "km_educacion": r.km_educacion,
                    "km_capital": r.km_capital,
                },
                "geometry": r.geom,
            }
            for r in rows
        ],
    }


@app.get("/rendimiento.geojson")
async def rendimiento(prov: str | None = None) -> dict:
    """Residuo out-of-sample: cuánto crece cada municipio vs lo que sus features predicen."""
    where = "WHERE d.cod_provincia = :prov" if prov else ""
    sql = text(f"""
        SELECT d.cod_municipio, d.nombre, r.residuo, r.z, r.clasificacion,
               ST_AsGeoJSON(ST_SimplifyPreserveTopology(d.geom_4326, 0.001))::json AS geom
        FROM dim_municipio d
        LEFT JOIN rendimiento_municipio r ON r.cod_municipio = d.cod_municipio
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
                    "residuo": r.residuo,
                    "z": r.z,
                    "clasificacion": r.clasificacion,
                },
                "geometry": r.geom,
            }
            for r in rows
        ],
    }


@app.get("/demografia.geojson")
async def demografia(prov: str | None = None) -> dict:
    """Descomposición vegetativo vs migratorio del cambio de población 2015-2024."""
    where = "WHERE d.cod_provincia = :prov" if prov else ""
    sql = text(f"""
        SELECT d.cod_municipio, d.nombre,
               x.saldo_vegetativo, x.saldo_migratorio, x.cambio_total, x.dominante, x.tipo,
               ST_AsGeoJSON(ST_SimplifyPreserveTopology(d.geom_4326, 0.001))::json AS geom
        FROM dim_municipio d
        LEFT JOIN demografia_municipio x ON x.cod_municipio = d.cod_municipio
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
                    "saldo_vegetativo": r.saldo_vegetativo,
                    "saldo_migratorio": r.saldo_migratorio,
                    "cambio_total": r.cambio_total,
                    "dominante": r.dominante,
                    "tipo": r.tipo,
                },
                "geometry": r.geom,
            }
            for r in rows
        ],
    }


@app.get("/inflexion.geojson")
async def inflexion(prov: str | None = None) -> dict:
    """Punto de inflexión de la población: tipo de giro y año en que cambió la tendencia."""
    where = "WHERE d.cod_provincia = :prov" if prov else ""
    sql = text(f"""
        SELECT d.cod_municipio, d.nombre,
               i.anio_inflexion, i.pend_antes, i.pend_despues, i.tipo, i.magnitud,
               ST_AsGeoJSON(ST_SimplifyPreserveTopology(d.geom_4326, 0.001))::json AS geom
        FROM dim_municipio d
        LEFT JOIN inflexion_municipio i ON i.cod_municipio = d.cod_municipio
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
                    "anio_inflexion": r.anio_inflexion,
                    "pend_antes": r.pend_antes,
                    "pend_despues": r.pend_despues,
                    "tipo": r.tipo,
                    "magnitud": r.magnitud,
                },
                "geometry": r.geom,
            }
            for r in rows
        ],
    }


@app.get("/servicios.geojson")
async def servicios(prov: str | None = None) -> dict:
    """Servicios OSM per capita por municipio (‰ hab) para el coroplético."""
    async with engine.connect() as conn:
        anio = (
            await conn.execute(
                text(
                    "SELECT max(anio) FROM fact_municipio_anual "
                    "WHERE poblacion_total IS NOT NULL"
                )
            )
        ).scalar_one_or_none()
        where = "WHERE d.cod_provincia = :prov" if prov else ""
        sql = text(f"""
            SELECT d.cod_municipio, d.nombre,
                   s.n_salud, s.n_educacion, s.n_comercio, s.n_total,
                   CASE WHEN f.poblacion_total > 0
                        THEN round((s.n_total::numeric / f.poblacion_total * 1000)::numeric, 2)
                        ELSE NULL END AS serv_1000,
                   ST_AsGeoJSON(ST_SimplifyPreserveTopology(d.geom_4326, 0.001))::json AS geom
            FROM dim_municipio d
            LEFT JOIN municipio_servicios s ON s.cod_municipio = d.cod_municipio
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
                    "n_salud": r.n_salud,
                    "n_educacion": r.n_educacion,
                    "n_comercio": r.n_comercio,
                    "n_total": r.n_total,
                    "serv_1000": float(r.serv_1000) if r.serv_1000 is not None else None,
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
                   f.temp_max_media, f.temp_min_media, f.temp_min_abs,
                   f.dias_despejados, f.humedad_media,
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
                    "temp_max_media": r.temp_max_media,
                    "temp_min_media": r.temp_min_media,
                    "temp_min_abs": r.temp_min_abs,
                    "dias_despejados": r.dias_despejados,
                    "humedad_media": r.humedad_media,
                },
                "geometry": r.geom,
            }
            for r in rows
        ],
    }


@app.get("/arquetipos.geojson")
async def arquetipos(prov: str | None = None) -> dict:
    """Arquetipo (cluster) de cada municipio + etiqueta legible."""
    where = "WHERE d.cod_provincia = :prov" if prov else ""
    sql = text(f"""
        SELECT d.cod_municipio, d.nombre, a.cluster, a.etiqueta,
               ST_AsGeoJSON(ST_SimplifyPreserveTopology(d.geom_4326, 0.001))::json AS geom
        FROM dim_municipio d
        LEFT JOIN arquetipo_municipio a ON a.cod_municipio = d.cod_municipio
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
                    "cluster": r.cluster,
                    "etiqueta": r.etiqueta,
                },
                "geometry": r.geom,
            }
            for r in rows
        ],
    }


@app.get("/prediccion.geojson")
async def prediccion(prov: str | None = None) -> dict:
    """Predicción del modelo ML: cambio %, banda de incertidumbre y drivers por municipio."""
    where = "WHERE d.cod_provincia = :prov" if prov else ""
    sql = text(f"""
        SELECT d.cod_municipio, d.nombre, p.cambio_pct, p.cambio_inf, p.cambio_sup,
               p.pob_base, p.pob_proyectada, p.anio_horizonte, p.drivers,
               ST_AsGeoJSON(ST_SimplifyPreserveTopology(d.geom_4326, 0.001))::json AS geom
        FROM dim_municipio d
        LEFT JOIN prediccion_ml p ON p.cod_municipio = d.cod_municipio
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
                    "cambio_inf": r.cambio_inf,
                    "cambio_sup": r.cambio_sup,
                    "pob_base": r.pob_base,
                    "pob_proyectada": r.pob_proyectada,
                    "anio_horizonte": r.anio_horizonte,
                    "drivers": r.drivers,
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


_ETIQUETA_COMP = {
    "renta": "renta alta",
    "paro": "empleo sano",
    "alquiler": "alquiler asequible",
    "envejecimiento": "población joven",
    "servicios": "buenos servicios",
}


@app.get("/recomendar")
async def recomendar(
    pob_min: int | None = None,
    pob_max: int | None = None,
    alquiler_max: float | None = None,
    temp_min: float | None = None,
    temp_max: float | None = None,
    km_salud_max: float | None = None,
    w_renta: float = 0.25,
    w_paro: float = 0.20,
    w_alquiler: float = 0.20,
    w_envejecimiento: float = 0.15,
    w_servicios: float = 0.20,
    limit: int = 20,
) -> list[dict]:
    """'¿Dónde debería vivir yo?': filtros duros + pesos → top-N nacional explicado."""
    limit = max(1, min(limit, 100))
    pesos = {
        "renta": w_renta,
        "paro": w_paro,
        "alquiler": w_alquiler,
        "envejecimiento": w_envejecimiento,
        "servicios": w_servicios,
    }
    sql = text("""
        SELECT d.cod_municipio AS cod, d.nombre, d.cod_provincia,
               i.c_renta, i.c_paro, i.c_alquiler, i.c_envejecimiento, i.c_servicios,
               f.poblacion_total AS pob, f.alquiler_eur_m2 AS alquiler,
               f.temp_media_anual AS temp,
               a.km_salud, r.prob AS riesgo_prob, p.cambio_pct
        FROM indice_municipio i
        JOIN dim_municipio d ON d.cod_municipio = i.cod_municipio
        LEFT JOIN fact_municipio_anual f
               ON f.cod_municipio = i.cod_municipio AND f.anio = i.anio
        LEFT JOIN municipio_aislamiento a ON a.cod_municipio = i.cod_municipio
        LEFT JOIN riesgo_municipio r ON r.cod_municipio = i.cod_municipio
        LEFT JOIN prediccion_ml p ON p.cod_municipio = i.cod_municipio
        WHERE i.anio = (SELECT max(anio) FROM indice_municipio)
    """)
    async with engine.connect() as conn:
        rows = (await conn.execute(sql)).all()

    candidatos = []
    for r in rows:
        if pob_min is not None and (r.pob is None or r.pob < pob_min):
            continue
        if pob_max is not None and (r.pob is None or r.pob > pob_max):
            continue
        if alquiler_max is not None and r.alquiler is not None and r.alquiler > alquiler_max:
            continue
        if temp_min is not None and (r.temp is None or r.temp < temp_min):
            continue
        if temp_max is not None and (r.temp is None or r.temp > temp_max):
            continue
        if km_salud_max is not None and (r.km_salud is None or r.km_salud > km_salud_max):
            continue
        comps = {
            "renta": r.c_renta,
            "paro": r.c_paro,
            "alquiler": r.c_alquiler,
            "envejecimiento": r.c_envejecimiento,
            "servicios": r.c_servicios,
        }
        num = den = 0.0
        for k, v in comps.items():
            if v is None:
                continue
            num += pesos[k] * v
            den += pesos[k]
        if den == 0:
            continue
        score = num / den
        razones = sorted(
            ((k, v) for k, v in comps.items() if v is not None and pesos[k] > 0),
            key=lambda kv: kv[1] * pesos[kv[0]],
            reverse=True,
        )[:2]
        candidatos.append(
            {
                "cod": r.cod,
                "nombre": r.nombre,
                "provincia": PROVINCIAS.get(r.cod_provincia, r.cod_provincia),
                "score": round(score, 1),
                "razones": [_ETIQUETA_COMP[k] for k, _ in razones],
                "pob": r.pob,
                "alquiler": r.alquiler,
                "temp": r.temp,
                "riesgo_pct": round(r.riesgo_prob * 100, 1) if r.riesgo_prob is not None else None,
                "cambio_pct": r.cambio_pct,
            }
        )
    candidatos.sort(key=lambda c: c["score"], reverse=True)
    return candidatos[:limit]


@app.get("/municipio/{cod}")
async def municipio_ficha(cod: str) -> dict:
    """Ficha completa de un municipio: identidad, wiki, serie, índice, ML, arquetipo y similares."""
    async with engine.connect() as conn:
        base = (
            await conn.execute(
                text("""
                    SELECT cod_municipio, nombre, cod_provincia, cod_ccaa, superficie_km2,
                           ST_Y(ST_Centroid(geom_4326)) AS lat,
                           ST_X(ST_Centroid(geom_4326)) AS lon
                    FROM dim_municipio WHERE cod_municipio = :cod
                """),
                {"cod": cod},
            )
        ).one_or_none()
        if base is None:
            raise HTTPException(status_code=404, detail="municipio no encontrado")

        serie = (
            await conn.execute(
                text("""
                    SELECT anio, poblacion_total, paro_media_anual,
                           renta_neta_media_persona AS renta, alquiler_eur_m2 AS alquiler,
                           temp_media_anual AS temp, precip_anual_mm AS precip,
                           pct_extranjeros
                    FROM fact_municipio_anual
                    WHERE cod_municipio = :cod
                    ORDER BY anio
                """),
                {"cod": cod},
            )
        ).all()

        indice = (
            await conn.execute(
                text("""
                    SELECT anio, score, c_renta, c_paro, c_alquiler, c_envejecimiento, c_servicios
                    FROM indice_municipio WHERE cod_municipio = :cod
                    ORDER BY anio DESC LIMIT 1
                """),
                {"cod": cod},
            )
        ).one_or_none()

        pred = (
            await conn.execute(
                text("""
                    SELECT anio_base, anio_horizonte, pob_base, pob_proyectada,
                           cambio_pct, cambio_inf, cambio_sup, drivers
                    FROM prediccion_ml WHERE cod_municipio = :cod
                """),
                {"cod": cod},
            )
        ).one_or_none()

        arq = (
            await conn.execute(
                text("""
                    SELECT cluster, etiqueta FROM arquetipo_municipio
                    WHERE cod_municipio = :cod
                """),
                {"cod": cod},
            )
        ).one_or_none()

        wiki = (
            await conn.execute(
                text("""
                    SELECT altitud, web, imagen, escudo, gentilicio,
                           wiki_titulo, descripcion, wiki_imagen
                    FROM municipio_wiki WHERE cod_municipio = :cod
                """),
                {"cod": cod},
            )
        ).one_or_none()

        serv = (
            await conn.execute(
                text("""
                    SELECT n_salud, n_educacion, n_comercio, n_total
                    FROM municipio_servicios WHERE cod_municipio = :cod
                """),
                {"cod": cod},
            )
        ).one_or_none()

        rsg = (
            await conn.execute(
                text("SELECT prob, nivel FROM riesgo_municipio WHERE cod_municipio = :cod"),
                {"cod": cod},
            )
        ).one_or_none()

        aisl = (
            await conn.execute(
                text("""
                    SELECT km_salud, km_educacion, km_capital FROM municipio_aislamiento
                    WHERE cod_municipio = :cod
                """),
                {"cod": cod},
            )
        ).one_or_none()

        conect = (
            await conn.execute(
                text("""
                    SELECT pct_fibra, pct_100mbps, pct_5g FROM municipio_conectividad
                    WHERE cod_municipio = :cod
                """),
                {"cod": cod},
            )
        ).one_or_none()

        clima_row = (
            await conn.execute(
                text("""
                    SELECT temp_media_anual AS temp, precip_anual_mm AS precip,
                           temp_max_media, temp_min_media, temp_min_abs,
                           dias_despejados, humedad_media
                    FROM fact_municipio_anual
                    WHERE cod_municipio = :cod AND temp_media_anual IS NOT NULL
                    ORDER BY anio DESC LIMIT 1
                """),
                {"cod": cod},
            )
        ).one_or_none()

        rend = (
            await conn.execute(
                text("""
                    SELECT residuo, z, clasificacion FROM rendimiento_municipio
                    WHERE cod_municipio = :cod
                """),
                {"cod": cod},
            )
        ).one_or_none()

        infl = (
            await conn.execute(
                text("""
                    SELECT anio_inflexion, pend_antes, pend_despues, tipo, magnitud
                    FROM inflexion_municipio WHERE cod_municipio = :cod
                """),
                {"cod": cod},
            )
        ).one_or_none()

        demo = (
            await conn.execute(
                text("""
                    SELECT saldo_vegetativo, saldo_migratorio, cambio_total, dominante, tipo
                    FROM demografia_municipio WHERE cod_municipio = :cod
                """),
                {"cod": cod},
            )
        ).one_or_none()

        gem = (
            await conn.execute(
                text("""
                    SELECT g.cod_gemelo, d.nombre, d.cod_provincia, g.distancia,
                           g.crec_propio, g.crec_gemelo, g.divergencia
                    FROM gemelo_municipio g
                    JOIN dim_municipio d ON d.cod_municipio = g.cod_gemelo
                    WHERE g.cod_municipio = :cod
                """),
                {"cod": cod},
            )
        ).one_or_none()

        sim_row = (
            await conn.execute(
                text("SELECT similares FROM similar_municipio WHERE cod_municipio = :cod"),
                {"cod": cod},
            )
        ).one_or_none()
        similares: list[dict] = []
        if sim_row and sim_row.similares:
            cods = [c for c in sim_row.similares.split(",") if c]
            if cods:
                nombres = (
                    await conn.execute(
                        text("""
                            SELECT cod_municipio, nombre, cod_provincia
                            FROM dim_municipio WHERE cod_municipio = ANY(:cods)
                        """),
                        {"cods": cods},
                    )
                ).all()
                by_cod = {r.cod_municipio: r for r in nombres}
                similares = [
                    {
                        "cod": c,
                        "nombre": by_cod[c].nombre,
                        "provincia": PROVINCIAS.get(by_cod[c].cod_provincia, by_cod[c].cod_provincia),
                    }
                    for c in cods
                    if c in by_cod
                ]

    return {
        "cod": base.cod_municipio,
        "nombre": base.nombre,
        "provincia": {
            "cod": base.cod_provincia,
            "nombre": PROVINCIAS.get(base.cod_provincia, base.cod_provincia),
        },
        "cod_ccaa": base.cod_ccaa,
        "superficie_km2": base.superficie_km2,
        "centroide": {"lat": base.lat, "lon": base.lon},
        "wiki": (
            {
                "descripcion": wiki.descripcion,
                "gentilicio": wiki.gentilicio,
                "altitud": wiki.altitud,
                "web": wiki.web,
                "imagen": wiki.wiki_imagen or wiki.imagen,
                "escudo": wiki.escudo,
                "wiki_titulo": wiki.wiki_titulo,
            }
            if wiki
            else None
        ),
        "serie": [
            {
                "anio": r.anio,
                "poblacion": r.poblacion_total,
                "paro": r.paro_media_anual,
                "renta": r.renta,
                "alquiler": r.alquiler,
                "temp": r.temp,
                "precip": r.precip,
                "pct_extranjeros": r.pct_extranjeros,
            }
            for r in serie
        ],
        "indice": (
            {
                "anio": indice.anio,
                "score": indice.score,
                "componentes": {
                    "renta": indice.c_renta,
                    "paro": indice.c_paro,
                    "alquiler": indice.c_alquiler,
                    "envejecimiento": indice.c_envejecimiento,
                    "servicios": indice.c_servicios,
                },
            }
            if indice
            else None
        ),
        "prediccion": (
            {
                "anio_base": pred.anio_base,
                "anio_horizonte": pred.anio_horizonte,
                "pob_base": pred.pob_base,
                "pob_proyectada": pred.pob_proyectada,
                "cambio_pct": pred.cambio_pct,
                "cambio_inf": pred.cambio_inf,
                "cambio_sup": pred.cambio_sup,
                "drivers": pred.drivers,
            }
            if pred
            else None
        ),
        "arquetipo": ({"cluster": arq.cluster, "etiqueta": arq.etiqueta} if arq else None),
        "inflexion": (
            {
                "anio": infl.anio_inflexion,
                "pend_antes": infl.pend_antes,
                "pend_despues": infl.pend_despues,
                "tipo": infl.tipo,
                "magnitud": infl.magnitud,
            }
            if infl
            else None
        ),
        "demografia": (
            {
                "saldo_vegetativo": demo.saldo_vegetativo,
                "saldo_migratorio": demo.saldo_migratorio,
                "cambio_total": demo.cambio_total,
                "dominante": demo.dominante,
                "tipo": demo.tipo,
            }
            if demo
            else None
        ),
        "rendimiento": (
            {"residuo": rend.residuo, "z": rend.z, "clasificacion": rend.clasificacion}
            if rend
            else None
        ),
        "gemelo": (
            {
                "cod": gem.cod_gemelo,
                "nombre": gem.nombre,
                "provincia": PROVINCIAS.get(gem.cod_provincia, gem.cod_provincia),
                "distancia": gem.distancia,
                "crec_propio": gem.crec_propio,
                "crec_gemelo": gem.crec_gemelo,
                "divergencia": gem.divergencia,
            }
            if gem
            else None
        ),
        "servicios": (
            {
                "salud": serv.n_salud,
                "educacion": serv.n_educacion,
                "comercio": serv.n_comercio,
                "total": serv.n_total,
            }
            if serv
            else None
        ),
        "riesgo": (
            {"prob": round(rsg.prob * 100, 1), "nivel": rsg.nivel}
            if rsg and rsg.prob is not None
            else None
        ),
        "aislamiento": (
            {"km_salud": aisl.km_salud, "km_educacion": aisl.km_educacion, "km_capital": aisl.km_capital}
            if aisl
            else None
        ),
        "conectividad": (
            {"pct_fibra": conect.pct_fibra, "pct_100mbps": conect.pct_100mbps, "pct_5g": conect.pct_5g}
            if conect
            else None
        ),
        "clima": (
            {
                "temp": clima_row.temp,
                "precip": clima_row.precip,
                "temp_max_media": clima_row.temp_max_media,
                "temp_min_media": clima_row.temp_min_media,
                "temp_min_abs": clima_row.temp_min_abs,
                "dias_despejados": clima_row.dias_despejados,
                "humedad_media": clima_row.humedad_media,
            }
            if clima_row
            else None
        ),
        "similares": similares,
    }
