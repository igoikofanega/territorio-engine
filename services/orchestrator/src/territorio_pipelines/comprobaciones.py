"""Comprobaciones de calidad sobre la matriz, como `asset_check` de Dagster.

Por qué existe esto: quince fuentes hacen UPSERT sobre la misma tabla, cada una con sus
columnas, y hasta ahora **nada verificaba el resultado**. Un adaptador que perdiera los
ceros a la izquierda del código INE, o que duplicase la clave, o que cargara media España,
se materializaba en verde y el fallo aparecía semanas después en un mapa raro.

Las comprobaciones son deliberadamente tontas y baratas: cuentan filas y comparan con lo
que la propia base de datos ya sabe. No sustituyen a los tests —que corren sin base de
datos— sino que vigilan **los datos**, que es lo que los tests no pueden ver.

Se ejecutan solas tras materializar su asset, y a mano con:

    make comprobar
"""

from __future__ import annotations

from dagster import AssetCheckResult, AssetCheckSeverity, asset_check
from sqlalchemy import text
from sqlalchemy.engine import Engine

from .assets import dim_municipio, padron

#: Municipios de España según el IGN, que es la fuente de `dim_municipio`. La cifra se
#: mueve poco (fusiones muy ocasionales), así que una desviación grande delata una carga
#: parcial, no un cambio real. Ojo: no coincide con los municipios que tienen población
#: (8.131), porque el Padrón no cubre a todos.
MUNICIPIOS_ESPERADOS = 8217
TOLERANCIA_MUNICIPIOS = 0.02

#: Nadie vive en un municipio de 0 habitantes y ninguno pasa de Madrid.
POBLACION_MAX = 4_000_000


def _uno(engine: Engine, sql: str) -> int:
    with engine.connect() as conn:
        return int(conn.execute(text(sql)).scalar_one())


@asset_check(asset=dim_municipio, blocking=True)
def codigos_de_municipio_bien_formados() -> AssetCheckResult:
    """`cod_municipio` es texto de 5 dígitos: los ceros a la izquierda importan.

    Es la invariante más fácil de romper de todo el proyecto. Basta con que un adaptador
    lea el código como entero —y media docena de fuentes lo publican así— para que las
    provincias 01 a 09 pierdan el cero: Vitoria-Gasteiz deja de ser "01059" y pasa a
    "1059", que no casa con nada. Los municipios de las otras 43 provincias sobreviven,
    así que el fallo se ve como huecos en el norte y en Andalucía occidental, no como un
    error.
    """
    from .db import engine

    malos = _uno(
        engine,
        "SELECT count(*) FROM dim_municipio WHERE cod_municipio !~ '^[0-9]{5}$'",
    )
    return AssetCheckResult(
        passed=malos == 0,
        severity=AssetCheckSeverity.ERROR,
        metadata={"codigos_mal_formados": malos},
        description=(
            "todos los códigos son 5 dígitos"
            if malos == 0
            else f"{malos} códigos no son texto de 5 dígitos"
        ),
    )


@asset_check(asset=dim_municipio)
def el_censo_de_municipios_esta_completo() -> AssetCheckResult:
    """El número de municipios cargados se parece al de España.

    Aviso y no error: una fusión municipal real mueve la cifra, y en ese caso lo correcto
    es actualizar la constante, no bloquear la carga.
    """
    from .db import engine

    n = _uno(engine, "SELECT count(*) FROM dim_municipio")
    desvio = abs(n - MUNICIPIOS_ESPERADOS) / MUNICIPIOS_ESPERADOS
    return AssetCheckResult(
        passed=desvio <= TOLERANCIA_MUNICIPIOS,
        severity=AssetCheckSeverity.WARN,
        metadata={"municipios": n, "esperados": MUNICIPIOS_ESPERADOS, "desvio": round(desvio, 4)},
        description=f"{n} municipios cargados (esperados ~{MUNICIPIOS_ESPERADOS})",
    )


@asset_check(asset=padron, blocking=True)
def la_clave_de_la_matriz_es_unica() -> AssetCheckResult:
    """`(cod_municipio, anio)` no se repite.

    La matriz se construye por acumulación de UPSERTs, así que un duplicado significa que
    algún loader está insertando en vez de actualizar y que las capas están sumando dos
    veces el mismo municipio.
    """
    from .db import engine

    dups = _uno(
        engine,
        "SELECT count(*) FROM (SELECT cod_municipio, anio FROM fact_municipio_anual "
        "GROUP BY cod_municipio, anio HAVING count(*) > 1) d",
    )
    return AssetCheckResult(
        passed=dups == 0,
        severity=AssetCheckSeverity.ERROR,
        metadata={"claves_duplicadas": dups},
        description="clave única" if dups == 0 else f"{dups} claves duplicadas",
    )


@asset_check(asset=padron, blocking=True)
def la_poblacion_es_plausible() -> AssetCheckResult:
    """Sin poblaciones negativas ni imposibles.

    Un valor negativo o absurdo casi siempre significa que se ha leído la columna
    equivocada de un CSV, no que haya pasado algo en el municipio.
    """
    from .db import engine

    malos = _uno(
        engine,
        "SELECT count(*) FROM fact_municipio_anual WHERE poblacion_total IS NOT NULL "
        f"AND (poblacion_total < 0 OR poblacion_total > {POBLACION_MAX})",
    )
    return AssetCheckResult(
        passed=malos == 0,
        severity=AssetCheckSeverity.ERROR,
        metadata={"valores_implausibles": malos, "maximo_admitido": POBLACION_MAX},
        description="población dentro de rango" if malos == 0 else f"{malos} valores imposibles",
    )


@asset_check(asset=padron)
def ningun_anio_pierde_cobertura() -> AssetCheckResult:
    """Ningún año con población tiene mucha menos que el año mejor cubierto.

    Detecta la carga a medias: si el Padrón de un año entra sólo para media España, la
    serie se rompe en silencio y los modelos entrenan con un año mutilado sin avisar.
    Es la versión "por año" de la trampa que `calendario.py` resuelve por columna.
    """
    from .db import engine

    with engine.connect() as conn:
        filas = conn.execute(
            text(
                "SELECT anio, count(poblacion_total) AS n FROM fact_municipio_anual "
                "GROUP BY anio HAVING count(poblacion_total) > 0 ORDER BY anio"
            )
        ).all()
    if not filas:
        return AssetCheckResult(
            passed=False,
            severity=AssetCheckSeverity.ERROR,
            description="ningún año tiene datos de población",
        )
    mejor = max(r.n for r in filas)
    flojos = {str(r.anio): r.n for r in filas if r.n < mejor * 0.5}
    return AssetCheckResult(
        passed=not flojos,
        severity=AssetCheckSeverity.WARN,
        metadata={"mejor_cobertura": mejor, "anios_a_medias": str(flojos)},
        description=(
            f"{len(filas)} años con cobertura homogénea"
            if not flojos
            else f"años cargados a medias: {flojos}"
        ),
    )


COMPROBACIONES = [
    codigos_de_municipio_bien_formados,
    el_censo_de_municipios_esta_completo,
    la_clave_de_la_matriz_es_unica,
    la_poblacion_es_plausible,
    ningun_anio_pierde_cobertura,
]
