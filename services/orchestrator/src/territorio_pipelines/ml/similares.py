"""'Pueblos como el tuyo': vecinos más cercanos en el espacio de features.

NearestNeighbors sobre las features estandarizadas de un año reciente → los k municipios
más parecidos a cada uno. Reutiliza el mismo dataset que el modelo y el clustering.
"""

from __future__ import annotations

from sklearn.impute import SimpleImputer
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import StandardScaler
from sqlalchemy.engine import Engine

from .. import calendario as cal
from .features import FEATURES, construir_dataset

K = 8
# Año de referencia: el último con las features casi-estáticas cubiertas
# (clima y % de extranjeros). Se deriva de los datos, no se fija a mano.
COLUMNAS_REF = ["temp_media_anual", "pct_extranjeros"]


def calcular_similares(engine: Engine, k: int = K, anio: int | None = None) -> list[dict]:
    """Devuelve [{cod, similares}] con los k vecinos (códigos, separados por coma)."""
    if anio is None:
        anio = cal.ultimo_anio_comun(engine, COLUMNAS_REF)
        if anio is None:
            raise RuntimeError(f"ningún año cubre a la vez {COLUMNAS_REF}")
    df = construir_dataset(engine, [anio])
    df = df[df["pob"].notna()].reset_index(drop=True)
    x = StandardScaler().fit_transform(SimpleImputer(strategy="median").fit_transform(df[FEATURES]))

    nn = NearestNeighbors(n_neighbors=k + 1).fit(x)
    _, indices = nn.kneighbors(x)
    cods = df["cod"].to_numpy()
    return [
        {"cod": cods[i], "similares": ",".join([cods[j] for j in vecinos if j != i][:k])}
        for i, vecinos in enumerate(indices)
    ]
