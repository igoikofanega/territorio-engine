"""Semáforo de despoblación: probabilidad calibrada de pérdida fuerte de población.

Clasificador (gradient boosting) que estima P(perder más del UMBRAL% de población
en 5 años) desde las mismas features del modelo de regresión. Se entrena con los
años base antiguos, se CALIBRA (isotónica) con los recientes cuyo futuro ya se
conoce — así la probabilidad significa lo que dice — y se aplica al año base
actual. Salida: probabilidad + nivel (verde/ámbar/rojo).
"""

from __future__ import annotations

from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.frozen import FrozenEstimator
from sklearn.metrics import brier_score_loss, roc_auc_score
from sqlalchemy.engine import Engine

from .features import FEATURES, TARGET, construir_dataset
from .modelo import ANIO_PRED, ANIOS_TRAIN, ANIOS_VAL

UMBRAL_PERDIDA = -10.0  # % en 5 años que define el evento 'despoblación fuerte'
CORTES = (0.30, 0.60)  # verde < .30 <= ámbar < .60 <= rojo


def _nivel(p: float) -> str:
    if p >= CORTES[1]:
        return "rojo"
    if p >= CORTES[0]:
        return "ambar"
    return "verde"


def calcular_riesgo(engine: Engine) -> tuple[list[dict], dict]:
    """([{cod, prob, nivel}], métricas) del semáforo de despoblación."""
    df = construir_dataset(engine, ANIOS_TRAIN + ANIOS_VAL)
    df = df[df[TARGET].notna() & df["pob"].notna()]
    df["evento"] = (df[TARGET] <= UMBRAL_PERDIDA).astype(int)
    tr = df[df["anio_base"].isin(ANIOS_TRAIN)]
    va = df[df["anio_base"].isin(ANIOS_VAL)]

    base = HistGradientBoostingClassifier(
        max_iter=400, learning_rate=0.05, max_leaf_nodes=31, l2_regularization=1.0, random_state=0
    )
    base.fit(tr[FEATURES], tr["evento"])
    # calibración isotónica sobre el holdout temporal: probabilidades honestas
    cal = CalibratedClassifierCV(FrozenEstimator(base), method="isotonic")
    cal.fit(va[FEATURES], va["evento"])

    p_va = cal.predict_proba(va[FEATURES])[:, 1]
    metricas = {
        "auc": round(float(roc_auc_score(va["evento"], p_va)), 3),
        "brier": round(float(brier_score_loss(va["evento"], p_va)), 4),
        "tasa_evento": round(float(va["evento"].mean()), 3),
    }

    dp = construir_dataset(engine, [ANIO_PRED])
    dp = dp[dp["pob"].notna()]
    prob = cal.predict_proba(dp[FEATURES])[:, 1]
    recs = [
        {"cod": c, "prob": round(float(p), 3), "nivel": _nivel(float(p))}
        for c, p in zip(dp["cod"].to_numpy(), prob, strict=True)
    ]
    return recs, metricas
