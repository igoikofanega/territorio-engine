"""Assets de Dagster que construyen la matriz municipio×año.

Cada asset es un nodo del grafo de datos. De momento son STUBS: declaran la
estructura y las dependencias del MVP. La lógica de ingesta se añadirá fuente a
fuente (ver docs/matrix-spec.md). El asset `matriz_municipio_anual` es el objetivo.
"""

from dagster import AssetExecutionContext, asset


@asset(group_name="dimensiones")
def dim_municipio(context: AssetExecutionContext) -> int:
    """Tabla maestra de municipios + geometrías (fuente: georef-spain/IGN).

    Requiere que la migración de Alembic haya creado la tabla (`make migrate`).
    """
    from .loaders import load_municipios
    from .sources.ign import download_raw

    path = download_raw()
    context.log.info(f"Crudo aterrizado en {path}")
    result = load_municipios(path)
    context.add_output_metadata(result)
    context.log.info(f"dim_municipio: {result}")
    return result["municipios"]


@asset(group_name="fuentes")
def padron(context: AssetExecutionContext) -> int:
    """Población total por municipio y año (INE tabla 29005, .px → pyaxis), 2015→.

    Requiere la migración 0002 (`make migrate`).
    """
    from .loaders import load_padron
    from .sources.padron import download_raw

    path = download_raw()
    context.log.info(f"Crudo aterrizado en {path}")
    result = load_padron(path)
    context.add_output_metadata(result)
    context.log.info(f"padron: {result}")
    return result["filas"]


@asset(group_name="fuentes")
def aire(context: AssetExecutionContext) -> int:
    """Calidad del aire (PM2.5, NO2, PM10, O3) muestreando rasters EEA. Requiere 0028."""
    from .loaders import load_aire

    result = load_aire()
    context.add_output_metadata(result)
    context.log.info(f"aire: {result}")
    return result["municipios"]


@asset(group_name="fuentes")
def fibra(context: AssetExecutionContext) -> int:
    """Cobertura de banda ancha por municipio (SETELECO). Requiere 0027."""
    from .loaders import load_fibra
    from .sources.fibra import download_raw

    path = download_raw()
    context.log.info(f"Crudo aterrizado en {path}")
    result = load_fibra(path)
    context.add_output_metadata(result)
    context.log.info(f"fibra: {result}")
    return result["municipios"]


@asset(group_name="fuentes", deps=[padron])
def nacionalidad(context: AssetExecutionContext) -> int:
    """Población extranjera y % por municipio (INE 33571). Requiere 0025."""
    from .loaders import load_nacionalidad
    from .sources.nacionalidad import download_raw

    path = download_raw()
    context.log.info(f"Crudo aterrizado en {path}")
    result = load_nacionalidad(path)
    context.add_output_metadata(result)
    context.log.info(f"nacionalidad: {result}")
    return result["filas"]


@asset(group_name="fuentes")
def piramide(context: AssetExecutionContext) -> int:
    """Pirámide de edad municipal (INE quinquenal, bucle por 52 provincias), 2015→.

    Requiere la migración 0003 (`make migrate`).
    """
    from .loaders import load_piramide

    result = load_piramide(log=context.log.info)
    context.add_output_metadata(result)
    context.log.info(f"piramide: {result}")
    return result["filas"]


@asset(group_name="fuentes")
def mnp(context: AssetExecutionContext) -> int:
    """Tasas vitales PROVINCIALES (natalidad+mortalidad, INE 1470/1482) → fact_provincia_anual.

    El MNP municipal no existe para municipios pequeños; el modelo aplica estas tasas
    provinciales a la estructura de edad municipal. Requiere la migración 0004.
    """
    from .loaders import load_mnp

    result = load_mnp()
    context.add_output_metadata(result)
    context.log.info(f"mnp: {result}")
    return result["filas"]


@asset(group_name="fuentes")
def renta_adrh(context: AssetExecutionContext) -> int:
    """Renta neta media por persona por municipio (INE ADRH, bucle por provincia), 2015→.

    Requiere la migración 0008.
    """
    from .loaders import load_renta

    result = load_renta()
    context.add_output_metadata(result)
    context.log.info(f"renta_adrh: {result}")
    return result["filas"]


