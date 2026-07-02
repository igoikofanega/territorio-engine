"""Carga de datos crudos en las tablas de PostGIS."""

from __future__ import annotations

import json
import time
from collections import defaultdict
from pathlib import Path

import httpx
import numpy as np
import pandas as pd
from pydantic import ValidationError
from sqlalchemy import text

from . import indice as idx
from . import proyeccion as proy
from . import proyeccion_cohorte as hp
from .db import engine
from .sources import aemet, alquiler, mnp, padron, paro, piramide, renta, wikidata, wikipedia
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


_INSERT_RENTA = text("""
INSERT INTO fact_municipio_anual (cod_municipio, anio, renta_neta_media_persona)
VALUES (:cod, :anio, :renta)
ON CONFLICT (cod_municipio, anio) DO UPDATE SET
    renta_neta_media_persona = EXCLUDED.renta_neta_media_persona
""")


def load_renta(provincias: list[str] | None = None) -> dict[str, int]:
    """Carga la renta neta media por persona iterando provincia a provincia (ADRH)."""
    provs = sorted(provincias or renta.PROV_TABLA)
    rows = 0
    with engine.begin() as conn:
        for prov in provs:
            batch = list(renta.records_from_df(renta.parse_px(renta.download_provincia(prov))))
            if batch:
                conn.execute(_INSERT_RENTA, batch)
                rows += len(batch)
    return {"provincias": len(provs), "filas": rows}


_INSERT_ALQUILER = text("""
INSERT INTO fact_municipio_anual (cod_municipio, anio, alquiler_eur_m2)
VALUES (:cod, :anio, :alquiler)
ON CONFLICT (cod_municipio, anio) DO UPDATE SET alquiler_eur_m2 = EXCLUDED.alquiler_eur_m2
""")


def load_alquiler() -> dict[str, int]:
    """Carga el alquiler medio €/m² (SERPAVI, nacional) en fact_municipio_anual."""
    df = alquiler.parse_excel(alquiler.download())
    batch = list(alquiler.records_from_df(df))
    with engine.begin() as conn:
        if batch:
            conn.execute(_INSERT_ALQUILER, batch)
    return {"filas": len(batch)}


_INSERT_INDICE = text("""
INSERT INTO indice_municipio
    (cod_municipio, anio, score, c_renta, c_paro, c_alquiler, c_envejecimiento)
VALUES (:cod, :anio, :score, :c_renta, :c_paro, :c_alquiler, :c_envejecimiento)
ON CONFLICT (cod_municipio, anio) DO UPDATE SET
    score = EXCLUDED.score, c_renta = EXCLUDED.c_renta, c_paro = EXCLUDED.c_paro,
    c_alquiler = EXCLUDED.c_alquiler, c_envejecimiento = EXCLUDED.c_envejecimiento
""")
_ANIO_INDICE = 2022  # año con cobertura de las 4 capas


def _na(v: object) -> float | None:
    return None if pd.isna(v) else round(float(v), 1)


def load_indice(anio: int = _ANIO_INDICE) -> dict[str, int]:
    """Calcula el índice "¿dónde vivir?" (percentiles ponderados) → indice_municipio."""
    df = pd.read_sql(
        "SELECT cod_municipio, renta_neta_media_persona AS renta, alquiler_eur_m2 AS alquiler, "
        f"paro_media_anual AS paro, poblacion_total AS pob "
        f"FROM fact_municipio_anual WHERE anio = {anio}",
        engine,
    )
    env = pd.read_sql(
        "SELECT cod_municipio, sum(poblacion) FILTER (WHERE edad_min >= 65)::float "
        "/ NULLIF(sum(poblacion) FILTER (WHERE edad_min < 15), 0) * 100 AS envej "
        f"FROM fact_piramide WHERE anio = {anio} GROUP BY cod_municipio",
        engine,
    )
    df = df.merge(env, on="cod_municipio", how="left")
    df["paro_1000"] = (df["paro"] / df["pob"] * 1000).replace([float("inf"), float("-inf")], None)

    def pct(col: str, clave: str) -> pd.Series:
        rank = df[col].rank(pct=True) * 100
        return rank if idx.MEJOR_ALTO[clave] else 100 - rank

    df["c_renta"] = pct("renta", "renta")
    df["c_paro"] = pct("paro_1000", "paro")
    df["c_alquiler"] = pct("alquiler", "alquiler")
    df["c_envejecimiento"] = pct("envej", "envejecimiento")

    rows = []
    for r in df.itertuples(index=False):
        comps = {
            "renta": _na(r.c_renta),
            "paro": _na(r.c_paro),
            "alquiler": _na(r.c_alquiler),
            "envejecimiento": _na(r.c_envejecimiento),
        }
        score = idx.combina(comps)
        if score is None:
            continue
        rows.append(
            {
                "cod": r.cod_municipio,
                "anio": anio,
                "score": score,
                "c_renta": comps["renta"],
                "c_paro": comps["paro"],
                "c_alquiler": comps["alquiler"],
                "c_envejecimiento": comps["envejecimiento"],
            }
        )
    with engine.begin() as conn:
        if rows:
            conn.execute(_INSERT_INDICE, rows)
    return {"municipios": len(rows)}


