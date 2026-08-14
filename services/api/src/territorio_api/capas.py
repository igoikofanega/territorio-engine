"""Registro declarativo de las capas coropléticas y su factoría de endpoints.

Casi todas las capas del mapa responden a la misma forma: partir de `dim_municipio`,
hacer un LEFT JOIN con la tabla que tiene el dato, filtrar opcionalmente por provincia
y devolver un FeatureCollection con la geometría simplificada. Escribir eso 19 veces a
mano son ~700 líneas que solo se diferencian en la tabla y en la lista de campos.

Aquí se declara cada capa como datos y `registrar()` genera los endpoints. Añadir una
capa nueva es una entrada en `CAPAS`, no un endpoint copiado.

Este registro es el **espejo servidor** de `frontend/src/escalas.ts`: si añades una capa
aquí, el frontend la consume añadiendo su entrada allí.

Fuera de este registro quedan a propósito las capas que no comparten la forma:
`/municipios.geojson` (sin JOIN), `/envejecimiento.geojson` (agrega `fact_piramide` en
una CTE) y `/lisa.geojson` (filtra por variable y valida el parámetro). Forzarlas aquí
haría el registro más complicado que el código que ahorra.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fastapi import APIRouter
from sqlalchemy import text

from .db import engine

# Tolerancia de simplificación de la geometría (grados). Es lo que hace que el
# coroplético de una provincia entera viaje en un tamaño razonable.
GEOM = "ST_AsGeoJSON(ST_SimplifyPreserveTopology(d.geom_4326, 0.001))::json AS geom"


@dataclass(frozen=True)
class Anio:
    """De dónde sale el año de la capa y si el cliente puede elegirlo.

    `columna` restringe el `max(anio)` a las filas donde esa columna tiene dato: el
    último año del padrón no tiene por qué ser el último con renta publicada.
    """

    tabla: str
    columna: str | None = None
    parametro: bool = False

    def sql(self) -> str:
        filtro = f" WHERE {self.columna} IS NOT NULL" if self.columna else ""
        return f"SELECT max(anio) FROM {self.tabla}{filtro}"  # noqa: S608 — literales fijos


@dataclass(frozen=True)
class Capa:
    """Una capa coroplética: de dónde sale el dato y qué campos expone."""

    ruta: str
    resumen: str
    #: (expresión SQL, nombre de la propiedad en el GeoJSON)
    campos: tuple[tuple[str, str], ...]
    tabla: str | None = None
    alias: str = "x"
    #: el LEFT JOIN principal filtra además por `:anio` (tablas con grano municipio×año)
    join_por_anio: bool = False
    #: JOINs adicionales, escritos tal cual (p. ej. servicios necesita la población)
    joins_extra: tuple[str, ...] = field(default_factory=tuple)
    anio: Anio | None = None

    def sql(self, con_prov: bool) -> str:
        seleccion = ", ".join(f"{expr} AS {prop}" for expr, prop in self.campos)
        joins = []
        if self.tabla:
            cond = f"{self.alias}.cod_municipio = d.cod_municipio"
            if self.join_por_anio:
                cond += f" AND {self.alias}.anio = :anio"
            joins.append(f"LEFT JOIN {self.tabla} {self.alias} ON {cond}")
        joins.extend(self.joins_extra)
        where = "WHERE d.cod_provincia = :prov" if con_prov else ""
        return f"""
            SELECT d.cod_municipio, d.nombre, {seleccion}, {GEOM}
            FROM dim_municipio d
            {" ".join(joins)}
            {where}
            ORDER BY d.cod_municipio
        """  # noqa: S608 — todos los fragmentos son literales del registro, no entrada de usuario


def _coleccion(capa: Capa, rows, anio: int | None) -> dict:
    props = [prop for _, prop in capa.campos]
    salida: dict = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "cod_municipio": r.cod_municipio,
                    "nombre": r.nombre,
                    **{p: getattr(r, p) for p in props},
                },
                "geometry": r.geom,
            }
            for r in rows
        ],
    }
    if capa.anio is not None:
        salida["properties"] = {"anio": anio}
    return salida


async def consultar(capa: Capa, prov: str | None, anio: int | None) -> dict:
    """Ejecuta la capa y devuelve el FeatureCollection."""
    async with engine.connect() as conn:
        if capa.anio is not None and anio is None:
            anio = (await conn.execute(text(capa.anio.sql()))).scalar_one_or_none()
        params: dict[str, object] = {}
        if capa.anio is not None:
            params["anio"] = anio
        if prov:
            params["prov"] = prov
        rows = (await conn.execute(text(capa.sql(bool(prov))), params)).all()
    return _coleccion(capa, rows, anio)


# ─────────────────────────────────────────────────────────────────────────────
# El registro. Una entrada por capa; el orden es el del menú del frontend.
# ─────────────────────────────────────────────────────────────────────────────

_FMA = Anio("fact_municipio_anual")

CAPAS: tuple[Capa, ...] = (
    Capa(
        ruta="/coropleta.geojson",
        resumen="Población y densidad por municipio para un año.",
        tabla="fact_municipio_anual",
        alias="f",
        join_por_anio=True,
        anio=Anio("fact_municipio_anual", parametro=True),
        campos=(
            ("f.poblacion_total", "poblacion_total"),
            ("round(f.poblacion_total / NULLIF(d.superficie_km2, 0))::int", "densidad"),
        ),
    ),
    Capa(
        ruta="/renta.geojson",
        resumen="Renta neta media por persona (€/año) por municipio (INE ADRH).",
        tabla="fact_municipio_anual",
        alias="f",
        join_por_anio=True,
        anio=Anio("fact_municipio_anual", "renta_neta_media_persona", parametro=True),
        campos=(("round(f.renta_neta_media_persona)::int", "renta"),),
    ),
    Capa(
        ruta="/alquiler.geojson",
        resumen="Alquiler de referencia (€/m² al mes) por municipio (SERPAVI).",
        tabla="fact_municipio_anual",
        alias="f",
        join_por_anio=True,
        anio=Anio("fact_municipio_anual", "alquiler_eur_m2", parametro=True),
        campos=(("f.alquiler_eur_m2", "alquiler"),),
    ),
    Capa(
        ruta="/paro.geojson",
        resumen="Paro registrado: media anual y tasa por mil habitantes.",
        tabla="fact_municipio_anual",
        alias="f",
        join_por_anio=True,
        anio=Anio("fact_municipio_anual", "paro_media_anual", parametro=True),
        campos=(
            ("f.paro_media_anual", "paro_media_anual"),
            (
                "round(f.paro_media_anual::numeric / NULLIF(f.poblacion_total, 0) * 1000)::int",
                "paro_1000",
            ),
        ),
    ),
    Capa(
        ruta="/extranjeros.geojson",
        resumen="Población de nacionalidad extranjera y su porcentaje (INE 33571).",
        tabla="fact_municipio_anual",
        alias="f",
        join_por_anio=True,
        anio=Anio("fact_municipio_anual", "pct_extranjeros", parametro=True),
        campos=(
            ("f.pct_extranjeros", "pct_extranjeros"),
            ("f.poblacion_extranjera", "poblacion_extranjera"),
        ),
    ),
    Capa(
        ruta="/servicios.geojson",
        resumen="Servicios OSM per cápita por municipio (‰ hab).",
        tabla="municipio_servicios",
        alias="s",
        anio=Anio("fact_municipio_anual", "poblacion_total"),
        joins_extra=(
            "LEFT JOIN fact_municipio_anual f "
            "ON f.cod_municipio = d.cod_municipio AND f.anio = :anio",
        ),
        campos=(
            ("s.n_salud", "n_salud"),
            ("s.n_educacion", "n_educacion"),
            ("s.n_comercio", "n_comercio"),
            ("s.n_total", "n_total"),
            (
                "CASE WHEN f.poblacion_total > 0 "
                "THEN round((s.n_total::numeric / f.poblacion_total * 1000), 2)::float8 "
                "ELSE NULL END",
                "serv_1000",
            ),
        ),
    ),
    Capa(
        ruta="/fibra.geojson",
        resumen="Cobertura de banda ancha: % de hogares con fibra (FTTH), ≥100 Mbps y 5G.",
        tabla="municipio_conectividad",
        alias="c",
        campos=(
            ("c.pct_fibra", "pct_fibra"),
            ("c.pct_100mbps", "pct_100mbps"),
            ("c.pct_5g", "pct_5g"),
        ),
    ),
    Capa(
        ruta="/aire.geojson",
        resumen="Calidad del aire (EEA interpolado): PM2.5, NO2, PM10 y O3 en µg/m³.",
        tabla="municipio_aire",
        alias="a",
        campos=(("a.pm25", "pm25"), ("a.no2", "no2"), ("a.pm10", "pm10"), ("a.o3", "o3")),
    ),
    Capa(
        ruta="/aislamiento.geojson",
        resumen="Distancia por carretera a sanidad, educación y capital de provincia (km).",
        tabla="municipio_aislamiento",
        alias="a",
        campos=(
            ("a.km_salud", "km_salud"),
            ("a.km_educacion", "km_educacion"),
            ("a.km_capital", "km_capital"),
        ),
    ),
    Capa(
        ruta="/clima.geojson",
        resumen="Clima por municipio: temperaturas, precipitación, días despejados y humedad.",
        tabla="fact_municipio_anual",
        alias="f",
        join_por_anio=True,
        anio=Anio("fact_municipio_anual", "temp_media_anual"),
        campos=(
            ("f.temp_media_anual", "temp"),
            ("f.precip_anual_mm", "precip"),
            ("f.temp_max_media", "temp_max_media"),
            ("f.temp_min_media", "temp_min_media"),
            ("f.temp_min_abs", "temp_min_abs"),
            ("f.dias_despejados", "dias_despejados"),
            ("f.humedad_media", "humedad_media"),
        ),
    ),
    Capa(
        ruta="/indice.geojson",
        resumen='Índice "¿dónde vivir?" (0-100) y percentiles por componente.',
        tabla="indice_municipio",
        alias="i",
        join_por_anio=True,
        anio=Anio("indice_municipio"),
        campos=(
            ("i.score", "score"),
            ("i.c_renta", "c_renta"),
            ("i.c_paro", "c_paro"),
            ("i.c_alquiler", "c_alquiler"),
            ("i.c_envejecimiento", "c_envejecimiento"),
            ("i.c_servicios", "c_servicios"),
        ),
    ),
    Capa(
        ruta="/arquetipos.geojson",
        resumen="Arquetipo (clúster) de cada municipio y su etiqueta.",
        tabla="arquetipo_municipio",
        alias="a",
        campos=(("a.cluster", "cluster"), ("a.etiqueta", "etiqueta")),
    ),
    Capa(
        ruta="/rendimiento.geojson",
        resumen="Residuo out-of-sample: municipios que van por encima o por debajo de lo predicho.",
        tabla="rendimiento_municipio",
        alias="r",
        campos=(("r.residuo", "residuo"), ("r.z", "z"), ("r.clasificacion", "clasificacion")),
    ),
    Capa(
        ruta="/inflexion.geojson",
        resumen="Punto de inflexión de la serie de población: el año en que cambió la tendencia.",
        tabla="inflexion_municipio",
        alias="i",
        campos=(
            ("i.anio_inflexion", "anio_inflexion"),
            ("i.pend_antes", "pend_antes"),
            ("i.pend_despues", "pend_despues"),
            ("i.tipo", "tipo"),
            ("i.magnitud", "magnitud"),
        ),
    ),
    Capa(
        ruta="/demografia.geojson",
        resumen="Descomposición del cambio de población: saldo vegetativo frente a migratorio.",
        tabla="demografia_municipio",
        alias="x",
        campos=(
            ("x.saldo_vegetativo", "saldo_vegetativo"),
            ("x.saldo_migratorio", "saldo_migratorio"),
            ("x.cambio_total", "cambio_total"),
            ("x.dominante", "dominante"),
            ("x.tipo", "tipo"),
        ),
    ),
    Capa(
        ruta="/prediccion.geojson",
        resumen="Predicción ML del cambio de población a 5 años, con banda de incertidumbre.",
        tabla="prediccion_ml",
        alias="p",
        campos=(
            ("p.cambio_pct", "cambio_pct"),
            ("p.cambio_inf", "cambio_inf"),
            ("p.cambio_sup", "cambio_sup"),
            ("p.pob_base", "pob_base"),
            ("p.pob_proyectada", "pob_proyectada"),
            ("p.anio_horizonte", "anio_horizonte"),
            ("p.drivers", "drivers"),
        ),
    ),
    Capa(
        ruta="/riesgo.geojson",
        resumen="Semáforo de despoblación: probabilidad calibrada de perder >10% en 5 años.",
        tabla="riesgo_municipio",
        alias="r",
        campos=(
            # La probabilidad se guarda en 0-1 y se sirve en porcentaje.
            ("round((r.prob * 100)::numeric, 1)::float8", "prob"),
            ("r.nivel", "nivel"),
        ),
    ),
    Capa(
        ruta="/futuro.geojson",
        resumen="Proyección demográfica v1 (tendencia log-lineal).",
        tabla="proyeccion_municipio",
        alias="p",
        campos=(
            ("p.cambio_pct", "cambio_pct"),
            ("p.trayectoria", "trayectoria"),
            ("p.pob_base", "pob_base"),
            ("p.pob_proyectada", "pob_proyectada"),
            ("p.anio_horizonte", "anio_horizonte"),
        ),
    ),
    Capa(
        ruta="/futuro-cohorte.geojson",
        resumen="Proyección demográfica v2 (cohorte-componente, Hamilton-Perry).",
        tabla="proyeccion_cohorte",
        alias="p",
        campos=(
            ("p.cambio_pct", "cambio_pct"),
            ("p.trayectoria", "trayectoria"),
            ("p.pob_base", "pob_base"),
            ("p.pob_proyectada", "pob_proyectada"),
            ("p.anio_horizonte", "anio_horizonte"),
        ),
    ),
)

assert len({c.ruta for c in CAPAS}) == len(CAPAS), "hay rutas duplicadas en CAPAS"


def _endpoint(capa: Capa):
    """Construye el handler de una capa.

    Es una función aparte y no un cuerpo de bucle para que cada handler cierre sobre
    *su* capa: definidos dentro del bucle, todos compartirían la variable y acabarían
    sirviendo la última. Además, así la firma que ve FastAPI contiene exactamente los
    parámetros de consulta reales y nada más.
    """
    if capa.anio is not None and capa.anio.parametro:

        async def handler(prov: str | None = None, anio: int | None = None) -> dict:
            return await consultar(capa, prov, anio)
    else:

        async def handler(prov: str | None = None) -> dict:  # type: ignore[misc]
            return await consultar(capa, prov, None)

    handler.__name__ = capa.ruta.strip("/").replace(".geojson", "").replace("-", "_")
    handler.__doc__ = capa.resumen
    return handler


def registrar(router: APIRouter) -> None:
    """Da de alta un endpoint GET por cada capa del registro."""
    for capa in CAPAS:
        router.get(capa.ruta, summary=capa.resumen)(_endpoint(capa))
