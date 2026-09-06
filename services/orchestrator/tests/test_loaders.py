"""Tests del SQL de carga. Sin base de datos: se inspeccionan las sentencias.

`loaders.py` son 1.240 líneas donde vive todo el SQL del proyecto, y no tenía ni un test.
No se puede ejercitar la escritura sin PostGIS, pero sí se puede exigir que **las
sentencias sean coherentes con el esquema**, que es donde se esconde el fallo caro:

- Un `INSERT` sin `ON CONFLICT` revienta la segunda vez que se ejecuta una ingesta, y las
  ingestas de este proyecto son reanudables por diseño.
- Un `ON CONFLICT` cuya clave no sea la primaria real de la tabla duplica filas en
  silencio, y la matriz se construye por acumulación de UPSERTs: nadie se entera.
- Una columna que se inserta pero **no** se actualiza en el `DO UPDATE` deja valores
  rancios al reingerir. Es el peor de los tres, porque no falla nunca: simplemente el
  dato deja de refrescarse y nadie lo nota hasta que los números dejan de cuadrar.
"""

from __future__ import annotations

import re

import pytest
from sqlalchemy.sql.elements import TextClause

from territorio_pipelines import loaders
from territorio_pipelines.models import Base

#: Columnas que legítimamente no se refrescan en el `DO UPDATE`, con su razón.
#: Cada excepción tiene que estar aquí y justificada; no vale ampliarla sin más.
EXENCIONES = {
    # La clave de conflicto es (cod_municipio, url_sha1) y url_sha1 es el SHA-1 de la
    # propia url: si la clave casa, la url es la misma por construcción.
    ("noticia_municipio", "url"),
}


def _sentencias() -> list[tuple[str, str]]:
    return [(k, v.text) for k, v in vars(loaders).items() if isinstance(v, TextClause)]


def _inserts() -> list[tuple[str, str, str, list[str]]]:
    """(nombre, sql, tabla, columnas) de cada INSERT del módulo."""
    salida = []
    for nombre, sql in _sentencias():
        m = re.search(r"INSERT\s+INTO\s+(\w+)\s*\(([^)]*)\)", sql, re.I | re.S)
        if m:
            cols = [c.strip() for c in m.group(2).split(",")]
            salida.append((nombre, sql, m.group(1), cols))
    return salida


def _clave_conflicto(sql: str) -> list[str] | None:
    m = re.search(r"ON\s+CONFLICT\s*\(([^)]*)\)\s*DO\s+UPDATE", sql, re.I)
    return [c.strip() for c in m.group(1).split(",")] if m else None


def _columnas_actualizadas(sql: str) -> set[str]:
    if "DO UPDATE SET" not in sql:
        return set()
    return set(re.findall(r"(\w+)\s*=\s*", sql.split("DO UPDATE SET", 1)[1]))


IDS = [n for n, _, _, _ in _inserts()]


def test_hay_sentencias_que_inspeccionar():
    """Si un refactor mueve el SQL fuera del módulo, este fichero dejaría de comprobar
    nada y seguiría en verde. Esto lo impide."""
    assert len(_inserts()) >= 20, "se esperaban las ~27 sentencias de carga"


@pytest.mark.parametrize(("nombre", "sql", "tabla", "cols"), _inserts(), ids=IDS)
class TestCadaUpsert:
    def test_es_idempotente(self, nombre, sql, tabla, cols):
        """Las ingestas se relanzan por diseño; un INSERT a secas peta la segunda vez."""
        assert _clave_conflicto(sql) is not None, (
            f"{nombre} no tiene ON CONFLICT ... DO UPDATE: no es reanudable"
        )

    def test_la_tabla_existe_en_el_modelo(self, nombre, sql, tabla, cols):
        assert tabla in Base.metadata.tables, (
            f"{nombre} escribe en {tabla}, que no está en models.py"
        )

    def test_la_clave_de_conflicto_es_la_primaria(self, nombre, sql, tabla, cols):
        """Si no coinciden, PostgreSQL no puede usar el índice único y la fila se duplica
        en vez de actualizarse."""
        pk = [c.name for c in Base.metadata.tables[tabla].primary_key.columns]
        assert _clave_conflicto(sql) == pk, (
            f"{nombre}: ON CONFLICT {_clave_conflicto(sql)} != clave primaria de {tabla} {pk}"
        )

    def test_las_columnas_insertadas_existen(self, nombre, sql, tabla, cols):
        reales = {c.name for c in Base.metadata.tables[tabla].columns}
        assert set(cols) <= reales, f"{nombre} inserta columnas inexistentes: {set(cols) - reales}"

    def test_todo_lo_que_inserta_lo_refresca(self, nombre, sql, tabla, cols):
        """La columna que se inserta pero no se actualiza deja datos rancios al reingerir,
        y no falla nunca: simplemente deja de refrescarse."""
        clave = _clave_conflicto(sql) or []
        actualizadas = _columnas_actualizadas(sql)
        sin_refrescar = {
            c
            for c in cols
            if c not in clave and c not in actualizadas and (tabla, c) not in EXENCIONES
        }
        assert not sin_refrescar, (
            f"{nombre}: {sorted(sin_refrescar)} se insertan pero no se refrescan al reingerir"
        )


def test_las_exenciones_siguen_haciendo_falta():
    """Una exención que ya no aplica es documentación que miente."""
    vivas = set()
    for _n, sql, tabla, cols in _inserts():
        clave = _clave_conflicto(sql) or []
        actualizadas = _columnas_actualizadas(sql)
        vivas |= {(tabla, c) for c in cols if c not in clave and c not in actualizadas}
    assert vivas >= EXENCIONES, f"exenciones que ya no hacen falta: {EXENCIONES - vivas}"


class TestNa:
    """`_na` normaliza los huecos antes de que lleguen al SQL."""

    def test_convierte_nan_en_none(self):
        assert loaders._na(float("nan")) is None

    def test_deja_pasar_los_numeros(self):
        assert loaders._na(3.5) == 3.5
        assert loaders._na(0) == 0.0

    def test_none_sigue_siendo_none(self):
        assert loaders._na(None) is None
