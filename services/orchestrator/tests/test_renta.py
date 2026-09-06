import pandas as pd

from territorio_pipelines.sources.renta import records_from_df

DF = pd.DataFrame(
    {
        "Unidades territoriales": [
            "28079 Madrid",
            "2807901 Madrid distrito 01",  # distrito (7 díg) → descartar
            "28079 Madrid",
            "28080 Majadahonda",
            "31001 Abáigar",  # enmascarado por secreto estadístico: DATA vacío
        ],
        "Indicadores de renta media y mediana": [
            "Renta neta media por persona",
            "Renta neta media por persona",
            "Renta neta media por hogar",  # otro indicador → descartar
            "Renta neta media por persona",
            "Renta neta media por persona",
        ],
        "Periodo": ["2022", "2022", "2022", "2010", "2019"],  # 2010 fuera de ventana
        "DATA": ["18632.0", "20000.0", "40000.0", "25000.0", ""],
    }
)


def test_solo_municipios_indicador_y_ventana():
    recs = [r for r in records_from_df(DF, anio_min=2015) if not r["secreto"]]
    assert len(recs) == 1
    assert recs[0]["cod"] == "28079"
    assert recs[0]["renta"] == 18632.0


def test_el_secreto_estadistico_se_conserva_no_se_descarta():
    """El INE publica la fila con DATA vacío cuando la renta está protegida. Antes se
    filtraba con `notna()` y el hueco quedaba indistinguible de un municipio que la
    fuente ni siquiera menciona. La diferencia importa: el enmascaramiento está
    correlacionado con el tamaño, y el tamaño predice el target del modelo."""
    recs = {(r["cod"], r["anio"]): r for r in records_from_df(DF, anio_min=2015)}
    assert ("31001", 2019) in recs, "la fila enmascarada se ha descartado"
    enmascarada = recs[("31001", 2019)]
    assert enmascarada["secreto"] is True
    assert enmascarada["renta"] is None


def test_un_valor_medido_no_se_marca_como_secreto():
    recs = {(r["cod"], r["anio"]): r for r in records_from_df(DF, anio_min=2015)}
    assert recs[("28079", 2022)]["secreto"] is False
