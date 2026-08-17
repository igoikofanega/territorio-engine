"""Tests del cliente de LLM y del etiquetado de titulares. Sin red y sin clave.

Lo que se prueba es el **parseo**, que es donde falla esto de verdad: el modelo devuelve
JSON envuelto en markdown, con prosa alrededor, con menos objetos de los pedidos o con un
tema que no está en la lista. Ninguna de esas cosas debe tumbar una ejecución de miles de
titulares, y ninguna debe convertirse en una etiqueta inventada.
"""

from __future__ import annotations

import pytest

from territorio_pipelines import extraccion, llm

RESPUESTA_OK = """[
  {"i": 0, "pertenece": true,  "confianza": 0.95, "tema": "empleo",  "signo": -1},
  {"i": 1, "pertenece": false, "confianza": 0.9,  "tema": "cultura", "signo": 0}
]"""


# --- llm.json_de -------------------------------------------------------------------


def test_json_pelado():
    assert llm.json_de('{"a": 1}') == {"a": 1}


def test_json_envuelto_en_markdown():
    """Pasa con casi todos los proveedores por mucho que el prompt pida JSON pelado."""
    assert llm.json_de('```json\n[{"i": 0}]\n```') == [{"i": 0}]
    assert llm.json_de('```\n[{"i": 0}]\n```') == [{"i": 0}]


def test_json_con_prosa_alrededor():
    assert llm.json_de('Aquí tienes el resultado:\n[{"i": 0}]\nEspero que sirva.') == [{"i": 0}]


def test_json_irreconocible_devuelve_none():
    """Devuelve None en vez de lanzar: un lote malo no debe tumbar la ejecución."""
    assert llm.json_de("no hay json aquí") is None
    assert llm.json_de("") is None


def test_config_falla_si_falta_algo(monkeypatch):
    for v in ("LLM_BASE_URL", "LLM_API_KEY", "LLM_MODELO"):
        monkeypatch.delenv(v, raising=False)
    with pytest.raises(RuntimeError, match="LLM_BASE_URL"):
        llm.config()


def test_config_completa(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "https://api.ejemplo.com/v1")
    monkeypatch.setenv("LLM_API_KEY", "sk-falsa")
    monkeypatch.setenv("LLM_MODELO", "un-modelo")
    assert llm.config()["modelo"] == "un-modelo"


# --- extraccion --------------------------------------------------------------------


def test_el_prompt_lleva_el_medio():
    """El dominio desambigua mejor que el titular: elnortedecastilla.es ≠ Navarra."""
    p = extraccion.prompt(
        "Tudela", "Navarra", [{"titular": "Tudela invierte en luminarias", "medio": "elnorte.es"}]
    )
    assert "Tudela (provincia de Navarra, España)" in p
    assert "0. [elnorte.es] Tudela invierte en luminarias" in p


def test_parsear_respuesta_correcta():
    r = extraccion.parsear(RESPUESTA_OK, 2)
    assert r[0] == {"pertenece": True, "confianza": 0.95, "tema": "empleo", "signo": -1.0}
    assert r[1]["pertenece"] is False


def test_parsear_tolera_el_envoltorio_en_un_objeto():
    r = extraccion.parsear('{"resultados": ' + RESPUESTA_OK + "}", 2)
    assert len(r) == 2


def test_un_tema_fuera_de_la_lista_cae_en_otros():
    r = extraccion.parsear('[{"i": 0, "pertenece": true, "tema": "gastronomía", "signo": 0}]', 1)
    assert r[0]["tema"] == "otros"


def test_no_se_inventan_etiquetas():
    """Sin `pertenece` booleano no hay fila: una etiqueta inventada por el parser
    entraría en las métricas como si fuese una decisión del modelo."""
    assert extraccion.parsear('[{"i": 0, "tema": "empleo"}]', 1) == {}
    assert extraccion.parsear('[{"i": 0, "pertenece": "sí"}]', 1) == {}


def test_se_descartan_indices_fuera_de_rango_y_repetidos():
    resp = (
        '[{"i": 5, "pertenece": true}, {"i": 0, "pertenece": true}, {"i": 0, "pertenece": false}]'
    )
    r = extraccion.parsear(resp, 2)
    assert list(r) == [0]
    assert r[0]["pertenece"] is True  # se queda el primero, no el repetido


def test_respuesta_basura_no_lanza():
    assert extraccion.parsear("el modelo se fue por las ramas", 3) == {}


def test_confianza_y_signo_se_acotan():
    r = extraccion.parsear('[{"i": 0, "pertenece": true, "confianza": 7, "signo": -9}]', 1)
    assert r[0]["confianza"] == 1.0
    assert r[0]["signo"] == -1.0


def test_etiquetar_lote_vacio_no_llama_al_modelo():
    assert extraccion.etiquetar(None, "m", "Tudela", "Navarra", []) == {}


# --- comportamiento ante la cuota del proveedor ---------------------------------------


class _ErrorDeCuota(Exception):
    """Sustituto de `openai.RateLimitError`, que necesita una respuesta HTTP real."""


@pytest.fixture
def sin_esperas(monkeypatch):
    """El throttle es correcto en producción e inaceptable en un test."""
    monkeypatch.setattr(llm.time, "sleep", lambda _s: None)


def _cliente_que_siempre_limita(monkeypatch):
    """Cliente cuyo `create` siempre lanza el error de límite del SDK."""
    import openai

    monkeypatch.setattr(openai, "RateLimitError", _ErrorDeCuota)

    class _Completions:
        def create(self, **_kw):
            raise _ErrorDeCuota("429")

    class _Chat:
        completions = _Completions()

    class _Cliente:
        chat = _Chat()

    return _Cliente()


def test_la_cuota_agotada_se_distingue_de_una_averia(monkeypatch, sin_esperas):
    """Un límite diario no se arregla esperando: hay que parar, y quien llama debe poder
    saber que fue eso y no un fallo del código."""
    cliente = _cliente_que_siempre_limita(monkeypatch)
    with pytest.raises(llm.CuotaAgotada):
        llm.completar(cliente, "un-modelo", "sistema", "usuario")


def test_un_429_pasajero_se_reintenta(monkeypatch, sin_esperas):
    """Si el límite era por minuto, el reintento entra y no se pierde la tanda."""
    import openai

    monkeypatch.setattr(openai, "RateLimitError", _ErrorDeCuota)

    class _Msg:
        content = RESPUESTA_OK

    class _Choice:
        message = _Msg()

    class _Resp:
        choices = [_Choice()]

    llamadas = {"n": 0}

    class _Completions:
        def create(self, **_kw):
            llamadas["n"] += 1
            if llamadas["n"] == 1:
                raise _ErrorDeCuota("429")
            return _Resp()

    class _Chat:
        completions = _Completions()

    class _Cliente:
        chat = _Chat()

    assert llm.completar(_Cliente(), "un-modelo", "s", "u") == RESPUESTA_OK
    assert llamadas["n"] == 2
