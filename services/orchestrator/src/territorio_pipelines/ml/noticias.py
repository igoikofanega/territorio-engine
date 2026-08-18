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
2. **Cero y hueco no son lo mismo, y aquí conviven tres estados.** Un municipio del
   ámbito con los titulares clasificados y ninguna noticia en la ventana vale `0`: se
   miró y no había. Uno que no llegó al umbral de etiquetado vale `NaN`: no se miró.
   Y fuera del ámbito no hay fila. Fundir los dos primeros en un cero le enseñaría al
   modelo que los pueblos pequeños no salen en prensa, que es justo lo que no sabemos.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sqlalchemy.engine import Engine

#: Años hacia atrás que entran en la ventana, además del propio año base.
VENTANA = 2

#: Temas con contenido económico. El resto de la prensa local —deporte, cultura,
#: sucesos— domina en volumen, y separarla es justamente lo que permite que la feature
#: mida algo distinto del ruido.
TEMAS_ECONOMICOS = ("empleo", "empresa", "vivienda", "infraestructura", "servicios")

#: Las tres que se derivan del recuento. `noticias_1000hab` se calcula al final,
#: cuando ya se ha cruzado con la poblacion.
_COLS_DERIVADAS = ["noticias_signo", "noticias_pct_negativas", "noticias_pct_economicas"]

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


def _etiquetados(engine: Engine, cod_provincia: str) -> set[str]:
    """Municipios cuyos titulares llegaron a clasificarse.

    El etiquetado descarta los municipios que no alcanzan un mínimo de titulares (ver
    `loaders.MIN_TITULARES`), así que los suyos siguen con `pertenece` a nulo. Sin este
    conjunto, esos municipios entrarían en las features como **cero noticias**, que es
    una afirmación falsa: no es que no se hablara de ellos, es que no se miró.
    """
    df = pd.read_sql(
        "SELECT DISTINCT n.cod_municipio AS cod "
        "FROM noticia_municipio n JOIN dim_municipio d USING (cod_municipio) "
        "WHERE n.modelo IS NOT NULL AND d.cod_provincia = %(prov)s",
        engine,
        params={"prov": cod_provincia},
    )
    return set(df["cod"])


def construir(
    engine: Engine,
    anios_base: list[int],
    cod_provincia: str,
    poblacion: pd.DataFrame,
    ventana: int = VENTANA,
) -> pd.DataFrame:
    """Features de prensa por `(cod, anio_base)` para los municipios del ámbito.

    `poblacion` son las columnas `cod, anio, pob` con las que se normaliza el recuento.
    Devuelve **una fila por municipio del ámbito y año base**.

    Tres estados distintos, y confundirlos arruinaría la ablación:

    - Municipio **medido con noticias** → los valores que salgan.
    - Municipio **medido sin noticias en la ventana** → `0` noticias. En un ámbito
      consultado por completo, la ausencia es un dato.
    - Municipio **no etiquetado** (por debajo del umbral) → `NaN` en todo. No se miró.
    """
    arts = _leer(engine, cod_provincia)
    medidos = _etiquetados(engine, cod_provincia)
    municipios = sorted(poblacion.loc[poblacion["cod"].str[:2] == cod_provincia, "cod"].unique())
    sin_medir = [m for m in municipios if m not in medidos]

    filas = []
    for t in anios_base:
        del_periodo = arts[arts["anio"].between(t - ventana, t)]
        agg = (
            del_periodo.groupby("cod")
            .agg(
                n=("signo", "size"),
                n_signo=("signo", "count"),
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
        #
        # Dos denominadores distintos, y no es un descuido: `signo` puede venir nulo —el
        # modelo no siempre lo devuelve y el parser prefiere dejarlo vacío a inventarlo—,
        # así que el porcentaje de negativas se calcula sobre los titulares que SÍ tienen
        # signo. Con el recuento total saldría sistemáticamente infravalorado. `tema`, en
        # cambio, cae en "otros" cuando el modelo no acierta con la lista, así que ahí el
        # denominador correcto es el total.
        den_noticias = agg["n"].replace(0, pd.NA)
        den_signo = agg["n_signo"].replace(0, pd.NA)
        base["noticias_pct_negativas"] = (agg["negativas"] / den_signo).to_numpy(float) * 100
        base["noticias_pct_economicas"] = (agg["economicas"] / den_noticias).to_numpy(float) * 100
        # Los no etiquetados quedan en NaN, incluido el recuento: ahí ni siquiera el cero
        # es cierto. HistGradientBoosting trata los NaN de forma nativa.
        base.loc[base["cod"].isin(sin_medir), ["n_noticias", *_COLS_DERIVADAS]] = np.nan
        filas.append(base)

    df = pd.concat(filas, ignore_index=True)
    pob = poblacion.rename(columns={"anio": "anio_base"})
    df = df.merge(pob, on=["cod", "anio_base"], how="left")
    df["noticias_1000hab"] = df["n_noticias"] / df["pob"] * 1000
    return df[["cod", "anio_base", *FEATURES_NOTICIAS]]
