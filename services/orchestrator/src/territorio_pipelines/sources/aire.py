"""Adaptador de calidad del aire (EEA, mapas interpolados anuales).

Fuente: European Environment Agency, "European air quality data (interpolated data)".
Rasters GeoTIFF a 1 km (EPSG:3035, ETRS89-LAEA) que combinan estaciones, modelos de
transporte químico e interpolación (regression-interpolation-merging). Cobertura europea
completa, así que cada municipio tiene valor (a diferencia de las estaciones, urbanas y
dispersas). Muestreamos el centroide de cada municipio.

Se descargan de los "datashare" públicos (Nextcloud) de la EEA. Los tokens y nombres
corresponden a los datos de 2025 (interim, junio 2026); si la EEA los rota, hay que
recapturarlos desde https://www.eea.europa.eu/en/datahub (item 82700fbd…).
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import httpx
import rasterio
from pyproj import Transformer

_BASE = "https://sdi.eea.europa.eu/datashare/s/{token}/download?files={fichero}"
# clave interna → (token del datashare, fichero .tif, unidad)
CAPAS = {
    "pm25": ("CDgfZq5SoRGozXo", "pm25_avg25_int.tif"),  # media anual PM2.5 (µg/m³)
    "no2": ("MqaoYXK4DKtAw2c", "no2_avg25_int.tif"),  # media anual NO2 (µg/m³)
    "pm10": ("RYFMP684HBLqLSy", "pm10_avg25_int.tif"),  # media anual PM10 (µg/m³)
    "o3": ("mt8xa6iHg2mF6nf", "o3_peak25_int.tif"),  # indicador de pico de O3 (salud)
}
CRS_RASTER = 3035
RAW_DIR = Path(os.environ.get("RAW_DIR", "/data/raw"))
_NODATA = -1e30  # el nodata real es -3.4e38; cortamos por debajo de -1e30


def download_raster(clave: str, raw_dir: Path = RAW_DIR) -> Path:
    """Descarga (si falta) el GeoTIFF de una capa a la landing zone."""
    token, fichero = CAPAS[clave]
    dest = raw_dir / f"eea-aire-{clave}-2025.tif"
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        return dest
    url = _BASE.format(token=token, fichero=fichero)
    with httpx.stream("GET", url, timeout=300, follow_redirects=True) as resp:
        resp.raise_for_status()
        with dest.open("wb") as fh:
            for chunk in resp.iter_bytes():
                fh.write(chunk)
    return dest


def muestrear(centroides: list[tuple[str, float, float]]) -> Iterator[dict]:
    """Para cada (cod, lon, lat) devuelve {cod, pm25, no2, pm10, o3} muestreando los rasters.

    `centroides` en EPSG:4326. Se reproyecta a 3035 (el CRS de los rasters) una sola vez.
    """
    tr = Transformer.from_crs(4326, CRS_RASTER, always_xy=True)
    cods = [c for c, _, _ in centroides]
    xs, ys = tr.transform([lon for _, lon, _ in centroides], [lat for _, _, lat in centroides])
    puntos = list(zip(xs, ys, strict=True))

    valores: dict[str, list] = {}
    for clave in CAPAS:
        path = download_raster(clave)
        with rasterio.open(path) as ds:
            valores[clave] = [
                (None if (v is None or v <= _NODATA) else round(float(v), 1))
                for (v,) in ds.sample(puntos)
            ]

    for i, cod in enumerate(cods):
        fila = {"cod": cod, **{k: valores[k][i] for k in CAPAS}}
        if all(fila[k] is None for k in CAPAS):
            continue
        yield fila
