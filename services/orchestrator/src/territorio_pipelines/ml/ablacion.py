"""Ablación de las features de prensa: ¿aportan señal o no?

Aplica **literalmente** el criterio que el ADR 0005 (`docs/adr/0005-capa-de-noticias-y-llm.md`)
dejó escrito antes de ver ningún resultado. Este módulo no decide nada: evalúa tres
condiciones fijadas de antemano y devuelve si se cumplen. Si aquí se tocan los umbrales
se pierde lo único que hacía creíble el experimento, así que no se tocan.

Tres brazos, misma partición temporal y mismos hiperparámetros, semillas 0-4:

- **A · sin** — las features actuales del modelo.
- **B · con** — las actuales más las de prensa.
- **C · permutadas** — las actuales más las de prensa **barajadas entre municipios dentro
  del mismo año base**.

El brazo C es el que hace creíble el resultado. Conserva la distribución marginal de las
features de prensa y destruye solo su vínculo con el municipio: si B mejora sobre A pero C
mejora igual, lo medido es la capacidad del modelo de aprovechar ruido extra, no
información.

**Su MAE no es comparable con el del modelo bandera.** Años base 2018-2021, horizonte 3 y
solo el ámbito con cobertura de prensa. Los años base de producción son 2015-2020 y GDELT
arranca en 2017: comparar sobre la ventana de producción mediría el hueco de datos, no las
noticias. Por eso vive en su propio experimento de MLflow.
"""

from __future__ import annotations

import mlflow
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error
from sqlalchemy.engine import Engine

from .features import FEATURES, TARGET, construir_dataset
from .features_noticias import FEATURES_NOTICIAS, _leer_noticias
from .features_noticias import calcular as calcular_noticias
from .modelo import nuevo_modelo

#: Configuración fijada en el ADR 0005 §7. No se ajusta a lo que salga.
ANIOS_BASE = [2018, 2019, 2020, 2021]
ANIOS_TRAIN = [2018, 2019]
ANIOS_VAL = [2020, 2021]
HORIZONTE_ABL = 3
PROVINCIA = "31"
SEMILLAS = range(5)

#: Puerta previa del ADR 0005 §6: con menos cobertura que esto, cualquier métrica de
#: ablación sería ruido con formato de tabla, y la parte de ML se cancela.
MIN_MUNICIPIOS_COBERTURA = 60

#: Criterio de aceptación preinscrito (ADR 0005 §8). Las tres condiciones a la vez.
MEJORA_MINIMA_PP = 0.20
N_BOOTSTRAP = 1000

EXPERIMENTO_ABL = "noticias-ablacion"

#: Estratos de población. Son INFORMATIVOS: el criterio del ADR no está estratificado.
ESTRATOS = {
    "<500": (0, 500),
    "500-2000": (500, 2000),
    "2000-10000": (2000, 10000),
    ">10000": (10000, float("inf")),
}


def permutar(df: pd.DataFrame, columnas: list[str], semilla: int) -> pd.DataFrame:
    """Baraja `columnas` entre municipios **dentro de cada año base**.

    Dentro del año y no globalmente: si se barajara entre años se destruiría también la
    tendencia temporal de la cobertura de prensa, y el brazo placebo saldría más fácil de
    batir de lo que debe. Lo único que tiene que romperse es la correspondencia entre un
    municipio y sus noticias.
    """
    out = df.copy()
    rng = np.random.default_rng(semilla)
    for _t, idx in out.groupby("anio_base").groups.items():
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
    """IC del 95 % de la media de `dif` por remuestreo de municipios (ADR 0005 §8.3)."""
    rng = np.random.default_rng(semilla)
    n = len(dif)
    medias = [rng.choice(dif, size=n, replace=True).mean() for _ in range(N_BOOTSTRAP)]
    return float(np.percentile(medias, 2.5)), float(np.percentile(medias, 97.5))


def _por_estrato(va: pd.DataFrame, err_a: np.ndarray, err_b: np.ndarray) -> dict[str, dict]:
    """Desglose informativo por tamaño de municipio. No entra en el criterio."""
    pob = va["pob"].to_numpy()
    salida = {}
    for nombre, (lo, hi) in ESTRATOS.items():
        m = (pob >= lo) & (pob < hi)
        if not m.any():
            continue
        salida[nombre] = {
            "n": int(m.sum()),
            "mae_sin": round(float(err_a[m].mean()), 3),
            "mae_con": round(float(err_b[m].mean()), 3),
        }
    return salida


