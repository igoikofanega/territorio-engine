"""Tests de la evaluación. Sin base de datos y sin red: datos sintéticos.

Lo que se protege aquí son las propiedades que hacen que el número signifique algo:
que ningún pliegue entrene con el futuro, que un pliegue degenerado se descarte en vez
de rellenarse, y que el semáforo no se mida sobre los mismos datos con los que se calibra.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from territorio_pipelines.ml import evaluacion as ev


def _residuos(n: int = 400) -> pd.DataFrame:
    rng = np.random.default_rng(0)
    pob = rng.choice([120.0, 800.0, 4000.0, 30000.0], size=n)
    error = rng.normal(size=n)
    return pd.DataFrame(
        {
            "cod": [f"{31000 + i:05d}" for i in range(n)],
            "pob": pob,
            "cod_provincia": rng.choice(["31", "26", "42"], size=n),
            "real": error * 2,
            "pred": error,
            "error": error,
            "abs_error": np.abs(error),
        }
    )


class TestErrorPorEstrato:
    def test_cubre_los_estratos_presentes(self):
        salida = ev.error_por_estrato(_residuos())
        assert {d["estrato"] for d in salida} == set(ev.ESTRATOS)

    def test_no_inventa_estratos_vacios(self):
        solo_pequenos = _residuos()
        solo_pequenos = solo_pequenos[solo_pequenos["pob"] < 500]
        salida = ev.error_por_estrato(solo_pequenos)
        assert [d["estrato"] for d in salida] == ["<500"]

    def test_el_mae_es_no_negativo(self):
        assert all(d["mae"] >= 0 for d in ev.error_por_estrato(_residuos()))


class TestErrorPorProvincia:
    def test_ordena_de_mejor_a_peor(self):
        salida = ev.error_por_provincia(_residuos())
        assert salida["mejores"][0]["mae"] <= salida["peores"][0]["mae"]

    def test_descarta_provincias_con_pocos_municipios(self):
        d = _residuos(30)
        d["cod_provincia"] = [f"{i:02d}" for i in range(len(d))]  # 1 municipio cada una
        salida = ev.error_por_provincia(d)
        assert salida["mejores"] == [] and salida["peores"] == []


class TestFiabilidad:
    def test_un_modelo_perfectamente_calibrado_cae_en_la_diagonal(self):
        rng = np.random.default_rng(0)
        p = rng.uniform(0, 1, 20000)
        y = (rng.uniform(0, 1, 20000) < p).astype(int)
        for tramo in ev._fiabilidad(y, p):
            assert abs(tramo["prob_media"] - tramo["frec_observada"]) < 0.05

    def test_detecta_el_exceso_de_confianza(self):
        """Un modelo que promete 0,9 cuando ocurre 0,3 tiene que verse en el diagrama."""
        p = np.full(500, 0.9)
        y = np.zeros(500, dtype=int)
        y[:150] = 1
        tramos = ev._fiabilidad(y, p)
        assert tramos[-1]["prob_media"] > tramos[-1]["frec_observada"] + 0.5

    def test_ignora_los_tramos_sin_municipios(self):
        p = np.full(100, 0.05)
        y = np.zeros(100, dtype=int)
        assert len(ev._fiabilidad(y, p)) == 1


class TestBacktestRodante:
    """El backtest se ejerce entero contra un `construir_dataset` sintético."""

    @staticmethod
    def _dataset(anios: list[int], hueco_en: list[int] | None = None) -> pd.DataFrame:
        rng = np.random.default_rng(1)
        hueco_en = hueco_en or []
        filas = []
        for t in anios:
            n = 150
            d = pd.DataFrame({"cod": [f"{31000 + i:05d}" for i in range(n)], "anio_base": t})
            for c in ev.FEATURES:
                d[c] = rng.normal(size=n)
            # crec_prev3 es un cociente de poblaciones: siempre positivo y cerca de 1.
            # El baseline de tendencia lo eleva a una potencia fraccionaria.
            d["crec_prev3"] = 1 + rng.normal(scale=0.05, size=n)
            if t in hueco_en:
                d["crec_prev3"] = np.nan
            d["pob"] = rng.integers(100, 30000, n).astype(float)
            d["cod_provincia"] = "31"
            d[ev.TARGET] = 2 * d["log_pob"] + rng.normal(scale=2.0, size=n)
            filas.append(d)
        return pd.concat(filas, ignore_index=True)

    def _correr(self, monkeypatch, folds, hueco_en=None):
        monkeypatch.setattr(ev.cal, "folds_rodantes", lambda e, h, embargo=1: folds)
        monkeypatch.setattr(
            ev, "construir_dataset", lambda e, anios: self._dataset(anios, hueco_en)
        )
        monkeypatch.setattr(
            ev,
            "nuevo_modelo",
            lambda: __import__("sklearn.ensemble", fromlist=["x"]).HistGradientBoostingRegressor(
                max_iter=20
            ),
        )
        return ev.backtest_rodante(None, embargo=1)

    def test_un_pliegue_por_anio_de_validacion(self, monkeypatch):
        r = self._correr(monkeypatch, [([2015, 2016], 2017), ([2015, 2016, 2017], 2018)])
        assert r["n_pliegues"] == 2
        assert [p["anio_val"] for p in r["pliegues"]] == [2017, 2018]

    def test_nunca_entrena_con_el_anio_de_validacion(self, monkeypatch):
        r = self._correr(monkeypatch, [([2015, 2016], 2017)])
        for p in r["pliegues"]:
            assert p["anio_val"] not in p["anios_train"]
            assert max(p["anios_train"]) < p["anio_val"]

    def test_descarta_el_pliegue_con_una_feature_vacia(self, monkeypatch):
        """Rellenar ese hueco sería inventar datos; descartarlo y decirlo, no."""
        r = self._correr(monkeypatch, [([2015], 2016), ([2015, 2016], 2017)], hueco_en=[2015])
        assert r["n_pliegues"] == 1
        assert r["descartados"][0]["anio_val"] == 2016
        assert "crec_prev3" in r["descartados"][0]["motivo"]

    def test_informa_dispersion_no_solo_media(self, monkeypatch):
        r = self._correr(monkeypatch, [([2015, 2016], 2017), ([2015, 2016, 2017], 2018)])
        for k in ("mae_media", "mae_desviacion", "mae_min", "mae_max"):
            assert k in r
        assert r["mae_min"] <= r["mae_media"] <= r["mae_max"]

    def test_sin_pliegues_devuelve_vacio_sin_reventar(self, monkeypatch):
        monkeypatch.setattr(ev.cal, "folds_rodantes", lambda e, h, embargo=1: [])
        r = ev.backtest_rodante(None, embargo=5)
        assert r["n_pliegues"] == 0 and r["residuos"] is None

    def test_devuelve_los_baselines_en_cada_pliegue(self, monkeypatch):
        r = self._correr(monkeypatch, [([2015, 2016], 2017)])
        p = r["pliegues"][0]
        assert p["mae_persistencia"] > 0 and p["mae_tendencia"] > 0


class TestCalibracionRiesgo:
    def test_exige_tres_anios_base(self, monkeypatch):
        monkeypatch.setattr(ev.cal, "anios_backtest", lambda e, h: ([2015, 2016], [], []))
        with pytest.raises(RuntimeError, match="3 años base"):
            ev.calibracion_riesgo(None)
