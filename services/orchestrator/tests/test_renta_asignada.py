"""La renta que el INE asigna a los municipios de menos de 100 habitantes.

Desde la edición ADRH 2020 el INE ya no deja en blanco la renta de esos municipios: les
asigna la media de los municipios de menos de 100 habitantes de su provincia (ediciones
2020 y 2021) o de su comarca agraria (desde 2022). Metodología ADRH, INE, octubre 2025.

Es uno de cada seis municipios con renta desde 2020, y hasta ahora se guardaba como si
fuera la renta propia del municipio. En Navarra, 22 municipios de Tierra Estella tienen
18.318 € en 2023 porque es la media de su comarca, no porque ganen lo mismo.
"""

from __future__ import annotations

import pytest
from sqlalchemy import Computed

from territorio_pipelines.models import FactMunicipioAnual


@pytest.fixture
def columna():
    return FactMunicipioAnual.__table__.c.flag_renta_asignada


def test_es_una_columna_calculada_por_la_base(columna):
    """Calculada en la fila, no por un cargador: población y renta vienen de fuentes que
    se cargan en cualquier orden, y una marca escrita por uno de los dos quedaría rancia
    en cuanto se recargue el otro."""
    assert isinstance(columna.computed, Computed)
    assert columna.computed.persisted is True


@pytest.mark.parametrize(
    "condicion",
    ["renta_neta_media_persona IS NOT NULL", "anio >= 2020", "poblacion_total < 100"],
)
def test_aplica_la_regla_del_ine(columna, condicion):
    """Las tres a la vez: hay renta, el año es de la etapa en que se asigna en vez de
    ocultarse, y el municipio no llega a los 100 habitantes del umbral."""
    assert condicion in str(columna.computed.sqltext)
