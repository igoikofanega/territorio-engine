"""Tests del adaptador de GDELT. Sin red: las respuestas van grabadas.

Lo que se prueba con más cuidado son las tres rarezas de la API, porque son las que
romperían la ingesta en silencio: el aviso de exceso de peticiones que llega **con estado
200 y en texto plano**, el cuerpo vacío cuando no hay resultados, y la reanudación.
"""

from __future__ import annotations

import json

import pytest

from territorio_pipelines.sources import gdelt

# Recorte de una respuesta real de la API (consulta "Tudela", 2019).
RESPUESTA = json.dumps(
    {
        "articles": [
            {
                "url": "https://www.diariodenavarra.es/noticias/tudela-patinodromo.html",
                "title": "Los clubes usuarios del Patinódromo ,  de Tudela ,  a la espera",
                "seendate": "20191024T050000Z",
                "domain": "diariodenavarra.es",
                "language": "Spanish",
            },
            {
                # Tudela de Duero (Valladolid): la homonimia que desambigua el LLM, no
                # la ingesta. Aquí tiene que entrar igual.
                "url": "https://www.elnortedecastilla.es/tudela-luminarias.html",
                "title": "Tudela invierte 1,17 millones en el cambio de luminarias",
                "seendate": "20191020T174500Z",
                "domain": "elnortedecastilla.es",
                "language": "Spanish",
            },
            {"url": "", "title": "sin url", "seendate": "20190101T000000Z"},
        ]
    }
)


class _Resp:
    def __init__(self, text: str) -> None:
        self.text = text


class _ClienteFalso:
    """Cliente que devuelve respuestas guionizadas y cuenta las llamadas."""

    def __init__(self, *cuerpos: str) -> None:
        self.cuerpos = list(cuerpos)
        self.llamadas = 0

    def get(self, url, params=None):
        self.llamadas += 1
        return _Resp(self.cuerpos.pop(0))


@pytest.fixture(autouse=True)
def sin_esperas(monkeypatch):
    """El throttle de 5,5 s es correcto en producción e inaceptable en un test."""
    monkeypatch.setattr(gdelt.time, "sleep", lambda _s: None)


def test_nombre_consulta_quita_la_aclaracion_administrativa():
    # Ningún medio escribe "Noáin (Valle de Elorz)"; buscarlo así no encuentra nada.
    assert gdelt.nombre_consulta("Noáin (Valle de Elorz)") == "Noáin"
    assert gdelt.nombre_consulta("Tudela") == "Tudela"


def test_params_acotan_el_anio_completo():
    p = gdelt._params("Tudela", 2019)
    assert p["query"] == '"Tudela" sourcecountry:spain'
    assert p["startdatetime"] == "20190101000000"
    assert p["enddatetime"] == "20191231235959"


def test_articulos_parsea_y_descarta_lo_incompleto(tmp_path):
    f = tmp_path / "2019.json"
    f.write_text(RESPUESTA, encoding="utf-8")
    recs = list(gdelt.articulos(f, "31232"))
    assert len(recs) == 2  # la entrada sin url se descarta
    a = recs[0]
    assert a["cod"] == "31232"
    assert a["medio"] == "diariodenavarra.es"
    assert str(a["fecha"]) == "2019-10-24"
    assert a["titular"] == "Los clubes usuarios del Patinódromo , de Tudela , a la espera"
    assert len(a["url_sha1"]) == 40


def test_articulos_no_revienta_con_un_crudo_ilegible(tmp_path):
    f = tmp_path / "roto.json"
    f.write_text("no soy json", encoding="utf-8")
    assert list(gdelt.articulos(f, "31232")) == []
    assert list(gdelt.articulos(tmp_path / "no-existe.json", "31232")) == []


def test_saturado_detecta_el_tope_de_la_api(tmp_path):
    lleno = tmp_path / "lleno.json"
    arts = [{"url": f"http://x/{i}", "title": "t"} for i in range(gdelt.MAXRECORDS)]
    lleno.write_text(json.dumps({"articles": arts}), encoding="utf-8")
    assert gdelt.saturado(lleno) is True

    corto = tmp_path / "corto.json"
    corto.write_text(RESPUESTA, encoding="utf-8")
    assert gdelt.saturado(corto) is False


def test_cuerpo_vacio_es_cero_resultados_no_un_error():
    """GDELT contesta con el cuerpo vacío cuando no hay noticias. No es un fallo."""
    cliente = _ClienteFalso("")
    assert json.loads(gdelt._pedir(cliente, {"query": "x"}))["articles"] == []


def test_el_aviso_de_limite_se_reintenta_y_no_se_confunde_con_datos():
    """El aviso llega con estado 200 y en texto plano: `resp.json()` lo daría por roto."""
    aviso = "Please limit requests to one every 5 seconds or contact kalev.leetaru5@gmail.com"
    cliente = _ClienteFalso(aviso, RESPUESTA)
    cuerpo = gdelt._pedir(cliente, {"query": "x"})
    assert cliente.llamadas == 2
    assert json.loads(cuerpo)["articles"]


def test_una_consulta_rechazada_falla_alto_y_claro():
    cliente = _ClienteFalso("Your query was malformed")
    with pytest.raises(RuntimeError, match="rechazó la consulta"):
        gdelt._pedir(cliente, {"query": "x"})


def test_descargar_es_reanudable(tmp_path):
    """El crudo ya descargado no se vuelve a pedir: la serie completa son casi 4 horas."""
    cliente = _ClienteFalso(RESPUESTA)
    p1 = gdelt.descargar(cliente, "31232", "Tudela", 2019, tmp_path)
    assert cliente.llamadas == 1

    p2 = gdelt.descargar(cliente, "31232", "Tudela", 2019, tmp_path)
    assert p2 == p1
    assert cliente.llamadas == 1  # no ha vuelto a llamar


def test_descargar_no_deja_temporales(tmp_path):
    gdelt.descargar(_ClienteFalso(RESPUESTA), "31232", "Tudela", 2019, tmp_path)
    assert list((tmp_path / "31232").glob("*.tmp")) == []


def test_anios_acepta_rango_y_lista():
    assert gdelt.anios("2017-2020") == (2017, 2018, 2019, 2020)
    assert gdelt.anios("2018,2024") == (2018, 2024)
    assert gdelt.anios("") == ()
