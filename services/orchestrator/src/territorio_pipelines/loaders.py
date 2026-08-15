"""Carga de datos crudos en las tablas de PostGIS."""

from __future__ import annotations

import json
import time
from collections import defaultdict
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import httpx
import numpy as np
import pandas as pd
from pydantic import ValidationError
from sqlalchemy import text

from . import indice as idx
from . import proyeccion as proy
from . import proyeccion_cohorte as hp
from .db import engine
from .sources import (
    aemet,
    alquiler,
    fibra,
    gdelt,
    mnp,
    nacionalidad,
    osm,
    padron,
    paro,
    piramide,
    renta,
    wikidata,
    wikipedia,
)
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
    (cod_municipio, anio, score, c_renta, c_paro, c_alquiler, c_envejecimiento, c_servicios)
VALUES (:cod, :anio, :score, :c_renta, :c_paro, :c_alquiler, :c_envejecimiento, :c_servicios)
ON CONFLICT (cod_municipio, anio) DO UPDATE SET
    score = EXCLUDED.score, c_renta = EXCLUDED.c_renta, c_paro = EXCLUDED.c_paro,
    c_alquiler = EXCLUDED.c_alquiler, c_envejecimiento = EXCLUDED.c_envejecimiento,
    c_servicios = EXCLUDED.c_servicios
""")
_ANIO_INDICE = 2022  # año con cobertura de las 4 capas


def _na(v: Any) -> float | None:
    # `Any` y no `object`: v es un valor de celda de pandas, dinámico por naturaleza,
    # y `pd.isna` es la comprobación de tipo real en tiempo de ejecución.
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
    serv = pd.read_sql(
        "SELECT cod_municipio, n_total AS n_serv FROM municipio_servicios",
        engine,
    )
    df = df.merge(env, on="cod_municipio", how="left").merge(serv, on="cod_municipio", how="left")
    df["paro_1000"] = (df["paro"] / df["pob"] * 1000).replace([float("inf"), float("-inf")], None)
    df["serv_1000"] = (df["n_serv"] / df["pob"] * 1000).replace([float("inf"), float("-inf")], None)

    def pct(col: str, clave: str) -> pd.Series:
        rank = df[col].rank(pct=True) * 100
        return rank if idx.MEJOR_ALTO[clave] else 100 - rank

    df["c_renta"] = pct("renta", "renta")
    df["c_paro"] = pct("paro_1000", "paro")
    df["c_alquiler"] = pct("alquiler", "alquiler")
    df["c_envejecimiento"] = pct("envej", "envejecimiento")
    df["c_servicios"] = pct("serv_1000", "servicios")

    rows = []
    for r in df.itertuples(index=False):
        comps = {
            "renta": _na(r.c_renta),
            "paro": _na(r.c_paro),
            "alquiler": _na(r.c_alquiler),
            "envejecimiento": _na(r.c_envejecimiento),
            "servicios": _na(r.c_servicios),
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
                "c_servicios": comps["servicios"],
            }
        )
    with engine.begin() as conn:
        if rows:
            conn.execute(_INSERT_INDICE, rows)
    return {"municipios": len(rows)}


_INSERT_CLIMA = text("""
INSERT INTO fact_municipio_anual
    (cod_municipio, anio, temp_media_anual, precip_anual_mm,
     temp_max_media, temp_min_media, temp_min_abs, dias_despejados, humedad_media)
VALUES (:cod, :anio, :temp, :precip,
        :temp_max, :temp_min, :temp_min_abs, :dias_despejados, :humedad)
ON CONFLICT (cod_municipio, anio) DO UPDATE SET
    temp_media_anual = EXCLUDED.temp_media_anual, precip_anual_mm = EXCLUDED.precip_anual_mm,
    temp_max_media = EXCLUDED.temp_max_media, temp_min_media = EXCLUDED.temp_min_media,
    temp_min_abs = EXCLUDED.temp_min_abs, dias_despejados = EXCLUDED.dias_despejados,
    humedad_media = EXCLUDED.humedad_media
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
    mlon, mlat = munis["lon"].to_numpy(), munis["lat"].to_numpy()

    def interp(clave: str) -> np.ndarray:
        sval = np.array([e.get(clave) if e.get(clave) is not None else np.nan for e in ests])
        return _idw(mlon, mlat, slon, slat, sval)

    # cada variable climática interpolada por IDW desde las estaciones que la reportan
    temp = interp("tm")
    precip = interp("prec")
    tmax = interp("tm_max")
    tmin = interp("tm_min")
    tminabs = interp("ta_min")
    despej = interp("n_des")
    hum = interp("hr")

    def r1(v: float) -> float | None:
        return None if np.isnan(v) else round(float(v), 1)

    rows = []
    for i, cod in enumerate(munis["cod_municipio"]):
        celsius, mm = r1(temp[i]), (None if np.isnan(precip[i]) else round(float(precip[i])))
        fila = {
            "cod": cod,
            "anio": anio,
            "temp": celsius,
            "precip": mm,
            "temp_max": r1(tmax[i]),
            "temp_min": r1(tmin[i]),
            "temp_min_abs": r1(tminabs[i]),
            "dias_despejados": (None if np.isnan(despej[i]) else round(float(despej[i]))),
            "humedad": r1(hum[i]),
        }
        if all(v is None for k, v in fila.items() if k not in ("cod", "anio")):
            continue
        rows.append(fila)
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


