import numpy as np

from territorio_pipelines.ml.modelo import _tendencia, nuevo_modelo


def test_tendencia_baseline():
    assert abs(_tendencia(np.array([1.0]))[0]) < 1e-9  # sin cambio → 0%
    assert _tendencia(np.array([1.1]))[0] > 0  # crecimiento → positivo
    assert _tendencia(np.array([0.9]))[0] < 0  # decrecimiento → negativo
    assert abs(_tendencia(np.array([np.nan]))[0]) < 1e-9  # NaN → tratado como sin cambio


def test_nuevo_modelo_soporta_nan():
    # HistGradientBoosting acepta NaN de forma nativa (clave para features dispersas)
    modelo = nuevo_modelo()
    x = np.array([[1.0, np.nan], [2.0, 3.0], [np.nan, 1.0], [4.0, 2.0]])
    y = np.array([0.0, 1.0, 2.0, 3.0])
    modelo.fit(x, y)
    assert modelo.predict(np.array([[1.0, np.nan]])).shape == (1,)
