import pandas as pd

from territorio_pipelines.sources.paro import records_from_df

DF = pd.DataFrame(
    {
        "Código mes": ["202401", "202402", "202401", "00 raro"],
        "Codigo Municipio": ["04001", "04001", "34120", "Total"],
        "total Paro Registrado": ["80", "100", "5000", "9"],
    }
)


def test_media_anual_y_filtra_agregados():
    recs = {(r["cod"], r["anio"]): r for r in records_from_df(DF)}
    # 04001: media de 80 y 100 = 90; 34120: 5000; "Total" descartado (no 5 díg)
    assert recs[("04001", 2024)]["paro"] == 90
    assert recs[("34120", 2024)]["paro"] == 5000
    assert all(k[0] != "Total" for k in recs)