@asset(group_name="fuentes")
def alquiler(context: AssetExecutionContext) -> int:
    """Precio del alquiler €/m² por municipio (SERPAVI/MIVAU, nacional), 2015→.

    Requiere la migración 0009.
    """
    from .loaders import load_alquiler

    result = load_alquiler()
    context.add_output_metadata(result)
    context.log.info(f"alquiler: {result}")
    return result["filas"]


@asset(group_name="fuentes")
def paro_sepe(context: AssetExecutionContext) -> int:
    """Paro registrado por municipio (SEPE, CSV anual nacional → media anual), 2015→.

    Requiere la migración 0007.
    """
    from .loaders import load_paro

    result = load_paro()
    context.add_output_metadata(result)
    context.log.info(f"paro_sepe: {result}")
    return result["filas"]


@asset(
    group_name="matriz",
    deps=[dim_municipio, padron, mnp, renta_adrh, paro_sepe],
)
def matriz_municipio_anual(context: AssetExecutionContext) -> int:
    """Matriz unificada `(cod_municipio, anio)` — objetivo del MVP.

    Funde las fuentes sobre la clave municipal. Alimenta a la API y al modelo
    bandera (trayectoria poblacional por cohorte-componente).
    """
    context.log.info("STUB: fusión de fuentes → fact_municipio_anual (2015→).")
    return 0


@asset(group_name="modelo", deps=[padron])
def proyeccion(context: AssetExecutionContext) -> int:
    """Proyección demográfica municipal (v1: tendencia log-lineal) → proyeccion_municipio.

    Responde "¿hacia dónde va este pueblo?". Requiere la migración 0005 y población
    cargada (asset `padron`).
    """
    from .loaders import load_proyeccion

    result = load_proyeccion()
    context.add_output_metadata(result)
    context.log.info(f"proyeccion: {result}")
    return result["municipios"]


@asset(group_name="fuentes")
def wikidata(context: AssetExecutionContext) -> int:
    """Hechos de Wikidata por municipio (altitud, web, escudo, imagen…). Requiere 0014."""
    from .loaders import load_wikidata

    result = load_wikidata()
    context.add_output_metadata(result)
    context.log.info(f"wikidata: {result}")
    return result["municipios"]


@asset(group_name="fuentes")
def servicios(context: AssetExecutionContext) -> int:
    """Equipamientos (salud/educación/comercio) por municipio desde OSM. Requiere 0015."""
    from .loaders import load_osm

    result = load_osm()
    context.add_output_metadata(result)
    context.log.info(f"servicios: {result}")
    return result["municipios"]


@asset(group_name="fuentes", deps=[wikidata])
def wikipedia(context: AssetExecutionContext) -> int:
    """Descripciones (texto) de Wikipedia por municipio → municipio_wiki. Ingesta lenta."""
    from .loaders import load_wikipedia

    result = load_wikipedia()
    context.add_output_metadata(result)
    context.log.info(f"wikipedia: {result}")
    return result["municipios"]


@asset(group_name="fuentes")
def clima(context: AssetExecutionContext) -> int:
    """Clima por municipio (AEMET, interpolación estación→municipio), normal 2015-2024.

    Requiere la migración 0011 y AEMET_API_KEY. Ingesta lenta (~250 estaciones útiles).
    """
    from .loaders import load_clima

    result = load_clima()
    context.add_output_metadata(result)
    context.log.info(f"clima: {result}")
    return result["municipios"]


@asset(group_name="modelo", deps=[padron, paro_sepe, renta_adrh, alquiler, piramide, servicios])
def indice(context: AssetExecutionContext) -> int:
    """Índice compuesto "¿dónde vivir?" (renta+paro+alquiler+envejecimiento+servicios) → indice_municipio.

    Requiere las migraciones 0010 y 0017 y las capas cargadas (incluidos servicios OSM).
    """
    from .loaders import load_indice

    result = load_indice()
    context.add_output_metadata(result)
    context.log.info(f"indice: {result}")
    return result["municipios"]


@asset(group_name="modelo", deps=[padron, paro_sepe, renta_adrh, alquiler, clima, mnp, piramide])
def prediccion_ml(context: AssetExecutionContext) -> int:
    """Modelo ML (gradient boosting) validado con backtest → prediccion_ml. Requiere 0012.

    Entrena, valida temporalmente, registra en MLflow y predice 2023→2028 con drivers.
    """
    from .loaders import load_prediccion_ml

    result = load_prediccion_ml()
    context.add_output_metadata(result)
    context.log.info(f"prediccion_ml: {result}")
    return result["municipios"]


