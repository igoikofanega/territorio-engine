from geoalchemy2 import Geometry
from sqlalchemy import Boolean, Column, Date, Float, Integer, String

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

    Crece por columnas a medida que entran fuentes nuevas; el orden de abajo sigue el
    de las migraciones que las añadieron. Mantener esto sincronizado con Alembic no es
    cosmético: `migrations/env.py` usa `Base.metadata` como `target_metadata`, así que
    una columna que exista en la BD pero no aquí sería propuesta para BORRARSE en el
    siguiente `alembic revision --autogenerate`. Lo verifica `test_modelos.py`.
    """

    __tablename__ = "fact_municipio_anual"

    cod_municipio = Column(String(5), primary_key=True)
    anio = Column(Integer, primary_key=True)
    # 0002 — Padrón (INE 29005)
    poblacion_total = Column(Integer)
    poblacion_hombres = Column(Integer)
    poblacion_mujeres = Column(Integer)
    # 0007 — paro registrado (SEPE)
    paro_media_anual = Column(Integer)
    # 0008 — renta (INE/AEAT ADRH)
    renta_neta_media_persona = Column(Float)
    # 0009 — alquiler de referencia (SERPAVI/MIVAU)
    alquiler_eur_m2 = Column(Float)
    # 0011 — clima (AEMET)
    temp_media_anual = Column(Float)
    precip_anual_mm = Column(Float)
    # 0023 — más variables meteorológicas (AEMET)
    temp_max_media = Column(Float)
    temp_min_media = Column(Float)
    temp_min_abs = Column(Float)
    dias_despejados = Column(Float)
    humedad_media = Column(Float)
    # 0025 — población extranjera (INE 33571)
    poblacion_extranjera = Column(Integer)
    pct_extranjeros = Column(Float)


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


class DemografiaMunicipio(Base):
    """Descomposición del cambio de población 2015-2024 en vegetativo y migratorio."""

    __tablename__ = "demografia_municipio"

    cod_municipio = Column(String(5), primary_key=True)
    saldo_vegetativo = Column(Integer)
    saldo_migratorio = Column(Integer)
    cambio_total = Column(Integer)
    dominante = Column(String(12))
    tipo = Column(String(32))


class InflexionMunicipio(Base):
    """Punto de inflexión de la serie de población: el año en que el pueblo se dio la vuelta."""

    __tablename__ = "inflexion_municipio"

    cod_municipio = Column(String(5), primary_key=True)
    anio_inflexion = Column(Integer)
    pend_antes = Column(Float)
    pend_despues = Column(Float)
    tipo = Column(String(16))
    magnitud = Column(Float)


class RiesgoMunicipio(Base):
    """Semáforo de despoblación: probabilidad calibrada de pérdida fuerte a 5 años."""

    __tablename__ = "riesgo_municipio"

    cod_municipio = Column(String(5), primary_key=True)
    prob = Column(Float)
    nivel = Column(String(6))


class LisaMunicipio(Base):
    """Cluster espacial LISA (Moran local) por variable: hot/cold spots significativos."""

    __tablename__ = "lisa_municipio"

    cod_municipio = Column(String(5), primary_key=True)
    variable = Column(String(20), primary_key=True)
    valor = Column(Float)
    categoria = Column(String(10))
    p = Column(Float)


class MunicipioAire(Base):
    """Calidad del aire por municipio (EEA, mapas interpolados): PM2.5, NO2, PM10, O3."""

    __tablename__ = "municipio_aire"

    cod_municipio = Column(String(5), primary_key=True)
    pm25 = Column(Float)
    no2 = Column(Float)
    pm10 = Column(Float)
    o3 = Column(Float)


class MunicipioConectividad(Base):
    """Cobertura de banda ancha por municipio (SETELECO): fibra, ≥100 Mbps y 5G."""

    __tablename__ = "municipio_conectividad"

    cod_municipio = Column(String(5), primary_key=True)
    pct_fibra = Column(Float)
    pct_100mbps = Column(Float)
    pct_5g = Column(Float)


class MunicipioAislamiento(Base):
    """Distancias en km al servicio más cercano y a la capital de provincia (proxy)."""

    __tablename__ = "municipio_aislamiento"

    cod_municipio = Column(String(5), primary_key=True)
    km_salud = Column(Float)
    km_educacion = Column(Float)
    km_capital = Column(Float)


class RendimientoMunicipio(Base):
    """Residuo out-of-sample del modelo: crece más/menos de lo que sus features predicen."""

    __tablename__ = "rendimiento_municipio"

    cod_municipio = Column(String(5), primary_key=True)
    residuo = Column(Float)
    z = Column(Float)
    n_obs = Column(Integer)
    clasificacion = Column(String(10))


class GemeloMunicipio(Base):
    """Gemelo divergente: el municipio más parecido en features con destino distinto."""

    __tablename__ = "gemelo_municipio"

    cod_municipio = Column(String(5), primary_key=True)
    cod_gemelo = Column(String(5))
    distancia = Column(Float)
    crec_propio = Column(Float)
    crec_gemelo = Column(Float)
    divergencia = Column(Float)


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


class NoticiaMunicipio(Base):
    """Artículos de prensa atribuidos a un municipio (GDELT DOC 2.0). Ver ADR 0005.

    Único grano no anual del repositorio: la fila es `(municipio, artículo)`, y la
    agregación a `municipio × año` se hace en la capa de features, no aquí.

    **Solo metadatos.** Titular, fecha, medio y URL; nunca el cuerpo del artículo.

    Las cuatro últimas columnas las rellena la extracción con LLM y son nulas hasta
    entonces. `pertenece` es la importante: la consulta a GDELT es por nombre, así que
    "Tudela" trae también noticias de Tudela de Duero. `modelo` guarda con qué se
    etiquetó, porque una etiqueta sin saber quién la puso no es reproducible.
    """

    __tablename__ = "noticia_municipio"

    cod_municipio = Column(String(5), primary_key=True)
    #: La URL no vale como clave: las hay de más de 2.700 bytes y no caben en un B-tree.
    url_sha1 = Column(String(40), primary_key=True)
    url = Column(String, nullable=False)
    titular = Column(String, nullable=False)
    medio = Column(String(160))
    fecha = Column(Date, index=True)
    idioma = Column(String(20))
    pertenece = Column(Boolean)
    confianza = Column(Float)
    tema = Column(String(40))
    signo = Column(Float)
    modelo = Column(String(80))


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
