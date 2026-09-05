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

from .. import calendario
from .features import FEATURES, TARGET, construir_dataset
from .modelo import COLUMNAS_PRED, HORIZONTE

UMBRAL_PERDIDA = -10.0  # % en 5 años que define el evento 'despoblación fuerte'
CORTES = (0.30, 0.60)  # verde < .30 <= ámbar < .60 <= rojo


def _nivel(p: float) -> str:
    if p >= CORTES[1]:
        return "rojo"
    if p >= CORTES[0]:
        return "ambar"
    return "verde"


def calcular_riesgo(engine: Engine) -> tuple[list[dict], dict]:
    """([{cod, prob, nivel}], métricas) del semáforo de despoblación.

    Comparte la misma ventana de años que el modelo de regresión, para que las dos
    salidas del proyecto hablen de los mismos datos.
    """
    anios_base, _, _ = calendario.anios_backtest(engine, HORIZONTE)
    if len(anios_base) < 3:
        raise RuntimeError(
            f"hacen falta 3 años base para entrenar, calibrar y medir por separado: {anios_base}"
        )
    anio_pred = calendario.ultimo_anio_comun(engine, COLUMNAS_PRED)
    if anio_pred is None:
        raise RuntimeError(f"ningún año cubre a la vez {COLUMNAS_PRED}")

    # Tres tramos, todos temporales. Antes la isotónica se ajustaba sobre el conjunto de
    # validación y el Brier se calculaba sobre ESE MISMO conjunto: el número salía
    # optimista por construcción, así que la promesa de "el 70% significa 70%" no estaba
    # demostrada. Ahora el año de medida es uno que el calibrador no ha visto.
    anios_train, anio_cal, anio_test = anios_base[:-2], anios_base[-2], anios_base[-1]

    df = construir_dataset(engine, anios_base)
    df = df[df[TARGET].notna() & df["pob"].notna()]
    df["evento"] = (df[TARGET] <= UMBRAL_PERDIDA).astype(int)
    tr = df[df["anio_base"].isin(anios_train)]
    ca = df[df["anio_base"] == anio_cal]
    te = df[df["anio_base"] == anio_test]

    base = HistGradientBoostingClassifier(
        max_iter=400, learning_rate=0.05, max_leaf_nodes=31, l2_regularization=1.0, random_state=0
    )
    base.fit(tr[FEATURES], tr["evento"])
    cal = CalibratedClassifierCV(FrozenEstimator(base), method="isotonic")
    cal.fit(ca[FEATURES], ca["evento"])

    y_te = te["evento"].to_numpy()
    p_te = cal.predict_proba(te[FEATURES])[:, 1]
    metricas = {
        "auc": round(float(roc_auc_score(y_te, p_te)), 3),
        "brier": round(float(brier_score_loss(y_te, p_te)), 4),
        "brier_sin_calibrar": round(
            float(brier_score_loss(y_te, base.predict_proba(te[FEATURES])[:, 1])), 4
        ),
        "tasa_evento": round(float(y_te.mean()), 3),
        "anio_calibracion": anio_cal,
        "anio_test": anio_test,
    }

    dp = construir_dataset(engine, [anio_pred])
    dp = dp[dp["pob"].notna()]
    prob = cal.predict_proba(dp[FEATURES])[:, 1]
    recs = [
        {"cod": c, "prob": round(float(p), 3), "nivel": _nivel(float(p))}
        for c, p in zip(dp["cod"].to_numpy(), prob, strict=True)
    ]
    return recs, metricas