_INSERT_CLIMA = text("""
INSERT INTO fact_municipio_anual (cod_municipio, anio, temp_media_anual, precip_anual_mm)
VALUES (:cod, :anio, :temp, :precip)
ON CONFLICT (cod_municipio, anio) DO UPDATE SET
    temp_media_anual = EXCLUDED.temp_media_anual, precip_anual_mm = EXCLUDED.precip_anual_mm
""")
_ANIO_CLIMA = 2022  # normal reciente (media 2015-2024) almacenada en el año del índice


def _idw(mlon, mlat, slon, slat, sval, k: int = 3) -> np.ndarray:
    """Interpolación IDW de las k estaciones más cercanas (distancia en grados, k=3)."""
    mask = ~np.isnan(sval)
    slon, slat, sval = slon[mask], slat[mask], sval[mask]
    d2 = (mlon[:, None] - slon[None, :]) ** 2 + (mlat[:, None] - slat[None, :]) ** 2 + 1e-9
    kk = min(k, len(sval))
    idx_k = np.argpartition(d2, kk - 1, axis=1)[:, :kk]
    filas = np.arange(len(mlon))[:, None]
    w = 1.0 / d2[filas, idx_k]
    return (w * sval[idx_k]).sum(1) / w.sum(1)


def load_clima(anio: int = _ANIO_CLIMA) -> dict[str, int]:
    """Descarga el clima por estación (AEMET) e interpola a municipio (IDW)."""
    with aemet.cliente() as client:
        ests = [
            {**e, **c}
            for e in aemet.estaciones(client)
            if (c := aemet.clima_estacion(client, e["indicativo"])) is not None
        ]
    if not ests:
        return {"municipios": 0, "estaciones": 0}
    munis = pd.read_sql(
        "SELECT cod_municipio, ST_X(ST_Centroid(geom_4326)) AS lon, "
        "ST_Y(ST_Centroid(geom_4326)) AS lat FROM dim_municipio",
        engine,
    )
    slon = np.array([e["lon"] for e in ests])
    slat = np.array([e["lat"] for e in ests])
    stemp = np.array([e["tm"] if e["tm"] is not None else np.nan for e in ests])
    sprec = np.array([e["prec"] if e["prec"] is not None else np.nan for e in ests])
    mlon, mlat = munis["lon"].to_numpy(), munis["lat"].to_numpy()

    temp = _idw(mlon, mlat, slon, slat, stemp)
    precip = _idw(mlon, mlat, slon, slat, sprec)
    rows = []
    for cod, t, p in zip(munis["cod_municipio"], temp, precip, strict=False):
        celsius = None if np.isnan(t) else round(float(t), 1)
        mm = None if np.isnan(p) else round(float(p))
        if celsius is None and mm is None:
            continue
        rows.append({"cod": cod, "anio": anio, "temp": celsius, "precip": mm})
    with engine.begin() as conn:
        if rows:
            conn.execute(_INSERT_CLIMA, rows)
    return {"municipios": len(rows), "estaciones": len(ests)}


_INSERT_PREDICCION_ML = text("""
INSERT INTO prediccion_ml
    (cod_municipio, anio_base, anio_horizonte, pob_base, pob_proyectada,
     cambio_pct, cambio_inf, cambio_sup, drivers)
VALUES (:cod, :anio_base, :anio_horizonte, :pob_base, :pob_proyectada,
        :cambio_pct, :cambio_inf, :cambio_sup, :drivers)
ON CONFLICT (cod_municipio) DO UPDATE SET
    anio_base = EXCLUDED.anio_base, anio_horizonte = EXCLUDED.anio_horizonte,
    pob_base = EXCLUDED.pob_base, pob_proyectada = EXCLUDED.pob_proyectada,
    cambio_pct = EXCLUDED.cambio_pct, cambio_inf = EXCLUDED.cambio_inf,
    cambio_sup = EXCLUDED.cambio_sup, drivers = EXCLUDED.drivers
""")


