"""Tests del registro de capas.

No tocan la base de datos: comprueban el registro y el SQL que genera, que es donde
puede colarse un error silencioso (una capa que apunta a la tabla equivocada, un alias
que no casa, un campo duplicado). El contrato de datos se verificó comparando las
respuestas reales antes y después del refactor; esto es la red que evita reintroducirlo.
"""

from __future__ import annotations

import pytest

from territorio_api.capas import CAPAS, Anio, Capa
from territorio_api.main import app


def test_rutas_unicas():
    rutas = [c.ruta for c in CAPAS]
    assert len(rutas) == len(set(rutas))


@pytest.mark.parametrize("capa", CAPAS, ids=lambda c: c.ruta)
def test_capa_bien_formada(capa: Capa):
    assert capa.ruta.startswith("/") and capa.ruta.endswith(".geojson")
    assert capa.campos, "una capa sin campos no aporta nada"
    assert capa.resumen, "el resumen alimenta la documentación OpenAPI"
    props = [prop for _, prop in capa.campos]
    assert len(props) == len(set(props)), f"propiedades duplicadas en {capa.ruta}"
    # `cod_municipio` y `nombre` los añade la factoría; declararlos otra vez los pisaría.
    assert not {"cod_municipio", "nombre"} & set(props)


@pytest.mark.parametrize("capa", CAPAS, ids=lambda c: c.ruta)
def test_join_por_anio_requiere_anio(capa: Capa):
    # Sin `anio` no hay parámetro :anio que ligar, así que el JOIN reventaría.
    if capa.join_por_anio:
        assert capa.anio is not None, f"{capa.ruta} filtra el JOIN por año pero no declara Anio"


@pytest.mark.parametrize("capa", CAPAS, ids=lambda c: c.ruta)
def test_sql_coherente(capa: Capa):
    sql = capa.sql(con_prov=True)
    assert "FROM dim_municipio d" in sql
    assert "ST_AsGeoJSON" in sql
    assert ":prov" in sql
    if capa.tabla:
        assert f"LEFT JOIN {capa.tabla} {capa.alias}" in sql
    # Cada parámetro que aparece en el SQL debe poder ligarse.
    if ":anio" in sql:
        assert capa.anio is not None, f"{capa.ruta} usa :anio sin declararlo"


@pytest.mark.parametrize("capa", CAPAS, ids=lambda c: c.ruta)
def test_sql_sin_prov_no_filtra(capa: Capa):
    sql = capa.sql(con_prov=False)
    assert ":prov" not in sql, "sin provincia no debe quedar un parámetro sin ligar"


@pytest.mark.parametrize("capa", CAPAS, ids=lambda c: c.ruta)
def test_alias_usados_estan_declarados(capa: Capa):
    """Un campo `x.foo` cuyo alias no existe en ningún JOIN es un 500 en producción."""
    declarados = {"d"} | ({capa.alias} if capa.tabla else set())
    for extra in capa.joins_extra:
        partes = extra.split()
        declarados.add(partes[partes.index("JOIN") + 2])
    for expr, prop in capa.campos:
        for token in expr.replace("(", " ").replace(")", " ").replace(",", " ").split():
            if "." in token and not token[0].isdigit():
                alias = token.split(".")[0].lstrip("'\"")
                if alias.isidentifier():
                    assert alias in declarados, (
                        f"{capa.ruta}: el campo {prop} usa el alias '{alias}', "
                        f"que no está en ningún JOIN ({sorted(declarados)})"
                    )


def test_anio_sql():
    assert Anio("t").sql() == "SELECT max(anio) FROM t"
    assert Anio("t", "c").sql() == "SELECT max(anio) FROM t WHERE c IS NOT NULL"


def test_todas_las_capas_registradas_en_la_app():
    rutas = set(app.openapi()["paths"])
    for capa in CAPAS:
        assert capa.ruta in rutas, f"{capa.ruta} no llegó a la aplicación"
    # Las tres que quedan fuera del registro a propósito.
    for ruta in ("/municipios.geojson", "/envejecimiento.geojson", "/lisa.geojson"):
        assert ruta in rutas


def test_capas_con_anio_parametro_exponen_el_parametro():
    paths = app.openapi()["paths"]
    for capa in CAPAS:
        params = {p["name"] for p in paths[capa.ruta]["get"].get("parameters", [])}
        assert "prov" in params, f"{capa.ruta} debe permitir filtrar por provincia"
        espera_anio = capa.anio is not None and capa.anio.parametro
        assert ("anio" in params) is espera_anio, (
            f"{capa.ruta}: parámetro anio={'esperado' if espera_anio else 'no esperado'}"
        )


def test_la_factoria_no_filtra_estado_entre_capas():
    """Cada endpoint debe servir su capa, no la última del bucle (bug clásico de closures)."""
    paths = app.openapi()["paths"]
    resumenes = {capa.ruta: paths[capa.ruta]["get"]["summary"] for capa in CAPAS}
    assert len(set(resumenes.values())) == len(CAPAS)
    for capa in CAPAS:
        assert resumenes[capa.ruta] == capa.resumen
