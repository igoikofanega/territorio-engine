"""Features de prensa agregadas a `municipio × año`.

La tabla `noticia_municipio` tiene grano `(municipio, artículo)`. Aquí se agrega a la
ventana `[T-2, T]` que fija el ADR 0005: lo que se ha dicho de un municipio en los tres
años hasta el año base, que es lo que podría anticipar su trayectoria.

**Solo entran los titulares con `pertenece = true`.** Sin ese filtro, la ficha de Tudela
mezclaría noticias de Tudela de Duero y la feature mediría homonimia, no territorio.

Dos decisiones que condicionan lo que estas features pueden llegar a medir:

1. **El recuento se normaliza por población.** El bruto mide tamaño, no dinamismo:
   Pamplona satura el tope de 250 artículos de la API y Abáigar devuelve cero, y el
   modelo ya tiene `log_pob` para saber cuál es grande. Una feature que solo replique el
   tamaño no aporta nada y además ensucia la interpretación de la ablación.
2. **Cero es un valor medido, no un hueco.** En el ámbito consultado (Navarra) sabemos
   que se preguntó por todos los municipios, así que "ninguna noticia" es información. En
   un municipio no consultado sería un `NaN`, y por eso la ablación se restringe al
   ámbito: mezclar ambos casos le enseñaría al modelo a distinguir navarros del resto.
"""

from __future__ import annotations

import pandas as pd
from sqlalchemy.engine import Engine

#: Años hacia atrás que entran en la ventana, además del propio año base.
VENTANA = 2

#: Temas con contenido económico. El resto de la prensa local —deporte, cultura,
#: sucesos— domina en volumen, y separarla es justamente lo que permite que la feature
#: mida algo distinto del ruido.
TEMAS_ECONOMICOS = ("empleo", "empresa", "vivienda", "infraestructura", "servicios")

FEATURES_NOTICIAS = [
    "noticias_1000hab",
    "noticias_signo",
    "noticias_pct_negativas",
    "noticias_pct_economicas",
]


def _leer(engine: Engine, cod_provincia: str) -> pd.DataFrame:
    """Titulares pertenecientes al municipio, con su año. Uno por fila."""
    return pd.read_sql(
        "SELECT n.cod_municipio AS cod, extract(year FROM n.fecha)::int AS anio, "
        "n.tema, n.signo "
        "FROM noticia_municipio n JOIN dim_municipio d USING (cod_municipio) "
        "WHERE n.pertenece AND n.fecha IS NOT NULL AND d.cod_provincia = %(prov)s",
        engine,
        params={"prov": cod_provincia},
    )


def construir(
    engine: Engine,
    anios_base: list[int],
    cod_provincia: str,
    poblacion: pd.DataFrame,
    ventana: int = VENTANA,
) -> pd.DataFrame:
    """Features de prensa por `(cod, anio_base)` para los municipios del ámbito.

    `poblacion` son las columnas `cod, anio, pob` con las que se normaliza el recuento.
    Devuelve **una fila por municipio del ámbito y año base**, con ceros donde no hubo
    noticias: en un ámbito consultado por completo, la ausencia es un dato.
    """
    arts = _leer(engine, cod_provincia)
    municipios = sorted(poblacion.loc[poblacion["cod"].str[:2] == cod_provincia, "cod"].unique())

    filas = []
    for t in anios_base:
        del_periodo = arts[arts["anio"].between(t - ventana, t)]
        agg = (
            del_periodo.groupby("cod")
            .agg(
                n=("signo", "size"),
                noticias_signo=("signo", "mean"),
                negativas=("signo", lambda s: (s < 0).sum()),
                economicas=("tema", lambda s: s.isin(TEMAS_ECONOMICOS).sum()),
            )
            .reindex(municipios)
        )
        agg["n"] = agg["n"].fillna(0)
        base = pd.DataFrame({"cod": municipios, "anio_base": t})
        base["n_noticias"] = agg["n"].to_numpy()
        # El signo medio no existe si no hubo noticias: es NaN, no cero. Cero significaría
        # "se habló de él en tono neutro", que es una afirmación distinta de "no se habló".
        base["noticias_signo"] = agg["noticias_signo"].to_numpy()
        # Sin noticias el denominador es 0 y los porcentajes salen NaN, que es lo
        # correcto: un porcentaje sobre cero titulares no existe.
        den = agg["n"].replace(0, pd.NA)
        base["noticias_pct_negativas"] = (agg["negativas"] / den).to_numpy(float) * 100
        base["noticias_pct_economicas"] = (agg["economicas"] / den).to_numpy(float) * 100
        filas.append(base)

    df = pd.concat(filas, ignore_index=True)
    pob = poblacion.rename(columns={"anio": "anio_base"})
    df = df.merge(pob, on=["cod", "anio_base"], how="left")
    df["noticias_1000hab"] = df["n_noticias"] / df["pob"] * 1000
    return df[["cod", "anio_base", *FEATURES_NOTICIAS]]
