"""Que ninguna feature del año base T proceda de un año posterior a T.

Este fichero existe por un fallo real: `pct_extranjeros` se leía con
`DISTINCT ON ... ORDER BY anio DESC`, es decir el valor MÁS RECIENTE, y se aplicaba a
todos los años base incluidos los de entrenamiento. Medido sobre la base de datos real,
la correlación de esa feature con el cambio de población 2015→2020 subía de 0,159 (valor
contemporáneo de 2015) a 0,275 (valor de 2022): un 73% de señal que venía de mirar al
futuro, no del municipio.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from territorio_pipelines.ml import features as f

MUNICIPIOS = ["31001", "31002", "31003"]
ANIOS = list(range(2015, 2024))


def _tablas() -> dict[str, pd.DataFrame]:
    """Fuentes sintéticas donde el año es distinguible dentro del propio valor.

    `pct_extranjeros` vale `anio - 2000`, así que leer el año equivocado se ve a simple
    vista: si para el año base 2015 aparece un 22, viene de 2022.
    """
    fma = pd.DataFrame(
        [
            {
                "cod": c,
                "anio": a,
                "pob": 1000 + i * 100 + (a - 2015),
                "paro": 50.0,
                "renta": 12000.0,
                "alquiler": 5.0,
            }
            for i, c in enumerate(MUNICIPIOS)
            for a in ANIOS
        ]
    )
    ext = pd.DataFrame(
        [
            {"cod": c, "anio": a, "pct_extranjeros": float(a - 2000)}
            for c in MUNICIPIOS
            for a in range(2015, 2023)  # la serie real acaba en 2022
        ]
    )
    return {
        "fma": fma,
        "dim": pd.DataFrame(
            [{"cod": c, "cod_provincia": "31", "superficie_km2": 10.0} for c in MUNICIPIOS]
        ),
        "env": pd.DataFrame(
            [{"cod": c, "anio": a, "envejecimiento": 100.0} for c in MUNICIPIOS for a in ANIOS]
        ),
        "prov": pd.DataFrame(
            [
                {
                    "cod_provincia": "31",
                    "anio": a,
                    "tasa_natalidad": 8.0,
                    "tasa_mortalidad": 9.0,
                }
                for a in ANIOS
            ]
        ),
        "clima": pd.DataFrame(
            [
                {
                    "cod": c,
                    "temp": 13.0,
                    "precip": 700.0,
                    "dias_despejados": 80.0,
                    "temp_min_media": 6.0,
                }
                for c in MUNICIPIOS
            ]
        ),
        "aisl": pd.DataFrame([{"cod": c, "km_salud": 5.0, "km_capital": 30.0} for c in MUNICIPIOS]),
        "ext": ext,
        "fib": pd.DataFrame([{"cod": c, "pct_fibra": 60.0} for c in MUNICIPIOS]),
    }


@pytest.fixture
def sin_bd(monkeypatch):
    monkeypatch.setattr(f, "_leer", lambda engine: _tablas())
    monkeypatch.setattr(f.cal, "ultimo_anio", lambda engine, col: 2022)
    return None


class TestAsof:
    def test_toma_el_valor_del_propio_anio_cuando_existe(self):
        ancho = f._asof(_tablas()["ext"], "pct_extranjeros", 2022)
        assert ancho.loc["31001", 2015] == 15.0
        assert ancho.loc["31001", 2019] == 19.0

    def test_arrastra_el_ultimo_conocido_hacia_adelante(self):
        # la serie acaba en 2022; para 2023 vale 2022, nunca un valor inventado
        ancho = f._asof(_tablas()["ext"], "pct_extranjeros", 2023)
        assert ancho.loc["31001", 2022] == 22.0
        assert ancho.loc["31001", 2023] == 22.0

    def test_nunca_arrastra_hacia_atras(self):
        # una serie que empieza en 2019 no puede rellenar 2015: eso sería mirar al futuro
        largo = pd.DataFrame(
            [{"cod": "31001", "anio": a, "pct_extranjeros": 1.0} for a in (2019, 2020)]
        )
        ancho = f._asof(largo, "pct_extranjeros", 2020)
        assert 2015 not in ancho.columns

    def test_serie_vacia_no_revienta(self):
        vacio = pd.DataFrame(columns=["cod", "anio", "pct_extranjeros"])
        assert f._asof(vacio, "pct_extranjeros", 2020).empty


class TestAntiFuga:
    def test_el_anio_base_no_recibe_datos_posteriores(self, sin_bd):
        df = f.construir_dataset(None, [2015, 2016, 2017])
        for t in (2015, 2016, 2017):
            fila = df[df["anio_base"] == t]
            esperado = float(t - 2000)
            assert (fila["pct_extranjeros"] == esperado).all(), (
                f"el año base {t} recibió pct_extranjeros de otro año: "
                f"{sorted(fila['pct_extranjeros'].unique())}"
            )

    def test_todos_los_anios_base_no_comparten_el_mismo_valor(self, sin_bd):
        # el fallo original hacía que TODOS los años base recibiesen el valor de 2022
        df = f.construir_dataset(None, [2015, 2020])
        valores = df.groupby("anio_base")["pct_extranjeros"].first()
        assert valores[2015] != valores[2020]

    def test_el_anio_de_prediccion_usa_el_ultimo_conocido(self, sin_bd):
        # 2023 no tiene dato propio: debe heredar el de 2022, no quedarse vacío
        df = f.construir_dataset(None, [2023], horizonte=5)
        assert (df["pct_extranjeros"] == 22.0).all()

    def test_el_target_mira_al_futuro_a_proposito(self, sin_bd):
        # contraste: el TARGET sí es posterior a T, y debe seguir siéndolo
        df = f.construir_dataset(None, [2015], horizonte=5)
        pob = _tablas()["fma"]
        p15 = pob[(pob["cod"] == "31001") & (pob["anio"] == 2015)]["pob"].iloc[0]
        p20 = pob[(pob["cod"] == "31001") & (pob["anio"] == 2020)]["pob"].iloc[0]
        fila = df[df["cod"] == "31001"].iloc[0]
        assert fila[f.TARGET] == pytest.approx((p20 / p15 - 1) * 100)

    def test_las_features_estaticas_siguen_presentes(self, sin_bd):
        # clima (normal climática) y fibra (foto sin histórico) no se desfasan: se declaran
        df = f.construir_dataset(None, [2015])
        assert df["temp"].notna().all()
        assert df["pct_fibra"].notna().all()

    def test_no_quedan_features_fuera_del_dataset(self, sin_bd):
        df = f.construir_dataset(None, [2018])
        faltan = [c for c in f.FEATURES if c not in df.columns]
        assert not faltan, f"features ausentes del dataset: {faltan}"

    def test_crec_prev3_solo_mira_hacia_atras(self, sin_bd):
        df = f.construir_dataset(None, [2015])
        # 2012 no existe en la serie sintética (empieza en 2015) → sin tendencia previa
        assert df["crec_prev3"].isna().all()
        assert not np.isfinite(df["crec_prev3"].to_numpy(dtype=float)).any()