_INSERT_SIMILAR = text("""
INSERT INTO similar_municipio (cod_municipio, similares)
VALUES (:cod, :similares)
ON CONFLICT (cod_municipio) DO UPDATE SET similares = EXCLUDED.similares
""")


def load_similares() -> dict:
    """Calcula y guarda los 'pueblos como el tuyo' (vecinos en features)."""
    from .ml.similares import calcular_similares

    recs = calcular_similares(engine)
    with engine.begin() as conn:
        if recs:
            conn.execute(_INSERT_SIMILAR, recs)
    return {"municipios": len(recs)}


_INSERT_RENDIMIENTO = text("""
INSERT INTO rendimiento_municipio (cod_municipio, residuo, z, n_obs, clasificacion)
VALUES (:cod, :residuo, :z, :n_obs, :clasificacion)
ON CONFLICT (cod_municipio) DO UPDATE SET
    residuo = EXCLUDED.residuo, z = EXCLUDED.z, n_obs = EXCLUDED.n_obs,
    clasificacion = EXCLUDED.clasificacion
""")


def load_rendimiento() -> dict:
    """Residuo out-of-sample del modelo por municipio → rendimiento_municipio."""
    from .ml.rendimiento import calcular_rendimiento

    recs = calcular_rendimiento(engine)
    with engine.begin() as conn:
        if recs:
            conn.execute(_INSERT_RENDIMIENTO, recs)
    return {"municipios": len(recs)}


_INSERT_GEMELO = text("""
INSERT INTO gemelo_municipio
    (cod_municipio, cod_gemelo, distancia, crec_propio, crec_gemelo, divergencia)
VALUES (:cod, :cod_gemelo, :distancia, :crec_propio, :crec_gemelo, :divergencia)
ON CONFLICT (cod_municipio) DO UPDATE SET
    cod_gemelo = EXCLUDED.cod_gemelo, distancia = EXCLUDED.distancia,
    crec_propio = EXCLUDED.crec_propio, crec_gemelo = EXCLUDED.crec_gemelo,
    divergencia = EXCLUDED.divergencia
""")


def load_gemelos() -> dict:
    """Gemelo divergente por municipio → gemelo_municipio."""
    from .ml.gemelos import calcular_gemelos

    recs = calcular_gemelos(engine)
    with engine.begin() as conn:
        if recs:
            conn.execute(_INSERT_GEMELO, recs)
    return {"municipios": len(recs)}


_INSERT_RIESGO = text("""
INSERT INTO riesgo_municipio (cod_municipio, prob, nivel)
VALUES (:cod, :prob, :nivel)
ON CONFLICT (cod_municipio) DO UPDATE SET prob = EXCLUDED.prob, nivel = EXCLUDED.nivel
""")


def load_riesgo() -> dict:
    """Semáforo de despoblación (probabilidad calibrada) → riesgo_municipio."""
    from .ml.riesgo import calcular_riesgo

    recs, metricas = calcular_riesgo(engine)
    with engine.begin() as conn:
        if recs:
            conn.execute(_INSERT_RIESGO, recs)
    return {"municipios": len(recs), **metricas}


_INSERT_INFLEXION = text("""
INSERT INTO inflexion_municipio
    (cod_municipio, anio_inflexion, pend_antes, pend_despues, tipo, magnitud)
VALUES (:cod, :anio_inflexion, :pend_antes, :pend_despues, :tipo, :magnitud)
ON CONFLICT (cod_municipio) DO UPDATE SET
    anio_inflexion = EXCLUDED.anio_inflexion, pend_antes = EXCLUDED.pend_antes,
    pend_despues = EXCLUDED.pend_despues, tipo = EXCLUDED.tipo, magnitud = EXCLUDED.magnitud
""")


