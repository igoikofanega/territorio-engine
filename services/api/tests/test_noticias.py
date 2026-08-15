"""Tests del endpoint de noticias. Sin base de datos: se sustituye el motor.

Lo que se comprueba es lo único que puede engañar al usuario: que un municipio fuera de
Navarra no se sirva como "sin noticias" sino como "no consultado". Es la diferencia entre
un dato y un hueco, y el ADR 0005 la declara obligatoria.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from territorio_api import main


class _Conn:
    """Conexión de mentira: la primera consulta da la provincia, la segunda las filas."""

    def __init__(self, provincia, filas=()):
        self.provincia = provincia
        self.filas = filas
        self.consultas = 0

    async def execute(self, *_a, **_k):
        self.consultas += 1
        return self

    def scalar_one_or_none(self):
        return self.provincia

    def all(self):
        return list(self.filas)


class _Engine:
    def __init__(self, conn):
        self.conn = conn

    def connect(self):
        conn = self.conn

        class _Ctx:
            async def __aenter__(self):
                return conn

            async def __aexit__(self, *_a):
                return False

        return _Ctx()


@pytest.fixture
def cliente(monkeypatch):
    def _montar(provincia, filas=()):
        monkeypatch.setattr(main, "engine", _Engine(_Conn(provincia, filas)))
        return TestClient(main.app)

    return _montar


def test_municipio_inexistente_da_404(cliente):
    r = cliente(None).get("/municipio/99999/noticias")
    assert r.status_code == 404


def test_fuera_de_navarra_no_es_cero_noticias_sino_no_consultado(cliente):
    """Un municipio de Cuenca sin noticias no es un municipio que no sale en la prensa."""
    r = cliente("16").get("/municipio/16078/noticias")
    assert r.status_code == 200
    assert r.json()["consultado"] is False
    assert r.json()["noticias"] == []


def test_en_navarra_sin_titulares_si_es_cero(cliente):
    r = cliente("31").get("/municipio/31001/noticias")
    assert r.json()["consultado"] is True
    assert r.json()["noticias"] == []


class _Fila:
    def __init__(self, **kw):
        self.__dict__.update(kw)


def test_serializa_los_titulares(cliente):
    import datetime

    fila = _Fila(
        titular="La fábrica amplía plantilla",
        medio="diariodenavarra.es",
        url="https://diariodenavarra.es/x",
        fecha=datetime.date(2024, 3, 1),
        tema="empleo",
        signo=1.0,
    )
    r = cliente("31", [fila]).get("/municipio/31232/noticias")
    n = r.json()["noticias"][0]
    assert n["fecha"] == "2024-03-01"
    assert n["medio"] == "diariodenavarra.es"
    assert n["tema"] == "empleo"
