import pandas as pd

from territorio_pipelines.sources.mnp import records_from_dfs

NAT = pd.DataFrame(
    {
        "Provincias": ["Total Nacional", "34 Palencia", "34 Palencia", "34 Palencia"],
        "Periodo": ["2022", "2022", "2010", "2024"],
        "DATA": ["7.5", "5.434163", "6.0", "5.1"],
    }
)
MORT = pd.DataFrame(
    {
        "Provincias": ["34 Palencia", "34 Palencia"],
        "Periodo": ["2022", "2024"],
        "DATA": ["14.23776", "14.9"],
    }
)


def test_records_merge_provincial():
    recs = {(r["cod_provincia"], r["anio"]): r for r in records_from_dfs(NAT, MORT, anio_min=2015)}
    # Total Nacional descartado; 2010 fuera de ventana
    assert set(recs) == {("34", 2022), ("34", 2024)}
    assert round(recs[("34", 2022)]["tasa_natalidad"], 2) == 5.43
    assert round(recs[("34", 2022)]["tasa_mortalidad"], 2) == 14.24
