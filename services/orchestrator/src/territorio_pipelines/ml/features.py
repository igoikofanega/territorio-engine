"""Construcción del dataset de ML (features + target) desde la matriz municipal.

Para cada municipio y año base T se arma un vector de features (demografía, economía,
vivienda, clima, tasas provinciales, tendencia reciente) y el target = variación % de
población de T a T+horizonte. Sirve tanto para entrenar/validar (filas con target) como
para predecir el futuro (año base reciente, target NaN). Los huecos se dejan como NaN:
el gradient boosting de histograma (HistGradientBoosting) los maneja de forma nativa.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sqlalchemy.engine import Engine

from .. import calendario as cal

# Features que entran al modelo (el orden no importa; se referencian por nombre).
FEATURES = [
    "log_pob",
    "densidad",
    "paro_1000",
    "renta",
    "alquiler",
    "envejecimiento",
    "temp",
    "precip",
    "tasa_natalidad",
    "tasa_mortalidad",
    "crec_prev3",
    "km_salud",
    "km_capital",
    "dias_despejados",
    "temp_min_media",
    "pct_extranjeros",
    "pct_fibra",
]
TARGET = "target"
HORIZONTE = 5


def _leer(engine: Engine) -> dict[str, pd.DataFrame]:
    fma = pd.read_sql(
        "SELECT cod_municipio AS cod, anio, poblacion_total AS pob, paro_media_anual AS paro, "
        "renta_neta_media_persona AS renta, alquiler_eur_m2 AS alquiler "
        "FROM fact_municipio_anual",
        engine,
    )
    dim = pd.read_sql(
        "SELECT cod_municipio AS cod, cod_provincia, superficie_km2 FROM dim_municipio", engine
    )
    env = pd.read_sql(
        "SELECT cod_municipio AS cod, anio, "
        "sum(poblacion) FILTER (WHERE edad_min >= 65)::float "
        "/ NULLIF(sum(poblacion) FILTER (WHERE edad_min < 15), 0) * 100 AS envejecimiento "
        "FROM fact_piramide GROUP BY cod_municipio, anio",
        engine,
    )
    prov = pd.read_sql(
        "SELECT cod_provincia, anio, tasa_natalidad, tasa_mortalidad FROM fact_provincia_anual",
        engine,
    )
    # clima y % extranjeros se tratan como atributos casi-estáticos del municipio (se toma
    # el valor más reciente disponible y se aplica a todos los años base, como ya se hacía
    # con temp/precip). Así el modelo puede usarlos también en el año de predicción.
    # El clima se guarda como una normal climática en un único año (AEMET no publica
    # serie anual municipal), así que hay que preguntar cuál es en vez de fijarlo.
    anio_clima = cal.ultimo_anio(engine, "temp_media_anual")
    clima = pd.read_sql(
        "SELECT cod_municipio AS cod, temp_media_anual AS temp, precip_anual_mm AS precip, "
        "dias_despejados, temp_min_media FROM fact_municipio_anual WHERE anio = %(anio)s",
        engine,
        params={"anio": anio_clima},
    )
    ext = pd.read_sql(
        "SELECT DISTINCT ON (cod_municipio) cod_municipio AS cod, pct_extranjeros "
        "FROM fact_municipio_anual WHERE pct_extranjeros IS NOT NULL "
        "ORDER BY cod_municipio, anio DESC",
        engine,
    )
    try:
        aisl = pd.read_sql(
            "SELECT cod_municipio AS cod, km_salud, km_capital FROM municipio_aislamiento",
            engine,
        )
    except Exception:  # tabla aún no creada/cargada: features quedarán NaN
        aisl = pd.DataFrame(columns=["cod", "km_salud", "km_capital"])
    try:
        fib = pd.read_sql(
            "SELECT cod_municipio AS cod, pct_fibra FROM municipio_conectividad", engine
        )
    except Exception:
        fib = pd.DataFrame(columns=["cod", "pct_fibra"])
    return {
        "fma": fma,
        "dim": dim,
        "env": env,
        "prov": prov,
        "clima": clima,
        "aisl": aisl,
        "ext": ext,
        "fib": fib,
    }


def construir_dataset(
    engine: Engine, anios_base: list[int], horizonte: int = HORIZONTE
) -> pd.DataFrame:
    """DataFrame con FEATURES + TARGET por (municipio, año base)."""
    d = _leer(engine)
    fma, dim, env, prov, clima, aisl, ext, fib = (
        d["fma"],
        d["dim"],
        d["env"],
        d["prov"],
        d["clima"],
        d["aisl"],
        d["ext"],
        d["fib"],
    )
    pop_wide = fma.pivot_table(index="cod", columns="anio", values="pob")

    frames = []
    for t in anios_base:
        base = fma[fma["anio"] == t][["cod", "pob", "paro", "renta", "alquiler"]].copy()
        base = base.merge(dim, on="cod", how="left")
        base["densidad"] = base["pob"] / base["superficie_km2"]
        base["paro_1000"] = base["paro"] / base["pob"] * 1000
        base["log_pob"] = np.log(base["pob"].clip(lower=1))
        base = base.merge(env[env["anio"] == t][["cod", "envejecimiento"]], on="cod", how="left")
        base = base.merge(clima, on="cod", how="left")
        base = base.merge(aisl, on="cod", how="left")
        base = base.merge(ext, on="cod", how="left")
        base = base.merge(fib, on="cod", how="left")
        pr = prov[prov["anio"] == t][["cod_provincia", "tasa_natalidad", "tasa_mortalidad"]]
        base = base.merge(pr, on="cod_provincia", how="left")

        if t - 3 in pop_wide.columns:
            crec = (pop_wide[t] / pop_wide[t - 3]).rename("crec_prev3").reset_index()
            base = base.merge(crec, on="cod", how="left")
        else:
            base["crec_prev3"] = np.nan

        if t + horizonte in pop_wide.columns:
            tgt = ((pop_wide[t + horizonte] / pop_wide[t] - 1) * 100).rename(TARGET).reset_index()
            base = base.merge(tgt, on="cod", how="left")
        else:
            base[TARGET] = np.nan

        base["anio_base"] = t
        frames.append(base)

    return pd.concat(frames, ignore_index=True)
