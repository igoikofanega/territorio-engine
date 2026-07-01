import pytest

from territorio_pipelines.sources.aemet import _num, dms_a_decimal


def test_dms_a_decimal():
    assert dms_a_decimal("394924N") == pytest.approx(39.8233, abs=1e-3)
    assert dms_a_decimal("025309E") == pytest.approx(2.8858, abs=1e-3)
    assert dms_a_decimal("034512W") == pytest.approx(-3.7533, abs=1e-3)  # oeste → negativo


def test_num_limpia_anotaciones():
    assert _num("19,7") == 19.7
    assert _num("42.0(13/ago)") == 42.0
    assert _num(None) is None
    assert _num("") is None
