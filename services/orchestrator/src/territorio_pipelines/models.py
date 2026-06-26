from geoalchemy2 import Geometry
from sqlalchemy import Column, Float, String

from .db import Base


class DimMunicipio(Base):
    """Tabla maestra de municipios. Spec: docs/matrix-spec.md.

    `cod_municipio` es TEXTO de 5 dígitos (ceros a la izquierda). Geometrías en
    4326 (frontend) y 25830 (cálculos métricos peninsulares).
    """

    __tablename__ = "dim_municipio"

    cod_municipio = Column(String(5), primary_key=True)
    nombre = Column(String, nullable=False)
    cod_provincia = Column(String(2), nullable=False, index=True)
    cod_ccaa = Column(String(2))
    superficie_km2 = Column(Float)
    geom_4326 = Column(Geometry("MULTIPOLYGON", srid=4326))
    geom_25830 = Column(Geometry("MULTIPOLYGON", srid=25830))
