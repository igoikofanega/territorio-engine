"""Adaptador de geometrías municipales.

Fuente MVP: Opendatasoft `georef-spain-municipio` (GeoJSON, derivado de fuentes
oficiales/IGN). Campo `mun_code` = código INE de 5 dígitos; EPSG:4326.
Fuente canónica documentada para swap futuro: CNIG (ver docs/adr/0002).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import httpx
from pydantic import BaseModel, Field

EXPORT_URL = (
    "https://public.opendatasoft.com/api/explore/v2.1/catalog/"
    "datasets/georef-spain-municipio/exports/geojson"
)
RAW_DIR = Path(os.environ.get("RAW_DIR", "/data/raw"))
RAW_FILE = RAW_DIR / "georef-spain-municipio.geojson"


class MunicipioProps(BaseModel):
    """Propiedades validadas de un municipio del GeoJSON de origen."""

    mun_code: str = Field(min_length=5, max_length=5)
    mun_name: str
    acom_code: str | None = None


def download_raw(url: str = EXPORT_URL, dest: Path = RAW_FILE) -> Path:
    """Descarga el GeoJSON a la landing zone. Crudo inmutable: no re-descarga."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        return dest
    with httpx.stream("GET", url, timeout=180, follow_redirects=True) as resp:
        resp.raise_for_status()
        with dest.open("wb") as fh:
            for chunk in resp.iter_bytes():
                fh.write(chunk)
    return dest


def feature_to_row(feature: dict) -> tuple[MunicipioProps, dict]:
    """Valida una feature y devuelve (propiedades, geometría GeoJSON)."""
    props = MunicipioProps.model_validate(feature["properties"])
    return props, feature["geometry"]


def read_features(path: Path) -> list[dict]:
    """Lee la FeatureCollection y devuelve la lista de features."""
    data = json.loads(Path(path).read_text())
    return data["features"]
