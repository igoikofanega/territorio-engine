from territorio_pipelines.proyeccion import clasifica, proyecta


def test_declive_se_proyecta_a_la_baja():
    # Serie claramente decreciente
    fit = proyecta(
        [2015, 2016, 2017, 2018, 2019, 2020], [1000, 950, 900, 860, 820, 780], horizonte=2030
    )
    assert fit is not None
    assert fit["cagr"] < 0
    assert fit["pob_proyectada"] < fit["pob_base"]
    assert fit["trayectoria"] in ("En declive", "En riesgo de vaciamiento", "En extinción")


def test_datos_insuficientes():
    assert proyecta([2015, 2016], [100, 90]) is None


def test_clasifica_umbrales():
    assert clasifica(-30, 500) == "En riesgo de vaciamiento"
    assert clasifica(-10, 500) == "En declive"
    assert clasifica(0, 500) == "Estable"
    assert clasifica(10, 500) == "En crecimiento"
    assert clasifica(-90, 10) == "En extinción"
