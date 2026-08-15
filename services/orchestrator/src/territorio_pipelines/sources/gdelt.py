"""Adaptador de noticias (GDELT DOC 2.0).

Devuelve **metadatos** de artículos de prensa que mencionan un municipio: titular, fecha,
medio y URL. Nunca el cuerpo: ver `docs/adr/0005-capa-de-noticias-y-llm.md`.

Tres peculiaridades de esta API que explican el código:

1. **El histórico arranca en 2017.** No hay nada antes, por mucho que se pida.
2. **Un límite de 1 petición cada 5 segundos**, y cuando se supera no devuelve un 429:
   devuelve **200 con un aviso en texto plano**. Un `resp.json()` ingenuo revienta con un
   error de parseo que no dice nada de lo que ha pasado realmente.
3. **Sin resultados = cuerpo vacío**, no un JSON con lista vacía.

La consulta es deliberadamente **amplia**: el nombre del municipio en medios españoles, sin
intentar desambiguar aquí. "Tudela" trae también noticias de Tudela de Duero (Valladolid),
y filtrar por provincia en la consulta perdería la mayoría de las noticias buenas, porque
un titular local rara vez nombra la provincia. Esa decisión la toma la capa de extracción,
que es donde se puede medir si acierta.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from collections.abc import Iterator
from datetime import date, datetime
from pathlib import Path

import httpx

API = "https://api.gdeltproject.org/api/v2/doc/doc"
#: 5,0 s es el límite anunciado; 5,5 deja margen para no jugársela en cada petición.
THROTTLE_S = 5.5
#: Espera adicional cuando GDELT contesta con el aviso de exceso de peticiones.
ESPERA_LIMITE_S = 30.0
#: Primer año con datos en GDELT.
ANIO_INI = 2017
#: Tope duro de la API. Un municipio que lo alcance está saturando la consulta.
MAXRECORDS = 250

RAW_DIR = Path(os.environ.get("RAW_DIR", "/data/raw")) / "gdelt"

_PARENTESIS = re.compile(r"\s*\([^)]*\)")


def nombre_consulta(nombre: str) -> str:
    """Nombre del municipio tal como se busca en prensa.

    Los nombres del INE llevan a veces una aclaración administrativa entre paréntesis
    —"Noáin (Valle de Elorz)"— que ningún medio escribe. Se quita.
    """
    return _PARENTESIS.sub("", nombre).strip()


def _params(nombre: str, anio: int) -> dict[str, str]:
    return {
        "query": f'"{nombre_consulta(nombre)}" sourcecountry:spain',
        "mode": "artlist",
        "format": "json",
        "startdatetime": f"{anio}0101000000",
        "enddatetime": f"{anio}1231235959",
        "maxrecords": str(MAXRECORDS),
        "sort": "datedesc",
    }


def cliente() -> httpx.Client:
    return httpx.Client(timeout=60, follow_redirects=True)


def _pedir(client: httpx.Client, params: dict[str, str], reintentos: int = 4) -> str:
    """Cuerpo JSON de una consulta, respetando el límite de peticiones.

    Espera **antes** de pedir, no después: así la pausa se respeta también cuando la
    llamada anterior falló, que es justo cuando más fácil es saltarse el límite.
    """
    for intento in range(reintentos):
        time.sleep(THROTTLE_S)
        try:
            resp = client.get(API, params=params)
        except httpx.HTTPError:
            continue
        cuerpo = resp.text.strip()
        if not cuerpo:
            return '{"articles": []}'  # sin resultados: GDELT devuelve el cuerpo vacío
        if cuerpo.startswith("{"):
            return cuerpo
        if "limit" in cuerpo.lower():  # aviso de exceso de peticiones, con estado 200
            time.sleep(ESPERA_LIMITE_S * (intento + 1))
            continue
        # Cualquier otro texto plano es un rechazo de la consulta: fallar alto y claro,
        # no dejar un fichero crudo con un mensaje de error dentro.
        raise RuntimeError(f"GDELT rechazó la consulta {params['query']!r}: {cuerpo[:200]}")
    raise RuntimeError(f"GDELT no respondió tras {reintentos} intentos: {params['query']!r}")


def descargar(
    client: httpx.Client, cod: str, nombre: str, anio: int, raw_dir: Path = RAW_DIR
) -> Path:
    """Aterriza la respuesta cruda de `(municipio, año)` y devuelve su ruta.

    **Reanudable**: si el fichero ya existe no se vuelve a pedir. Con casi 4 horas de
    ingesta para la serie completa, que un corte obligue a empezar de cero no es una
    opción. Se escribe a un temporal y se renombra, para que un corte a media escritura
    no deje un JSON truncado que luego se dé por bueno.
    """
    dest = raw_dir / cod / f"{anio}.json"
    if dest.exists():
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    cuerpo = _pedir(client, _params(nombre, anio))
    tmp = dest.with_suffix(".tmp")
    tmp.write_text(cuerpo, encoding="utf-8")
    tmp.replace(dest)
    return dest


def _fecha(seendate: str) -> date | None:
    """'20191012T184500Z' → date. None si no se puede leer."""
    try:
        return datetime.strptime(seendate[:8], "%Y%m%d").date()
    except (ValueError, TypeError):
        return None


def articulos(path: Path, cod: str) -> Iterator[dict]:
    """Registros de un fichero crudo, listos para cargar.

    `url_sha1` es la segunda mitad de la clave. La URL en crudo no sirve como clave: hay
    enlaces de más de 2.700 bytes y un índice B-tree de PostgreSQL no los admite.
    """
    try:
        datos = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return
    for art in datos.get("articles") or []:
        url = (art.get("url") or "").strip()
        titular = " ".join((art.get("title") or "").split())
        if not url or not titular:
            continue
        yield {
            "cod": cod,
            "url_sha1": hashlib.sha1(url.encode("utf-8")).hexdigest(),  # noqa: S324 — clave, no seguridad
            "url": url,
            "titular": titular,
            "medio": (art.get("domain") or "")[:160],
            "fecha": _fecha(art.get("seendate") or ""),
            "idioma": (art.get("language") or "")[:20],
        }


def saturado(path: Path) -> bool:
    """¿Esta consulta alcanzó el tope de la API?

    Importa para la honestidad del dato: si un municipio-año trae 250 artículos, el número
    real es "250 o más", no 250. Cualquier feature que cuente noticias tiene que saberlo.
    """
    try:
        datos = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return False
    return len(datos.get("articles") or []) >= MAXRECORDS


def anios(spec: str) -> tuple[int, ...]:
    """Parsea la ventana de años: `'2018,2024'` o `'2017-2025'`. Vacío → tupla vacía."""
    spec = spec.strip()
    if not spec:
        return ()
    if "-" in spec:
        ini, fin = (int(x) for x in spec.split("-", 1))
        return tuple(range(ini, fin + 1))
    return tuple(int(x) for x in spec.split(",") if x.strip())
