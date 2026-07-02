from territorio_pipelines.indice import combina


def test_combina_completo():
    # 80*.25 + 60*.20 + 40*.20 + 20*.15 + 90*.20 = 20 + 12 + 8 + 3 + 18 = 61.0
    score = combina(
        {"renta": 80, "paro": 60, "alquiler": 40, "envejecimiento": 20, "servicios": 90}
    )
    assert score == 61.0


def test_combina_renormaliza_parciales():
    # solo renta disponible → su propio valor
    assert (
        combina(
            {"renta": 80, "paro": None, "alquiler": None, "envejecimiento": None, "servicios": None}
        )
        == 80.0
    )


def test_combina_sin_datos():
    assert (
        combina(
            {
                "renta": None,
                "paro": None,
                "alquiler": None,
                "envejecimiento": None,
                "servicios": None,
            }
        )
        is None
    )
