"""Descomposición del cambio de población: vegetativo vs migratorio.

El cambio de población de un municipio entre 2015 y 2024 se separa en dos motores:
- Saldo vegetativo (nacimientos − defunciones): ESTIMADO aplicando las tasas vitales
  PROVINCIALES (fact_provincia_anual) a la población municipal de cada año. Es una
  aproximación honesta —no hay tasas municipales— pero capta bien el signo y magnitud.
- Saldo migratorio: el residuo (cambio real − vegetativo estimado).

La combinación de signos cuenta la historia: pueblos que solo sobreviven por inmigración,
otros en doble declive, etc. Ata con los puntos de inflexión y el % de extranjeros.
"""

from __future__ import annotations

import pandas as pd
from sqlalchemy.engine import Engine

from .. import calendario as cal

# Ventana de la serie de población: primer y último año con cobertura real.
COLUMNA_SERIE = "poblacion_total"


def _clasificar(veg: float, mig: float) -> str:
    """Etiqueta legible según el signo de cada motor."""
    if veg >= 0 and mig >= 0:
        return "doble motor"
    if veg < 0 <= mig:
        return "sostenido por migración" if (veg + mig) >= 0 else "migración frena la caída"
    if veg >= 0 > mig:
        return "pierde por éxodo"
    return "doble declive"


def calcular_demografia(
    engine: Engine, ini: int | None = None, fin: int | None = None
) -> list[dict]:
    """[{cod, saldo_vegetativo, saldo_migratorio, cambio_total, dominante, tipo}].

    Sin `ini`/`fin` usa toda la ventana con cobertura de población.
    """
    if ini is None:
        ini = cal.primer_anio(engine, COLUMNA_SERIE)
    if fin is None:
        fin = cal.ultimo_anio(engine, COLUMNA_SERIE)
    if ini is None or fin is None or ini >= fin:
        raise RuntimeError(f"ventana de población insuficiente: {ini}-{fin}")
    pop = pd.read_sql(
        "SELECT cod_municipio AS cod, anio, poblacion_total AS pob "
        "FROM fact_municipio_anual WHERE poblacion_total IS NOT NULL",
        engine,
    )
    rates = pd.read_sql(
        "SELECT cod_provincia AS prov, anio, "
        "(tasa_natalidad - tasa_mortalidad) / 1000.0 AS tasa_veg FROM fact_provincia_anual",
        engine,
    )
    wide = pop.pivot_table(index="cod", columns="anio", values="pob")
    rate = rates.pivot_table(index="prov", columns="anio", values="tasa_veg")

    salida = []
    for cod, fila in wide.iterrows():
        if ini not in fila or fin not in fila or pd.isna(fila[ini]) or pd.isna(fila[fin]):
            continue
        prov = cod[:2]
        if prov not in rate.index:
            continue
        # saldo vegetativo acumulado: cada año, población × tasa vegetativa provincial
        veg = 0.0
        ok = True
        for t in range(ini, fin):
            sin_pob = t not in fila or pd.isna(fila[t])
            sin_tasa = t not in rate.columns or pd.isna(rate.loc[prov, t])
            if sin_pob or sin_tasa:
                ok = False
                break
            veg += float(fila[t]) * float(rate.loc[prov, t])
        if not ok:
            continue
        cambio = float(fila[fin]) - float(fila[ini])
        mig = cambio - veg
        salida.append(
            {
                "cod": cod,
                "saldo_vegetativo": round(veg),
                "saldo_migratorio": round(mig),
                "cambio_total": round(cambio),
                "dominante": "vegetativo" if abs(veg) >= abs(mig) else "migratorio",
                "tipo": _clasificar(veg, mig),
            }
        )
    return salida
