"""Municipios que desafían su destino: residuo out-of-sample del modelo.

Se entrena el mismo gradient boosting con los años base antiguos y se mide, en los
años de validación (futuro ya conocido), cuánto creció cada municipio POR ENCIMA o
POR DEBAJO de lo que sus características predecían. El residuo medio (puntos
porcentuales) y su z-score señalan a los que sobre-rinden ("algo tienen que no
medimos") y a los que bajo-rinden. No es causalidad: es una brújula para investigar.
"""

from __future__ import annotations

import numpy as np
from sqlalchemy.engine import Engine

from .. import calendario as cal
from .features import FEATURES, TARGET, construir_dataset
from .modelo import HORIZONTE, nuevo_modelo

UMBRAL_Z = 1.0  # |z| a partir del cual un municipio se considera fuera de lo esperado


def calcular_rendimiento(engine: Engine) -> list[dict]:
    """[{cod, residuo, z, n_obs, clasificacion}] con el residuo medio out-of-sample.

    Usa el mismo corte temporal que el modelo: el residuo solo es honesto si se mide
    sobre años que el modelo no vio al entrenar.
    """
    _, anios_train, anios_val = cal.anios_backtest(engine, HORIZONTE)
    if not anios_val:
        raise RuntimeError(f"no hay años suficientes para el backtest a {HORIZONTE} años")

    df = construir_dataset(engine, anios_train + anios_val)
    df = df[df[TARGET].notna() & df["pob"].notna()]
    tr = df[df["anio_base"].isin(anios_train)]
    va = df[df["anio_base"].isin(anios_val)].copy()

    modelo = nuevo_modelo()
    modelo.fit(tr[FEATURES], tr[TARGET])
    va["residuo"] = va[TARGET] - modelo.predict(va[FEATURES])

    g = va.groupby("cod").agg(residuo=("residuo", "mean"), n_obs=("residuo", "size")).reset_index()
    sd = float(g["residuo"].std()) or 1.0
    g["z"] = g["residuo"] / sd
    g["clasificacion"] = np.select(
        [g["z"] >= UMBRAL_Z, g["z"] <= -UMBRAL_Z], ["sobre", "bajo"], default="esperado"
    )
    return [
        {
            "cod": r.cod,
            "residuo": round(float(r.residuo), 2),
            "z": round(float(r.z), 2),
            "n_obs": int(r.n_obs),
            "clasificacion": r.clasificacion,
        }
        for r in g.itertuples(index=False)
    ]
