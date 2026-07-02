"""Adaptador de descripciones de Wikipedia (texto) por municipio.

Usa el título de artículo que trajo Wikidata (`municipio_wiki.wiki_titulo`) y pide el
resumen a la REST API de Wikipedia en español → extracto (texto para NLP) + miniatura.
Muchas llamadas (~6.000) → throttling; ingesta pensada para background.
"""

from __future__ import annotations

import time
from urllib.parse import quote

import httpx

BASE = "https://es.wikipedia.org/api/rest_v1/page/summary/"
UA = "territorio-engine/0.1 (https://github.com/igoikofanega; proyecto educativo)"
THROTTLE_S = 0.2


def extraer(j: dict) -> dict:
    """Del JSON del resumen, saca (descripcion, imagen). Pura y testeable."""
    return {"descripcion": j.get("extract"), "imagen": (j.get("thumbnail") or {}).get("source")}


def resumen(client: httpx.Client, titulo: str, reintentos: int = 3) -> dict | None:
    for intento in range(reintentos):
        try:
            r = client.get(BASE + quote(titulo, safe=""), headers={"User-Agent": UA})
            if r.status_code == 429:  # rate limit → esperar y reintentar
                time.sleep(5 * (intento + 1))
                continue
            if r.status_code != 200:
                return None
            return extraer(r.json())
        except Exception:
            time.sleep(2)
    return None
