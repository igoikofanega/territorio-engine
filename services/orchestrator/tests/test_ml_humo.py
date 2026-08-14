"""Test de humo del entrenamiento completo, sin base de datos y sin red.

Punto ciego que cierra: los demás tests de ML cubren funciones sueltas (`_tendencia`,
`nuevo_modelo`), pero nadie ejecutaba `entrenar_y_predecir()`, que es lo que corre
`make entrenar-ml`. Con esa laguna, un cambio incompatible en la API de MLflow pasaba
el CI en verde y solo se descubría al entrenar a mano. Pasó de verdad: un PR de
dependabot subía mlflow de 2.x a 3.x —rompiendo el tope `<3` puesto a propósito— y
todos los jobs salieron en verde.

El dataset es sintético y el tracking va a un SQLite temporal, así que el test es
hermético: sin PostGIS, sin servidor de MLflow y sin red. Se usa SQLite y no `file://`
porque el Model Registry, que `entrenar_y_predecir` utiliza, no funciona sobre ficheros.

El entrenamiento se hace **una sola vez** para todo el módulo: son cuatro modelos con
la configuración real (400 iteraciones cada uno) y repetirlo por test multiplicaba por
cuatro el tiempo del CI sin añadir cobertura.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from territorio_pipelines.ml import modelo as m
from territorio_pipelines.ml.features import FEATURES, TARGET

# Ventana sintética, con la misma forma que la real: años base cuyo futuro ya se
# conoce, y un año de predicción posterior sin target.
ANIOS_BASE = [2015, 2016, 2017, 2018, 2019, 2020]
ANIOS_TRAIN = [2015, 2016, 2017, 2018]
ANIOS_VAL = [2019, 2020]
ANIO_PRED = 2023


def _dataset(anios: list[int], n: int = 120) -> pd.DataFrame:
    """Datos sintéticos con la forma que devuelve `construir_dataset`.

    La señal es deliberadamente aprendible (el target depende de dos features más ruido)
    para que el ajuste converja; lo que se comprueba es la mecánica, no la calidad.
    """
    rng = np.random.default_rng(0)
    filas = []
    for t in anios:
        d = pd.DataFrame({f: rng.normal(size=n) for f in FEATURES})
        # `crec_prev3` es un cociente de poblaciones (pob[t] / pob[t-3]), siempre > 0.
        # El baseline de tendencia lo eleva a horizonte/3, y una base negativa daría NaN.
        d["crec_prev3"] = rng.uniform(0.85, 1.15, size=n)
        d["cod"] = [f"{i:05d}" for i in range(n)]
        d["pob"] = rng.integers(80, 50_000, size=n).astype(float)
        d["anio_base"] = t
        d[TARGET] = 2 * d["log_pob"] - 1.5 * d["paro_1000"] + rng.normal(scale=0.5, size=n)
        if anios == [ANIO_PRED]:
            d[TARGET] = np.nan  # el año de predicción no tiene futuro conocido
        # Huecos a propósito: HistGradientBoosting los admite y la matriz real los tiene.
        d.loc[d.index[:5], "alquiler"] = np.nan
        filas.append(d)
    return pd.concat(filas, ignore_index=True)


@pytest.fixture(scope="module")
def entrenamiento(tmp_path_factory):
    """Ejecuta `entrenar_y_predecir` una vez y devuelve (predicciones, métricas, mlflow)."""
    import mlflow
    from _pytest.monkeypatch import MonkeyPatch

    mp = MonkeyPatch()
    tmp = tmp_path_factory.mktemp("mlflow")
    uri = f"sqlite:///{tmp}/mlflow.db"
    mp.delenv("MLFLOW_TRACKING_URI", raising=False)
    mlflow.set_tracking_uri(uri)
    mlflow.set_registry_uri(uri)
    mp.setattr(m, "construir_dataset", lambda engine, anios, horizonte=m.HORIZONTE: _dataset(anios))
    # El calendario consulta la base de datos para derivar los años; aquí se fija la
    # ventana a mano para que el test siga siendo hermético. Que los años se deriven en
    # producción lo cubre tests/test_calendario.py.
    mp.setattr(m.cal, "anios_backtest", lambda e, h, **kw: (ANIOS_BASE, ANIOS_TRAIN, ANIOS_VAL))
    mp.setattr(m.cal, "ultimo_anio_comun", lambda e, cols, **kw: ANIO_PRED)

    pred, metricas = m.entrenar_y_predecir(engine=None)
    yield pred, metricas, mlflow
    mp.undo()


def test_metricas_del_backtest(entrenamiento):
    _, metricas, _ = entrenamiento
    for clave in ("mae", "r2", "mae_persistencia", "mae_tendencia", "n_train", "n_val"):
        assert clave in metricas, f"falta la métrica {clave}"
    assert metricas["n_train"] > 0 and metricas["n_val"] > 0
    assert np.isfinite(metricas["mae"]) and metricas["mae"] >= 0
    # Los baselines honestos deben calcularse siempre, no solo cuando conviene.
    assert np.isfinite(metricas["mae_persistencia"])
    assert np.isfinite(metricas["mae_tendencia"])


def test_forma_de_las_predicciones(entrenamiento):
    pred, _, _ = entrenamiento
    esperadas = {
        "cod",
        "anio_base",
        "anio_horizonte",
        "pob_base",
        "cambio_pct",
        "cambio_inf",
        "cambio_sup",
        "drivers",
        "pob_proyectada",
    }
    assert esperadas <= set(pred.columns)
    assert len(pred) > 0
    assert (pred["anio_horizonte"] == ANIO_PRED + m.HORIZONTE).all()
    assert pred["cambio_pct"].notna().all()


def test_la_banda_de_incertidumbre_esta_ordenada(entrenamiento):
    """`cambio_inf` nunca puede superar a `cambio_sup`.

    Los cuantiles q10 y q90 se ajustan por separado y pueden cruzarse; el código lo
    corrige con min/max. Si esa protección desaparece, el mapa dibujaría bandas
    invertidas sin que nada fallase.
    """
    pred, _, _ = entrenamiento
    assert (pred["cambio_inf"] <= pred["cambio_sup"]).all()


def test_todas_las_features_tienen_etiqueta():
    """Sin etiqueta, el tooltip de drivers saldría con un KeyError."""
    assert set(FEATURES) <= set(m.ETIQUETAS), (
        f"features sin etiqueta en ETIQUETAS: {sorted(set(FEATURES) - set(m.ETIQUETAS))}"
    )


def test_los_drivers_salen_del_catalogo(entrenamiento):
    pred, _, _ = entrenamiento
    etiquetas = set(m.ETIQUETAS.values())
    for texto in pred["drivers"]:
        for parte in texto.split(" · "):
            assert parte.rstrip("↑↓") in etiquetas, f"driver desconocido: {parte}"


def test_quedan_registradas_las_metricas_en_mlflow(entrenamiento):
    """Si MLflow cambia su API de logging, esto falla aquí y no al entrenar a mano."""
    _, _, mlflow = entrenamiento
    exp = mlflow.get_experiment_by_name(m.EXPERIMENTO)
    assert exp is not None, f"no se creó el experimento {m.EXPERIMENTO}"
    runs = mlflow.search_runs(experiment_ids=[exp.experiment_id])
    assert len(runs) == 1
    fila = runs.iloc[0]
    assert fila["metrics.mae"] >= 0
    assert fila["params.modelo"] == "HistGradientBoosting"
    # La importancia por permutación se registra feature a feature.
    assert any(c.startswith("metrics.imp_") for c in runs.columns)
