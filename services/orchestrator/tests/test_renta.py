import pandas as pd

from territorio_pipelines.sources.renta import records_from_df

DF = pd.DataFrame(
    {
        "Unidades territoriales": [
            "28079 Madrid",
            "2807901 Madrid distrito 01",  # distrito (7 díg) → descartar
            "28079 Madrid",
            "28080 Majadahonda",
        ],
        "Indicadores de renta media y mediana": [
            "Renta neta media por persona",
            "Renta neta media por persona",
            "Renta neta media por hogar",  # otro indicador → descartar
            "Renta neta media por persona",
        ],
        "Periodo": ["2022", "2022", "2022", "2010"],  # 2010 fuera de ventana
        "DATA": ["18632.0", "20000.0", "40000.0", "25000.0"],
    }
)


def test_solo_municipios_indicador_y_ventana():
    recs = list(records_from_df(DF, anio_min=2015))
    assert len(recs) == 1
    assert recs[0]["cod"] == "28079"
    assert recs[0]["renta"] == 18632.0
