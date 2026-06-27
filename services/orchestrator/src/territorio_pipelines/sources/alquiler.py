"""Adaptador de precio del alquiler municipal (SERPAVI, MIVAU).

Fuente: base de datos SERPAVI (explotación de fuentes tributarias, 2011-2024), Excel
con hoja "Municipios" a nivel municipal directo (CUMUN = código INE de 5 dígitos).
Métrica: `ALQM2_LV_M_VC_{año}` = alquiler medio €/m²·mes (vivienda colectiva). El Excel
está en formato ancho (una columna por año); lo pasamos a largo. Ventana 2015→.
"""

from __future__ import annotations

import os
import re
from collections.abc import Iterator
from pathlib import Path

import httpx
import pandas as pd

URL = (
    "https://cdn.mivau.gob.es/portal-web-mivau/vivienda/serpavi/"
    "2026-03-09_bd_SERPAVI_2011-2024%20-%20DEFINITIVO%20WEB.xlsx"
)
UA = "Mozilla/5.0 (X11; Linux x86_64) Chrome/120 Safari/537.36"
RAW_DIR = Path(os.environ.get("RAW_DIR", "/data/raw"))
RAW_FILE = RAW_DIR / "serpavi-2011-2024.xlsx"
ANIO_MIN = 2015
_COL = re.compile(r"^ALQM2_LV_M_VC_(\d{2})$")  # alquiler €/m² medio, vivienda colectiva
_COD5 = re.compile(r"^\d{5}$")


def download(dest: Path = RAW_FILE) -> Path:
    """Descarga el Excel de SERPAVI a la landing zone (inmutable). ~68 MB."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        return dest
    with httpx.stream(
        "GET", URL, headers={"User-Agent": UA}, timeout=240, follow_redirects=True
    ) as r:
        r.raise_for_status()
        with dest.open("wb") as fh:
            for chunk in r.iter_bytes():
                fh.write(chunk)
    return dest


def parse_excel(path: Path) -> pd.DataFrame:
    """Lee la hoja Municipios (solo CUMUN + columnas de alquiler medio anual)."""
    return pd.read_excel(
        path,
        sheet_name="Municipios",
        dtype={"CUMUN": str},
        usecols=lambda c: c == "CUMUN" or bool(_COL.match(str(c))),
    )


def records_from_df(df: pd.DataFrame, anio_min: int = ANIO_MIN) -> Iterator[dict]:
    """Filas `(cod, anio, alquiler)` desde el formato ancho. Función pura (testeable)."""
    val_cols = [c for c in df.columns if _COL.match(str(c))]
    long = df.melt(id_vars=["CUMUN"], value_vars=val_cols, var_name="col", value_name="alquiler")
    long["anio"] = 2000 + long["col"].str.extract(r"_(\d{2})$")[0].astype(int)
    long = long[long["anio"] >= anio_min]
    long["alquiler"] = pd.to_numeric(long["alquiler"], errors="coerce")
    long = long.dropna(subset=["alquiler"])
    long["cod"] = long["CUMUN"].str.strip()
    long = long[long["cod"].str.match(_COD5)]
    for r in long[["cod", "anio", "alquiler"]].itertuples(index=False):
        yield {"cod": r.cod, "anio": int(r.anio), "alquiler": round(float(r.alquiler), 2)}
