"""Años derivados de la cobertura real de los datos, no escritos a mano.

Motivación: la capa de ML tenía años fijados en el código (`ANIO_PRED = 2023`,
`WHERE anio = 2022`, `ANIOS_TRAIN = [2015..2018]`…). Funcionaban, pero caducan solos: en
cuanto entra una fuente con un año nuevo hay que recordar tocar seis ficheros, y si no se
hace el modelo sigue entrenando con una ventana cada vez más vieja sin que nada falle.

El detalle que hace esto menos trivial de lo que parece es que **`max(anio)` no sirve**.
La matriz ya contiene años a medio cargar: 2026 existe con 7.030 filas de paro y cero de
población, porque el CSV del SEPE del año en curso se publica antes que el Padrón. Tomar
ese año como "el último" produciría un dataset vacío en silencio.

Por eso todo aquí se pregunta por **cobertura**: el último año en que una columna tiene
dato para una fracción razonable de los municipios que llega a cubrir en su mejor año. La
normalización es contra el máximo de la propia columna, no contra el total de municipios,
porque hay fuentes con cobertura estructuralmente parcial —el alquiler de SERPAVI nunca
pasa de ~2.500 municipios de 8.131— y exigirles cobertura nacional las descartaría
siempre.
"""

from __future__ import annotations

from collections.abc import Sequence

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

TABLA = "fact_municipio_anual"

#: Fracción del mejor año de una columna que un año debe alcanzar para considerarse
#: cubierto. 0.5 descarta años a medio cargar sin ser tan estricto como para exigir que
#: una fuente esté completa.
COBERTURA_MIN = 0.5


def cobertura(engine: Engine, columna: str, tabla: str = TABLA) -> pd.Series:
    """Nº de filas con dato en `columna`, por año. Índice = año."""
    sql = text(f"""
        SELECT anio, count({columna}) AS n
        FROM {tabla} GROUP BY anio ORDER BY anio
    """)  # noqa: S608 — `columna` y `tabla` son literales del código, no entrada de usuario
    with engine.connect() as conn:
        filas = conn.execute(sql).all()
    return pd.Series({r.anio: r.n for r in filas}, dtype="int64")


def anios_cubiertos(
    engine: Engine,
    columna: str,
    tabla: str = TABLA,
    cobertura_min: float = COBERTURA_MIN,
) -> list[int]:
    """Años en que `columna` alcanza `cobertura_min` de su mejor año, en orden."""
    c = cobertura(engine, columna, tabla)
    if c.empty or c.max() == 0:
        return []
    return sorted(int(a) for a in c[c >= c.max() * cobertura_min].index)


def ultimo_anio(engine: Engine, columna: str, tabla: str = TABLA) -> int | None:
    """Último año con cobertura suficiente de `columna`. None si no hay ninguno."""
    anios = anios_cubiertos(engine, columna, tabla)
    return anios[-1] if anios else None


def primer_anio(engine: Engine, columna: str, tabla: str = TABLA) -> int | None:
    """Primer año con cobertura suficiente de `columna`. None si no hay ninguno."""
    anios = anios_cubiertos(engine, columna, tabla)
    return anios[0] if anios else None


def ultimo_anio_comun(engine: Engine, columnas: Sequence[str], tabla: str = TABLA) -> int | None:
    """Último año en que **todas** las columnas tienen cobertura a la vez.

    Es lo que hace falta para elegir el año base de una predicción: de nada sirve el
    último año de población si ese año no tiene renta ni paro.
    """
    conjuntos = [set(anios_cubiertos(engine, c, tabla)) for c in columnas]
    if not conjuntos:
        return None
    comunes = set.intersection(*conjuntos)
    return max(comunes) if comunes else None


def anios_backtest(
    engine: Engine,
    horizonte: int,
    columna: str = "poblacion_total",
    frac_train: float = 0.67,
) -> tuple[list[int], list[int], list[int]]:
    """Devuelve `(base, train, val)` para un backtest **temporal**.

    Los años base son aquellos cuyo futuro a `horizonte` años ya se conoce: si la
    población llega hasta 2025 y el horizonte es 5, el último año base válido es 2020.
    El corte train/val es cronológico —nunca aleatorio—, con los años antiguos para
    entrenar y los recientes para validar.
    """
    anios = anios_cubiertos(engine, columna)
    if not anios:
        return [], [], []
    tope = anios[-1] - horizonte
    base = [a for a in anios if a <= tope]
    if len(base) < 2:
        return base, base, []
    corte = max(1, round(len(base) * frac_train))
    return base, base[:corte], base[corte:]
