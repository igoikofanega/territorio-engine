"""Golden set: verdad de referencia para medir la extracción con LLM.

Va **antes** que las features a propósito. No se construyen features sobre una extracción
cuya calidad no está medida; si el clasificador confunde Tudela con Tudela de Duero el 30 %
de las veces, cualquier señal que salga después es indistinguible de ese error.

**Cómo se reparte el fichero, y por qué.** El repositorio declara que no redistribuye
datos, y el ADR 0005 limita lo que se almacena a metadatos. Un CSV con 150 titulares
dentro del repositorio contradiría ambas cosas. Así que se parte en dos:

- El fichero **para etiquetar** (con titulares) se genera en la zona de crudos, que no se
  versiona. Es de usar y tirar.
- El fichero de **etiquetas** (solo `url_sha1` + juicio) sí se versiona. No contiene texto
  de nadie y basta para reproducir la medición: quien clone el repositorio y ejecute la
  ingesta recupera los titulares por su hash.

La muestra es **estratificada por municipio**, no aleatoria sobre el total: Pamplona y
Tudela saturan el tope de 250 artículos de la API, así que una muestra simple sería casi
toda de esas dos y no mediría nada sobre los pueblos pequeños, que son el objeto del
proyecto.
"""

from __future__ import annotations

import csv
import os
from pathlib import Path

import pandas as pd
from sqlalchemy.engine import Engine

RAW_DIR = Path(os.environ.get("RAW_DIR", "/data/raw"))
#: Fichero de trabajo, con titulares. No se versiona.
PARA_ETIQUETAR = RAW_DIR / "golden" / "noticias-para-etiquetar.csv"
#: Etiquetas de referencia. Sí se versiona: no lleva texto de terceros. `docs/golden` se
#: monta en el contenedor (ver docker-compose.yml) porque el fichero tiene que acabar en
#: el repositorio, no en un volumen.
ETIQUETAS = Path(os.environ.get("GOLDEN_ETIQUETAS", "/app/docs/golden/noticias-etiquetas.csv"))

#: Titulares por municipio en la muestra. Con ~20 municipios cubiertos da unas 160 filas,
#: suficiente para una proporción con un error de ±8 puntos, que es lo que hace falta para
#: decidir si la extracción sirve.
POR_MUNICIPIO = 8

CAMPOS_TRABAJO = (
    "cod_municipio",
    "url_sha1",
    "municipio",
    "medio",
    "fecha",
    "titular",
    "pertenece",
    "tema",
    "signo",
)
CAMPOS_ETIQUETAS = ("cod_municipio", "url_sha1", "pertenece", "tema", "signo")


def muestra(engine: Engine, por_municipio: int = POR_MUNICIPIO) -> pd.DataFrame:
    """Muestra estratificada por municipio, reproducible (semilla fija)."""
    df = pd.read_sql(
        "SELECT n.cod_municipio, n.url_sha1, d.nombre AS municipio, n.medio, n.fecha, n.titular "
        "FROM noticia_municipio n JOIN dim_municipio d USING (cod_municipio)",
        engine,
    )
    if df.empty:
        return df
    return (
        df.groupby("cod_municipio", group_keys=False)
        .apply(lambda g: g.sample(min(len(g), por_municipio), random_state=0), include_groups=True)
        .sort_values(["cod_municipio", "fecha"])
        .reset_index(drop=True)
    )


def exportar(
    engine: Engine, dest: Path = PARA_ETIQUETAR, por_municipio: int = POR_MUNICIPIO
) -> int:
    """Escribe el CSV para etiquetar a mano. Devuelve el número de filas."""
    df = muestra(engine, por_municipio)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=CAMPOS_TRABAJO)
        w.writeheader()
        for r in df.to_dict("records"):
            w.writerow({**dict.fromkeys(CAMPOS_TRABAJO, ""), **r})
    return len(df)


def _bool(v: object) -> bool | None:
    s = str(v).strip().lower()
    if s in ("1", "true", "si", "sí", "v", "x"):
        return True
    if s in ("0", "false", "no", "f"):
        return False
    return None


def leer_etiquetas(path: Path = ETIQUETAS) -> pd.DataFrame:
    """Etiquetas de referencia. Las filas sin `pertenece` legible se descartan."""
    df = pd.read_csv(path, dtype={"cod_municipio": str, "url_sha1": str})
    df["pertenece"] = df["pertenece"].map(_bool)
    return df[df["pertenece"].notna()].reset_index(drop=True)


def metricas(engine: Engine, path: Path = ETIQUETAS) -> dict:
    """Compara las etiquetas del modelo con las de referencia.

    La métrica que manda es la de `pertenece`, y se dan las cuatro celdas de la matriz de
    confusión además de los porcentajes: con clases desbalanceadas —si el 85 % de los
    titulares pertenecen de verdad— un acierto del 85 % puede significar que el modelo
    dice "sí" a todo, y eso solo se ve en la matriz.
    """
    ref = leer_etiquetas(path)
    if ref.empty:
        return {"n": 0}
    pred = pd.read_sql(
        "SELECT cod_municipio, url_sha1, pertenece AS pred_pertenece, tema AS pred_tema, "
        "signo AS pred_signo, modelo FROM noticia_municipio WHERE modelo IS NOT NULL",
        engine,
    )
    m = ref.merge(pred, on=["cod_municipio", "url_sha1"], how="inner")
    if m.empty:
        return {"n": 0, "sin_etiquetar": len(ref)}

    vp = int(((m["pertenece"]) & (m["pred_pertenece"])).sum())
    fp = int((~m["pertenece"] & (m["pred_pertenece"])).sum())
    fn = int(((m["pertenece"]) & ~m["pred_pertenece"]).sum())
    vn = int((~m["pertenece"] & ~m["pred_pertenece"]).sum())
    precision = vp / (vp + fp) if vp + fp else None
    recall = vp / (vp + fn) if vp + fn else None
    out = {
        "n": len(m),
        "sin_etiquetar": len(ref) - len(m),
        "modelo": m["modelo"].iloc[0],
        "acierto_pertenece": round((vp + vn) / len(m), 3),
        "precision": round(precision, 3) if precision is not None else None,
        "recall": round(recall, 3) if recall is not None else None,
        "vp": vp,
        "fp": fp,
        "fn": fn,
        "vn": vn,
        #: Referencia obligatoria: qué acertaría decir "pertenece" a todo. Si el modelo no
        #: la supera, no está clasificando, está asintiendo.
        "base_decir_que_si": round(int(m["pertenece"].sum()) / len(m), 3),
    }
    con_tema = m[m["tema"].notna() & m["pred_tema"].notna()]
    if len(con_tema):
        out["acierto_tema"] = round(float((con_tema["tema"] == con_tema["pred_tema"]).mean()), 3)
    return out
