"""Modelo de proyección demográfica municipal (v1: tendencia log-lineal).

Ajusta log(población) ~ año sobre la serie del Padrón (2015→) y proyecta a un
horizonte, clasificando la trayectoria. Es la primera respuesta a "¿hacia dónde va
este pueblo?". v2 incorporará cohorte-componente con la pirámide + tasas provinciales.
"""

from __future__ import annotations

import numpy as np

HORIZONTE = 2035


def clasifica(cambio_pct: float, pob_proyectada: float) -> str:
    """Etiqueta de trayectoria a partir del cambio proyectado y el tamaño final."""
    if pob_proyectada < 50:
        return "En extinción"
    if cambio_pct <= -20:
        return "En riesgo de vaciamiento"
    if cambio_pct <= -5:
        return "En declive"
    if cambio_pct < 5:
        return "Estable"
    return "En crecimiento"


def proyecta(anios: list[int], poblaciones: list[int], horizonte: int = HORIZONTE) -> dict | None:
    """Ajusta la tendencia y proyecta. Devuelve None si hay datos insuficientes.

    Función pura (sin BD): regresión OLS de log(pob) sobre el año → CAGR, y
    proyección compuesta desde el último año observado al horizonte.
    """
    pares = [(a, p) for a, p in zip(anios, poblaciones, strict=False) if p and p > 0]
    if len(pares) < 3:
        return None
    pares.sort()
    aa = np.array([a for a, _ in pares], dtype=float)
    logp = np.log(np.array([p for _, p in pares], dtype=float))
    pendiente, _ = np.polyfit(aa, logp, 1)
    cagr = float(np.exp(pendiente) - 1)

    anio_base, pob_base = int(pares[-1][0]), int(pares[-1][1])
    n = horizonte - anio_base
    pob_proyectada = pob_base * (1 + cagr) ** n
    cambio_pct = (pob_proyectada / pob_base - 1) * 100

    return {
        "anio_base": anio_base,
        "pob_base": pob_base,
        "cagr": round(cagr, 5),
        "anio_horizonte": horizonte,
        "pob_proyectada": int(round(pob_proyectada)),
        "cambio_pct": round(cambio_pct, 1),
        "trayectoria": clasifica(cambio_pct, pob_proyectada),
    }
