"""Tests de la ablación. Sin base de datos y sin red: datos sintéticos.

Lo que se comprueba aquí no es que la ablación dé un número, sino que **no pueda dar el
número equivocado**: que el brazo permutado conserve la distribución y rompa el vínculo,
y que el criterio de aceptación diga que no cuando no hay señal. Un experimento cuyo
criterio se cumple por construcción no mide nada.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from territorio_pipelines.ml import ablacion
from territorio_pipelines.ml.features_noticias import FEATURES_NOTICIAS

PRIMERA = FEATURES_NOTICIAS[0]


def _df(n_por_anio: int = 40) -> pd.DataFrame:
    rng = np.random.default_rng(0)
    filas = []
    for t in ablacion.ANIOS_BASE:
        d = pd.DataFrame({"cod": [f"31{i:03d}" for i in range(n_por_anio)], "anio_base": t})
        for col in FEATURES_NOTICIAS:
            d[col] = rng.normal(size=n_por_anio)
        filas.append(d)
    return pd.concat(filas, ignore_index=True)


class TestPermutacion:
    def test_conserva_la_distribucion(self):
        """Si el placebo cambiara los valores no sería un placebo: sería otro experimento."""
        df = _df()
        out = ablacion.permutar(df, FEATURES_NOTICIAS, semilla=1)
        for t in ablacion.ANIOS_BASE:
            antes = np.sort(df.loc[df["anio_base"] == t, PRIMERA].to_numpy())
            despues = np.sort(out.loc[out["anio_base"] == t, PRIMERA].to_numpy())
            assert np.allclose(antes, despues)

    def test_rompe_el_vinculo_con_el_municipio(self):
        df = _df()
        out = ablacion.permutar(df, FEATURES_NOTICIAS, semilla=1)
        iguales = (df[PRIMERA].to_numpy() == out[PRIMERA].to_numpy()).mean()
        assert iguales < 0.5, "la permutación apenas movió nada"

    def test_no_mezcla_anios(self):
        """Barajar entre años destruiría también la tendencia temporal de la cobertura, y
        el placebo saldría más fácil de batir de lo que debe."""
        df = _df()
        out = ablacion.permutar(df, FEATURES_NOTICIAS, semilla=3)
        assert (df["anio_base"].to_numpy() == out["anio_base"].to_numpy()).all()
        for t in ablacion.ANIOS_BASE:
            antes = set(np.round(df.loc[df["anio_base"] == t, PRIMERA], 9))
            despues = set(np.round(out.loc[out["anio_base"] == t, PRIMERA], 9))
            assert antes == despues

    def test_mueve_todas_las_columnas_a_la_vez(self):
        """Las features de un municipio deben viajar juntas: barajadas por separado, el
        brazo placebo tendría combinaciones que no existen en los datos."""
        df = _df()
        out = ablacion.permutar(df, FEATURES_NOTICIAS, semilla=5)
        t = ablacion.ANIOS_BASE[0]
        filas_orig = df[df["anio_base"] == t][FEATURES_NOTICIAS].to_numpy()
        filas_perm = out[out["anio_base"] == t][FEATURES_NOTICIAS].to_numpy()
        orig = {tuple(np.round(r, 9)) for r in filas_orig}
        perm = {tuple(np.round(r, 9)) for r in filas_perm}
        assert orig == perm


class TestIntervaloBootstrap:
    def test_incluye_el_cero_cuando_no_hay_diferencia(self):
        """Con dos brazos idénticos la diferencia es ruido centrado en cero. Si el IC
        excluyera el cero aquí, el experimento aprobaría cualquier cosa."""
        dif = np.random.default_rng(0).normal(scale=1.0, size=200)
        bajo, alto = ablacion._ic_bootstrap(dif)
        assert bajo < 0 < alto

    def test_excluye_el_cero_ante_una_diferencia_real(self):
        dif = np.random.default_rng(0).normal(loc=1.0, scale=0.5, size=200)
        bajo, _alto = ablacion._ic_bootstrap(dif)
        assert bajo > 0


class TestCriterioPreinscrito:
    def test_los_umbrales_son_los_del_adr(self):
        """Si alguien los relaja tras ver el resultado, el experimento deja de valer.
        Este test existe para que ese cambio no pase inadvertido en una revisión."""
        assert ablacion.MEJORA_MINIMA_PP == 0.20
        assert ablacion.N_BOOTSTRAP == 1000
        assert ablacion.HORIZONTE_ABL == 3
        assert ablacion.ANIOS_BASE == [2018, 2019, 2020, 2021]
        assert ablacion.ANIOS_TRAIN == [2018, 2019]
        assert ablacion.ANIOS_VAL == [2020, 2021]
        assert list(ablacion.SEMILLAS) == [0, 1, 2, 3, 4]
        assert ablacion.PROVINCIA == "31"

    def test_las_tres_condiciones_son_conjuntivas(self):
        """El ADR exige las tres a la vez. Que dos se cumplan no basta."""
        import inspect

        fuente = inspect.getsource(ablacion.ablacion)
        assert "cond_mejora and cond_placebo and cond_ic" in fuente


class TestSinSenal:
    """Con noticias que son ruido puro, el veredicto tiene que ser 'rechazar'."""

    @pytest.fixture(scope="class")
    def ablacion_sobre_ruido(self):
        """El criterio se ejerce entero; solo se abaratan el ajuste y el remuestreo, que
        no son lo que este test comprueba."""
        from sklearn.ensemble import HistGradientBoostingRegressor

        mp = pytest.MonkeyPatch()
        rng = np.random.default_rng(7)

        def dataset(engine, anios, horizonte=3):
            filas = []
            for t in anios:
                n = 120
                d = pd.DataFrame({"cod": [f"31{i:03d}" for i in range(n)], "anio_base": t})
                for c in ablacion.FEATURES:
                    d[c] = rng.normal(size=n)
                d["pob"] = rng.integers(100, 20000, n).astype(float)
                d[ablacion.TARGET] = 2 * d["log_pob"] + rng.normal(scale=2.0, size=n)
                filas.append(d)
            return pd.concat(filas, ignore_index=True)

        def noticias(engine, anios, poblacion, anios_train=None):
            out = poblacion[["cod", "anio_base"]].copy()
            for c in FEATURES_NOTICIAS:  # ruido sin relación con el target
                out[c] = rng.normal(size=len(out))
            return out

        mp.setattr(ablacion, "construir_dataset", dataset)
        mp.setattr(ablacion, "calcular_noticias", noticias)
        mp.setattr(ablacion, "_registrar", lambda r: None)
        mp.setattr(ablacion, "cobertura", lambda engine: 200)  # la puerta §6 se prueba aparte
        mp.setattr(ablacion, "nuevo_modelo", lambda: HistGradientBoostingRegressor(max_iter=30))
        mp.setattr(ablacion, "N_BOOTSTRAP", 200)
        try:
            yield ablacion.ablacion(None)
        finally:
            mp.undo()

    def test_rechaza(self, ablacion_sobre_ruido):
        assert ablacion_sobre_ruido["decision"] == "rechazar"
        assert ablacion_sobre_ruido["aportan_senal"] is False

    def test_no_alcanza_la_mejora_minima(self, ablacion_sobre_ruido):
        assert ablacion_sobre_ruido["cond_mejora_minima"] is False

    def test_informa_de_los_tres_brazos(self, ablacion_sobre_ruido):
        for k in ("mae_sin", "mae_con", "mae_permutadas"):
            assert ablacion_sobre_ruido[k] > 0


class TestPuertaDeCobertura:
    """ADR 0005 §6: con menos de 60 municipios cubiertos no se compara nada."""

    def test_cancela_cuando_la_cobertura_es_insuficiente(self, monkeypatch):
        monkeypatch.setattr(ablacion, "cobertura", lambda engine: 59)
        monkeypatch.setattr(ablacion, "_registrar", lambda r: None)
        r = ablacion.ablacion(None)
        assert r["decision"] == "cancelar"
        assert r["aportan_senal"] is False
        assert "59" in r["motivo"]

    def test_el_minimo_es_el_del_adr(self):
        assert ablacion.MIN_MUNICIPIOS_COBERTURA == 60

    def test_no_entrena_nada_si_cancela(self, monkeypatch):
        """Cancelar debe cortar antes del ajuste: si entrenara, el número existiría y
        alguien acabaría publicándolo."""
        monkeypatch.setattr(ablacion, "cobertura", lambda engine: 10)
        monkeypatch.setattr(ablacion, "_registrar", lambda r: None)

        def explota(*a, **k):
            raise AssertionError("no debería construir el dataset si la puerta cierra")

        monkeypatch.setattr(ablacion, "construir_dataset", explota)
        assert ablacion.ablacion(None)["decision"] == "cancelar"
