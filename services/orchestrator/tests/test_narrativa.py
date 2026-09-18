"""Tests del grounding determinista de los informes narrativos. Sin LLM.

Lo que se prueba es la validación, no la generación: los tres candados (cifras, nombres,
prompt) son funciones puras que deben detectar violaciones de forma fiable.
"""

from __future__ import annotations

import pytest

from territorio_pipelines import llm
from territorio_pipelines.narrativa import (
    SISTEMA,
    _lecturas,
    _numeros_del_contexto,
    hash_datos,
    recorrer,
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


class TestLecturas:
    def test_enteros(self):
        assert _lecturas("37286") == {37286.0}

    def test_formato_espanol_con_miles_y_decimales(self):
        assert _lecturas("14.520,5") == {14520.5}

    def test_porcentaje(self):
        assert _lecturas("2,3%") == {2.3}

    def test_negativos(self):
        assert _lecturas("-2,3%") == {-2.3}

    def test_anios(self):
        assert _lecturas("2023") == {2023.0}

    def test_con_punto_y_sin_coma_caben_las_dos_lecturas(self):
        """Miles a la española o decimal a la del JSON: no hay forma de saber cuál."""
        assert _lecturas("8.7") == {87.0, 8.7}


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
        """La violación se informa tal como está escrita. Esa lista vuelve al modelo en el
        reintento, y antes le llegaba "183180.0" por un "18318.0" que él mismo había
        escrito: una corrección que no había forma de entender."""
        texto = "La población alcanzó los 99999 habitantes."
        violaciones = verificar_cifras(texto, DATOS_EJEMPLO)
        assert violaciones == ["99999"]

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


# --- recorrer: el bucle de generación, sin base de datos ni LLM ---------------------


def _candidatos(n: int) -> list[tuple[str, dict]]:
    return [(f"31{i:03d}", {"poblacion": 100 + i}) for i in range(1, n + 1)]


class _Registro:
    """Hace de LLM y de base de datos: apunta qué se generó y qué se guardó."""

    def __init__(self, aceptar: bool = True, fallar_en: int | None = None, error=None):
        self.generados: list[dict] = []
        self.guardados: list[tuple[str, str, bool]] = []
        self.aceptar = aceptar
        self.fallar_en = fallar_en
        self.error = error or llm.CuotaAgotada("429 tras 3 intentos")

    def generar(self, datos: dict) -> dict:
        if self.fallar_en is not None and len(self.generados) == self.fallar_en:
            raise self.error
        self.generados.append(datos)
        return {"texto": "informe" if self.aceptar else None, "aceptado": self.aceptar}

    def guardar(self, cod: str, h: str, resultado: dict) -> None:
        self.guardados.append((cod, h, resultado["aceptado"]))


class TestRecorrer:
    def test_salta_lo_que_no_ha_cambiado_sin_llamar_al_modelo(self):
        cands = _candidatos(3)
        previos = {cod: hash_datos(datos) for cod, datos in cands}
        r = _Registro()
        res = recorrer(cands, previos, r.generar, r.guardar)
        assert r.generados == []
        assert res["sin_cambio"] == 3 and res["pendientes"] == 0

    def test_regenera_cuando_cambian_los_datos(self):
        cands = _candidatos(2)
        previos = {"31001": "hash-de-otros-datos", "31002": hash_datos(cands[1][1])}
        r = _Registro()
        res = recorrer(cands, previos, r.generar, r.guardar)
        assert [c for c, _, _ in r.guardados] == ["31001"]
        assert res["generados"] == 1 and res["sin_cambio"] == 1

    def test_el_limite_cuenta_informes_nuevos_no_candidatos(self):
        """Con el límite aplicado a la lista de candidatos, cada tanda miraba siempre los
        mismos primeros municipios —ya hechos— y nunca avanzaba."""
        cands = _candidatos(6)
        previos = {cod: hash_datos(datos) for cod, datos in cands[:3]}
        r = _Registro()
        res = recorrer(cands, previos, r.generar, r.guardar, limite=2)
        assert [c for c, _, _ in r.guardados] == ["31004", "31005"]
        assert res["generados"] == 2 and res["pendientes"] == 1

    def test_la_cuota_agotada_para_limpio_y_conserva_lo_hecho(self):
        cands = _candidatos(5)
        r = _Registro(fallar_en=2)
        res = recorrer(cands, {}, r.generar, r.guardar)
        assert [c for c, _, _ in r.guardados] == ["31001", "31002"]
        assert res["parado_por_cuota"] is True
        assert res["generados"] == 2 and res["pendientes"] == 3

    def test_un_error_que_no_es_de_cuota_no_se_disfraza_de_cuota(self):
        """Antes se decidía buscando "rate" en el mensaje, que también está en
        "generate" o "iterate": una avería cualquiera podía parar la tanda en silencio."""
        r = _Registro(fallar_en=0, error=ValueError("failed to generate: bad iterate"))
        with pytest.raises(ValueError):
            recorrer(_candidatos(2), {}, r.generar, r.guardar)

    def test_un_rechazado_se_guarda_para_no_volver_a_pagarlo(self):
        """Si no se guardara, cada tanda gastaría de nuevo en el mismo municipio."""
        r = _Registro(aceptar=False)
        res = recorrer(_candidatos(1), {}, r.generar, r.guardar)
        assert r.guardados == [("31001", hash_datos({"poblacion": 101}), False)]
        assert res["rechazados"] == 1 and res["generados"] == 0


# --- La consulta que alimenta el informe --------------------------------------------


class TestConsultaNarrativa:
    """El informe dice que sus cifras salen de la ficha, así que tiene que leer los datos
    como los lee la ficha: cada uno en su último año con valor. Tomar "la última fila de
    la matriz" daba el año en curso, que solo tiene paro de unos meses: el informe se
    quedaba sin población ni renta sin que nada fallara."""

    @pytest.fixture
    def sql(self):
        from territorio_pipelines import loaders

        return " ".join(loaders._SQL_NARRATIVA.text.split())

    def test_no_toma_la_ultima_fila_de_la_matriz(self, sql):
        assert "SELECT * FROM fact_municipio_anual" not in sql

    @pytest.mark.parametrize(
        "columna", ["poblacion_total", "renta_neta_media_persona", "paro_media_anual"]
    )
    def test_cada_dato_sale_de_su_ultimo_anio_con_valor(self, sql, columna):
        assert f"{columna} IS NOT NULL" in sql

    def test_el_paro_exige_un_anio_completo(self, sql):
        """Una media de paro sobre un mes no es comparable con la de un año: en 2026 la
        de Abáigar salía de un solo mes y el informe la daba como la tasa del año."""
        assert "paro_meses >= 12" in sql

    def test_la_probabilidad_de_riesgo_llega_en_porcentaje(self, sql):
        """Como fracción, el informe escribía "una probabilidad de riesgo del 0.022"."""
        assert "AS probabilidad_riesgo_pct" in sql and "AS prob_riesgo," not in sql

    @pytest.mark.parametrize(
        "alias",
        [
            "parados_media_anual",
            "cambio_poblacion_previsto_pct",
            "cambio_previsto_minimo_pct",
            "cambio_previsto_maximo_pct",
            "proyeccion_desde",
            "proyeccion_hasta",
            "factores_de_la_proyeccion",
        ],
    )
    def test_el_nombre_de_cada_dato_dice_lo_que_es(self, sql, alias):
        """El candado solo comprueba que cada cifra exista, no que se use para lo que es.
        Con `paro` = 15 el informe escribió "una tasa de paro del 15 por ciento" (son
        personas), y con `cambio_pct` habló de "tendencia reciente" (es una proyección).
        El nombre del campo es lo único que el modelo tiene para no equivocarse."""
        assert f"AS {alias}" in sql

    @pytest.mark.parametrize("ambiguo", ["AS paro,", "AS cambio_pct", "AS drivers"])
    def test_no_quedan_nombres_ambiguos(self, sql, ambiguo):
        assert ambiguo not in sql

    @pytest.mark.parametrize("alias", ["anio_poblacion", "anio_paro", "anio_renta"])
    def test_cada_cifra_lleva_su_anio(self, sql, alias):
        """Con los datos en años distintos (población 2025, renta 2023), un solo `anio`
        haría que el informe atribuyera la renta al año equivocado."""
        assert f"AS {alias}" in sql


class TestCifrasConPuntoDecimal:
    """El modelo copia los números del JSON tal cual, con punto decimal. El verificador
    solo conocía el formato español (punto = miles) y rechazaba las cifras exactas:
    `8.7` pasaba a 87, `18318.0` a 183180 y `0.022` a 22. Con los datos completos, los
    tres primeros informes salieron rechazados por eso y no por inventar nada."""

    DATOS = {"cambio_pct": 8.7, "renta": 18318.0, "prob": 0.022, "poblacion": 74}

    @pytest.mark.parametrize(
        "texto",
        [
            "un cambio del 8.7 por ciento",
            "una renta de 18318.0 euros",
            "una probabilidad del 0.022",
            "una renta de 18.318 euros",  # formato español: sigue valiendo
            "un cambio del 8,7 por ciento",
        ],
    )
    def test_la_cifra_exacta_en_cualquier_formato_no_es_violacion(self, texto):
        assert verificar_cifras(texto, self.DATOS) == []

    @pytest.mark.parametrize("texto", ["un cambio del 9.3 por ciento", "74.500 habitantes"])
    def test_una_cifra_inventada_sigue_siendo_violacion(self, texto):
        """Aceptar dos lecturas no puede abrir la puerta a cifras que no están."""
        assert verificar_cifras(texto, self.DATOS) != []


class TestPrompt:
    def test_no_pide_una_tendencia_que_no_se_le_da(self):
        """Se le pedía "situación actual → tendencia reciente → proyección" sin un solo
        dato de tendencia, y la sacaba de la proyección: presentaba como pasado lo que el
        modelo espera que ocurra."""
        assert "tendencia reciente" not in SISTEMA

    def test_distingue_lo_previsto_de_lo_ocurrido(self):
        assert "previsto" in SISTEMA and "no un hecho" in SISTEMA

    def test_advierte_que_los_parados_son_personas(self):
        assert "personas, no una tasa" in SISTEMA


class TestNombresQueContienenOtros:
    """El candado buscaba cada municipio de España como subcadena del texto, y el propio
    nombre del municipio siempre aparece. Los 24 rechazados de la primera tanda completa
    lo eran por esto y por nada más: "Ares" dentro de "Areso", "Arcos" en "Los Arcos"."""

    TODOS = {
        "Areso",
        "Ares",
        "Los Arcos",
        "Arcos",
        "Oroz-Betelu",
        "Betelu",
        "Mira",
        "Miranda de Arga",
        "Puente la Reina",
        "Reina",
        "Tafalla",
    }

    @pytest.mark.parametrize(
        "propio",
        ["Areso", "Los Arcos", "Oroz-Betelu", "Miranda de Arga", "Puente la Reina"],
    )
    def test_el_nombre_propio_no_dispara_el_candado(self, propio):
        texto = f"{propio} cuenta con una población de 100 habitantes. En {propio} se prevé…"
        assert verificar_nombres(texto, {propio}, self.TODOS) == []

    def test_citar_de_verdad_otro_municipio_sigue_siendo_violacion(self):
        """Tapar el nombre propio no puede tapar también una mención real a otro."""
        texto = "Los Arcos crece más que Arcos y que Tafalla."
        assert sorted(verificar_nombres(texto, {"Los Arcos"}, self.TODOS)) == ["Arcos", "Tafalla"]

    def test_un_nombre_corto_dentro_de_otra_palabra_no_cuenta(self):
        texto = "Areso mira al futuro con una renta de 20000 euros."
        assert verificar_nombres(texto, {"Areso"}, self.TODOS) == []
