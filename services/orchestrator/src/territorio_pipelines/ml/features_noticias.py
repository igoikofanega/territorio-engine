"""Features de noticias para el modelo de ML.

Cuatro variables derivadas de la cobertura de prensa local, diseñadas para capturar
señal que las variables económicas estándar no ven — con la hipótesis explícita de que
probablemente NO mejoren el modelo (ver ADR 0005 y `ablacion.py`).

**Anti-leakage.** La ventana `[T-2, T]` es estricta: las features del año base T usan
solo artículos anteriores o iguales a T. El test `test_no_fuga_temporal` lo verifica.

**`noticias_exceso`, no la cobertura bruta.** `log1p(n_noticias)` correlaciona ~0.85
con `log_pob`, que ya es una feature: el modelo solo reaprendería el tamaño. El residuo
— "¿sale este pueblo más o menos de lo que le tocaría?" — es la señal nueva. El ajuste
se hace solo con años de entrenamiento.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sqlalchemy.engine import Engine

FEATURES_NOTICIAS = [
    "noticias_exceso",
    "noticias_saldo",
    "noticias_inversion_1000",
    "noticias_cierre_1000",
]

VENTANA = 2


def _leer_noticias(engine: Engine) -> pd.DataFrame:
    """Lee la tabla de noticias anuales agregadas."""
    try:
        return pd.read_sql(
            "SELECT cod_municipio AS cod, anio, n_noticias, n_positivas, n_negativas, "
            "n_empleo, n_empresa FROM municipio_noticias_anual",
            engine,
        )
    except Exception:
        return pd.DataFrame(
            columns=[
                "cod",
                "anio",
                "n_noticias",
                "n_positivas",
                "n_negativas",
                "n_empleo",
                "n_empresa",
            ]
        )


def _agregar_ventana(noticias: pd.DataFrame, anio_base: int) -> pd.DataFrame:
    """Suma de noticias en la ventana [anio_base - VENTANA, anio_base]."""
    mascara = (noticias["anio"] >= anio_base - VENTANA) & (noticias["anio"] <= anio_base)
    return (
        noticias[mascara]
        .groupby("cod")[["n_noticias", "n_positivas", "n_negativas", "n_empleo", "n_empresa"]]
        .sum()
        .reset_index()
    )


def calcular(
    engine: Engine | None,
    anios_base: list[int],
    poblacion: pd.DataFrame,
    anios_train: list[int] | None = None,
    noticias_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Features de noticias para cada (municipio, año_base).

    `poblacion` debe tener columnas `cod`, `anio_base`, `pob`.
    `anios_train` es la lista de años de entrenamiento — el ajuste de exceso se hace
    solo con estos años para evitar leakage. Si es None, se usa todo (solo para
    predicción, cuando el ajuste viene de fuera).

    Devuelve un DataFrame con `cod`, `anio_base` y las 4 features.
    """
    if noticias_df is None:
        assert engine is not None
        noticias_df = _leer_noticias(engine)

    if noticias_df.empty:
        out = poblacion[["cod", "anio_base"]].copy()
        for f in FEATURES_NOTICIAS:
            out[f] = np.nan
        return out

    frames = []
    for t in anios_base:
        agg = _agregar_ventana(noticias_df, t)
        base = poblacion[poblacion["anio_base"] == t][["cod", "anio_base", "pob"]].merge(
            agg, on="cod", how="left"
        )
        base["n_noticias"] = base["n_noticias"].fillna(0)
        base["n_positivas"] = base["n_positivas"].fillna(0)
        base["n_negativas"] = base["n_negativas"].fillna(0)
        base["n_empleo"] = base["n_empleo"].fillna(0)
        base["n_empresa"] = base["n_empresa"].fillna(0)
        frames.append(base)

    todo = pd.concat(frames, ignore_index=True)
    log_n = np.log1p(todo["n_noticias"])
    log_pob = np.log(todo["pob"].clip(lower=1))

    if anios_train is not None:
        mask_train = todo["anio_base"].isin(anios_train)
    else:
        mask_train = pd.Series(True, index=todo.index)

    x_tr, y_tr = log_pob[mask_train].to_numpy(), log_n[mask_train].to_numpy()
    validos = np.isfinite(x_tr) & np.isfinite(y_tr) & (x_tr > 0)
    if validos.sum() > 10:
        a, b = np.polyfit(x_tr[validos], y_tr[validos], 1)
        esperado = a * log_pob + b
        todo["noticias_exceso"] = log_n - esperado
    else:
        todo["noticias_exceso"] = 0.0

    n_eventos = todo["n_positivas"] + todo["n_negativas"]
    saldo = (todo["n_positivas"] - todo["n_negativas"]) / n_eventos.replace(0, np.nan)
    todo["noticias_saldo"] = saldo.where(n_eventos >= 3, np.nan)

    pob_1000 = todo["pob"] / 1000
    todo["noticias_inversion_1000"] = todo["n_empleo"] / pob_1000.replace(0, np.nan)
    todo["noticias_cierre_1000"] = todo["n_empresa"] / pob_1000.replace(0, np.nan)

    todo.loc[todo["n_noticias"] == 0, "noticias_inversion_1000"] = 0.0
    todo.loc[todo["n_noticias"] == 0, "noticias_cierre_1000"] = 0.0

    return todo[["cod", "anio_base"] + FEATURES_NOTICIAS]
