import pandas as pd

from territorio_pipelines.sources.padron import records_from_df

# Formato largo como el que entrega pyaxis sobre el .px del INE (tabla 29005).
DF = pd.DataFrame(
    {
        "Municipios": [
            "34001 Abarca",
            "34001 Abarca",
            "34001 Abarca",
            "34001 Abarca",  # año fuera de ventana
            "34001 Abarca",  # año reciente
            "Total Nacional",  # agregado: código no es 5 dígitos
        ],
        "Sexo": ["Total", "Hombres", "Mujeres", "Total", "Total", "Total"],
        "Periodo": ["2024", "2024", "2024", "2010", "2025", "2024"],
        "DATA": [100, 48, 52, 90, 110, 47000000],
    }
)


def test_records_filtra_y_pivota():
    recs = {(r["cod"], r["anio"]): r for r in records_from_df(DF, anio_min=2015)}
    assert set(recs) == {("34001", 2024), ("34001", 2025)}  # 2010 fuera; agregado descartado
    assert recs[("34001", 2024)]["total"] == 100
    assert recs[("34001", 2024)]["hombres"] == 48
    assert recs[("34001", 2024)]["mujeres"] == 52
    assert recs[("34001", 2025)]["total"] == 110
