"""Carga de datos crudos en las tablas de PostGIS."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import pandas as pd
from pydantic import ValidationError
from sqlalchemy import text

from . import proyeccion as proy
from . import proyeccion_cohorte as hp
from .db import engine
from .sources import mnp, padron, paro, piramide
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


_INSERT_PARO = text("""
INSERT INTO fact_municipio_anual (cod_municipio, anio, paro_media_anual)
VALUES (:cod, :anio, :paro)
ON CONFLICT (cod_municipio, anio) DO UPDATE SET paro_media_anual = EXCLUDED.paro_media_anual
""")


def load_paro(anios: list[int] | None = None) -> dict[str, int]:
    """Carga el paro registrado (media anual) en fact_municipio_anual. Fuente nacional."""
    years = anios if anios is not None else list(paro.anios_disponibles())
    rows = 0
    with engine.begin() as conn:
        for anio in years:
            path = paro.download(anio)
            if path is None:
                continue
            batch = list(paro.records_from_df(paro.parse_csv(path)))
            if batch:
                conn.execute(_INSERT_PARO, batch)
                rows += len(batch)
    return {"filas": rows}


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


_INSERT_PROY = text("""
INSERT INTO proyeccion_municipio
    (cod_municipio, anio_base, pob_base, cagr, anio_horizonte, pob_proyectada,
     cambio_pct, trayectoria)
VALUES (:cod_municipio, :anio_base, :pob_base, :cagr, :anio_horizonte,
        :pob_proyectada, :cambio_pct, :trayectoria)
ON CONFLICT (cod_municipio) DO UPDATE SET
    anio_base = EXCLUDED.anio_base, pob_base = EXCLUDED.pob_base, cagr = EXCLUDED.cagr,
    anio_horizonte = EXCLUDED.anio_horizonte, pob_proyectada = EXCLUDED.pob_proyectada,
    cambio_pct = EXCLUDED.cambio_pct, trayectoria = EXCLUDED.trayectoria
""")


def load_proyeccion(horizonte: int = proy.HORIZONTE) -> dict[str, int]:
    """Ajusta la proyección de cada municipio desde fact_municipio_anual y la guarda."""
    df = pd.read_sql(
        "SELECT cod_municipio, anio, poblacion_total FROM fact_municipio_anual", engine
    )
    rows = []
    for cod, g in df.groupby("cod_municipio"):
        fit = proy.proyecta(g["anio"].tolist(), g["poblacion_total"].tolist(), horizonte)
        if fit:
            rows.append({"cod_municipio": cod, **fit})
    with engine.begin() as conn:
        if rows:
            conn.execute(_INSERT_PROY, rows)
    return {"municipios": len(rows)}


_INSERT_PROY_COHORTE = text("""
INSERT INTO proyeccion_cohorte
    (cod_municipio, anio_base, pob_base, anio_horizonte, pob_proyectada, cambio_pct, trayectoria)
VALUES (:cod_municipio, :anio_base, :pob_base, :anio_horizonte, :pob_proyectada,
        :cambio_pct, :trayectoria)
ON CONFLICT (cod_municipio) DO UPDATE SET
    anio_base = EXCLUDED.anio_base, pob_base = EXCLUDED.pob_base,
    anio_horizonte = EXCLUDED.anio_horizonte, pob_proyectada = EXCLUDED.pob_proyectada,
    cambio_pct = EXCLUDED.cambio_pct, trayectoria = EXCLUDED.trayectoria
""")

_T0, _T1, _PASOS = 2017, 2022, 3  # 2022 + 5×3 = 2037
_HORIZONTE = _T1 + 5 * _PASOS
_MIN_DENOM = 25.0  # bajo este umbral usamos la media provincial (borrow strength)


def load_proyeccion_cohorte() -> dict[str, int]:
    """Proyección cohorte-componente (Hamilton-Perry) sobre los municipios con pirámide.

    Solo cubre las provincias cuya pirámide esté cargada. CCR/CWR municipales con
    respaldo provincial agregado para municipios pequeños.
    """
    df = pd.read_sql(
        f"SELECT cod_municipio, anio, sexo, edad_min, poblacion "
        f"FROM fact_piramide WHERE anio IN ({_T0}, {_T1})",
        engine,
    )
    pir: dict[tuple[str, int], dict] = defaultdict(dict)
    for r in df.itertuples(index=False):
        pir[(r.cod_municipio, r.anio)][(r.sexo, r.edad_min)] = float(r.poblacion)

    # Agregados provinciales para el respaldo (pooling)
    ccr_num: dict = defaultdict(float)
    ccr_den: dict = defaultdict(float)
    cwr_kids: dict = defaultdict(float)
    cwr_fert: dict = defaultdict(float)
    for (cod, anio), p in pir.items():
        prov = cod[:2]
        for sexo in ("H", "M"):
            for e in hp.EDADES[:-1]:
                if anio == _T0:
                    ccr_den[(prov, sexo, e)] += p.get((sexo, e), 0.0)
                else:
                    ccr_num[(prov, sexo, e)] += p.get((sexo, e + 5), 0.0)
        if anio == _T1:
            for sexo in ("H", "M"):
                cwr_kids[(prov, sexo)] += p.get((sexo, 0), 0.0)
            cwr_fert[prov] += sum(p.get(("M", e), 0.0) for e in hp.MUJERES_FERTILES)

    rows = []
    for cod in {c for c, _ in pir}:
        p0, p1 = pir.get((cod, _T0)), pir.get((cod, _T1))
        if not p0 or not p1:
            continue
        prov = cod[:2]
        ccrs = {}
        for sexo in ("H", "M"):
            for e in hp.EDADES[:-1]:
                if p0.get((sexo, e), 0.0) >= _MIN_DENOM:
                    ccrs[(sexo, e)] = hp.ccr(p0, p1, sexo, e)
                else:
                    den = ccr_den[(prov, sexo, e)]
                    ccrs[(sexo, e)] = (
                        min(ccr_num[(prov, sexo, e)] / den, hp.CAP_CCR) if den else None
                    )
        fert = sum(p1.get(("M", e), 0.0) for e in hp.MUJERES_FERTILES)
        cwrs = {}
        for sexo in ("H", "M"):
            if fert >= _MIN_DENOM:
                cwrs[sexo] = hp.cwr(p1, sexo)
            else:
                cwrs[sexo] = cwr_kids[(prov, sexo)] / cwr_fert[prov] if cwr_fert[prov] else 0.0

        pob_base = int(round(hp.total(p1)))
        if pob_base <= 0:
            continue
        pob_proy = int(round(hp.total(hp.proyecta(p1, ccrs, cwrs, _PASOS))))
        cambio = (pob_proy / pob_base - 1) * 100
        rows.append(
            {
                "cod_municipio": cod,
                "anio_base": _T1,
                "pob_base": pob_base,
                "anio_horizonte": _HORIZONTE,
                "pob_proyectada": pob_proy,
                "cambio_pct": round(cambio, 1),
                "trayectoria": proy.clasifica(cambio, pob_proy),
            }
        )
    with engine.begin() as conn:
        if rows:
            conn.execute(_INSERT_PROY_COHORTE, rows)
    return {"municipios": len(rows)}
