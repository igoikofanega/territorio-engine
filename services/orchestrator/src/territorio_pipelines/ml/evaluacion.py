"""Evaluación del modelo: backtest de origen rodante, análisis de error y calibración.

Este módulo no entrena el modelo de producción — eso lo hace `modelo.py`. Lo que hace es
**medirlo bien**, que es un problema distinto y, en un proyecto sobre despoblación, el que
de verdad importa: un MAE agregado dice poco cuando la tesis del proyecto es que los
pueblos pequeños son ruidosos.

Cuatro cosas que un corte único no puede dar:

1. **Dispersión.** Varios pliegues de origen rodante en vez de una cifra suelta.
2. **El coste del solape.** El target mira 5 años adelante, así que con pliegues contiguos
   las ventanas de train y validación comparten trayectoria. Se mide con dos embargos
   distintos para que se vea cuánto del acierto venía de ahí.
3. **Dónde falla.** Error por estrato de población y por provincia, no solo el total.
4. **Si le sobra estructura.** Moran's I sobre los residuos: si el error está agrupado en
   el espacio, el modelo se está dejando geografía sin explicar.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.frozen import FrozenEstimator
from sklearn.inspection import permutation_importance
from sklearn.metrics import brier_score_loss, mean_absolute_error, r2_score, roc_auc_score
from sqlalchemy import text
from sqlalchemy.engine import Engine

from .. import calendario as cal
from .ablacion import ESTRATOS
from .features import FEATURES, TARGET, construir_dataset
from .modelo import HORIZONTE, _tendencia, nuevo_modelo
from .riesgo import UMBRAL_PERDIDA

#: Embargos a comparar: contiguo (lo que se hacía) y sin solape de ventanas de target.
EMBARGO_CONTIGUO = 1
K_VECINOS = 8


def _metricas(y: np.ndarray, pred: np.ndarray, crec_prev3: np.ndarray) -> dict[str, float]:
    """El modelo y sus dos baselines sobre exactamente las mismas filas."""
    return {
        "mae": float(mean_absolute_error(y, pred)),
        "r2": float(r2_score(y, pred)),
        "mae_persistencia": float(mean_absolute_error(y, np.zeros_like(y))),
        "mae_tendencia": float(mean_absolute_error(y, _tendencia(crec_prev3))),
    }


def backtest_rodante(engine: Engine, embargo: int = EMBARGO_CONTIGUO) -> dict:
    """Un pliegue por año base de validación, entrenando siempre con el pasado.

    Devuelve las métricas de cada pliegue, el resumen media ± desviación, y los residuos
    del pliegue más reciente (los que se usan para el análisis espacial).
    """
    folds = cal.folds_rodantes(engine, HORIZONTE, embargo=embargo)
    if not folds:
        return {
            "embargo": embargo,
            "n_pliegues": 0,
            "pliegues": [],
            "descartados": [],
            "residuos": None,
        }

    anios = sorted({a for train, val in folds for a in [*train, val]})
    df = construir_dataset(engine, anios)
    df = df[df[TARGET].notna()]

    pliegues, descartados, residuos = [], [], None
    for train, val in folds:
        tr = df[df["anio_base"].isin(train)]
        va = df[df["anio_base"] == val]
        if tr.empty or va.empty:
            descartados.append({"anio_val": val, "motivo": "partición vacía"})
            continue
        # Una feature entera a NaN en entrenamiento hace degenerar el binning del modelo.
        # Pasa de verdad: `crec_prev3` necesita el año T-3 y la población empieza en 2015,
        # así que los años base 2015-2017 no la tienen. Se descarta el pliegue y se dice
        # cuál, en vez de rellenar el hueco con un valor inventado.
        vacias = [c for c in FEATURES if tr[c].isna().all()]
        if vacias:
            descartados.append(
                {"anio_val": val, "motivo": f"sin dato en entrenamiento para {', '.join(vacias)}"}
            )
            continue
        m = nuevo_modelo()
        m.fit(tr[FEATURES], tr[TARGET])
        y = va[TARGET].to_numpy()
        pred = m.predict(va[FEATURES])
        pliegues.append(
            {
                "anio_val": val,
                "anios_train": train,
                "n_train": len(tr),
                "n_val": len(va),
                **{
                    k: round(v, 3)
                    for k, v in _metricas(y, pred, va["crec_prev3"].to_numpy()).items()
                },
            }
        )
        residuos = va[["cod", "pob", "cod_provincia"]].copy()
        residuos["real"] = y
        residuos["pred"] = pred
        residuos["error"] = y - pred
        residuos["abs_error"] = np.abs(y - pred)

    if not pliegues:
        return {
            "embargo": embargo,
            "n_pliegues": 0,
            "pliegues": [],
            "descartados": descartados,
            "residuos": None,
        }

    maes = np.array([p["mae"] for p in pliegues])
    return {
        "embargo": embargo,
        "n_pliegues": len(pliegues),
        "pliegues": pliegues,
        "descartados": descartados,
        "mae_media": round(float(maes.mean()), 3),
        "mae_desviacion": round(float(maes.std(ddof=1)) if len(maes) > 1 else 0.0, 3),
        "mae_min": round(float(maes.min()), 3),
        "mae_max": round(float(maes.max()), 3),
        "residuos": residuos,
    }


def error_por_estrato(residuos: pd.DataFrame) -> list[dict]:
    """MAE por tamaño de municipio. La tesis del proyecto se juega aquí."""
    salida = []
    for nombre, (lo, hi) in ESTRATOS.items():
        m = residuos[(residuos["pob"] >= lo) & (residuos["pob"] < hi)]
        if m.empty:
            continue
        salida.append(
            {
                "estrato": nombre,
                "n": len(m),
                "mae": round(float(m["abs_error"].mean()), 3),
                "sesgo": round(float(m["error"].mean()), 3),
                "mae_persistencia": round(float(m["real"].abs().mean()), 3),
            }
        )
    return salida


def error_por_provincia(residuos: pd.DataFrame, n: int = 5) -> dict[str, list[dict]]:
    """Las provincias donde mejor y peor va, para saber si el error es geográfico."""
    g = (
        residuos.groupby("cod_provincia")
        .agg(n=("abs_error", "size"), mae=("abs_error", "mean"), sesgo=("error", "mean"))
        .reset_index()
    )
    g = g[g["n"] >= 20].sort_values("mae")
    fmt = lambda d: [  # noqa: E731
        {
            "cod_provincia": r.cod_provincia,
            "n": int(r.n),
            "mae": round(float(r.mae), 3),
            "sesgo": round(float(r.sesgo), 3),
        }
        for r in d.itertuples(index=False)
    ]
    return {"mejores": fmt(g.head(n)), "peores": fmt(g.tail(n).iloc[::-1])}


def moran_residuos(engine: Engine, residuos: pd.DataFrame, k: int = K_VECINOS) -> dict:
    """Moran's I global sobre el residuo. ¿Queda estructura espacial sin explicar?

    Si el error estuviese repartido al azar en el mapa, I rondaría 0. Un I positivo y
    significativo dice que municipios vecinos fallan en el mismo sentido, es decir que hay
    geografía que las features no capturan. Es una comprobación que este proyecto puede
    hacer casi gratis, porque ya tiene PostGIS y los centroides.
    """
    from esda.moran import Moran
    from libpysal.weights import KNN

    coords = pd.read_sql(
        text(
            "SELECT cod_municipio AS cod, ST_X(ST_Centroid(geom_25830)) AS x, "
            "ST_Y(ST_Centroid(geom_25830)) AS y FROM dim_municipio"
        ),
        engine,
    )
    d = residuos.merge(coords, on="cod", how="inner").dropna(subset=["x", "y", "error"])
    d = d.reset_index(drop=True)
    if len(d) < k + 1:
        return {"n": len(d), "moran_i": None, "p": None}
    w = KNN.from_array(d[["x", "y"]].to_numpy(), k=k)
    w.transform = "r"
    mi = Moran(d["error"].to_numpy(), w, permutations=999)
    return {
        "n": len(d),
        "k_vecinos": k,
        "moran_i": round(float(mi.I), 4),
        "esperado_bajo_azar": round(float(mi.EI), 4),
        "p": round(float(mi.p_sim), 4),
    }


def importancia(engine: Engine) -> list[dict]:
    """Importancia por permutación sobre el pliegue más reciente."""
    folds = cal.folds_rodantes(engine, HORIZONTE, embargo=EMBARGO_CONTIGUO)
    train, val = folds[-1]
    df = construir_dataset(engine, [*train, val])
    df = df[df[TARGET].notna()]
    tr, va = df[df["anio_base"].isin(train)], df[df["anio_base"] == val]
    m = nuevo_modelo()
    m.fit(tr[FEATURES], tr[TARGET])
    imp = permutation_importance(m, va[FEATURES], va[TARGET], n_repeats=5, random_state=0)
    orden = np.argsort(imp.importances_mean)[::-1]
    return [
        {
            "feature": FEATURES[i],
            "importancia": round(float(imp.importances_mean[i]), 4),
            "desviacion": round(float(imp.importances_std[i]), 4),
        }
        for i in orden
    ]


def calibracion_riesgo(engine: Engine) -> dict:
    """Calibración del semáforo medida **fuera** de los datos con los que se calibra.

    El fallo que corrige: `riesgo.py` ajustaba la isotónica sobre el conjunto de validación
    y calculaba el Brier sobre ese mismo conjunto, así que el número salía optimista por
    construcción y la promesa de "el 70% significa 70%" no estaba demostrada.

    Aquí la partición es de tres tramos, todos temporales: se entrena con los años base
    antiguos, se calibra con el penúltimo y se mide con el último, que el calibrador no ha
    visto. Se informa también del Brier **sin** calibrar, porque una calibración que no
    mejora nada tampoco merece el nombre.
    """
    anios_base, _, _ = cal.anios_backtest(engine, HORIZONTE)
    if len(anios_base) < 3:
        raise RuntimeError(f"hacen falta 3 años base para calibrar y medir aparte: {anios_base}")
    train, anio_cal, anio_test = anios_base[:-2], anios_base[-2], anios_base[-1]

    df = construir_dataset(engine, anios_base)
    df = df[df[TARGET].notna() & df["pob"].notna()]
    df["evento"] = (df[TARGET] <= UMBRAL_PERDIDA).astype(int)
    tr = df[df["anio_base"].isin(train)]
    ca = df[df["anio_base"] == anio_cal]
    te = df[df["anio_base"] == anio_test]

    base = HistGradientBoostingClassifier(
        max_iter=400, learning_rate=0.05, max_leaf_nodes=31, l2_regularization=1.0, random_state=0
    )
    base.fit(tr[FEATURES], tr["evento"])
    calibrado = CalibratedClassifierCV(FrozenEstimator(base), method="isotonic")
    calibrado.fit(ca[FEATURES], ca["evento"])

    y = te["evento"].to_numpy()
    p_sin = base.predict_proba(te[FEATURES])[:, 1]
    p_con = calibrado.predict_proba(te[FEATURES])[:, 1]

    return {
        "anios_train": train,
        "anio_calibracion": anio_cal,
        "anio_test": anio_test,
        "n_test": len(te),
        "tasa_evento_test": round(float(y.mean()), 4),
        "auc": round(float(roc_auc_score(y, p_con)), 4),
        "brier_sin_calibrar": round(float(brier_score_loss(y, p_sin)), 5),
        "brier_calibrado": round(float(brier_score_loss(y, p_con)), 5),
        "fiabilidad": _fiabilidad(y, p_con),
    }


def _fiabilidad(y: np.ndarray, p: np.ndarray, n_bins: int = 10) -> list[dict]:
    """Diagrama de fiabilidad: probabilidad prometida frente a frecuencia observada."""
    bordes = np.linspace(0, 1, n_bins + 1)
    salida = []
    for i in range(n_bins):
        m = (p >= bordes[i]) & (p < bordes[i + 1] if i < n_bins - 1 else p <= 1.0)
        if not m.any():
            continue
        salida.append(
            {
                "bin": f"{bordes[i]:.1f}-{bordes[i + 1]:.1f}",
                "n": int(m.sum()),
                "prob_media": round(float(p[m].mean()), 4),
                "frec_observada": round(float(y[m].mean()), 4),
            }
        )
    return salida


def evaluar(engine: Engine) -> dict:
    """Todo el informe, en un diccionario serializable."""
    contiguo = backtest_rodante(engine, embargo=EMBARGO_CONTIGUO)
    residuos = contiguo.pop("residuos")
    if residuos is None:
        raise RuntimeError(f"ningún pliegue utilizable: {contiguo['descartados']}")

    # ¿Cuánto del acierto viene del solape de ventanas de target? Se prueban embargos
    # crecientes; los que no dejan ningún pliegue se informan como no factibles, que es la
    # respuesta honesta cuando la ventana de datos no da para más.
    solape = []
    for e in range(2, HORIZONTE + 1):
        r = backtest_rodante(engine, embargo=e)
        r.pop("residuos", None)
        solape.append(
            {
                "embargo": e,
                "factible": r["n_pliegues"] > 0,
                "n_pliegues": r["n_pliegues"],
                "mae_media": r.get("mae_media"),
                "motivo": None if r["n_pliegues"] else "sin pliegues con datos suficientes",
            }
        )

    return {
        "horizonte": HORIZONTE,
        "backtest_contiguo": contiguo,
        "sensibilidad_al_embargo": solape,
        "error_por_estrato": error_por_estrato(residuos),
        "error_por_provincia": error_por_provincia(residuos),
        "moran_residuos": moran_residuos(engine, residuos),
        "importancia": importancia(engine),
        "riesgo": calibracion_riesgo(engine),
    }
