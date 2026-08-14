"""Capas coropléticas del mapa.

Los endpoints con forma común se generan desde el registro declarativo de
`territorio_api.capas`. Aquí solo viven los tres que no comparten esa forma.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from sqlalchemy import text

from ..capas import GEOM, registrar
from ..db import engine

router = APIRouter(tags=["capas"])

registrar(router)


@router.get("/municipios.geojson", summary="Geometrías municipales, sin datos asociados.")
async def municipios_geojson(prov: str | None = None) -> dict:
    """Solo geometría y nombre: la capa base del mapa."""
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


@router.get("/envejecimiento.geojson", summary="Índice de envejecimiento (65+ / 0-14 × 100).")
async def envejecimiento_geojson(prov: str | None = None, anio: int | None = None) -> dict:
    """Fuera del registro: se agrega desde `fact_piramide` con una CTE propia."""
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
            SELECT d.cod_municipio, d.nombre,
                   round(a.pob_65_mas::numeric / NULLIF(a.pob_0_14, 0) * 100)::int AS indice,
                   {GEOM}
            FROM dim_municipio d
            LEFT JOIN agg a ON a.cod_municipio = d.cod_municipio
            {where}
            ORDER BY d.cod_municipio
        """)  # noqa: S608 — `where` es literal fijo, no entrada de usuario
        params: dict[str, object] = {"anio": anio}
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


@router.get("/lisa.geojson", summary="Hot spots LISA (Moran local) de una variable.")
async def lisa_geojson(var: str = "crecimiento", prov: str | None = None) -> dict:
    """Fuera del registro: filtra por variable y valida el parámetro."""
    if var not in ("crecimiento", "renta"):
        raise HTTPException(status_code=400, detail="var debe ser 'crecimiento' o 'renta'")
    where = "AND d.cod_provincia = :prov" if prov else ""
    sql = text(f"""
        SELECT d.cod_municipio, d.nombre, l.valor, l.categoria, l.p, {GEOM}
        FROM dim_municipio d
        LEFT JOIN lisa_municipio l
               ON l.cod_municipio = d.cod_municipio AND l.variable = :var
        WHERE true {where}
        ORDER BY d.cod_municipio
    """)  # noqa: S608 — `where` es literal fijo, no entrada de usuario
    params: dict[str, object] = {"var": var}
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
