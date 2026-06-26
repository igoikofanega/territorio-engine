import pytest
from pydantic import ValidationError

from territorio_pipelines.sources.ign import MunicipioProps, feature_to_row

FEATURE = {
    "type": "Feature",
    "properties": {"mun_code": "34034", "mun_name": "Boadilla del Camino", "acom_code": "07"},
    "geometry": {"type": "Polygon", "coordinates": [[[0, 0], [0, 1], [1, 1], [0, 0]]]},
}


def test_feature_to_row_ok():
    props, geom = feature_to_row(FEATURE)
    assert props.mun_code == "34034"
    assert props.mun_code[:2] == "34"  # provincia derivada
    assert geom["type"] == "Polygon"


def test_props_rejects_short_code():
    with pytest.raises(ValidationError):
        MunicipioProps(mun_code="34", mun_name="x")
