"""Tests de la lectura de números desde el entorno.

El fallo que motivó esto fue real y silencioso: `docker-compose.yml` pasa
`LLM_THROTTLE_S: ${LLM_THROTTLE_S:-}`, así que si el `.env` no la define la variable llega
al contenedor **definida y vacía**. `float(os.environ.get("LLM_THROTTLE_S", "4"))` solo
usa el 4 cuando la variable no existe; vacía, revienta. El módulo `llm` dejaba de poder
importarse y la tanda diaria de etiquetado falló tres mañanas seguidas.
"""

from __future__ import annotations

import importlib
import pathlib
import re

import pytest

from territorio_pipelines import config


class TestNumeroEnv:
    def test_sin_variable_usa_el_defecto(self, monkeypatch):
        monkeypatch.delenv("TE_PRUEBA", raising=False)
        assert config.numero_env("TE_PRUEBA", 4.0) == 4.0

    @pytest.mark.parametrize("vacio", ["", "   ", "\t"])
    def test_vacia_usa_el_defecto(self, monkeypatch, vacio):
        """El caso de producción: compose define la variable aunque el .env no la tenga."""
        monkeypatch.setenv("TE_PRUEBA", vacio)
        assert config.numero_env("TE_PRUEBA", 4.0) == 4.0

    def test_con_valor_lo_convierte_al_tipo_del_defecto(self, monkeypatch):
        monkeypatch.setenv("TE_PRUEBA", "2.5")
        assert config.numero_env("TE_PRUEBA", 4.0) == 2.5
        monkeypatch.setenv("TE_PRUEBA", "25")
        valor = config.numero_env("TE_PRUEBA", 0)
        assert valor == 25 and isinstance(valor, int)

    def test_un_valor_invalido_falla_nombrando_la_variable(self, monkeypatch):
        """Una errata no debe convertirse en el defecto sin avisar: se diría que el ajuste
        se aplica cuando no es así. Tiene que fallar, y decir qué variable está mal."""
        monkeypatch.setenv("TE_PRUEBA", "cuatro")
        with pytest.raises(ValueError, match="TE_PRUEBA"):
            config.numero_env("TE_PRUEBA", 4.0)


def test_llm_se_importa_con_el_throttle_vacio(monkeypatch):
    """Regresión directa del fallo de producción."""
    from territorio_pipelines import llm

    monkeypatch.setenv("LLM_THROTTLE_S", "")
    recargado = importlib.reload(llm)
    try:
        assert recargado.THROTTLE_S == 4.0
    finally:
        monkeypatch.delenv("LLM_THROTTLE_S")
        importlib.reload(llm)


def test_nadie_convierte_el_entorno_a_mano():
    """Guardia contra el patrón que causó el fallo. `int(os.environ.get(...))` parece
    correcto y pasa cualquier revisión; solo revienta con la variable definida y vacía,
    que es justo lo que produce compose. Si este test falla, usa `config.numero_env`."""
    src = pathlib.Path(config.__file__).parent
    patron = re.compile(r"\b(?:int|float)\(\s*os\.environ")
    culpables = [
        f"{p.relative_to(src)}:{n}"
        for p in src.rglob("*.py")
        if p.name != "config.py"  # su docstring describe el patrón que sustituye
        for n, linea in enumerate(p.read_text().splitlines(), 1)
        if patron.search(linea)
    ]
    assert not culpables, f"conversión frágil del entorno en: {culpables}"
