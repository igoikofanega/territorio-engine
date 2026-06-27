"""Adaptador de paro registrado municipal (SEPE).

Fuente: SEPE datos abiertos, un CSV nacional por año (`Paro_por_municipios_{año}`),
mensual por municipio. Lo agregamos a media anual del total de paro registrado.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import date
from pathlib import Path

import httpx
import pandas as pd

URL = (
    "https://sede.sepe.gob.es/es/portaltrabaja/resources/sede/datos_abiertos/"
    "datos/Paro_por_municipios_{anio}_csv.csv"
)
RAW_DIR = Path(os.environ.get("RAW_DIR", "/data/raw"))
ANIO_MIN = 2015
COLS = ["Código mes", "Codigo Municipio", "total Paro Registrado"]


def anios_disponibles() -> range:
    return range(ANIO_MIN, date.today().year + 1)


def download(anio: int, raw_dir: Path = RAW_DIR) -> Path | None:
    """Descarga el CSV de un año a la landing zone. Devuelve None si no existe (404)."""
    dest = raw_dir / f"sepe-paro-{anio}.csv"
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        return dest
    resp = httpx.get(URL.format(anio=anio), timeout=120, follow_redirects=True)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    dest.write_bytes(resp.content)
    return dest


def parse_csv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, sep=";", encoding="latin-1", skiprows=1, dtype=str)
    df.columns = [c.strip() for c in df.columns]
    return df


def records_from_df(df: pd.DataFrame) -> Iterator[dict]:
    """Filas `(cod, anio, paro)` = media anual del paro registrado. Función pura."""
    d = df[COLS].copy()
    d["cod"] = d["Codigo Municipio"].str.strip()
    d = d[d["cod"].str.match(r"^\d{5}$")]
    d["anio"] = pd.to_numeric(d["Código mes"].str[:4], errors="coerce")
    d["paro"] = pd.to_numeric(d["total Paro Registrado"], errors="coerce")
    d = d.dropna(subset=["anio", "paro"])
    g = d.groupby(["cod", "anio"])["paro"].mean().round().reset_index()
    for r in g.itertuples(index=False):
        yield {"cod": r.cod, "anio": int(r.anio), "paro": int(r.paro)}
