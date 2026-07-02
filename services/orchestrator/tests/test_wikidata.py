from territorio_pipelines.sources.wikidata import records_from_bindings


def test_parse_binding():
    b = [
        {
            "ine": {"value": "28079"},
            "altitud": {"value": "663"},
            "articulo": {"value": "https://es.wikipedia.org/wiki/Madrid"},
        }
    ]
    r = list(records_from_bindings(b))
    assert r[0]["cod"] == "28079"
    assert r[0]["altitud"] == 663.0
    assert r[0]["wiki_titulo"] == "Madrid"


def test_zfill_y_dedup():
    b = [{"ine": {"value": "1001"}}, {"ine": {"value": "01001"}}]  # ambos → 01001, dedup
    r = list(records_from_bindings(b))
    assert len(r) == 1
    assert r[0]["cod"] == "01001"
