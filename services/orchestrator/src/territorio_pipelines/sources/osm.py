"""Adaptador de servicios (OpenStreetMap vía Overpass).

Cuenta equipamientos por municipio (salud, educación, comercio). Consulta Overpass
**por provincia (bbox)** para no saturar la instancia pública (las consultas nacionales
dan 504); con reintentos y backoff. La asignación a municipio se hace luego con PostGIS
(punto-en-polígono). Ingesta lenta → pensada para background.
"""

from __future__ import annotations

import time

import httpx

OVERPASS = "https://overpass-api.de/api/interpreter"
UA = "territorio-engine/0.1 (proyecto educativo)"
CATEGORIAS = {
    "salud": '"amenity"~"^(pharmacy|hospital|clinic|doctors|dentist)$"',
    "educacion": '"amenity"~"^(school|kindergarten|university|college)$"',
    "comercio": (
        '"shop"~"^(supermarket|convenience|bakery|butcher|greengrocer|mall|department_store)$"'
    ),
}


def _punto(el: dict) -> tuple[float, float] | None:
    if "lat" in el and "lon" in el:
        return (el["lon"], el["lat"])
    if "center" in el:
        return (el["center"]["lon"], el["center"]["lat"])
    return None


def consultar_bbox(
    filtro: str, bbox: tuple[float, float, float, float], timeout: int = 90, reintentos: int = 4
) -> list[tuple[float, float]]:
    """[(lon, lat)] de los elementos que casan el filtro dentro del bbox (S,W,N,E)."""
    s, w, n, e = bbox
    q = (
        f"[out:json][timeout:{timeout}];"
        f"(node[{filtro}]({s},{w},{n},{e});way[{filtro}]({s},{w},{n},{e}););out center;"
    )
    for intento in range(reintentos):
        try:
            r = httpx.post(
                OVERPASS, data={"data": q}, timeout=timeout + 40, headers={"User-Agent": UA}
            )
            if r.status_code in (429, 502, 503, 504):
                time.sleep(8 * (intento + 1))
                continue
            r.raise_for_status()
            return [p for el in r.json()["elements"] if (p := _punto(el))]
        except Exception:
            time.sleep(5 * (intento + 1))
    return []
