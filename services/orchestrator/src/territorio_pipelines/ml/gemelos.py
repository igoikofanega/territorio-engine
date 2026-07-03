"""Gemelos divergentes: municipios casi idénticos en features con destinos opuestos.

Para cada municipio se busca su vecino más cercano en el espacio de features
estandarizadas de un año base cuyo futuro ya conocemos, y se compara el crecimiento
real de ambos. Una divergencia grande con distancia pequeña es un 'experimento
natural': mismas condiciones medibles, resultados distintos — ahí hay algo que
investigar (gestión local, un empleador, carretera nueva…).
"""

from __future__ import annotations

from sklearn.impute import SimpleImputer
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import StandardScaler
from sqlalchemy.engine import Engine

from .features import FEATURES, TARGET, construir_dataset

ANIO_BASE = 2020  # su target (2020→2025) ya es historia conocida


def calcular_gemelos(engine: Engine, anio: int = ANIO_BASE) -> list[dict]:
    """[{cod, cod_gemelo, distancia, crec_propio, crec_gemelo, divergencia}]."""
    df = construir_dataset(engine, [anio])
    df = df[df["pob"].notna() & df[TARGET].notna()].reset_index(drop=True)
    x = StandardScaler().fit_transform(SimpleImputer(strategy="median").fit_transform(df[FEATURES]))

    nn = NearestNeighbors(n_neighbors=2).fit(x)
    dist, idx = nn.kneighbors(x)
    cods = df["cod"].to_numpy()
    crec = df[TARGET].to_numpy()

    salida = []
    for i in range(len(df)):
        j = int(idx[i, 1])  # el 0 es uno mismo
        salida.append(
            {
                "cod": cods[i],
                "cod_gemelo": cods[j],
                "distancia": round(float(dist[i, 1]), 3),
                "crec_propio": round(float(crec[i]), 1),
                "crec_gemelo": round(float(crec[j]), 1),
                "divergencia": round(abs(float(crec[i]) - float(crec[j])), 1),
            }
        )
    return salida
