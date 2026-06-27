import pandas as pd

from territorio_pipelines.sources.piramide import records_from_df

DF = pd.DataFrame(
    {
        "Sexo": ["Hombres", "Mujeres", "Total", "Hombres", "Hombres"],
        "Municipios": [
            "34001 Abarca",
            "34001 Abarca",
            "34001 Abarca",
            "34001 Abarca",
            "34 Palencia",
        ],
        "Periodo": [
            "1 de enero de 2022",
            "1 de enero de 2022",
            "1 de enero de 2022",
            "1 de enero de 2010",  # fuera de ventana
            "1 de enero de 2022",  # agregado provincial (código no 5 díg)
        ],
        "Edad (grupos quinquenales)": [
            "De 0 a 4 años",
            "De 65 a 69 años",
            "Todas las edades",  # agregado de edad
            "De 0 a 4 años",
            "De 0 a 4 años",
        ],
        "DATA": [10, 8, 999, 7, 5000],
    }
)


def test_records_filtra_y_normaliza():
    recs = list(records_from_df(DF, anio_min=2015))
    # Solo quedan las 2 filas válidas de 2022 (H/0-4 y M/65-69) del municipio 34001
    assert len(recs) == 2
    by = {(r["sexo"], r["edad_min"]): r for r in recs}
    assert by[("H", 0)]["cod"] == "34001"
    assert by[("H", 0)]["poblacion"] == 10
    assert by[("M", 65)]["anio"] == 2022
