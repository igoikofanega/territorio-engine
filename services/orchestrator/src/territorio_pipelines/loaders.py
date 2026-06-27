"""Carga de datos crudos en las tablas de PostGIS."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError
from sqlalchemy import text

from .db import engine
from .sources import mnp, padron, piramide
from .sources.ign import feature_to_row, read_features

# Calcula la geometría 4326 una sola vez (CTE) y deriva 25830 y superficie.
_INSERT_MUNICIPIO = text("""
INSERT INTO dim_municipio
    (cod_municipio, nombre, cod_provincia, cod_ccaa, geom_4326, geom_25830, superficie_km2)
SELECT :cod, :nombre, :prov, :ccaa,
       g, ST_Transform(g, 25830), ST_Area(g::geography) / 1000000.0
FROM (SELECT ST_Multi(ST_SetSRID(ST_GeomFromGeoJSON(:geom), 4326)) AS g) s
ON CONFLICT (cod_municipio) DO UPDATE SET
    nombre = EXCLUDED.nombre,
    cod_provincia = EXCLUDED.cod_provincia,
    cod_ccaa = EXCLUDED.cod_ccaa,
    geom_4326 = EXCLUDED.geom_4326,
    geom_25830 = EXCLUDED.geom_25830,
    superficie_km2 = EXCLUDED.superficie_km2
""")


def load_municipios(path: Path) -> dict[str, int]:
    """Inserta/actualiza `dim_municipio` desde el GeoJSON. Devuelve un conteo."""
    features = read_features(path)
    seen: set[str] = set()
    inserted = skipped = 0
    with engine.begin() as conn:
        for feature in features:
            try:
                props, geom = feature_to_row(feature)
            except (ValidationError, KeyError):
                skipped += 1
                continue
            if props.mun_code in seen:
                continue
            seen.add(props.mun_code)
            conn.execute(
                _INSERT_MUNICIPIO,
                {
                    "cod": props.mun_code,
                    "nombre": props.mun_name,
                    "prov": props.mun_code[:2],
                    "ccaa": props.acom_code,
                    "geom": json.dumps(geom),
                },
            )
            inserted += 1
    return {"municipios": inserted, "descartados": skipped}


_INSERT_PADRON = text("""
INSERT INTO fact_municipio_anual
    (cod_municipio, anio, poblacion_total, poblacion_hombres, poblacion_mujeres)
VALUES (:cod, :anio, :total, :hombres, :mujeres)
ON CONFLICT (cod_municipio, anio) DO UPDATE SET
    poblacion_total = EXCLUDED.poblacion_total,
    poblacion_hombres = EXCLUDED.poblacion_hombres,
    poblacion_mujeres = EXCLUDED.poblacion_mujeres
""")


def load_padron(path: Path, batch_size: int = 5000) -> dict[str, int]:
    """Carga población (2015→) en `fact_municipio_anual` desde el `.px` del INE."""
    df = padron.parse_px(path)
    batch: list[dict] = []
    rows = 0
    with engine.begin() as conn:
        for rec in padron.records_from_df(df):
            batch.append(rec)
            if len(batch) >= batch_size:
                conn.execute(_INSERT_PADRON, batch)
                rows += len(batch)
                batch = []
        if batch:
            conn.execute(_INSERT_PADRON, batch)
            rows += len(batch)
    return {"filas": rows}


_INSERT_PIRAMIDE = text("""
INSERT INTO fact_piramide (cod_municipio, anio, sexo, edad_min, poblacion)
VALUES (:cod, :anio, :sexo, :edad_min, :poblacion)
ON CONFLICT (cod_municipio, anio, sexo, edad_min) DO UPDATE SET
    poblacion = EXCLUDED.poblacion
""")


def load_piramide(provincias: list[str] | None = None, log=None) -> dict[str, int]:
    """Carga la pirámide en `fact_piramide` iterando provincia a provincia.

    `provincias` = None procesa las 52; pasar una lista (p. ej. ["34"]) para pruebas.
    """
    provs = sorted(provincias or piramide.PROV_TABLA)
    total = 0
    with engine.begin() as conn:
        for prov in provs:
            path = piramide.download_provincia(prov)
            batch = [
                {
                    "cod": r["cod"],
                    "anio": r["anio"],
                    "sexo": r["sexo"],
                    "edad_min": r["edad_min"],
                    "poblacion": r["poblacion"],
                }
                for r in piramide.records_from_df(piramide.parse_px(path))
            ]
            if batch:
                conn.execute(_INSERT_PIRAMIDE, batch)
                total += len(batch)
            if log:
                log(f"  provincia {prov}: {len(batch)} filas")
    return {"provincias": len(provs), "filas": total}


_INSERT_MNP = text("""
INSERT INTO fact_provincia_anual (cod_provincia, anio, tasa_natalidad, tasa_mortalidad)
VALUES (:cod_provincia, :anio, :tasa_natalidad, :tasa_mortalidad)
ON CONFLICT (cod_provincia, anio) DO UPDATE SET
    tasa_natalidad = EXCLUDED.tasa_natalidad,
    tasa_mortalidad = EXCLUDED.tasa_mortalidad
""")


def load_mnp() -> dict[str, int]:
    """Carga tasas vitales provinciales (natalidad + mortalidad) en fact_provincia_anual."""
    nat = mnp.parse_px(mnp.download(mnp.TABLA_NATALIDAD))
    mort = mnp.parse_px(mnp.download(mnp.TABLA_MORTALIDAD))
    recs = list(mnp.records_from_dfs(nat, mort))
    with engine.begin() as conn:
        if recs:
            conn.execute(_INSERT_MNP, recs)
    return {"filas": len(recs)}
