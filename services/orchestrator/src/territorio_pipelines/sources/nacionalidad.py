"""Adaptador de población extranjera (Padrón por nacionalidad).

Fuente: INE tabla 33571 "Población por sexo, municipios, nacionalidad (español/extranjero)
y edad (grandes grupos)" (PC-Axis `.px`). Extraemos, por municipio y año, la población
total y la extranjera (sexo=Total, edad=Todas las edades) y derivamos el % de extranjeros.
La inmigración es a menudo lo que sostiene o revierte el declive de los pueblos.
"""

from __future__ import annotations

import os
import re
from collections.abc import Iterator
from pathlib import Path

import httpx
import pandas as pd
from pyaxis import pyaxis

EXPORT_URL = "https://www.ine.es/jaxiT3/files/t/es/px/33571.px"
RAW_DIR = Path(os.environ.get("RAW_DIR", "/data/raw"))
RAW_FILE = RAW_DIR / "ine-33571-nacionalidad.px"
ANIO_MIN = 2015
_COD5 = re.compile(r"^\d{5}$")
_ANIO = re.compile(r"(\d{4})")


def download_raw(url: str = EXPORT_URL, dest: Path = RAW_FILE) -> Path:
    """Descarga el `.px` a la landing zone. Crudo inmutable: no re-descarga."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        return dest
    with httpx.stream("GET", url, timeout=180, follow_redirects=True) as resp:
        resp.raise_for_status()
        with dest.open("wb") as fh:
            for chunk in resp.iter_bytes():
                fh.write(chunk)
    return dest


def parse_px(path: Path) -> pd.DataFrame:
    return pyaxis.parse(str(path), encoding="ISO-8859-15")["DATA"]


def records_from_df(df: pd.DataFrame, anio_min: int = ANIO_MIN) -> Iterator[dict]:
    """Filas `(cod, anio, extranjera, pct)` desde el formato largo del INE.

    Función pura (sin red ni BD). Filtra Sexo=Total y Edad=Todas las edades, pivota la
    nacionalidad (Total/Extranjera) a columnas y calcula el porcentaje de extranjeros.
    """
    d = df.copy()
    d = d[(d["Sexo"] == "Total") & (d["Edad (grandes grupos)"] == "Todas las edades")]
    d["cod"] = d["Municipios"].str.slice(0, 5)
    d = d[d["cod"].str.match(_COD5)]
    d["anio"] = d["Periodo"].str.extract(_ANIO)[0].astype("Int64")
    d = d[d["anio"] >= anio_min]
    d["valor"] = pd.to_numeric(d["DATA"], errors="coerce")
    wide = d.pivot_table(
        index=["cod", "anio"], columns="Nacionalidad", values="valor", aggfunc="first"
    )
    for (cod, anio), row in wide.iterrows():
        total, ext = row.get("Total"), row.get("Extranjera")
        if pd.isna(total) or pd.isna(ext) or total <= 0:
            continue
        yield {
            "cod": cod,
            "anio": int(anio),
            "extranjera": int(ext),
            "pct": round(float(ext) / float(total) * 100, 1),
        }
