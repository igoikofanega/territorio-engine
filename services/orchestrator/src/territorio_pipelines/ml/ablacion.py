"""Ablación de las features de prensa: ¿aportan señal o no?

Implementa **literalmente** el criterio que el ADR 0005 dejó escrito antes de ver ningún
resultado. El código no decide nada: aplica tres condiciones fijadas de antemano y
devuelve si se cumplen. Si aquí se tocan los umbrales, se pierde lo único que hacía
creíble el experimento.

Tres brazos, misma partición temporal y mismos hiperparámetros:

- **A · sin** — las features actuales del modelo.
- **B · con** — las actuales más las de prensa.
- **C · permutadas** — las actuales más las de prensa **barajadas entre municipios dentro
  del mismo año base**.

El brazo C es el que hace creíble el resultado. Conserva la distribución marginal de las
features de prensa y destruye solo su vínculo con el municipio: si B mejora sobre A pero C
mejora igual, lo medido es la capacidad del modelo de aprovechar ruido extra, no
información.

**Configuración propia, y su MAE no es comparable con el del modelo bandera.** Años base
2018-2021, horizonte 3 y solo el ámbito con cobertura de prensa. Los años base del modelo
de producción son 2015-2020 y GDELT arranca en 2017: comparar sobre la ventana de
producción mediría el hueco de datos, no las noticias.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error
from sqlalchemy.engine import Engine

from . import noticias as noti
from .features import FEATURES, TARGET, construir_dataset
from .modelo import nuevo_modelo

#: Configuración fijada en el ADR 0005. No se ajusta a lo que salga.
ANIOS_BASE = [2018, 2019, 2020, 2021]
ANIOS_TRAIN = [2018, 2019]
ANIOS_VAL = [2020, 2021]
HORIZONTE = 3
PROVINCIA = "31"
SEMILLAS = range(5)

#: Criterio de aceptación preinscrito (ADR 0005). Las tres condiciones a la vez.
MEJORA_MINIMA_PP = 0.20
N_BOOTSTRAP = 1000

EXPERIMENTO = "noticias-ablacion"


def permutar(df: pd.DataFrame, columnas: list[str], semilla: int) -> pd.DataFrame:
    """Baraja `columnas` entre municipios **dentro de cada año base**.

    Dentro del año y no globalmente: si se barajara entre años se destruiría también la
    tendencia temporal de la cobertura de prensa, y el brazo placebo saldría más fácil de
    batir de lo que debe. Lo único que tiene que romperse es la correspondencia entre un
    municipio y sus noticias.
    """
    out = df.copy()
    rng = np.random.default_rng(semilla)
    for t, idx in out.groupby("anio_base").groups.items():  # noqa: B007 — `t` documenta el grupo
        orden = rng.permutation(len(idx))
        out.loc[idx, columnas] = out.loc[idx, columnas].to_numpy()[orden]
    return out


def _mae_por_semilla(
    tr: pd.DataFrame, va: pd.DataFrame, cols: list[str]
) -> tuple[float, np.ndarray]:
    """MAE medio sobre las semillas, y error absoluto por fila promediado sobre ellas.

    El error por fila se promedia y no se toma el del último ajuste: el bootstrap del
    criterio compara municipio a municipio, y hacerlo sobre una sola semilla metería en
    el intervalo la varianza del ajuste, no la de los datos.
    """
    maes = []
    y = va[TARGET].to_numpy()
    errores = np.zeros(len(y))
    semillas = list(SEMILLAS)
    for s in semillas:
        m = nuevo_modelo()
        m.set_params(random_state=s)
        m.fit(tr[cols], tr[TARGET])
        pred = m.predict(va[cols])
        maes.append(mean_absolute_error(y, pred))
        errores += np.abs(y - pred)
    return float(np.mean(maes)), errores / len(semillas)


def _ic_bootstrap(dif: np.ndarray, semilla: int = 0) -> tuple[float, float]:
    """IC del 95 % de la media de `dif` por remuestreo de municipios."""
    rng = np.random.default_rng(semilla)
    n = len(dif)
    medias = [rng.choice(dif, size=n, replace=True).mean() for _ in range(N_BOOTSTRAP)]
    return float(np.percentile(medias, 2.5)), float(np.percentile(medias, 97.5))


def ejecutar(engine: Engine) -> dict:
    """Corre los tres brazos y evalúa el criterio. Devuelve las métricas y el veredicto."""
    df = construir_dataset(engine, ANIOS_BASE, HORIZONTE)
    df = df[df["cod"].str[:2] == PROVINCIA]
    df = df[df[TARGET].notna()]
    if df.empty:
        raise RuntimeError(f"sin datos para la ablación en la provincia {PROVINCIA}")

    pob = df[["cod", "anio_base", "pob"]].rename(columns={"anio_base": "anio"})
    feats = noti.construir(engine, ANIOS_BASE, PROVINCIA, pob)
    df = df.merge(feats, on=["cod", "anio_base"], how="left")

    cols_a = FEATURES
    cols_b = FEATURES + noti.FEATURES_NOTICIAS
    tr, va = df[df["anio_base"].isin(ANIOS_TRAIN)], df[df["anio_base"].isin(ANIOS_VAL)]
    if tr.empty or va.empty:
        raise RuntimeError(f"partición vacía: train={len(tr)}, val={len(va)}")

    mae_a, err_a = _mae_por_semilla(tr, va, cols_a)
    mae_b, err_b = _mae_por_semilla(tr, va, cols_b)

    # El placebo se promedia sobre varias permutaciones: una sola podría salir buena o
    # mala por azar, y entonces el brazo de control sería tan ruidoso como lo que mide.
    maes_c = []
    for s in SEMILLAS:
        barajado = permutar(df, noti.FEATURES_NOTICIAS, semilla=s)
        tr_c = barajado[barajado["anio_base"].isin(ANIOS_TRAIN)]
        va_c = barajado[barajado["anio_base"].isin(ANIOS_VAL)]
        maes_c.append(_mae_por_semilla(tr_c, va_c, cols_b)[0])
    mae_c = float(np.mean(maes_c))

    delta_real = mae_a - mae_b
    delta_placebo = mae_a - mae_c
    ic_bajo, ic_alto = _ic_bootstrap(err_a - err_b)

    cond_mejora = delta_real >= MEJORA_MINIMA_PP
    cond_placebo = delta_placebo < delta_real / 2
    cond_ic = ic_bajo > 0 or ic_alto < 0
    return {
        "mae_sin": round(mae_a, 3),
        "mae_con": round(mae_b, 3),
        "mae_permutadas": round(mae_c, 3),
        "delta_real": round(delta_real, 3),
        "delta_placebo": round(delta_placebo, 3),
        "ic95_bajo": round(ic_bajo, 3),
        "ic95_alto": round(ic_alto, 3),
        "n_train": len(tr),
        "n_val": len(va),
        "cond_mejora_minima": bool(cond_mejora),
        "cond_placebo_no_reproduce": bool(cond_placebo),
        "cond_ic_excluye_cero": bool(cond_ic),
        "aportan_senal": bool(cond_mejora and cond_placebo and cond_ic),
    }
