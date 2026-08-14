"""Tests de la derivación de años a partir de la cobertura de los datos.

El caso que justifica todo el módulo es el del **año a medio cargar**: la matriz real
contiene 2026 con 7.030 filas de paro y cero de población, porque el CSV del SEPE del
año en curso se publica antes que el Padrón. Un `max(anio)` ingenuo lo tomaría por el
último año bueno y produciría un dataset vacío sin que nada fallase.

No necesitan base de datos: se inyecta la cobertura directamente.
"""

from __future__ import annotations

import pandas as pd
import pytest

from territorio_pipelines import calendario as cal

# Cobertura real de la matriz en agosto de 2026, simplificada. Nótese 2026: mucho paro,
# nada de población.
COBERTURA_REAL = {
    "poblacion_total": {2015: 8119, 2020: 8131, 2023: 8131, 2024: 8132, 2025: 8132, 2026: 0},
    "paro_media_anual": {2015: 6574, 2020: 8134, 2023: 7490, 2024: 7451, 2025: 7434, 2026: 7030},
    "renta_neta_media_persona": {2015: 6762, 2020: 8123, 2023: 8059, 2024: 0, 2025: 0, 2026: 0},
    "temp_media_anual": {2015: 0, 2020: 0, 2022: 8217, 2023: 0, 2024: 0, 2025: 0, 2026: 0},
    "alquiler_eur_m2": {2015: 1877, 2020: 2146, 2023: 2415, 2024: 2555, 2025: 0, 2026: 0},
}


@pytest.fixture
def engine_falso(monkeypatch):
    """Sustituye `cobertura` por la tabla de arriba: sin base de datos, determinista."""

    def fake(engine, columna, tabla=cal.TABLA):
        return pd.Series(COBERTURA_REAL.get(columna, {}), dtype="int64")

    monkeypatch.setattr(cal, "cobertura", fake)
    return object()  # basta con algo no nulo; nunca se usa


def test_ignora_el_anio_a_medio_cargar(engine_falso):
    """2026 tiene paro pero no población: no puede ser el último año de población."""
    assert cal.ultimo_anio(engine_falso, "poblacion_total") == 2025
    # Y para el paro sí es válido: 7.030 supera el 50% de su mejor año (8.134).
    assert cal.ultimo_anio(engine_falso, "paro_media_anual") == 2026


def test_primer_anio(engine_falso):
    assert cal.primer_anio(engine_falso, "poblacion_total") == 2015


def test_columna_sin_datos_devuelve_none(engine_falso):
    assert cal.ultimo_anio(engine_falso, "columna_que_no_existe") is None
    assert cal.primer_anio(engine_falso, "columna_que_no_existe") is None


def test_una_normal_climatica_en_un_solo_anio(engine_falso):
    """El clima se guarda como normal en un único año; debe detectarse ese año."""
    assert cal.ultimo_anio(engine_falso, "temp_media_anual") == 2022


def test_cobertura_estructuralmente_parcial(engine_falso):
    """El alquiler nunca cubre más de ~2.500 de 8.131 municipios.

    La normalización va contra el mejor año de la *propia* columna, no contra el total
    de municipios; si no, SERPAVI nunca tendría ningún año 'cubierto'.
    """
    assert cal.ultimo_anio(engine_falso, "alquiler_eur_m2") == 2024


def test_ultimo_anio_comun(engine_falso):
    """El año base de la predicción necesita varias columnas a la vez."""
    columnas = ["poblacion_total", "paro_media_anual", "renta_neta_media_persona"]
    # 2024 y 2025 tienen población y paro, pero no renta → cae a 2023.
    assert cal.ultimo_anio_comun(engine_falso, columnas) == 2023


def test_ultimo_anio_comun_sin_interseccion(engine_falso):
    # El clima solo existe en 2022, año sin cobertura declarada de alquiler en la tabla.
    assert cal.ultimo_anio_comun(engine_falso, ["temp_media_anual", "alquiler_eur_m2"]) is None


def test_anios_backtest_es_temporal(engine_falso):
    """El corte debe ser cronológico y dejar fuera los años sin futuro conocido."""
    base, train, val = cal.anios_backtest(engine_falso, horizonte=5)
    assert base == [2015, 2020]  # 2023+ no tienen futuro a 5 años dentro de la ventana
    # Nunca puede haber solape: sería fuga de información.
    assert not set(train) & set(val)
    assert train + val == base
    # Y el orden importa: entrenar con los años antiguos, validar con los recientes.
    assert max(train) < min(val)


def test_anios_backtest_sin_datos_no_revienta(monkeypatch):
    monkeypatch.setattr(cal, "cobertura", lambda e, c, tabla=cal.TABLA: pd.Series(dtype="int64"))
    assert cal.anios_backtest(object(), horizonte=5) == ([], [], [])


def test_anios_backtest_con_ventana_insuficiente(monkeypatch):
    """Si solo queda un año base, no hay validación posible y hay que decirlo."""
    monkeypatch.setattr(
        cal, "cobertura", lambda e, c, tabla=cal.TABLA: pd.Series({2015: 100, 2020: 100})
    )
    base, train, val = cal.anios_backtest(object(), horizonte=5)
    assert base == [2015]
    assert val == []