_INSERT_EXTRANJEROS = text("""
INSERT INTO fact_municipio_anual (cod_municipio, anio, poblacion_extranjera, pct_extranjeros)
VALUES (:cod, :anio, :extranjera, :pct)
ON CONFLICT (cod_municipio, anio) DO UPDATE SET
    poblacion_extranjera = EXCLUDED.poblacion_extranjera,
    pct_extranjeros = EXCLUDED.pct_extranjeros
""")


_INSERT_CONECTIVIDAD = text("""
INSERT INTO municipio_conectividad (cod_municipio, pct_fibra, pct_100mbps, pct_5g)
VALUES (:cod, :pct_fibra, :pct_100mbps, :pct_5g)
ON CONFLICT (cod_municipio) DO UPDATE SET
    pct_fibra = EXCLUDED.pct_fibra, pct_100mbps = EXCLUDED.pct_100mbps, pct_5g = EXCLUDED.pct_5g
""")


def load_fibra(path: Path, batch_size: int = 5000) -> dict[str, int]:
    """Cobertura de banda ancha (SETELECO) → municipio_conectividad."""
    batch: list[dict] = []
    rows = 0
    with engine.begin() as conn:
        for rec in fibra.records(path):
            batch.append(rec)
            if len(batch) >= batch_size:
                conn.execute(_INSERT_CONECTIVIDAD, batch)
                rows += len(batch)
                batch = []
        if batch:
            conn.execute(_INSERT_CONECTIVIDAD, batch)
            rows += len(batch)
    return {"municipios": rows}


def load_nacionalidad(path: Path, batch_size: int = 5000) -> dict[str, int]:
    """Población extranjera y % por municipio·año (INE 33571) → fact_municipio_anual."""
    df = nacionalidad.parse_px(path)
    batch: list[dict] = []
    rows = 0
    with engine.begin() as conn:
        for rec in nacionalidad.records_from_df(df):
            batch.append(rec)
            if len(batch) >= batch_size:
                conn.execute(_INSERT_EXTRANJEROS, batch)
                rows += len(batch)
                batch = []
        if batch:
            conn.execute(_INSERT_EXTRANJEROS, batch)
            rows += len(batch)
    return {"filas": rows}


def load_inflexiones() -> dict:
    """Puntos de inflexión de la serie de población → inflexion_municipio."""
    from .ml.inflexion import calcular_inflexiones

    recs = calcular_inflexiones(engine)
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM inflexion_municipio"))
        if recs:
            conn.execute(_INSERT_INFLEXION, recs)
    return {"municipios": len(recs)}


_INSERT_DEMOGRAFIA = text("""
INSERT INTO demografia_municipio
    (cod_municipio, saldo_vegetativo, saldo_migratorio, cambio_total, dominante, tipo)
VALUES (:cod, :saldo_vegetativo, :saldo_migratorio, :cambio_total, :dominante, :tipo)
ON CONFLICT (cod_municipio) DO UPDATE SET
    saldo_vegetativo = EXCLUDED.saldo_vegetativo, saldo_migratorio = EXCLUDED.saldo_migratorio,
    cambio_total = EXCLUDED.cambio_total, dominante = EXCLUDED.dominante, tipo = EXCLUDED.tipo
""")


def load_demografia() -> dict:
    """Descomposición vegetativo/migratorio del cambio de población → demografia_municipio."""
    from .ml.demografia import calcular_demografia

    recs = calcular_demografia(engine)
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM demografia_municipio"))
        if recs:
            conn.execute(_INSERT_DEMOGRAFIA, recs)
    return {"municipios": len(recs)}


_INSERT_LISA = text("""
INSERT INTO lisa_municipio (cod_municipio, variable, valor, categoria, p)
VALUES (:cod, :variable, :valor, :categoria, :p)
ON CONFLICT (cod_municipio, variable) DO UPDATE SET
    valor = EXCLUDED.valor, categoria = EXCLUDED.categoria, p = EXCLUDED.p
""")


def load_lisa() -> dict[str, int]:
    """Hot spots LISA (crecimiento y renta) → lisa_municipio."""
    from .ml.lisa import calcular_lisa

    total = 0
    for variable in ("crecimiento", "renta"):
        recs = calcular_lisa(engine, variable)
        with engine.begin() as conn:
            if recs:
                conn.execute(_INSERT_LISA, recs)
        total += len(recs)
    return {"filas": total}


