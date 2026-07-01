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
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, r2_score
from sqlalchemy.engine import Engine

from .features import FEATURES, TARGET, construir_dataset

ANIOS_BASE = [2015, 2016, 2017, 2018, 2019, 2020]
ANIOS_TRAIN = [2015, 2016, 2017, 2018]
ANIOS_VAL = [2019, 2020]
EXPERIMENTO = "vaciamiento"


def nuevo_modelo() -> HistGradientBoostingRegressor:
    return HistGradientBoostingRegressor(
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


def entrenar_y_backtest(engine: Engine) -> dict:
    """Entrena, valida con corte temporal y registra en MLflow. Devuelve las métricas."""
    df = construir_dataset(engine, ANIOS_BASE)
    df = df[df[TARGET].notna()]
    tr = df[df["anio_base"].isin(ANIOS_TRAIN)]
    va = df[df["anio_base"].isin(ANIOS_VAL)]

    model = nuevo_modelo()
    model.fit(tr[FEATURES], tr[TARGET])
    pred = model.predict(va[FEATURES])

    yva = va[TARGET].to_numpy()
    metrics = {
        "mae": float(mean_absolute_error(yva, pred)),
        "r2": float(r2_score(yva, pred)),
        "mae_persistencia": float(mean_absolute_error(yva, np.zeros_like(yva))),
        "mae_tendencia": float(mean_absolute_error(yva, _tendencia(va["crec_prev3"].to_numpy()))),
    }

    mlflow.set_experiment(EXPERIMENTO)
    with mlflow.start_run(run_name="histgb_backtest"):
        mlflow.log_params(
            {
                "modelo": "HistGradientBoostingRegressor",
                "features": ",".join(FEATURES),
                "anios_train": ANIOS_TRAIN,
                "anios_val": ANIOS_VAL,
                "n_train": len(tr),
                "n_val": len(va),
            }
        )
        mlflow.log_metrics(metrics)
        mlflow.sklearn.log_model(model, artifact_path="model")

    return {**metrics, "n_train": len(tr), "n_val": len(va)}
