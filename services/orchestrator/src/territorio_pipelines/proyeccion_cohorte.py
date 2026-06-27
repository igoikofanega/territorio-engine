"""Proyección demográfica v2: cohorte-componente (método Hamilton-Perry).

Usa SOLO las pirámides municipales (no hace falta mortalidad/fecundidad por edad,
que no existen a grano municipal). De dos pirámides separadas 5 años (2017→2022)
deriva las *cohort change ratios* (CCR) por sexo y grupo quinquenal, y proyecta la
pirámide en pasos de 5 años. Los nacimientos se estiman con la *child-woman ratio*
(niños 0-4 / mujeres 15-49). Para municipios pequeños, las CCR/CWR inestables se
sustituyen por la media provincial (borrow strength), todo en el loader.

Tipo pirámide: dict {(sexo, edad_min): poblacion}, sexo ∈ {'H','M'}.
"""

from __future__ import annotations

EDADES = list(range(0, 101, 5))  # 0,5,…,100
MUJERES_FERTILES = [15, 20, 25, 30, 35, 40, 45]
CAP_CCR = 2.5  # techo para evitar explosiones por migración puntual


def ccr(p0: dict, p1: dict, sexo: str, edad: int, cap: float = CAP_CCR) -> float | None:
    """Cohort change ratio del grupo `edad`→`edad+5` entre dos pirámides (t0,t1)."""
    denom = p0.get((sexo, edad), 0.0)
    if denom <= 0:
        return None
    return min(p1.get((sexo, edad + 5), 0.0) / denom, cap)


def cwr(p: dict, sexo: str) -> float | None:
    """Child-woman ratio: niños(0-4) de `sexo` por mujer 15-49."""
    fertiles = sum(p.get(("M", e), 0.0) for e in MUJERES_FERTILES)
    if fertiles <= 0:
        return None
    return p.get((sexo, 0), 0.0) / fertiles


def paso(actual: dict, ccrs: dict, cwrs: dict) -> dict:
    """Avanza la pirámide un paso de 5 años."""
    nuevo: dict = {}
    for sexo in ("H", "M"):
        for edad in EDADES[:-1]:
            r = ccrs.get((sexo, edad)) or 0.0
            nuevo[(sexo, edad + 5)] = r * actual.get((sexo, edad), 0.0)
    fert_old = sum(actual.get(("M", e), 0.0) for e in MUJERES_FERTILES)
    fert_new = sum(nuevo.get(("M", e), 0.0) for e in MUJERES_FERTILES)
    fertiles = 0.5 * (fert_old + fert_new)
    for sexo in ("H", "M"):
        nuevo[(sexo, 0)] = (cwrs.get(sexo) or 0.0) * fertiles
    return nuevo


def proyecta(base: dict, ccrs: dict, cwrs: dict, pasos: int) -> dict:
    """Proyecta `pasos` quinquenios desde la pirámide base."""
    piramide = dict(base)
    for _ in range(pasos):
        piramide = paso(piramide, ccrs, cwrs)
    return piramide


def total(piramide: dict) -> float:
    return sum(piramide.values())
