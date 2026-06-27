from territorio_pipelines.indice import combina


def test_combina_completo():
    # 80*.30 + 60*.25 + 40*.25 + 20*.20 = 53.0
    score = combina({"renta": 80, "paro": 60, "alquiler": 40, "envejecimiento": 20})
    assert score == 53.0


def test_combina_renormaliza_parciales():
    # solo renta disponible → su propio valor
    assert combina({"renta": 80, "paro": None, "alquiler": None, "envejecimiento": None}) == 80.0


def test_combina_sin_datos():
    assert combina({"renta": None, "paro": None, "alquiler": None, "envejecimiento": None}) is None
