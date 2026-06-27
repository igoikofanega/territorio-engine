import pandas as pd

from territorio_pipelines.sources.alquiler import records_from_df

DF = pd.DataFrame(
    {
        "CUMUN": ["01001", "01002"],
        "ALQM2_LV_M_VC_14": [5.0, 6.0],  # 2014 fuera de ventana
        "ALQM2_LV_M_VC_22": [6.75, None],  # 01002 sin dato 2022
        "ALQM2_LV_M_VC_24": [7.10, 6.34],
    }
)


def test_ancho_a_largo_y_ventana():
    recs = {(r["cod"], r["anio"]): r["alquiler"] for r in records_from_df(DF, anio_min=2015)}
    assert recs[("01001", 2022)] == 6.75
    assert recs[("01001", 2024)] == 7.10
    assert recs[("01002", 2024)] == 6.34
    assert ("01002", 2022) not in recs  # NaN descartado
    assert all(anio >= 2015 for _, anio in recs)  # 2014 fuera