_INSERT_AIRE = text("""
INSERT INTO municipio_aire (cod_municipio, pm25, no2, pm10, o3)
VALUES (:cod, :pm25, :no2, :pm10, :o3)
ON CONFLICT (cod_municipio) DO UPDATE SET
    pm25 = EXCLUDED.pm25, no2 = EXCLUDED.no2, pm10 = EXCLUDED.pm10, o3 = EXCLUDED.o3
""")


def load_aire(batch_size: int = 5000) -> dict[str, int]:
    """Calidad del aire (rasters EEA muestreados en el centroide) → municipio_aire."""
    from .sources import aire

    munis = pd.read_sql(
        "SELECT cod_municipio AS cod, ST_X(ST_Centroid(geom_4326)) AS lon, "
        "ST_Y(ST_Centroid(geom_4326)) AS lat FROM dim_municipio",
        engine,
    )
    centroides = list(munis.itertuples(index=False, name=None))
    recs = list(aire.muestrear(centroides))
    with engine.begin() as conn:
        for i in range(0, len(recs), batch_size):
            conn.execute(_INSERT_AIRE, recs[i : i + batch_size])
    return {"municipios": len(recs)}


def load_aislamiento() -> dict[str, int]:
    """Distancias (km) al servicio más cercano y a la capital → municipio_aislamiento.

    Todo en PostGIS sobre geom_25830 (metros): centroides temporales con índice gist
    y búsqueda KNN (<->). 'Capital' = municipio más poblado de la provincia (proxy).
    """
    with engine.begin() as conn:
        conn.execute(
            text("""
            CREATE TEMP TABLE _cent ON COMMIT DROP AS
            SELECT d.cod_municipio, d.cod_provincia, ST_Centroid(d.geom_25830) AS pt,
                   COALESCE(s.n_salud, 0) AS n_salud,
                   COALESCE(s.n_educacion, 0) AS n_educacion
            FROM dim_municipio d
            LEFT JOIN municipio_servicios s USING (cod_municipio)
        """)
        )
        conn.execute(text("CREATE INDEX ON _cent USING gist (pt)"))
        conn.execute(
            text("""
            CREATE TEMP TABLE _cap ON COMMIT DROP AS
            SELECT DISTINCT ON (d.cod_provincia) d.cod_provincia,
                   ST_Centroid(d.geom_25830) AS pt
            FROM dim_municipio d
            JOIN fact_municipio_anual f ON f.cod_municipio = d.cod_municipio
            WHERE f.anio = (SELECT max(anio) FROM fact_municipio_anual
                            WHERE poblacion_total IS NOT NULL)
            ORDER BY d.cod_provincia, f.poblacion_total DESC
        """)
        )
        conn.execute(
            text("""
            INSERT INTO municipio_aislamiento (cod_municipio, km_salud, km_educacion, km_capital)
            SELECT c.cod_municipio,
                   round((SELECT ST_Distance(c.pt, o.pt) FROM _cent o WHERE o.n_salud > 0
                          ORDER BY c.pt <-> o.pt LIMIT 1)::numeric / 1000, 1),
                   round((SELECT ST_Distance(c.pt, o.pt) FROM _cent o WHERE o.n_educacion > 0
                          ORDER BY c.pt <-> o.pt LIMIT 1)::numeric / 1000, 1),
                   round((SELECT ST_Distance(c.pt, cap.pt) FROM _cap cap
                          WHERE cap.cod_provincia = c.cod_provincia)::numeric / 1000, 1)
            FROM _cent c
            ON CONFLICT (cod_municipio) DO UPDATE SET
                km_salud = EXCLUDED.km_salud, km_educacion = EXCLUDED.km_educacion,
                km_capital = EXCLUDED.km_capital
        """)
        )
        n = conn.execute(text("SELECT count(*) FROM municipio_aislamiento")).scalar_one()
    return {"municipios": n}


