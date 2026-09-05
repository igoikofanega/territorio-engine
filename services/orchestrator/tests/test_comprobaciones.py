"""Tests de las comprobaciones de calidad. Sin base de datos: se falsea el motor.

Lo que importa de un `asset_check` no es que pase, es que **sepa fallar**. Una
comprobación que devuelve `passed=True` haga lo que haga es peor que ninguna, porque da
sensación de cobertura. Aquí se le dan datos malos a propósito y se exige que los cace.
"""

from __future__ import annotations

import pytest

from territorio_pipelines import comprobaciones as c


class _Resultado:
    def __init__(self, valor=None, filas=None):
        self._valor, self._filas = valor, filas or []

    def scalar_one(self):
        return self._valor

    def all(self):
        return self._filas


class _Conn:
    def __init__(self, valor=None, filas=None):
        self._r = _Resultado(valor, filas)

    def execute(self, *_a, **_k):
        return self._r

    def __enter__(self):
        return self

    def __exit__(self, *_a):
        return False


class _Engine:
    def __init__(self, valor=None, filas=None):
        self._valor, self._filas = valor, filas

    def connect(self):
        return _Conn(self._valor, self._filas)


class _Fila:
    def __init__(self, anio, n):
        self.anio, self.n = anio, n


@pytest.fixture
def motor(monkeypatch):
    """Sustituye `db.engine`, que las comprobaciones importan dentro de la función."""

    def _montar(valor=None, filas=None):
        from territorio_pipelines import db

        monkeypatch.setattr(db, "engine", _Engine(valor, filas), raising=False)

    return _montar


class TestCodigosDeMunicipio:
    def test_pasa_sin_codigos_mal_formados(self, motor):
        motor(valor=0)
        assert c.codigos_de_municipio_bien_formados().passed

    def test_falla_si_alguno_perdio_el_cero(self, motor):
        motor(valor=311)
        r = c.codigos_de_municipio_bien_formados()
        assert not r.passed
        assert r.metadata["codigos_mal_formados"].value == 311


class TestCensoDeMunicipios:
    def test_pasa_con_la_cifra_real(self, motor):
        motor(valor=c.MUNICIPIOS_ESPERADOS)
        assert c.el_censo_de_municipios_esta_completo().passed

    def test_tolera_una_fusion_municipal(self, motor):
        motor(valor=c.MUNICIPIOS_ESPERADOS - 3)
        assert c.el_censo_de_municipios_esta_completo().passed

    def test_falla_ante_una_carga_a_medias(self, motor):
        motor(valor=c.MUNICIPIOS_ESPERADOS // 2)
        assert not c.el_censo_de_municipios_esta_completo().passed


class TestClaveUnica:
    def test_pasa_sin_duplicados(self, motor):
        motor(valor=0)
        assert c.la_clave_de_la_matriz_es_unica().passed

    def test_falla_con_duplicados(self, motor):
        motor(valor=7)
        assert not c.la_clave_de_la_matriz_es_unica().passed


class TestPoblacionPlausible:
    def test_pasa_en_rango(self, motor):
        motor(valor=0)
        assert c.la_poblacion_es_plausible().passed

    def test_falla_con_valores_imposibles(self, motor):
        motor(valor=2)
        assert not c.la_poblacion_es_plausible().passed


class TestCoberturaPorAnio:
    def test_pasa_con_cobertura_homogenea(self, motor):
        motor(filas=[_Fila(a, 8100) for a in range(2015, 2026)])
        assert c.ningun_anio_pierde_cobertura().passed

    def test_caza_el_anio_cargado_a_medias(self, motor):
        filas = [_Fila(a, 8100) for a in range(2015, 2025)] + [_Fila(2025, 1200)]
        motor(filas=filas)
        r = c.ningun_anio_pierde_cobertura()
        assert not r.passed
        assert "2025" in r.metadata["anios_a_medias"].value

    def test_falla_si_no_hay_ningun_dato(self, motor):
        motor(filas=[])
        assert not c.ningun_anio_pierde_cobertura().passed


def test_todas_las_comprobaciones_estan_registradas():
    """Una comprobación que no entra en `COMPROBACIONES` no se ejecuta nunca.

    Es el fallo silencioso natural de este fichero: se añade un `@asset_check`, se da por
    hecho que Dagster lo descubre, y en realidad nunca corre.
    """
    from dagster import AssetChecksDefinition

    definidas = {k for k, v in vars(c).items() if isinstance(v, AssetChecksDefinition)}
    registradas = {
        k
        for k, v in vars(c).items()
        if isinstance(v, AssetChecksDefinition) and v in c.COMPROBACIONES
    }
    assert definidas == registradas, f"sin registrar en COMPROBACIONES: {definidas - registradas}"
