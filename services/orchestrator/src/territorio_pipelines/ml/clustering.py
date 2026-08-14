"""Clustering de municipios en arquetipos ("pueblos como el tuyo").

KMeans no supervisado sobre las features estandarizadas de un año reciente. Cada
municipio recibe un arquetipo (cluster), etiquetado automáticamente por los 2 rasgos
más marcados de su centroide. Se registra el silhouette en MLflow.
"""

from __future__ import annotations

import mlflow
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.impute import SimpleImputer
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler
from sqlalchemy.engine import Engine

from .. import calendario as cal
from .features import FEATURES, construir_dataset
from .modelo import ETIQUETAS, EXPERIMENTO

K = 6
# Año de referencia: el último con las features casi-estáticas cubiertas
# (clima y % de extranjeros). Se deriva de los datos, no se fija a mano.
COLUMNAS_REF = ["temp_media_anual", "pct_extranjeros"]


def entrenar_clusters(
    engine: Engine, k: int = K, anio: int | None = None
) -> tuple[pd.DataFrame, dict]:
    """Asigna un arquetipo a cada municipio. Devuelve (df[cod,cluster,etiqueta], métricas)."""
    if anio is None:
        anio = cal.ultimo_anio_comun(engine, COLUMNAS_REF)
        if anio is None:
            raise RuntimeError(f"ningún año cubre a la vez {COLUMNAS_REF}")
    df = construir_dataset(engine, [anio])
    df = df[df["pob"].notna()].reset_index(drop=True)

    pipe_x = StandardScaler().fit_transform(
        SimpleImputer(strategy="median").fit_transform(df[FEATURES])
    )
    km = KMeans(n_clusters=k, n_init=10, random_state=0)
    labels = km.fit_predict(pipe_x)
    sil = float(silhouette_score(pipe_x, labels, sample_size=5000, random_state=0))

    # etiqueta de cada cluster: los 2 rasgos más extremos de su centroide (z-score)
    etiquetas = {}
    for c in range(k):
        z = km.cluster_centers_[c]
        top = np.argsort(-np.abs(z))[:2]
        etiquetas[c] = " · ".join(
            f"{ETIQUETAS[FEATURES[i]]}{'↑' if z[i] >= 0 else '↓'}" for i in top
        )

    mlflow.set_experiment(EXPERIMENTO)
    with mlflow.start_run(run_name="kmeans_arquetipos"):
        mlflow.log_params({"k": k, "anio": anio, "features": ",".join(FEATURES)})
        mlflow.log_metric("silhouette", sil)

    out = pd.DataFrame({"cod": df["cod"].to_numpy(), "cluster": labels})
    out["etiqueta"] = out["cluster"].map(etiquetas)
    return out, {"silhouette": round(sil, 3), "k": k}