def load_osm(batch_size: int = 20000) -> dict[str, int]:
    """Descarga servicios OSM por provincia (bbox) y los cuenta por municipio (PostGIS)."""
    bboxes = pd.read_sql(
        "SELECT ST_YMin(bb) AS s, ST_XMin(bb) AS w, ST_YMax(bb) AS n, ST_XMax(bb) AS e "
        "FROM (SELECT ST_Extent(geom_4326) AS bb FROM dim_municipio GROUP BY cod_provincia) t",
        engine,
    )
    vistos: set[tuple[float, float, str]] = set()
    for b in bboxes.itertuples(index=False):
        bbox = (b.s, b.w, b.n, b.e)
        for cat, filtro in osm.CATEGORIAS.items():
            for lon, lat in osm.consultar_bbox(filtro, bbox):
                vistos.add((round(lon, 6), round(lat, 6), cat))
            time.sleep(1.0)
    puntos = [{"lon": x, "lat": y, "cat": c} for (x, y, c) in vistos]
    with engine.begin() as conn:
        conn.execute(
            text("CREATE TEMP TABLE _osm_pts (lon float8, lat float8, cat text) ON COMMIT DROP")
        )
        ins = text("INSERT INTO _osm_pts (lon, lat, cat) VALUES (:lon, :lat, :cat)")
        for i in range(0, len(puntos), batch_size):
            conn.execute(ins, puntos[i : i + batch_size])
        conn.execute(
            text("""
            INSERT INTO municipio_servicios
                (cod_municipio, n_salud, n_educacion, n_comercio, n_total)
            SELECT d.cod_municipio,
                   count(*) FILTER (WHERE p.cat = 'salud')::int,
                   count(*) FILTER (WHERE p.cat = 'educacion')::int,
                   count(*) FILTER (WHERE p.cat = 'comercio')::int,
                   count(*)::int
            FROM dim_municipio d
            JOIN _osm_pts p
              ON ST_Contains(d.geom_4326, ST_SetSRID(ST_MakePoint(p.lon, p.lat), 4326))
            GROUP BY d.cod_municipio
            ON CONFLICT (cod_municipio) DO UPDATE SET
                n_salud = EXCLUDED.n_salud, n_educacion = EXCLUDED.n_educacion,
                n_comercio = EXCLUDED.n_comercio, n_total = EXCLUDED.n_total
        """)
        )
        n = conn.execute(text("SELECT count(*) FROM municipio_servicios")).scalar_one()
    return {"municipios": n, "puntos": len(puntos)}


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


_INSERT_NOTICIA = text("""
INSERT INTO noticia_municipio
    (cod_municipio, url_sha1, url, titular, medio, fecha, idioma)
VALUES (:cod, :url_sha1, :url, :titular, :medio, :fecha, :idioma)
ON CONFLICT (cod_municipio, url_sha1) DO UPDATE SET
    titular = EXCLUDED.titular, medio = EXCLUDED.medio,
    fecha = EXCLUDED.fecha, idioma = EXCLUDED.idioma
""")

#: Ámbito de la capa de noticias: Navarra. Ver ADR 0005 — es una capa regional en un
#: proyecto nacional, y eso se marca en la interfaz en vez de disimularse.
PROVINCIA_NOTICIAS = "31"
#: Piloto: un año antiguo y uno reciente. Medir la cobertura solo con años recientes
#: daría una cifra optimista —la prensa local digitalizada crece con el tiempo— y la
#: pregunta que decide si hay ML es justamente si 2018 tiene datos.
ANIOS_PILOTO = (2018, 2024)


def load_noticias(
    cod_provincia: str = PROVINCIA_NOTICIAS,
    anios: Sequence[int] = ANIOS_PILOTO,
    raw_dir: Path = gdelt.RAW_DIR,
) -> dict:
    """Metadatos de prensa por municipio (GDELT) → noticia_municipio.

    Una consulta por `(municipio, año)`, a 5,5 s cada una. Reanudable: los ficheros
    crudos ya descargados no se vuelven a pedir, así que relanzar tras un corte continúa
    donde se quedó.
    """
    municipios = pd.read_sql(
        "SELECT cod_municipio AS cod, nombre FROM dim_municipio "
        "WHERE cod_provincia = %(prov)s ORDER BY cod_municipio",
        engine,
        params={"prov": cod_provincia},
    )
    filas = saturadas = 0
    con_articulos: set[str] = set()
    with gdelt.cliente() as client:
        for m in municipios.itertuples(index=False):
            # Una transacción por municipio, no una para toda la ingesta: son horas de
            # trabajo y dejar una transacción abierta todo ese rato es pedir problemas.
            for anio in anios:
                path = gdelt.descargar(client, m.cod, m.nombre, anio, raw_dir)
                lote = list(gdelt.articulos(path, m.cod))
                if gdelt.saturado(path):
                    saturadas += 1
                if not lote:
                    continue
                with engine.begin() as conn:
                    conn.execute(_INSERT_NOTICIA, lote)
                filas += len(lote)
                con_articulos.add(m.cod)
    return {
        "municipios_consultados": len(municipios),
        "municipios_con_articulos": len(con_articulos),
        "articulos": filas,
        "consultas_saturadas": saturadas,
        "anios": list(anios),
    }
