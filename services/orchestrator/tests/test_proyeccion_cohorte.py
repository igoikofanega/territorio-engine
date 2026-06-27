from territorio_pipelines.proyeccion_cohorte import ccr, cwr, proyecta, total


def test_ccr_basico_y_cap():
    p0 = {("H", 0): 100.0}
    p1 = {("H", 5): 80.0}
    assert ccr(p0, p1, "H", 0) == 0.8
    assert ccr(p0, p1, "H", 5) is None  # denominador 0
    assert ccr({("H", 0): 1.0}, {("H", 5): 1000.0}, "H", 0) == 2.5  # cap


def test_cwr():
    p = {("H", 0): 5.0, ("M", 15): 60.0, ("M", 20): 40.0}
    assert cwr(p, "H") == 0.05  # 5 / (60+40)


def test_proyecta_envejece_y_decrece():
    # Pirámide vieja: mucha gente mayor, pocos jóvenes y pocas mujeres fértiles.
    base = {("H", 70): 50.0, ("M", 70): 50.0, ("M", 30): 2.0, ("H", 0): 1.0, ("M", 0): 1.0}
    # CCR de supervivencia < 1 en los mayores; sin reemplazo joven
    ccrs = {("H", 70): 0.6, ("M", 70): 0.6, ("M", 30): 0.9, ("H", 0): 0.95, ("M", 0): 0.95}
    cwrs = {"H": 0.3, "M": 0.3}
    proj = proyecta(base, ccrs, cwrs, 2)
    assert total(proj) < total(base)  # un pueblo envejecido decrece
