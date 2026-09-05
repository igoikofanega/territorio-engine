"""Tests de las features de noticias para ML. Sin BD, sin red.

Lo importante es que la ventana temporal sea estricta (anti-leakage) y que los valores
tengan sentido: noticias_exceso mide el residuo, no la cobertura bruta.
"""

from __future__ import annotations

import pandas as pd
import pytest

from territorio_pipelines.ml.features_noticias import (
    FEATURES_NOTICIAS,
    calcular,
)


def _noticias() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "cod": ["31001"] * 4 + ["31201"] * 4,
            "anio": [2018, 2019, 2020, 2021] * 2,
            "n_noticias": [0, 2, 5, 3, 10, 20, 30, 40],
            "n_positivas": [0, 1, 2, 1, 5, 8, 12, 15],
            "n_negativas": [0, 0, 1, 1, 2, 5, 8, 10],
            "n_empleo": [0, 0, 1, 0, 3, 5, 8, 10],
            "n_empresa": [0, 1, 0, 1, 1, 2, 3, 5],
        }
    )


def _poblacion(anios: list[int]) -> pd.DataFrame:
    filas = []
    for t in anios:
        filas.append({"cod": "31001", "anio_base": t, "pob": 200.0})
        filas.append({"cod": "31201", "anio_base": t, "pob": 40000.0})
    return pd.DataFrame(filas)


class TestCalcular:
    def test_devuelve_todas_las_features(self):
        pob = _poblacion([2020])
        result = calcular(None, [2020], pob, anios_train=[2020], noticias_df=_noticias())
        for f in FEATURES_NOTICIAS:
            assert f in result.columns

    def test_municipio_sin_noticias_tiene_exceso_cero(self):
        noticias = _noticias()
        noticias = noticias[noticias["cod"] == "31201"]
        pob = pd.DataFrame([{"cod": "99999", "anio_base": 2020, "pob": 500.0}])
        result = calcular(None, [2020], pob, anios_train=[2020], noticias_df=noticias)
        assert result.iloc[0]["noticias_inversion_1000"] == 0.0
        assert result.iloc[0]["noticias_cierre_1000"] == 0.0

    def test_saldo_nan_con_pocos_eventos(self):
        noticias = pd.DataFrame(
            [
                {
                    "cod": "31001",
                    "anio": 2020,
                    "n_noticias": 2,
                    "n_positivas": 1,
                    "n_negativas": 0,
                    "n_empleo": 0,
                    "n_empresa": 0,
                }
            ]
        )
        pob = pd.DataFrame([{"cod": "31001", "anio_base": 2020, "pob": 200.0}])
        result = calcular(None, [2020], pob, anios_train=[2020], noticias_df=noticias)
        assert pd.isna(result.iloc[0]["noticias_saldo"])

    def test_saldo_definido_con_suficientes_eventos(self):
        noticias = pd.DataFrame(
            [
                {
                    "cod": "31001",
                    "anio": 2020,
                    "n_noticias": 10,
                    "n_positivas": 7,
                    "n_negativas": 3,
                    "n_empleo": 2,
                    "n_empresa": 1,
                }
            ]
        )
        pob = pd.DataFrame([{"cod": "31001", "anio_base": 2020, "pob": 200.0}])
        result = calcular(None, [2020], pob, anios_train=[2020], noticias_df=noticias)
        saldo = result.iloc[0]["noticias_saldo"]
        assert not pd.isna(saldo)
        assert abs(saldo - 0.4) < 0.01  # (7-3)/10

    def test_sin_noticias_devuelve_nan(self):
        pob = _poblacion([2020])
        result = calcular(
            None,
            [2020],
            pob,
            anios_train=[2020],
            noticias_df=pd.DataFrame(
                columns=[
                    "cod",
                    "anio",
                    "n_noticias",
                    "n_positivas",
                    "n_negativas",
                    "n_empleo",
                    "n_empresa",
                ]
            ),
        )
        for f in FEATURES_NOTICIAS:
            assert result[f].isna().all()


class TestAntiLeakage:
    def test_ventana_no_incluye_futuro(self):
        """Features del año base T usan solo artículos de [T-VENTANA, T]."""
        noticias = pd.DataFrame(
            [
                {
                    "cod": "31001",
                    "anio": 2019,
                    "n_noticias": 5,
                    "n_positivas": 3,
                    "n_negativas": 1,
                    "n_empleo": 1,
                    "n_empresa": 0,
                },
                {
                    "cod": "31001",
                    "anio": 2020,
                    "n_noticias": 10,
                    "n_positivas": 5,
                    "n_negativas": 2,
                    "n_empleo": 3,
                    "n_empresa": 1,
                },
                {
                    "cod": "31001",
                    "anio": 2021,
                    "n_noticias": 100,
                    "n_positivas": 50,
                    "n_negativas": 20,
                    "n_empleo": 30,
                    "n_empresa": 10,
                },
            ]
        )
        pob = pd.DataFrame([{"cod": "31001", "anio_base": 2020, "pob": 1000.0}])
        result = calcular(None, [2020], pob, anios_train=[2020], noticias_df=noticias)
        inv = result.iloc[0]["noticias_inversion_1000"]
        # Con ventana [2018, 2020], solo se ven 2019 y 2020: empleo = 1+3 = 4
        # Si incluyese 2021, empleo sería 34 (=1+3+30). La diferencia es 8.5x.
        assert inv < 10, "feature incluye datos del futuro (2021)"

    def test_ventana_incluye_anios_anteriores(self):
        noticias = pd.DataFrame(
            [
                {
                    "cod": "31001",
                    "anio": 2018,
                    "n_noticias": 5,
                    "n_positivas": 2,
                    "n_negativas": 1,
                    "n_empleo": 2,
                    "n_empresa": 0,
                },
                {
                    "cod": "31001",
                    "anio": 2020,
                    "n_noticias": 3,
                    "n_positivas": 1,
                    "n_negativas": 1,
                    "n_empleo": 1,
                    "n_empresa": 0,
                },
            ]
        )
        pob = pd.DataFrame([{"cod": "31001", "anio_base": 2020, "pob": 1000.0}])
        result = calcular(None, [2020], pob, anios_train=[2020], noticias_df=noticias)
        inv = result.iloc[0]["noticias_inversion_1000"]
        # Ventana [2018, 2020]: empleo = 2+1 = 3, pob/1000 = 1 → inv = 3.0
        assert inv == pytest.approx(3.0, abs=0.1)


class TestExceso:
    def test_exceso_es_residuo_no_cobertura(self):
        """Dos municipios con la misma cobertura relativa deben tener exceso similar."""
        noticias = pd.DataFrame(
            [
                {
                    "cod": "A",
                    "anio": 2020,
                    "n_noticias": 10,
                    "n_positivas": 5,
                    "n_negativas": 3,
                    "n_empleo": 2,
                    "n_empresa": 1,
                },
                {
                    "cod": "B",
                    "anio": 2020,
                    "n_noticias": 100,
                    "n_positivas": 50,
                    "n_negativas": 30,
                    "n_empleo": 20,
                    "n_empresa": 10,
                },
            ]
        )
        pob = pd.DataFrame(
            [
                {"cod": "A", "anio_base": 2020, "pob": 1000.0},
                {"cod": "B", "anio_base": 2020, "pob": 10000.0},
            ]
        )
        result = calcular(None, [2020], pob, anios_train=[2020], noticias_df=noticias)
        excesos = result.set_index("cod")["noticias_exceso"]
        # Ambos tienen 10 noticias por cada 1000 hab; el exceso debería ser parecido
        assert abs(excesos["A"] - excesos["B"]) < 1.0
