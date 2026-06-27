"""Índice compuesto "¿dónde vivir?" (0-100).

Combina varias capas normalizadas a percentil (0-100) y orientadas para que "más es
mejor": renta ↑, paro ↓, alquiler ↓ (asequibilidad), envejecimiento ↓ (vitalidad).
Los pesos son una ELECCIÓN (no una verdad objetiva); se exponen aquí y en docs. La
normalización a percentil se hace en el loader (vectorizada); aquí solo la combinación
ponderada, que renormaliza sobre los componentes disponibles (cobertura parcial).
"""

from __future__ import annotations

import math

# peso de cada componente (suman 1.0)
PESOS: dict[str, float] = {
    "renta": 0.30,
    "paro": 0.25,
    "alquiler": 0.25,
    "envejecimiento": 0.20,
}
# True = más es mejor; False = menos es mejor (se invierte el percentil en el loader)
MEJOR_ALTO: dict[str, bool] = {
    "renta": True,
    "paro": False,
    "alquiler": False,
    "envejecimiento": False,
}


def _vacio(valor: float | None) -> bool:
    return valor is None or (isinstance(valor, float) and math.isnan(valor))


def combina(componentes: dict[str, float | None], pesos: dict[str, float] = PESOS) -> float | None:
    """Media ponderada de los percentiles ya orientados. Renormaliza sobre los presentes.

    Devuelve None si no hay ningún componente disponible.
    """
    num = den = 0.0
    for clave, valor in componentes.items():
        if _vacio(valor):
            continue
        num += pesos[clave] * valor
        den += pesos[clave]
    return round(num / den, 1) if den > 0 else None
