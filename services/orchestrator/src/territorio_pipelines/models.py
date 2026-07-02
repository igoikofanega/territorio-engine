from geoalchemy2 import Geometry
from sqlalchemy import Column, Float, Integer, String

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


class FactMunicipioAnual(Base):
    """Matriz de hechos `(cod_municipio, anio)`. Spec: docs/matrix-spec.md.

    Por ahora solo demografía (Padrón). Se ampliará con MNP, renta, paro y clima.
    """

    __tablename__ = "fact_municipio_anual"

    cod_municipio = Column(String(5), primary_key=True)
    anio = Column(Integer, primary_key=True)
    poblacion_total = Column(Integer)
    poblacion_hombres = Column(Integer)
    poblacion_mujeres = Column(Integer)
    paro_media_anual = Column(Integer)
    renta_neta_media_persona = Column(Float)
    alquiler_eur_m2 = Column(Float)
    temp_media_anual = Column(Float)
    precip_anual_mm = Column(Float)


class FactPiramide(Base):
    """Pirámide de edad por municipio (grupos quinquenales). Insumo cohorte-componente.

    `edad_min` = límite inferior del grupo (0,5,…,100). `sexo` = 'H'/'M'.
    """

    __tablename__ = "fact_piramide"

    cod_municipio = Column(String(5), primary_key=True)
    anio = Column(Integer, primary_key=True)
    sexo = Column(String(1), primary_key=True)
    edad_min = Column(Integer, primary_key=True)
    poblacion = Column(Integer)


class FactProvinciaAnual(Base):
    """Tasas vitales por provincia y año (MNP). El modelo las aplica al grano municipal."""

    __tablename__ = "fact_provincia_anual"

    cod_provincia = Column(String(2), primary_key=True)
    anio = Column(Integer, primary_key=True)
    tasa_natalidad = Column(Float)
    tasa_mortalidad = Column(Float)


class ProyeccionMunicipio(Base):
    """Proyección demográfica por municipio (una fila por municipio). v1: tendencia."""

    __tablename__ = "proyeccion_municipio"

    cod_municipio = Column(String(5), primary_key=True)
    anio_base = Column(Integer)
    pob_base = Column(Integer)
    cagr = Column(Float)
    anio_horizonte = Column(Integer)
    pob_proyectada = Column(Integer)
    cambio_pct = Column(Float)
    trayectoria = Column(String)


class IndiceMunicipio(Base):
    """Índice compuesto "¿dónde vivir?" + percentiles por componente (explicabilidad)."""

    __tablename__ = "indice_municipio"

    cod_municipio = Column(String(5), primary_key=True)
    anio = Column(Integer, primary_key=True)
    score = Column(Float)
    c_renta = Column(Float)
    c_paro = Column(Float)
    c_alquiler = Column(Float)
    c_envejecimiento = Column(Float)
    c_servicios = Column(Float)


class PrediccionMl(Base):
    """Predicción del modelo ML (gradient boosting) + banda e explicación por municipio."""

    __tablename__ = "prediccion_ml"

    cod_municipio = Column(String(5), primary_key=True)
    anio_base = Column(Integer)
    anio_horizonte = Column(Integer)
    pob_base = Column(Integer)
    pob_proyectada = Column(Integer)
    cambio_pct = Column(Float)
    cambio_inf = Column(Float)
    cambio_sup = Column(Float)
    drivers = Column(String)


class MunicipioWiki(Base):
    """Hechos de Wikidata + descripción de Wikipedia por municipio (para la ficha)."""

    __tablename__ = "municipio_wiki"

    cod_municipio = Column(String(5), primary_key=True)
    altitud = Column(Float)
    web = Column(String)
    imagen = Column(String)
    escudo = Column(String)
    gentilicio = Column(String)
    wiki_titulo = Column(String)
    descripcion = Column(String)
    wiki_imagen = Column(String)


class MunicipioServicios(Base):
    """Recuento de equipamientos (OSM) por municipio: salud, educación, comercio."""

    __tablename__ = "municipio_servicios"

    cod_municipio = Column(String(5), primary_key=True)
    n_salud = Column(Integer)
    n_educacion = Column(Integer)
    n_comercio = Column(Integer)
    n_total = Column(Integer)


class SimilarMunicipio(Base):
    """'Pueblos como el tuyo': códigos de los municipios más parecidos (separados por coma)."""

    __tablename__ = "similar_municipio"

    cod_municipio = Column(String(5), primary_key=True)
    similares = Column(String)


class ArquetipoMunicipio(Base):
    """Arquetipo (cluster KMeans) de cada municipio + etiqueta legible."""

    __tablename__ = "arquetipo_municipio"

    cod_municipio = Column(String(5), primary_key=True)
    cluster = Column(Integer)
    etiqueta = Column(String)


class ProyeccionCohorte(Base):
    """Proyección cohorte-componente (Hamilton-Perry). Requiere pirámide cargada."""

    __tablename__ = "proyeccion_cohorte"

    cod_municipio = Column(String(5), primary_key=True)
    anio_base = Column(Integer)
    pob_base = Column(Integer)
    anio_horizonte = Column(Integer)
    pob_proyectada = Column(Integer)
    cambio_pct = Column(Float)
    trayectoria = Column(String)
