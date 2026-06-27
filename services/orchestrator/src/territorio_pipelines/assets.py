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
    """Atlas de Distribución de Renta (INE/AEAT), dato a nivel municipio."""
    context.log.info("STUB: renta neta media, Gini, S80/S20 (directo municipio).")
    return 0


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
