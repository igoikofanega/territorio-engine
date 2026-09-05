"""Tests del grounding determinista de los informes narrativos. Sin LLM.

Lo que se prueba es la validación, no la generación: los tres candados (cifras, nombres,
prompt) son funciones puras que deben detectar violaciones de forma fiable.
"""

from __future__ import annotations

from territorio_pipelines.narrativa import (
    _extraer_numeros,
    _numeros_del_contexto,
    hash_datos,
    verificar_cifras,
    verificar_nombres,
)

DATOS_EJEMPLO = {
    "nombre": "Tudela",
    "poblacion": 37286,
    "cambio_pct": -2.3,
    "renta": 14520.5,
    "similares": [{"nombre": "Tafalla"}],
    "gemelo": {"nombre": "Estella-Lizarra", "divergencia": 4.1},
}


class TestExtraerNumeros:
    def test_enteros(self):
        assert _extraer_numeros("Tiene 37286 habitantes") == [37286.0]

    def test_con_separador_de_miles(self):
        assert _extraer_numeros("Renta de 14.520,5 euros") == [14520.5]

    def test_porcentaje(self):
        nums = _extraer_numeros("Cayó un 2,3%")
        assert 2.3 in nums

    def test_negativos(self):
        nums = _extraer_numeros("Cambio de -2,3%")
        assert -2.3 in nums

    def test_anios(self):
        nums = _extraer_numeros("Entre 2015 y 2023")
        assert 2015.0 in nums
        assert 2023.0 in nums

    def test_sin_numeros(self):
        assert _extraer_numeros("Sin datos numéricos") == []


class TestNumerosDelContexto:
    def test_incluye_valores_y_redondeos(self):
        nums = _numeros_del_contexto({"v": 14520.5})
        assert 14520.5 in nums
        assert 14520.0 in nums  # round() — banker's rounding
        assert 14520.5 in nums  # round(x, 1)

    def test_incluye_rango_de_anios(self):
        nums = _numeros_del_contexto({})
        assert 2015.0 in nums
        assert 2028.0 in nums

    def test_anidados(self):
        nums = _numeros_del_contexto({"a": {"b": 42}})
        assert 42.0 in nums

    def test_listas(self):
        nums = _numeros_del_contexto({"a": [1, 2, 3]})
        assert 1.0 in nums
        assert 3.0 in nums


class TestVerificarCifras:
    def test_cifra_presente_no_es_violacion(self):
        texto = "Tudela tiene 37286 habitantes y una renta de 14.520,5 euros."
        assert verificar_cifras(texto, DATOS_EJEMPLO) == []

    def test_cifra_ausente_es_violacion(self):
        texto = "La población alcanzó los 99999 habitantes."
        violaciones = verificar_cifras(texto, DATOS_EJEMPLO)
        assert "99999.0" in violaciones

    def test_anios_siempre_permitidos(self):
        texto = "Entre 2015 y 2023 la población cayó."
        assert verificar_cifras(texto, DATOS_EJEMPLO) == []

    def test_redondeo_aceptable(self):
        texto = "Cayó un 2,3%."  # en los datos es -2.3
        assert verificar_cifras(texto, DATOS_EJEMPLO) == []


class TestVerificarNombres:
    def test_nombre_permitido(self):
        permitidos = {"Tudela", "Tafalla", "Estella-Lizarra"}
        todos = {"Tudela", "Tafalla", "Estella-Lizarra", "Corella", "Pamplona"}
        assert verificar_nombres("Tudela es similar a Tafalla.", permitidos, todos) == []

    def test_nombre_no_permitido(self):
        permitidos = {"Tudela"}
        todos = {"Tudela", "Pamplona"}
        violaciones = verificar_nombres("Comparado con Pamplona, Tudela...", permitidos, todos)
        assert "Pamplona" in violaciones

    def test_sin_municipios_mencionados(self):
        permitidos = {"Tudela"}
        todos = {"Tudela", "Pamplona"}
        assert verificar_nombres("El municipio tiene 37286 habitantes.", permitidos, todos) == []


class TestHashDatos:
    def test_es_determinista(self):
        assert hash_datos(DATOS_EJEMPLO) == hash_datos(DATOS_EJEMPLO)

    def test_cambia_con_datos_distintos(self):
        otros = {**DATOS_EJEMPLO, "poblacion": 99999}
        assert hash_datos(DATOS_EJEMPLO) != hash_datos(otros)

    def test_longitud_sha1(self):
        assert len(hash_datos(DATOS_EJEMPLO)) == 40
