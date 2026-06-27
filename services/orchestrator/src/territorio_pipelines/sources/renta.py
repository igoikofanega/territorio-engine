"""Adaptador de renta municipal (INE, Atlas de Distribución de Renta — ADRH).

Indicador "Renta neta media por persona" (€/año). Como la pirámide, es una tabla
`.px` POR PROVINCIA ("Indicadores de renta media y mediana"); el mapa provincia→tabla
se descubrió por escaneo y se fija aquí. La tabla incluye municipios/distritos/secciones:
nos quedamos solo con municipios (código de 5 dígitos). Ventana 2015→.

Pendiente: faltan Albacete (02) y Balears (07) — sus tablas están en otro bloque de ids.
"""

from __future__ import annotations

import os
import re
from collections.abc import Iterator
from pathlib import Path

import httpx
import pandas as pd
from pyaxis import pyaxis

# provincia (2 díg) -> id de tabla jaxiT3 (ADRH "Indicadores de renta media y mediana")
PROV_TABLA: dict[str, int] = {
    "01": 30824,
    "03": 30833,
    "04": 30842,
    "05": 30869,
    "06": 30878,
    "08": 30896,
    "09": 30926,
    "10": 30935,
    "11": 30944,
    "12": 30962,
    "13": 30971,
    "14": 30980,
    "15": 30989,
    "16": 30998,
    "17": 31016,
    "18": 31025,
    "19": 31034,
    "20": 31007,
    "21": 31043,
    "22": 31052,
    "23": 31061,
    "24": 31070,
    "25": 31079,
    "26": 31169,
    "27": 31088,
    "28": 31097,
    "29": 31106,
    "30": 31115,
    "31": 31124,
    "32": 31133,
    "33": 30860,
    "34": 31142,
    "35": 31151,
    "36": 31160,
    "37": 31178,
    "38": 31187,
    "39": 30953,
    "40": 31196,
    "41": 31205,
    "42": 31214,
    "43": 31223,
    "44": 31232,
    "45": 31241,
    "46": 31250,
    "47": 31259,
    "48": 30917,
    "49": 31268,
    "50": 31277,
    "51": 31286,
    "52": 31295,
}
URL = "https://www.ine.es/jaxiT3/files/t/es/px/{tabla}.px"
RAW_DIR = Path(os.environ.get("RAW_DIR", "/data/raw"))
ANIO_MIN = 2015
INDICADOR = "Renta neta media por persona"
_COD5 = re.compile(r"^\d{5}$")


def download_provincia(prov: str, raw_dir: Path = RAW_DIR) -> Path:
    """Descarga el `.px` de renta de una provincia a la landing zone (inmutable)."""
    tabla = PROV_TABLA[prov]
    dest = raw_dir / f"ine-renta-{prov}-{tabla}.px"
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        return dest
    with httpx.stream("GET", URL.format(tabla=tabla), timeout=180, follow_redirects=True) as resp:
        resp.raise_for_status()
        with dest.open("wb") as fh:
            for chunk in resp.iter_bytes():
                fh.write(chunk)
    return dest


def parse_px(path: Path) -> pd.DataFrame:
    return pyaxis.parse(str(path), encoding="ISO-8859-15")["DATA"]


def records_from_df(df: pd.DataFrame, anio_min: int = ANIO_MIN) -> Iterator[dict]:
    """Filas `(cod, anio, renta)` solo de municipios. Función pura (testeable).

    La columna del indicador se detecta dinámicamente porque su nombre varía entre
    provincias (p. ej. Álava: "Indicadores de renta media", sin "y mediana").
    """
    ind_col = next(c for c in df.columns if c not in ("Unidades territoriales", "Periodo", "DATA"))
    d = df[df[ind_col] == INDICADOR].copy()
    d["cod"] = d["Unidades territoriales"].str.split(" ", n=1).str[0]
    d = d[d["cod"].str.match(_COD5)]
    d["anio"] = pd.to_numeric(d["Periodo"], errors="coerce")
    d = d[d["anio"] >= anio_min]
    d["renta"] = pd.to_numeric(d["DATA"], errors="coerce")
    d = d[d["renta"].notna()].drop_duplicates(subset=["cod", "anio"])
    for r in d[["cod", "anio", "renta"]].itertuples(index=False):
        yield {"cod": r.cod, "anio": int(r.anio), "renta": float(r.renta)}
