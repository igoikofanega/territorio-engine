"""Adaptador de hechos de Wikidata por municipio.

Una sola consulta SPARQL trae, para cada municipio de España (unido por el código INE,
propiedad P772): altitud, web oficial, imagen, escudo, gentilicio y el título del
artículo de Wikipedia (que luego usa el adaptador de Wikipedia para el texto).
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from urllib.parse import unquote

import httpx

URL = "https://query.wikidata.org/sparql"
UA = "territorio-engine/0.1 (proyecto educativo; contacto: n/a)"
SPARQL = """
SELECT ?ine ?municipioLabel ?altitud ?web ?imagen ?escudo ?gentilicioLabel ?articulo WHERE {
  ?municipio wdt:P31 wd:Q2074737 ; wdt:P772 ?ine .
  OPTIONAL { ?municipio wdt:P2044 ?altitud. }
  OPTIONAL { ?municipio wdt:P856 ?web. }
  OPTIONAL { ?municipio wdt:P18 ?imagen. }
  OPTIONAL { ?municipio wdt:P94 ?escudo. }
  OPTIONAL { ?municipio wdt:P1549 ?gentilicio. }
  OPTIONAL { ?articulo schema:about ?municipio ; schema:isPartOf <https://es.wikipedia.org/> . }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "es". }
}
"""
_COD5 = re.compile(r"^\d{5}$")


def descargar() -> list[dict]:
    r = httpx.get(
        URL, params={"query": SPARQL, "format": "json"}, headers={"User-Agent": UA}, timeout=180
    )
    r.raise_for_status()
    return r.json()["results"]["bindings"]


def _val(b: dict, clave: str) -> str | None:
    return b.get(clave, {}).get("value") or None


def records_from_bindings(bindings: list[dict]) -> Iterator[dict]:
    """Filas `(cod, altitud, web, imagen, escudo, gentilicio, wiki_titulo)`. Pura y testeable."""
    vistos: set[str] = set()
    for b in bindings:
        ine = (_val(b, "ine") or "").zfill(5)
        if not _COD5.match(ine) or ine in vistos:
            continue
        vistos.add(ine)
        art = _val(b, "articulo")
        alt = _val(b, "altitud")
        yield {
            "cod": ine,
            "altitud": float(alt) if alt and _es_num(alt) else None,
            "web": _val(b, "web"),
            "imagen": _val(b, "imagen"),
            "escudo": _val(b, "escudo"),
            "gentilicio": _val(b, "gentilicioLabel"),
            "wiki_titulo": unquote(art.rsplit("/", 1)[-1]) if art else None,
        }


def _es_num(s: str) -> bool:
    try:
        float(s)
        return True
    except ValueError:
        return False
