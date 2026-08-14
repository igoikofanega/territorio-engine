"""Modelo predictivo de variación de población + backtest temporal (con MLflow).

Gradient boosting (HistGradientBoosting) que predice el cambio % de población a 5 años
desde las features del municipio. Se valida con un corte TEMPORAL (entreno con años base
antiguos, valido con los recientes cuyo futuro ya se conoce) y se compara con dos
baselines honestos: persistencia (0% de cambio) y tendencia (extrapolar el crecimiento
reciente). Todo se registra en MLflow.
"""

from __future__ import annotations

import mlflow
import mlflow.sklearn
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.inspection import permutation_importance
from sklearn.metrics import mean_absolute_error, r2_score
from sqlalchemy.engine import Engine

from .. import calendario as cal
from .features import FEATURES, TARGET, construir_dataset

HORIZONTE = 5
EXPERIMENTO = "vaciamiento"

# Columnas que el año base de la predicción debe tener cubiertas a la vez. No basta con
# el último año de población: sin renta ni paro, el vector de features iría medio vacío.
COLUMNAS_PRED = ["poblacion_total", "paro_media_anual", "renta_neta_media_persona"]

# etiqueta corta de cada feature para los "drivers" del tooltip
ETIQUETAS = {
    "log_pob": "tamaño",
    "densidad": "densidad",
    "paro_1000": "paro",
    "renta": "renta",
    "alquiler": "alquiler",
    "envejecimiento": "envejec.",
    "temp": "temp.",
    "precip": "lluvia",
    "tasa_natalidad": "natalidad",
    "tasa_mortalidad": "mortalidad",
    "crec_prev3": "tendencia",
    "km_salud": "sanidad lejos",
    "km_capital": "lejanía",
    "dias_despejados": "sol",
    "temp_min_media": "frío",
    "pct_extranjeros": "inmigración",
    "pct_fibra": "fibra",
}


def nuevo_modelo(loss: str = "squared_error", quantile: float | None = None):
    return HistGradientBoostingRegressor(
        loss=loss,
        quantile=quantile,
        max_iter=400,
        learning_rate=0.05,
        max_leaf_nodes=31,
        l2_regularization=1.0,
        random_state=0,
    )


def _tendencia(crec_prev3: np.ndarray, horizonte: int = 5) -> np.ndarray:
    """Baseline: extrapola el crecimiento trienal a `horizonte` años (%)."""
    r = np.where(np.isnan(crec_prev3), 1.0, crec_prev3)
    return (r ** (horizonte / 3) - 1) * 100


def _signo_correlacion(df) -> dict[str, float]:
    """Signo de la correlación de cada feature con el target (para orientar drivers)."""
    signos = {}
    y = df[TARGET]
    for f in FEATURES:
        x = df[f].fillna(df[f].median())
        c = np.corrcoef(x, y)[0, 1]
        signos[f] = 1.0 if (np.isnan(c) or c >= 0) else -1.0
    return signos


def _drivers(xp, importancia: dict, signo: dict) -> list[str]:
    """Por municipio, los 2 factores más determinantes (heurístico honesto, no causal)."""
    med = xp.median()
    iqr = (xp.quantile(0.75) - xp.quantile(0.25)).replace(0, 1.0)
    peso = pd.Series({f: importancia.get(f, 0.0) * signo[f] for f in FEATURES})
    contrib = ((xp[FEATURES] - med) / iqr) * peso
    salida = []
    for i in contrib.index:
        top = contrib.loc[i].abs().nlargest(2).index
        salida.append(
            " · ".join(f"{ETIQUETAS[f]}{'↑' if xp.loc[i, f] >= med[f] else '↓'}" for f in top)
        )
    return salida


def entrenar_y_predecir(engine: Engine) -> tuple[pd.DataFrame, dict]:
    """Backtest + entrenamiento final + predicción de futuro con drivers.

    Los años salen de la cobertura real de los datos (ver `calendario`), no fijados en
    el código: el corte es temporal y la ventana se desplaza sola cuando entra un año
    nuevo. Registra métricas, importancia y el modelo (Model Registry) en MLflow.
    Devuelve (predicciones, métricas).
    """
    anios_base, anios_train, anios_val = cal.anios_backtest(engine, HORIZONTE)
    if not anios_val:
        raise RuntimeError(
            f"no hay años suficientes para un backtest a {HORIZONTE} años "
            f"(base disponible: {anios_base})"
        )
    anio_pred = cal.ultimo_anio_comun(engine, COLUMNAS_PRED)
    if anio_pred is None:
        raise RuntimeError(f"ningún año cubre a la vez {COLUMNAS_PRED}")

    df = construir_dataset(engine, anios_base)
    df = df[df[TARGET].notna()]
    tr = df[df["anio_base"].isin(anios_train)]
    va = df[df["anio_base"].isin(anios_val)]

    # --- backtest temporal + baselines ---
    mb = nuevo_modelo()
    mb.fit(tr[FEATURES], tr[TARGET])
    yva = va[TARGET].to_numpy()
    pv = mb.predict(va[FEATURES])
    metrics = {
        "mae": float(mean_absolute_error(yva, pv)),
        "r2": float(r2_score(yva, pv)),
        "mae_persistencia": float(mean_absolute_error(yva, np.zeros_like(yva))),
        "mae_tendencia": float(mean_absolute_error(yva, _tendencia(va["crec_prev3"].to_numpy()))),
    }
    imp = permutation_importance(mb, va[FEATURES], yva, n_repeats=5, random_state=0)
    importancia = {f: float(v) for f, v in zip(FEATURES, imp.importances_mean, strict=False)}

    # --- modelos finales (punto + banda de incertidumbre 10-90) sobre todos los datos ---
    punto = nuevo_modelo()
    punto.fit(df[FEATURES], df[TARGET])
    q10 = nuevo_modelo(loss="quantile", quantile=0.1)
    q10.fit(df[FEATURES], df[TARGET])
    q90 = nuevo_modelo(loss="quantile", quantile=0.9)
    q90.fit(df[FEATURES], df[TARGET])
    signo = _signo_correlacion(df)

    mlflow.set_experiment(EXPERIMENTO)
    with mlflow.start_run(run_name="histgb"):
        mlflow.log_params(
            {
                "modelo": "HistGradientBoosting",
                "n_train": len(tr),
                "n_val": len(va),
                "anio_pred": anio_pred,
            }
        )
        mlflow.log_metrics(metrics)
        mlflow.log_metrics({f"imp_{f}": v for f, v in importancia.items()})
        mlflow.sklearn.log_model(punto, artifact_path="model", registered_model_name="vaciamiento")

    # --- predicción de futuro ---
    dp = construir_dataset(engine, [anio_pred], HORIZONTE)
    xp = dp[FEATURES]
    cambio = punto.predict(xp)
    inf, sup = q10.predict(xp), q90.predict(xp)
    pred = pd.DataFrame(
        {
            "cod": dp["cod"].to_numpy(),
            "anio_base": anio_pred,
            "anio_horizonte": anio_pred + HORIZONTE,
            "pob_base": dp["pob"].to_numpy(),
            "cambio_pct": np.round(cambio, 1),
            "cambio_inf": np.round(np.minimum(inf, sup), 1),
            "cambio_sup": np.round(np.maximum(inf, sup), 1),
            "drivers": _drivers(xp, importancia, signo),
        }
    )
    pred["pob_proyectada"] = (dp["pob"].to_numpy() * (1 + cambio / 100)).round()
    return pred[pred["pob_base"].notna()], {**metrics, "n_train": len(tr), "n_val": len(va)}
