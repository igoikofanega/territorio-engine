"""Adaptador de clima (AEMET OpenData).

API peculiar: patrón en DOS pasos (el endpoint devuelve una URL `datos` donde está el
JSON real, en latin-1 y con cert autofirmado), coordenadas en grados-min-seg, y límite
~50 peticiones/min (throttling). Usamos los valores climatológicos mensuales-anuales:
el registro "AAAA-13" trae `tm_mes` (temperatura media anual) y `p_mes` (precipitación
anual). Promediamos por estación sobre una ventana de años para máxima cobertura.
Requiere `AEMET_API_KEY` en el entorno.
"""

from __future__ import annotations

import json
import os
import time
import warnings

import httpx

BASE = "https://opendata.aemet.es/opendata/api"
# Cada estación = 2 peticiones (endpoint + URL de datos), ambas cuentan para el límite
# de ~50/min. 2.5 s/ciclo ≈ 48 req/min en total. La carga completa tarda ~40 min.
THROTTLE_S = 3.0
# AEMET limita mensualesanuales a 36 meses por petición → usamos los últimos 3 años
# (una llamada por estación) y promediamos para robustez.
ANIO_INI, ANIO_FIN = 2022, 2024


def _key() -> str:
    key = os.environ.get("AEMET_API_KEY", "")
    if not key:
        raise RuntimeError("Falta AEMET_API_KEY en el entorno")
    return key


def cliente() -> httpx.Client:
    warnings.filterwarnings("ignore")  # la URL de datos usa cert autofirmado
    return httpx.Client(timeout=60, verify=False)


def _get2(client: httpx.Client, path: str, reintentos: int = 4) -> list | None:
    """Petición en dos pasos con throttling y reintento ante 429. Devuelve datos o None."""
    for _ in range(reintentos):
        try:
            meta = client.get(BASE + path, params={"api_key": _key()}).json()
        except Exception:
            time.sleep(THROTTLE_S)
            continue
        estado = meta.get("estado")
        if estado == 429:  # cuota agotada: esperar y reintentar
            time.sleep(60)
            continue
        time.sleep(THROTTLE_S)
        if estado != 200:
            return None
        try:
            return json.loads(client.get(meta["datos"]).content.decode("latin-1"))
        except Exception:
            return None
    return None


def dms_a_decimal(coord: str) -> float:
    """'394924N' / '025309E' (grados-min-seg + hemisferio) → grados decimales."""
    hemi, n = coord[-1], coord[:-1]
    val = int(n[0:2]) + int(n[2:4]) / 60 + int(n[4:6]) / 3600
    return -val if hemi in ("S", "W") else val


def _num(v: object) -> float | None:
    if v is None:
        return None
    s = str(v).split("(")[0].strip().replace(",", ".")  # quita anotaciones "(13/ago)"
    try:
        return float(s)
    except ValueError:
        return None


def estaciones(client: httpx.Client) -> list[dict]:
    """Inventario de estaciones → [{indicativo, lon, lat}]."""
    inv = _get2(client, "/valores/climatologicos/inventarioestaciones/todasestaciones/")
    out = []
    for e in inv or []:
        try:
            out.append(
                {
                    "indicativo": e["indicativo"],
                    "lon": dms_a_decimal(e["longitud"]),
                    "lat": dms_a_decimal(e["latitud"]),
                }
            )
        except (KeyError, ValueError, IndexError):
            continue
    return out


def clima_estacion(
    client: httpx.Client, indicativo: str, ini: int = ANIO_INI, fin: int = ANIO_FIN
) -> dict | None:
    """Temperatura media y precipitación, promediadas sobre los años disponibles."""
    recs = _get2(
        client,
        f"/valores/climatologicos/mensualesanuales/datos/anioini/{ini}/aniofin/{fin}/estacion/{indicativo}",
    )
    if not recs:
        return None
    tms, precs = [], []
    for r in recs:
        if not str(r.get("fecha", "")).endswith("-13"):  # solo el registro anual
            continue
        tm, pr = _num(r.get("tm_mes")), _num(r.get("p_mes"))
        if tm is not None:
            tms.append(tm)
        if pr is not None:
            precs.append(pr)
    tm = sum(tms) / len(tms) if tms else None
    pr = sum(precs) / len(precs) if precs else None
    if tm is None and pr is None:
        return None
    return {"tm": tm, "prec": pr}
