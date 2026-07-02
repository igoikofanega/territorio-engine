from territorio_pipelines.sources.wikipedia import extraer


def test_extraer():
    j = {
        "extract": "Madrid es la capital de España.",
        "thumbnail": {"source": "http://img/madrid.jpg"},
    }
    r = extraer(j)
    assert r["descripcion"].startswith("Madrid es la capital")
    assert r["imagen"] == "http://img/madrid.jpg"


def test_extraer_sin_thumbnail():
    assert extraer({"extract": "texto"})["imagen"] is None