def load_prediccion_ml() -> dict:
    """Entrena el modelo ML, predice el futuro y guarda las predicciones. Devuelve métricas."""
    from .ml.modelo import entrenar_y_predecir

    pred, metrics = entrenar_y_predecir(engine)
    recs = [
        {
            "cod": r.cod,
            "anio_base": int(r.anio_base),
            "anio_horizonte": int(r.anio_horizonte),
            "pob_base": int(r.pob_base),
            "pob_proyectada": None if pd.isna(r.pob_proyectada) else int(r.pob_proyectada),
            "cambio_pct": float(r.cambio_pct),
            "cambio_inf": float(r.cambio_inf),
            "cambio_sup": float(r.cambio_sup),
            "drivers": r.drivers,
        }
        for r in pred.itertuples(index=False)
    ]
    with engine.begin() as conn:
        if recs:
            conn.execute(_INSERT_PREDICCION_ML, recs)
    return {"municipios": len(recs), "mae": round(metrics["mae"], 2), "r2": round(metrics["r2"], 3)}


_INSERT_ARQUETIPO = text("""
INSERT INTO arquetipo_municipio (cod_municipio, cluster, etiqueta)
VALUES (:cod, :cluster, :etiqueta)
ON CONFLICT (cod_municipio) DO UPDATE SET
    cluster = EXCLUDED.cluster, etiqueta = EXCLUDED.etiqueta
""")


def load_arquetipos() -> dict:
    """Agrupa los municipios en arquetipos (KMeans) y los guarda. Devuelve métricas."""
    from .ml.clustering import entrenar_clusters

    out, metrics = entrenar_clusters(engine)
    recs = [
        {"cod": r.cod, "cluster": int(r.cluster), "etiqueta": r.etiqueta}
        for r in out.itertuples(index=False)
    ]
    with engine.begin() as conn:
        if recs:
            conn.execute(_INSERT_ARQUETIPO, recs)
    return {"municipios": len(recs), **metrics}


_INSERT_WIKIDATA = text("""
INSERT INTO municipio_wiki
    (cod_municipio, altitud, web, imagen, escudo, gentilicio, wiki_titulo)
VALUES (:cod, :altitud, :web, :imagen, :escudo, :gentilicio, :wiki_titulo)
ON CONFLICT (cod_municipio) DO UPDATE SET
    altitud = EXCLUDED.altitud, web = EXCLUDED.web, imagen = EXCLUDED.imagen,
    escudo = EXCLUDED.escudo, gentilicio = EXCLUDED.gentilicio,
    wiki_titulo = EXCLUDED.wiki_titulo
""")


def load_wikidata() -> dict:
    """Carga hechos de Wikidata por municipio (no toca descripcion/wiki_imagen)."""
    recs = list(wikidata.records_from_bindings(wikidata.descargar()))
    with engine.begin() as conn:
        if recs:
            conn.execute(_INSERT_WIKIDATA, recs)
    return {"municipios": len(recs)}


_UPDATE_WIKIPEDIA = text("""
UPDATE municipio_wiki SET descripcion = :desc, wiki_imagen = :img WHERE cod_municipio = :cod
""")


def load_wikipedia() -> dict:
    """Rellena descripcion + wiki_imagen en municipio_wiki desde la REST API de Wikipedia."""
    titulos = pd.read_sql(
        "SELECT cod_municipio AS cod, wiki_titulo FROM municipio_wiki "
        "WHERE wiki_titulo IS NOT NULL",
        engine,
    )
    updates = []
    with httpx.Client(timeout=30, follow_redirects=True) as client:
        for r in titulos.itertuples(index=False):
            res = wikipedia.resumen(client, r.wiki_titulo)
            if res and res.get("descripcion"):
                updates.append({"cod": r.cod, "desc": res["descripcion"], "img": res.get("imagen")})
            time.sleep(wikipedia.THROTTLE_S)
    with engine.begin() as conn:
        if updates:
            conn.execute(_UPDATE_WIKIPEDIA, updates)
    return {"municipios": len(updates)}


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