@asset(group_name="modelo", deps=[padron, paro_sepe, renta_adrh, alquiler, clima])
def similares(context: AssetExecutionContext) -> int:
    """'Pueblos como el tuyo' (vecinos en features) → similar_municipio. Requiere 0016."""
    from .loaders import load_similares

    result = load_similares()
    context.add_output_metadata(result)
    context.log.info(f"similares: {result}")
    return result["municipios"]


@asset(group_name="fuentes", deps=[servicios])
def aislamiento(context: AssetExecutionContext) -> int:
    """Distancias al servicio más cercano y a la capital (PostGIS). Requiere 0020."""
    from .loaders import load_aislamiento

    result = load_aislamiento()
    context.add_output_metadata(result)
    context.log.info(f"aislamiento: {result}")
    return result["municipios"]


@asset(group_name="modelo", deps=[padron, paro_sepe, renta_adrh, alquiler, clima])
def riesgo(context: AssetExecutionContext) -> int:
    """Semáforo de despoblación: P(pérdida fuerte a 5 años), calibrada. Requiere 0022."""
    from .loaders import load_riesgo

    result = load_riesgo()
    context.add_output_metadata(result)
    context.log.info(f"riesgo: {result}")
    return result["municipios"]


@asset(group_name="modelo", deps=[padron, mnp])
def demografia(context: AssetExecutionContext) -> int:
    """Descomposición vegetativo vs migratorio del cambio de población. Requiere 0026."""
    from .loaders import load_demografia

    result = load_demografia()
    context.add_output_metadata(result)
    context.log.info(f"demografia: {result}")
    return result["municipios"]


@asset(group_name="modelo", deps=[padron])
def inflexiones(context: AssetExecutionContext) -> int:
    """Puntos de inflexión de la serie de población (change points). Requiere 0024."""
    from .loaders import load_inflexiones

    result = load_inflexiones()
    context.add_output_metadata(result)
    context.log.info(f"inflexiones: {result}")
    return result["municipios"]


@asset(group_name="modelo", deps=[padron, renta_adrh])
def lisa(context: AssetExecutionContext) -> int:
    """Hot spots LISA (Moran local) de crecimiento y renta. Requiere 0021."""
    from .loaders import load_lisa

    result = load_lisa()
    context.add_output_metadata(result)
    context.log.info(f"lisa: {result}")
    return result["filas"]


@asset(group_name="modelo", deps=[padron, paro_sepe, renta_adrh, alquiler, clima])
def rendimiento(context: AssetExecutionContext) -> int:
    """Residuo out-of-sample: municipios que desafían su predicción. Requiere 0019."""
    from .loaders import load_rendimiento

    result = load_rendimiento()
    context.add_output_metadata(result)
    context.log.info(f"rendimiento: {result}")
    return result["municipios"]


@asset(group_name="modelo", deps=[padron, paro_sepe, renta_adrh, alquiler, clima])
def gemelos(context: AssetExecutionContext) -> int:
    """Gemelos divergentes (vecino en features con destino opuesto). Requiere 0019."""
    from .loaders import load_gemelos

    result = load_gemelos()
    context.add_output_metadata(result)
    context.log.info(f"gemelos: {result}")
    return result["municipios"]


@asset(group_name="modelo", deps=[padron, paro_sepe, renta_adrh, alquiler, clima])
def arquetipos(context: AssetExecutionContext) -> int:
    """Clustering de municipios en arquetipos ('pueblos como el tuyo'). Requiere 0013."""
    from .loaders import load_arquetipos

    result = load_arquetipos()
    context.add_output_metadata(result)
    context.log.info(f"arquetipos: {result}")
    return result["municipios"]


@asset(group_name="modelo", deps=[piramide])
def proyeccion_cohorte(context: AssetExecutionContext) -> int:
    """Proyección v2 cohorte-componente (Hamilton-Perry) → proyeccion_cohorte.

    Solo municipios con pirámide cargada. Requiere la migración 0006.
    """
    from .loaders import load_proyeccion_cohorte

    result = load_proyeccion_cohorte()
    context.add_output_metadata(result)
    context.log.info(f"proyeccion_cohorte: {result}")
    return result["municipios"]
