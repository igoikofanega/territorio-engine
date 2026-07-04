"""Puntos de inflexión: el año en que cada pueblo 'se dio la vuelta'.

Sobre la serie de población 2015-2025 de cada municipio se busca el año que mejor
parte la serie en dos tramos lineales (mínimo error cuadrático combinado). Si ese
ajuste a dos tramos mejora sustancialmente al de una sola recta y las pendientes
cambian de forma relevante, se declara un punto de inflexión con su año, las
pendientes antes/después (hab/año) y el tipo de giro (remonta / se hunde / acelera /
frena). No es causal: marca CUÁNDO cambió la tendencia, no por qué.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sqlalchemy.engine import Engine

MIN_ANIOS = 7  # mínimo de puntos para intentar detectar inflexión
MEJORA_MIN = 0.30  # el ajuste a 2 tramos debe reducir el SSE al menos un 30%
CAMBIO_PENDIENTE_MIN = 0.003  # cambio mínimo de pendiente relativo a la población (frac/año)


def _sse_recta(x: np.ndarray, y: np.ndarray) -> float:
    """SSE del ajuste lineal por mínimos cuadrados."""
    if len(x) < 2:
        return 0.0
    a, b = np.polyfit(x, y, 1)
    return float(np.sum((y - (a * x + b)) ** 2))


def _pendiente(x: np.ndarray, y: np.ndarray) -> float:
    return float(np.polyfit(x, y, 1)[0]) if len(x) >= 2 else 0.0


def _clasificar(m_antes: float, m_despues: float) -> str:
    """Etiqueta legible del giro según el signo/magnitud de las pendientes."""
    if m_antes <= 0 < m_despues:
        return "remonta"
    if m_antes >= 0 > m_despues:
        return "se hunde"
    if m_despues > m_antes:
        return "acelera" if m_despues > 0 else "frena caída"
    return "frena" if m_despues >= 0 else "acelera caída"


def calcular_inflexiones(engine: Engine) -> list[dict]:
    """[{cod, anio_inflexion, pend_antes, pend_despues, tipo, magnitud}] por municipio."""
    df = pd.read_sql(
        "SELECT cod_municipio AS cod, anio, poblacion_total AS pob "
        "FROM fact_municipio_anual WHERE poblacion_total IS NOT NULL ORDER BY cod, anio",
        engine,
    )
    salida = []
    for cod, g in df.groupby("cod"):
        x = g["anio"].to_numpy(dtype=float)
        y = g["pob"].to_numpy(dtype=float)
        if len(x) < MIN_ANIOS or y.mean() <= 0:
            continue
        sse_base = _sse_recta(x, y)
        if sse_base <= 0:
            continue
        mejor = None
        # el punto de corte pertenece a ambos tramos (piecewise continuo por tramos)
        for k in range(2, len(x) - 2):
            xa, ya, xb, yb = x[: k + 1], y[: k + 1], x[k:], y[k:]
            sse = _sse_recta(xa, ya) + _sse_recta(xb, yb)
            if mejor is None or sse < mejor[0]:
                mejor = (sse, int(x[k]), _pendiente(xa, ya), _pendiente(xb, yb))
        if mejor is None:
            continue
        sse2, anio_c, m_antes, m_despues = mejor
        mejora = 1 - sse2 / sse_base
        cambio_rel = abs(m_despues - m_antes) / y.mean()
        if mejora < MEJORA_MIN or cambio_rel < CAMBIO_PENDIENTE_MIN:
            continue
        salida.append(
            {
                "cod": cod,
                "anio_inflexion": anio_c,
                "pend_antes": round(m_antes, 1),
                "pend_despues": round(m_despues, 1),
                "tipo": _clasificar(m_antes, m_despues),
                "magnitud": round(float(cambio_rel * 100), 2),  # cambio de pendiente en %/año
            }
        )
    return salida
