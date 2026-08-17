"""Tests de la ablación. Sin base de datos y sin red: datos sintéticos.

Lo que se comprueba aquí no es que la ablación dé un número, sino que **no pueda dar el
número equivocado**: que el brazo permutado conserve la distribución y rompa el vínculo,
y que el criterio de aceptación diga que no cuando no hay señal. Un experimento cuyo
criterio se cumple por construcción no mide nada.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from territorio_pipelines.ml import ablacion, noticias


def _df(n_por_anio: int = 40) -> pd.DataFrame:
    rng = np.random.default_rng(0)
    filas = []
    for t in ablacion.ANIOS_BASE:
        d = pd.DataFrame(
            {
                "cod": [f"31{i:03d}" for i in range(n_por_anio)],
                "anio_base": t,
                "noticias_1000hab": rng.normal(size=n_por_anio),
                "noticias_signo": rng.normal(size=n_por_anio),
                "noticias_pct_negativas": rng.uniform(0, 100, n_por_anio),
                "noticias_pct_economicas": rng.uniform(0, 100, n_por_anio),
            }
        )
        filas.append(d)
    return pd.concat(filas, ignore_index=True)


def test_permutar_conserva_la_distribucion():
    """Si el placebo cambiara los valores, no sería un placebo: sería otro experimento."""
    df = _df()
    out = ablacion.permutar(df, noticias.FEATURES_NOTICIAS, semilla=1)
    for t in ablacion.ANIOS_BASE:
        antes = np.sort(df.loc[df["anio_base"] == t, "noticias_signo"].to_numpy())
        despues = np.sort(out.loc[out["anio_base"] == t, "noticias_signo"].to_numpy())
        assert np.allclose(antes, despues)


def test_permutar_rompe_el_vinculo_con_el_municipio():
    df = _df()
    out = ablacion.permutar(df, noticias.FEATURES_NOTICIAS, semilla=1)
    iguales = (df["noticias_signo"].to_numpy() == out["noticias_signo"].to_numpy()).mean()
    assert iguales < 0.5, "la permutación apenas movió nada"


def test_permutar_no_mezcla_anios():
    """Barajar entre años destruiría también la tendencia temporal de la cobertura, y el
    placebo saldría más fácil de batir de lo que debe."""
    df = _df()
    out = ablacion.permutar(df, noticias.FEATURES_NOTICIAS, semilla=3)
    assert (df["anio_base"].to_numpy() == out["anio_base"].to_numpy()).all()
    for t in ablacion.ANIOS_BASE:
        conjunto_antes = set(np.round(df.loc[df["anio_base"] == t, "noticias_signo"], 9))
        conjunto_despues = set(np.round(out.loc[out["anio_base"] == t, "noticias_signo"], 9))
        assert conjunto_antes == conjunto_despues


def test_permutar_mueve_todas_las_columnas_a_la_vez():
    """Las cuatro features de un municipio deben viajar juntas: si se barajaran por
    separado, el brazo placebo tendría combinaciones que no existen en los datos."""
    df = _df()
    out = ablacion.permutar(df, noticias.FEATURES_NOTICIAS, semilla=5)
    primera = df[df["anio_base"] == ablacion.ANIOS_BASE[0]]
    salida = out[out["anio_base"] == ablacion.ANIOS_BASE[0]]
    pares_orig = {tuple(np.round(r, 9)) for r in primera[noticias.FEATURES_NOTICIAS].to_numpy()}
    pares_perm = {tuple(np.round(r, 9)) for r in salida[noticias.FEATURES_NOTICIAS].to_numpy()}
    assert pares_orig == pares_perm


def test_el_ic_bootstrap_incluye_el_cero_cuando_no_hay_diferencia():
    """Con dos brazos idénticos la diferencia es ruido centrado en cero, y el criterio
    debe reflejarlo. Si el IC excluyera el cero aquí, el experimento aprobaría cualquier
    cosa."""
    rng = np.random.default_rng(0)
    dif = rng.normal(scale=1.0, size=200)
    bajo, alto = ablacion._ic_bootstrap(dif)
    assert bajo < 0 < alto


def test_el_ic_bootstrap_excluye_el_cero_ante_una_diferencia_real():
    rng = np.random.default_rng(0)
    dif = rng.normal(loc=1.0, scale=0.5, size=200)
    bajo, alto = ablacion._ic_bootstrap(dif)
    assert bajo > 0


def test_los_umbrales_son_los_del_adr():
    """Si alguien los relaja tras ver el resultado, el experimento deja de valer. Este
    test existe para que ese cambio no pase inadvertido en una revisión."""
    assert ablacion.MEJORA_MINIMA_PP == 0.20
    assert ablacion.N_BOOTSTRAP == 1000
    assert ablacion.HORIZONTE == 3
    assert ablacion.ANIOS_BASE == [2018, 2019, 2020, 2021]
    assert list(ablacion.SEMILLAS) == [0, 1, 2, 3, 4]