def cobertura(engine: Engine) -> int:
    """Municipios del ámbito con al menos un artículo atribuido (ADR 0005 §6)."""
    noticias = _leer_noticias(engine)
    if noticias.empty:
        return 0
    con_articulos = noticias[(noticias["cod"].str[:2] == PROVINCIA) & (noticias["n_noticias"] > 0)]
    return int(con_articulos["cod"].nunique())


def ablacion(engine: Engine) -> dict:
    """Corre los tres brazos y evalúa el criterio. Devuelve métricas y veredicto.

    Antes de medir nada comprueba la puerta del ADR §6: si la cobertura de prensa no
    llega al mínimo preinscrito, no se compara — se cancela y se dice por qué.
    """
    n_cobertura = cobertura(engine)
    if n_cobertura < MIN_MUNICIPIOS_COBERTURA:
        cancelado = {
            "decision": "cancelar",
            "motivo": (
                f"cobertura insuficiente: {n_cobertura} municipios con artículos, "
                f"mínimo preinscrito {MIN_MUNICIPIOS_COBERTURA} (ADR 0005 §6)"
            ),
            "n_municipios_con_cobertura": n_cobertura,
            "aportan_senal": False,
        }
        _registrar(cancelado)
        return cancelado

    df = construir_dataset(engine, ANIOS_BASE, HORIZONTE_ABL)
    df = df[df["cod"].str[:2] == PROVINCIA]
    df = df[df[TARGET].notna() & df["pob"].notna()]
    if df.empty:
        raise RuntimeError(f"sin datos para la ablación en la provincia {PROVINCIA}")

    pob = df[["cod", "anio_base", "pob"]]
    feats = calcular_noticias(engine, ANIOS_BASE, pob, anios_train=ANIOS_TRAIN)
    df = df.merge(feats, on=["cod", "anio_base"], how="left")

    cols_a = FEATURES
    cols_b = FEATURES + FEATURES_NOTICIAS
    tr, va = df[df["anio_base"].isin(ANIOS_TRAIN)], df[df["anio_base"].isin(ANIOS_VAL)]
    if tr.empty or va.empty:
        raise RuntimeError(f"partición vacía: train={len(tr)}, val={len(va)}")

    mae_a, err_a = _mae_por_semilla(tr, va, cols_a)
    mae_b, err_b = _mae_por_semilla(tr, va, cols_b)

    # El placebo se promedia sobre varias permutaciones: una sola podría salir buena o
    # mala por azar, y entonces el brazo de control sería tan ruidoso como lo que mide.
    maes_c = []
    for s in SEMILLAS:
        barajado = permutar(df, FEATURES_NOTICIAS, semilla=s)
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
    aportan = bool(cond_mejora and cond_placebo and cond_ic)

    resultado = {
        "mae_sin": round(mae_a, 3),
        "mae_con": round(mae_b, 3),
        "mae_permutadas": round(mae_c, 3),
        "delta_real": round(delta_real, 3),
        "delta_placebo": round(delta_placebo, 3),
        "ic95_bajo": round(ic_bajo, 3),
        "ic95_alto": round(ic_alto, 3),
        "n_train": len(tr),
        "n_val": len(va),
        "n_municipios": int(df["cod"].nunique()),
        "n_municipios_con_cobertura": n_cobertura,
        "cond_mejora_minima": bool(cond_mejora),
        "cond_placebo_no_reproduce": bool(cond_placebo),
        "cond_ic_excluye_cero": bool(cond_ic),
        "aportan_senal": aportan,
        "decision": "aceptar" if aportan else "rechazar",
        "estratos": _por_estrato(va, err_a, err_b),
    }
    _registrar(resultado)
    return resultado


def _registrar(r: dict) -> None:
    """Deja el resultado en su propio experimento de MLflow, con el aviso incluido."""
    mlflow.set_experiment(EXPERIMENTO_ABL)
    with mlflow.start_run(run_name="ablacion_noticias"):
        mlflow.log_params(
            {
                "anios_base": str(ANIOS_BASE),
                "horizonte": HORIZONTE_ABL,
                "provincia": PROVINCIA,
                "mejora_minima_pp": MEJORA_MINIMA_PP,
                "n_bootstrap": N_BOOTSTRAP,
                "decision": r["decision"],
                "motivo": r.get("motivo", ""),
                "aviso": "MAE no comparable con el modelo bandera (ADR 0005 §7)",
            }
        )
        mlflow.log_metrics(
            {k: v for k, v in r.items() if isinstance(v, int | float) and not isinstance(v, bool)}
        )
