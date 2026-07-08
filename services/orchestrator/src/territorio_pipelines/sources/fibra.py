"""Adaptador de cobertura de banda ancha (SETELECO / Mº Transformación Digital).

Fuente: "Cobertura de Banda Ancha en España 2021-2025" (XLSX oficial, hoja
`Municipio_%hogar`), % de hogares con cobertura por tecnología y velocidad. Nos
quedamos con el año más reciente (junio 2025) de tres señales: FTTH (fibra hasta
el hogar), cobertura ≥100 Mbps y 5G. La fibra es un buen proxy de viabilidad del
teletrabajo, clave en el vuelco rural reciente.

El fichero se sirve desde `digital.gob.es` (el host `avance.digital.gob.es`
devuelve una página HTML, no el binario).
"""

from __future__ import annotations

import os
import re
from collections.abc import Iterator
from pathlib import Path

import httpx
import openpyxl

_DAM = (
    "/content/dam/portal-mtdfp/avance-digital/telecomunicacion-e-infraestructuras-digitales/"
    "areas_interes/banda-ancha/cobertura/documents/"
    "Cobertura_BA_Espa%C3%B1a_2021-2025_MUN_PROV_CCAA_Nacional_datosgob_DEF.xlsx"
)
EXPORT_URL = "https://digital.gob.es" + _DAM
RAW_DIR = Path(os.environ.get("RAW_DIR", "/data/raw"))
RAW_FILE = RAW_DIR / "seteleco-cobertura-ba.xlsx"
HOJA = "Municipio_%hogar"
_COD5 = re.compile(r"^\d{5}$")
_ANIO = "2025"  # año más reciente en el fichero


def download_raw(url: str = EXPORT_URL, dest: Path = RAW_FILE) -> Path:
    """Descarga el XLSX a la landing zone. Crudo inmutable: no re-descarga."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        return dest
    with httpx.stream("GET", url, timeout=240, follow_redirects=True) as resp:
        resp.raise_for_status()
        with dest.open("wb") as fh:
            for chunk in resp.iter_bytes():
                fh.write(chunk)
    return dest


def _norm(cabecera: object) -> str:
    return " ".join(str(cabecera or "").split()).lower()


def _localizar_columnas(header: tuple) -> dict[str, int]:
    """Índices de las columnas de interés (año más reciente) por texto de cabecera."""
    cols = {"cod": None, "fibra": None, "c100": None, "c5g": None}
    for j, c in enumerate(header):
        h = _norm(c)
        if h == "cmun":
            cols["cod"] = j
        elif "ftth" in h and _ANIO in h:
            cols["fibra"] = j
        elif "100mbps" in h and _ANIO in h:
            cols["c100"] = j
        elif h.startswith(f"5g (junio {_ANIO}"):
            cols["c5g"] = j
    faltan = [k for k, v in cols.items() if v is None]
    if faltan:
        raise RuntimeError(f"Columnas no encontradas en el XLSX de fibra: {faltan}")
    return cols


def _pct(v: object) -> float | None:
    """Fracción 0-1 → porcentaje 0-100 (1 decimal)."""
    if v is None:
        return None
    try:
        return round(float(v) * 100, 1)
    except (TypeError, ValueError):
        return None


def records(path: Path) -> Iterator[dict]:
    """Filas `(cod, pct_fibra, pct_100mbps, pct_5g)` desde la hoja municipal."""
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb[HOJA]
    it = ws.iter_rows(values_only=True)
    header = next(it)
    cols = _localizar_columnas(header)
    for row in it:
        cod = str(row[cols["cod"]] or "").strip().zfill(5)
        if not _COD5.match(cod):
            continue
        fibra, c100, c5g = _pct(row[cols["fibra"]]), _pct(row[cols["c100"]]), _pct(row[cols["c5g"]])
        if fibra is None and c100 is None and c5g is None:
            continue
        yield {"cod": cod, "pct_fibra": fibra, "pct_100mbps": c100, "pct_5g": c5g}
    wb.close()
