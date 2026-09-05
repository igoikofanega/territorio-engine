"""Ablación de tres brazos para las features de noticias.

Mide si la información de prensa local mejora el modelo de predicción de población,
o si la diferencia se explica por la capacidad extra del gradient boosting.

Los tres brazos:
- `sin_noticias`  — las 17 features base
- `con_noticias`  — las 17 + 4 de noticias
- `noticias_permutadas` — las 4 de noticias barajadas entre municipios (control nulo)

El brazo de permutación es lo que hace creíble el resultado: si `con_noticias` mejora
pero `noticias_permutadas` también lo hace, la "mejora" es capacidad extra del modelo,
no información real.

**Config separada.** GDELT arranca en 2017, así que la ventana de ablación es más corta
(horizonte 3, base 2018-2021) y sus resultados NO son comparables con el modelo titular
(horizonte 5). Los runs en MLflow se etiquetan `config=noticias_h3`.

**Criterio de aceptación fijado ANTES de ver el resultado:**
> Las features entran en FEATURES si y solo si
> `mae(con) < mae(sin) - 2·sd(semillas)` Y `mae(con) < mae(permutadas)`,
> en el estrato >2000 hab.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

import mlflow
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error
from sqlalchemy.engine import Engine

from .. import calendario as cal
from .features import FEATURES, TARGET, construir_dataset
from .features_noticias import FEATURES_NOTICIAS
from .features_noticias import calcular as calcular_noticias
from .modelo import EXPERIMENTO

HORIZONTE_ABL = 3
N_SEMILLAS = 5

ESTRATOS = {
    "<500": (0, 500),
    "500-2000": (500, 2000),
    "2000-10000": (2000, 10000),
    ">10000": (10000, float("inf")),
}


def _entrenar_evaluar(
    x_tr: pd.DataFrame,
    y_tr: pd.Series,
    x_va: pd.DataFrame,
    y_va: pd.Series,
    features: list[str],
    seed: int,
) -> float:
    m = HistGradientBoostingRegressor(
        max_iter=400,
        learning_rate=0.05,
        max_leaf_nodes=31,
        l2_regularization=1.0,
        random_state=seed,
    )
    m.fit(x_tr[features], y_tr)
    return float(mean_absolute_error(y_va, m.predict(x_va[features])))


def _permutar(df: pd.DataFrame, cols: list[str], seed: int) -> pd.DataFrame:
    """Permuta las columnas de noticias entre municipios, preservando la estructura."""
    rng = np.random.default_rng(seed)
    out = df.copy()
    for c in cols:
        out[c] = rng.permutation(out[c].to_numpy())
    return out


def ablacion(engine: Engine) -> dict:
    """Ejecuta la ablación de tres brazos y devuelve las métricas por estrato y brazo."""
    anios_base, anios_train, anios_val = cal.anios_backtest(engine, HORIZONTE_ABL)
    if not anios_val:
        raise RuntimeError(f"no hay años para ablación a horizonte {HORIZONTE_ABL}")

    df = construir_dataset(engine, anios_base, HORIZONTE_ABL)
    df = df[df[TARGET].notna()]

    news = calcular_noticias(
        engine, anios_base, df[["cod", "anio_base", "pob"]], anios_train=anios_train
    )
    df = df.merge(news, on=["cod", "anio_base"], how="left")

    features_base = FEATURES
    features_con = FEATURES + FEATURES_NOTICIAS

    tr = df[df["anio_base"].isin(anios_train)]
    va = df[df["anio_base"].isin(anios_val)]
    y_tr, y_va = tr[TARGET], va[TARGET]

    resultados: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))

    for seed in range(N_SEMILLAS):
        va_perm = _permutar(va, FEATURES_NOTICIAS, seed)
        tr_perm = _permutar(tr, FEATURES_NOTICIAS, seed)

        for nombre_estrato, (lo, hi) in [("global", (0, float("inf")))] + list(ESTRATOS.items()):
            mask_va = (va["pob"] >= lo) & (va["pob"] < hi)
            mask_tr = (tr["pob"] >= lo) & (tr["pob"] < hi)
            if mask_va.sum() < 10:
                continue

            mae_sin = _entrenar_evaluar(
                tr[mask_tr], y_tr[mask_tr], va[mask_va], y_va[mask_va], features_base, seed
            )
            mae_con = _entrenar_evaluar(
                tr[mask_tr], y_tr[mask_tr], va[mask_va], y_va[mask_va], features_con, seed
            )
            mae_perm = _entrenar_evaluar(
                tr_perm[mask_tr],
                y_tr[mask_tr],
                va_perm[mask_va],
                y_va[mask_va],
                features_con,
                seed,
            )

            resultados[nombre_estrato]["sin"].append(mae_sin)
            resultados[nombre_estrato]["con"].append(mae_con)
            resultados[nombre_estrato]["perm"].append(mae_perm)

    resumen: dict[str, dict[str, Any]] = {}
    for estrato, brazos in resultados.items():
        resumen[estrato] = {}
        for brazo, maes in brazos.items():
            resumen[estrato][brazo] = {
                "mae_media": round(float(np.mean(maes)), 4),
                "mae_std": round(float(np.std(maes)), 4),
                "n_semillas": len(maes),
            }

    # Decisión automática según el criterio pre-registrado
    decision = _decision(resumen)

    mlflow.set_experiment(EXPERIMENTO)
    with mlflow.start_run(run_name="ablacion_noticias"):
        mlflow.log_params(
            {
                "config": "noticias_h3",
                "horizonte": HORIZONTE_ABL,
                "n_semillas": N_SEMILLAS,
                "anios_train": str(anios_train),
                "anios_val": str(anios_val),
            }
        )
        for estrato, brazos_est in resumen.items():
            for brazo, stats in brazos_est.items():
                s: dict[str, Any] = stats
                mlflow.log_metric(f"mae_{estrato}_{brazo}", s["mae_media"])
                mlflow.log_metric(f"std_{estrato}_{brazo}", s["mae_std"])
        mlflow.log_param("decision", decision["veredicto"])
        mlflow.log_param("motivo", decision["motivo"])

    return {"estratos": resumen, "decision": decision}


def _decision(resumen: dict[str, Any]) -> dict[str, str]:
    """Aplica el criterio pre-registrado sobre el estrato >2000 hab."""
    clave = ">10000"
    if clave not in resumen:
        clave = "2000-10000"
    if clave not in resumen:
        return {"veredicto": "no_evaluable", "motivo": "sin datos en estratos grandes"}

    sin = resumen[clave]["sin"]
    con = resumen[clave]["con"]
    perm = resumen[clave]["perm"]

    mejora_vs_base = sin["mae_media"] - con["mae_media"]
    umbral = 2 * sin["mae_std"]
    mejor_que_perm = con["mae_media"] < perm["mae_media"]

    if mejora_vs_base > umbral and mejor_que_perm:
        return {
            "veredicto": "aceptar",
            "motivo": (
                f"MAE mejora {mejora_vs_base:.3f} pp (umbral 2σ = {umbral:.3f}) "
                f"y supera al control permutado"
            ),
        }
    partes = []
    if mejora_vs_base <= umbral:
        partes.append(f"mejora {mejora_vs_base:.3f} ≤ 2σ={umbral:.3f}")
    if not mejor_que_perm:
        partes.append("no supera al control permutado")
    return {"veredicto": "rechazar", "motivo": "; ".join(partes)}
