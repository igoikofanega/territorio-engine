"""Adaptador de la pirámide de edad municipal (Padrón, grupos quinquenales).

Fuente: INE "Población por sexo, municipios y edad (grupos quinquenales)". Es una
tabla `.px` POR PROVINCIA (no hay fichero nacional único), así que iteramos las 52
provincias. El mapa provincia→id de tabla se descubrió escaneando jaxiT3 y se fija
aquí como constante. Cubre 2003–2022; filtramos 2015→. Insumo del cohorte-componente.
"""

from __future__ import annotations

import os
import re
from collections.abc import Iterator
from pathlib import Path

import httpx
import pandas as pd
from pyaxis import pyaxis

# provincia (2 díg) -> id de tabla jaxiT3 (variante quinquenal)
PROV_TABLA: dict[str, int] = {
    "01": 33686,
    "02": 33576,
    "03": 33584,
    "04": 33645,
    "05": 33698,
    "06": 33704,
    "07": 33710,
    "08": 33716,
    "09": 33728,
    "10": 33734,
    "11": 33740,
    "12": 33752,
    "13": 33758,
    "14": 33764,
    "15": 33770,
    "16": 33776,
    "17": 33788,
    "18": 33794,
    "19": 33800,
    "20": 33782,
    "21": 33806,
    "22": 33812,
    "23": 33818,
    "24": 33824,
    "25": 33830,
    "26": 33890,
    "27": 33836,
    "28": 33842,
    "29": 33848,
    "30": 33854,
    "31": 33860,
    "32": 33866,
    "33": 33692,
    "34": 33872,
    "35": 33878,
    "36": 33884,
    "37": 33896,
    "38": 33902,
    "39": 33746,
    "40": 33908,
    "41": 33914,
    "42": 33920,
    "43": 33926,
    "44": 33932,
    "45": 33938,
    "46": 33944,
    "47": 33950,
    "48": 33722,
    "49": 33956,
    "50": 33962,
    "51": 33968,
    "52": 33974,
}
URL = "https://www.ine.es/jaxiT3/files/t/es/px/{tabla}.px"
RAW_DIR = Path(os.environ.get("RAW_DIR", "/data/raw"))
ANIO_MIN = 2015
_COD5 = re.compile(r"^\d{5}$")


def download_provincia(prov: str, raw_dir: Path = RAW_DIR) -> Path:
    """Descarga el `.px` de una provincia a la landing zone (crudo inmutable)."""
    tabla = PROV_TABLA[prov]
    dest = raw_dir / f"ine-piramide-{prov}-{tabla}.px"
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
    """Filas `(cod, anio, sexo, edad_min, poblacion)`. Función pura (testeable).

    Descarta agregados (Sexo=Total, Edad="Todas las edades", código no-5-dígitos).
    `edad_min` es el límite inferior del grupo quinquenal (0,5,…,100).
    """
    d = df.rename(columns={"Edad (grupos quinquenales)": "edad"}).copy()
    d = d[d["Sexo"].isin(["Hombres", "Mujeres"])]
    d["cod"] = d["Municipios"].str.slice(0, 5)
    d = d[d["cod"].str.match(_COD5)]
    d["edad_min"] = d["edad"].str.extract(r"(\d+)")  # NaN en "Todas las edades"
    d = d[d["edad_min"].notna()]
    d["anio"] = pd.to_numeric(d["Periodo"].str.extract(r"(\d{4})")[0], errors="coerce")
    d = d[d["anio"] >= anio_min]
    d["poblacion"] = pd.to_numeric(d["DATA"], errors="coerce")
    d = d[d["poblacion"].notna()]

    out = pd.DataFrame(
        {
            "cod": d["cod"],
            "anio": d["anio"].astype(int),
            "sexo": d["Sexo"].map({"Hombres": "H", "Mujeres": "M"}),
            "edad_min": d["edad_min"].astype(int),
            "poblacion": d["poblacion"].astype(int),
        }
    )
    yield from out.to_dict("records")
