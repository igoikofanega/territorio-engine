"""Tests del endpoint de narrativa. Sin base de datos."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from territorio_api import main


class _Fila:
    def __init__(self, **kw):
        self.__dict__.update(kw)


class _Conn:
    def __init__(self, fila=None):
        self._fila = fila

    async def execute(self, *_a, **_k):
        return self

    def one_or_none(self):
        return self._fila


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
    def _montar(fila=None):
        monkeypatch.setattr(main, "engine", _Engine(_Conn(fila)))
        return TestClient(main.app)

    return _montar


def test_narrativa_no_disponible(cliente):
    r = cliente().get("/municipio/31999/narrativa")
    assert r.status_code == 200
    assert r.json()["disponible"] is False


def test_narrativa_disponible(cliente):
    fila = _Fila(
        texto="El municipio tiene 500 habitantes.",
        modelo="gemini-3.1-flash-lite",
        aceptado=True,
    )
    r = cliente(fila).get("/municipio/31232/narrativa")
    data = r.json()
    assert data["disponible"] is True
    assert "500 habitantes" in data["texto"]
    assert data["modelo"] == "gemini-3.1-flash-lite"
