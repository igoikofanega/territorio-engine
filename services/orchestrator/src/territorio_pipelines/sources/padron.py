"""Adaptador de población municipal (Padrón).

Fuente: INE tabla 29005 "Cifras oficiales del padrón por municipio" (PC-Axis `.px`),
población total por `municipio × sexo × periodo`, serie 1996→. Se parsea con pyaxis
(la API JSON del INE no sirve bien el grano municipal). Ventana del proyecto: 2015→.
"""

from __future__ import annotations

import os
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx
import pandas as pd
from pyaxis import pyaxis

EXPORT_URL = "https://www.ine.es/jaxiT3/files/t/es/px/29005.px"
RAW_DIR = Path(os.environ.get("RAW_DIR", "/data/raw"))
RAW_FILE = RAW_DIR / "ine-29005-padron.px"
ANIO_MIN = 2015
_COD5 = re.compile(r"^\d{5}$")


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
    """Devuelve el DataFrame largo (Municipios, Sexo, Periodo, DATA)."""
    return pyaxis.parse(str(path), encoding="ISO-8859-15")["DATA"]


def records_from_df(df: pd.DataFrame, anio_min: int = ANIO_MIN) -> Iterator[dict]:
    """Transforma el formato largo del INE en filas `(cod, anio, total, h, m)`.

    Función pura (sin red ni BD) para poder testearla. Pivota el sexo a columnas,
    filtra por año y descarta agregados (códigos que no son 5 dígitos).
    """
    d = df.copy()
    d["cod"] = d["Municipios"].str.slice(0, 5)
    d = d[d["cod"].str.match(_COD5)]
    d["anio"] = pd.to_numeric(d["Periodo"], errors="coerce")
    d = d[d["anio"] >= anio_min]
    d["valor"] = pd.to_numeric(d["DATA"], errors="coerce")
    wide = d.pivot_table(index=["cod", "anio"], columns="Sexo", values="valor", aggfunc="first")

    def _int_or_none(value: Any) -> int | None:
        # `Any`: valor de celda de pandas; `pd.isna` es la comprobación real.
        return None if pd.isna(value) else int(value)

    for (cod, anio), row in wide.iterrows():
        total = row.get("Total")
        if pd.isna(total):
            continue
        yield {
            "cod": cod,
            "anio": int(anio),
            "total": int(total),
            "hombres": _int_or_none(row.get("Hombres")),
            "mujeres": _int_or_none(row.get("Mujeres")),
        }
