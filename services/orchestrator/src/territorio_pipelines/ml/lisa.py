"""Hot spots espaciales (LISA, Moran local): clusters que el coroplético no distingue.

Para una variable (crecimiento de población a 10 años, renta) se calcula el
estadístico de Moran local de cada municipio contra sus k vecinos geográficos.
Los significativos (p<0.05) se clasifican en: alto-alto (hot spot), bajo-bajo
(cold spot) y los outliers alto-bajo / bajo-alto. Detecta 'islas de prosperidad'
y 'vacíos contiguos' reales, separándolos del ruido.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

from .. import calendario as cal

K_VECINOS = 8
P_CORTE = 0.05

# Los años van parametrizados: se resuelven contra la cobertura real en `calcular_lisa`.
_SQL = {
    "crecimiento": """
        SELECT d.cod_municipio AS cod,
               ST_X(ST_Centroid(d.geom_25830)) AS x, ST_Y(ST_Centroid(d.geom_25830)) AS y,
               (b.pob_fin::float / NULLIF(a.pob_ini, 0) - 1) * 100 AS valor
        FROM dim_municipio d
        JOIN (SELECT cod_municipio, poblacion_total AS pob_ini FROM fact_municipio_anual
              WHERE anio = :ini) a ON a.cod_municipio = d.cod_municipio
        JOIN (SELECT cod_municipio, poblacion_total AS pob_fin FROM fact_municipio_anual
              WHERE anio = :fin) b ON b.cod_municipio = d.cod_municipio
    """,
    "renta": """
        SELECT d.cod_municipio AS cod,
               ST_X(ST_Centroid(d.geom_25830)) AS x, ST_Y(ST_Centroid(d.geom_25830)) AS y,
               f.renta_neta_media_persona AS valor
        FROM dim_municipio d
        JOIN fact_municipio_anual f ON f.cod_municipio = d.cod_municipio AND f.anio = :anio_renta
    """,
}

# cuadrantes de Moran local → etiqueta
_CUADRANTE = {1: "alto-alto", 2: "bajo-alto", 3: "bajo-bajo", 4: "alto-bajo"}


def calcular_lisa(engine: Engine, variable: str, k: int = K_VECINOS) -> list[dict]:
    """[{cod, variable, valor, categoria, p}] con el cluster LISA de cada municipio."""
    from esda.moran import Moran_Local
    from libpysal.weights import KNN

    if variable == "crecimiento":
        params = {
            "ini": cal.primer_anio(engine, "poblacion_total"),
            "fin": cal.ultimo_anio(engine, "poblacion_total"),
        }
    else:
        params = {"anio_renta": cal.ultimo_anio(engine, "renta_neta_media_persona")}
    if any(v is None for v in params.values()):
        raise RuntimeError(f"sin cobertura para calcular LISA de '{variable}': {params}")

    df = pd.read_sql(text(_SQL[variable]), engine, params=params).dropna(subset=["valor", "x", "y"])
    df = df.reset_index(drop=True)
    coords = df[["x", "y"]].to_numpy()
    w = KNN.from_array(coords, k=k)
    w.transform = "r"

    ml = Moran_Local(df["valor"].to_numpy(), w, permutations=999, seed=0)
    significativo = ml.p_sim < P_CORTE
    categoria = np.where(significativo, [_CUADRANTE[int(q)] for q in ml.q], "ns")

    return [
        {
            "cod": r.cod,
            "variable": variable,
            "valor": round(float(r.valor), 1),
            "categoria": str(categoria[i]),
            "p": round(float(ml.p_sim[i]), 4),
        }
        for i, r in enumerate(df.itertuples(index=False))
    ]
