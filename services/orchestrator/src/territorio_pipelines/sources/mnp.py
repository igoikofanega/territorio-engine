"""Adaptador de tasas vitales provinciales (MNP).

El MNP municipal no existe para municipios pequeños (solo capitales/>50k), así que
usamos tasas PROVINCIALES y el modelo las aplica a la estructura de edad municipal
(enfoque de áreas pequeñas). Fuentes INE (PC-Axis, por provincia × año):
  - 1470: Tasa Bruta de Natalidad
  - 1482: Tasa Bruta de Mortalidad
"""

from __future__ import annotations

import os
import re
from collections.abc import Iterator
from pathlib import Path

import httpx
import pandas as pd
from pyaxis import pyaxis

TABLA_NATALIDAD = 1470
TABLA_MORTALIDAD = 1482
URL = "https://www.ine.es/jaxiT3/files/t/es/px/{tabla}.px"
RAW_DIR = Path(os.environ.get("RAW_DIR", "/data/raw"))
ANIO_MIN = 2015
_PROV2 = re.compile(r"^\d{2}$")


def download(tabla: int, raw_dir: Path = RAW_DIR) -> Path:
    """Descarga un `.px` del INE a la landing zone (crudo inmutable)."""
    dest = raw_dir / f"ine-{tabla}.px"
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        return dest
    with httpx.stream("GET", URL.format(tabla=tabla), timeout=120, follow_redirects=True) as resp:
        resp.raise_for_status()
        with dest.open("wb") as fh:
            for chunk in resp.iter_bytes():
                fh.write(chunk)
    return dest


def parse_px(path: Path) -> pd.DataFrame:
    return pyaxis.parse(str(path), encoding="ISO-8859-15")["DATA"]


def _to_dict(df: pd.DataFrame, anio_min: int) -> dict[tuple[str, int], float]:
    """`{(cod_provincia, anio): valor}` descartando 'Total Nacional'."""
    d = df.copy()
    d["cod"] = d["Provincias"].str.slice(0, 2)
    d = d[d["cod"].str.match(_PROV2)]
    d["anio"] = pd.to_numeric(d["Periodo"], errors="coerce")
    d = d[d["anio"] >= anio_min]
    d["valor"] = pd.to_numeric(d["DATA"], errors="coerce")
    d = d[d["valor"].notna()]
    return {(r.cod, int(r.anio)): float(r.valor) for r in d.itertuples(index=False)}


def records_from_dfs(
    df_natalidad: pd.DataFrame, df_mortalidad: pd.DataFrame, anio_min: int = ANIO_MIN
) -> Iterator[dict]:
    """Filas `(cod_provincia, anio, tasa_natalidad, tasa_mortalidad)`. Función pura."""
    nat = _to_dict(df_natalidad, anio_min)
    mort = _to_dict(df_mortalidad, anio_min)
    for cod, anio in sorted(nat.keys() | mort.keys()):
        yield {
            "cod_provincia": cod,
            "anio": anio,
            "tasa_natalidad": nat.get((cod, anio)),
            "tasa_mortalidad": mort.get((cod, anio)),
        }
