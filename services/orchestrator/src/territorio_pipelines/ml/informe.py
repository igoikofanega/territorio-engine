"""Genera el informe de evaluación versionado en `docs/evaluacion/`.

Las cifras del README venían de MLflow copiadas a mano: si el modelo cambiaba y nadie
actualizaba el texto, no fallaba nada. Aquí se escriben a fichero, se versionan, y quien
lee el repositorio puede comprobarlas sin levantar la plataforma.

Se ejecuta con `make evaluar`.
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from sqlalchemy.engine import Engine  # noqa: E402

from .evaluacion import evaluar  # noqa: E402

DESTINO = Path("docs/evaluacion")

# Del sistema de diseño del proyecto (docs/design-system.md). Una sola tinta para los
# datos; el gris es referencia, no una serie más.
AZUL = "#0050cb"
GRIS = "#727687"
TINTA = "#191c1e"
TINTA_SUAVE = "#424656"
REJILLA = "#e0e3e5"


def _miles(n: int | float) -> str:
    """Separador de miles español: 8.131, no 8,131. El proyecto escribe en español."""
    return f"{int(n):,}".replace(",", ".")


def _dec(x: float, n: int = 2, signo: bool = False) -> str:
    """Decimal en español: 5,796 — no 5.796, que con miles a punto se lee como 5796."""
    fmt = f"{{:+.{n}f}}" if signo else f"{{:.{n}f}}"
    return fmt.format(x).replace(".", ",")


def _figura(ancho: float = 8.0, alto: float = 4.5):
    fig, ax = plt.subplots(figsize=(ancho, alto), dpi=160)
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")
    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)
    for lado in ("left", "bottom"):
        ax.spines[lado].set_color(REJILLA)
    ax.tick_params(colors=TINTA_SUAVE, labelsize=9)
    ax.grid(axis="y", color=REJILLA, linewidth=0.8)
    ax.set_axisbelow(True)
    return fig, ax


def _guardar(fig, nombre: str, destino: Path) -> str:
    ruta = destino / nombre
    fig.tight_layout()
    fig.savefig(ruta, facecolor="white")
    plt.close(fig)
    return nombre


def grafico_estratos(datos: list[dict], destino: Path) -> str:
    """Donde el proyecto se juega su tesis: el error por tamaño de municipio."""
    fig, ax = _figura()
    etiquetas = [d["estrato"] for d in datos]
    x = range(len(datos))
    ax.bar(x, [d["mae"] for d in datos], color=AZUL, width=0.55, label="modelo")
    ax.plot(
        x,
        [d["mae_persistencia"] for d in datos],
        color=GRIS,
        linestyle="--",
        marker="o",
        markersize=6,
        linewidth=2,
        label="no cambia nada (referencia)",
    )
    for i, d in enumerate(datos):
        ax.text(i, d["mae"] + 0.15, _dec(d["mae"]), ha="center", color=TINTA, fontsize=9)
    ax.set_xticks(list(x))
    ax.set_xticklabels([f"{e}\nn={_miles(d['n'])}" for e, d in zip(etiquetas, datos, strict=True)])
    ax.set_ylabel("MAE (puntos porcentuales)", color=TINTA_SUAVE, fontsize=9)
    ax.set_title(
        "El error se concentra en los pueblos pequeños, que son el objeto del proyecto",
        color=TINTA,
        fontsize=11,
        loc="left",
        pad=12,
    )
    manejadores, rotulos = ax.get_legend_handles_labels()
    orden = sorted(range(len(rotulos)), key=lambda i: rotulos[i] != "modelo")
    ax.legend(
        [manejadores[i] for i in orden],
        [rotulos[i] for i in orden],
        frameon=False,
        fontsize=9,
        labelcolor=TINTA_SUAVE,
    )
    return _guardar(fig, "error-por-estrato.png", destino)


def grafico_fiabilidad(datos: list[dict], destino: Path) -> str:
    """Lo prometido frente a lo observado. La diagonal es la calibración perfecta."""
    fig, ax = _figura(6.5, 5.0)
    prom = [d["prob_media"] for d in datos]
    obs = [d["frec_observada"] for d in datos]
    tam = [max(20.0, min(400.0, d["n"] / 15)) for d in datos]
    ax.plot([0, 1], [0, 1], color=GRIS, linestyle="--", linewidth=2, label="calibración perfecta")
    ax.plot(prom, obs, color=AZUL, linewidth=2, marker="o", markersize=0, label="observado")
    ax.scatter(prom, obs, s=tam, color=AZUL, zorder=3, edgecolor="white", linewidth=1.5)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_xlabel("probabilidad que da el modelo", color=TINTA_SUAVE, fontsize=9)
    ax.set_ylabel("frecuencia observada", color=TINTA_SUAVE, fontsize=9)
    ax.set_title(
        "Por encima del 40% el modelo promete más de lo que ocurre\n"
        "(tamaño del punto = municipios en el tramo)",
        color=TINTA,
        fontsize=11,
        loc="left",
        pad=12,
    )
    ax.grid(color=REJILLA, linewidth=0.8)
    ax.legend(frameon=False, fontsize=9, labelcolor=TINTA_SUAVE, loc="upper left")
    return _guardar(fig, "fiabilidad.png", destino)


def grafico_importancia(datos: list[dict], destino: Path, top: int = 12) -> str:
    d = datos[:top][::-1]
    fig, ax = _figura(8.0, 5.0)
    y = range(len(d))
    ax.barh(y, [r["importancia"] for r in d], color=AZUL, height=0.6)
    ax.set_yticks(list(y))
    ax.set_yticklabels([r["feature"] for r in d])
    ax.grid(axis="x", color=REJILLA, linewidth=0.8)
    ax.grid(axis="y", visible=False)
    for i, r in enumerate(d):
        ax.text(
            r["importancia"],
            i,
            f"  {_dec(r['importancia'], 3)}",
            va="center",
            color=TINTA,
            fontsize=8,
        )
    ax.set_xlim(0, max(r["importancia"] for r in d) * 1.18)
    ax.set_xlabel("caída del R² al permutar la variable", color=TINTA_SUAVE, fontsize=9)
    ax.set_title(
        "Importancia por permutación — asociación, no causa",
        color=TINTA,
        fontsize=11,
        loc="left",
        pad=12,
    )
    return _guardar(fig, "importancia.png", destino)


def _tabla(cabeceras: list[str], filas: list[list]) -> str:
    linea = lambda c: "| " + " | ".join(str(x) for x in c) + " |"  # noqa: E731
    return "\n".join(
        [
            linea(cabeceras),
            "|" + "|".join(["---"] * len(cabeceras)) + "|",
            *[linea(f) for f in filas],
        ]
    )


def _markdown(r: dict, graficos: dict[str, str]) -> str:
    bt = r["backtest_contiguo"]
    ri = r["riesgo"]
    mo = r["moran_residuos"]

    pliegues = _tabla(
        [
            "Año de validación",
            "Entrena con",
            "n val",
            "MAE",
            "R²",
            "MAE persistencia",
            "MAE tendencia",
        ],
        [
            [
                p["anio_val"],
                f"{min(p['anios_train'])}-{max(p['anios_train'])}",
                _miles(p["n_val"]),
                _dec(p["mae"], 3),
                _dec(p["r2"], 3),
                _dec(p["mae_persistencia"], 3),
                _dec(p["mae_tendencia"], 3),
            ]
            for p in bt["pliegues"]
        ],
    )
    estratos = _tabla(
        ["Tamaño", "n", "MAE", "Sesgo", "MAE si no cambia nada"],
        [
            [
                d["estrato"],
                _miles(d["n"]),
                _dec(d["mae"]),
                _dec(d["sesgo"], signo=True),
                _dec(d["mae_persistencia"]),
            ]
            for d in r["error_por_estrato"]
        ],
    )
    embargo = _tabla(
        ["Embargo (años)", "Pliegues", "MAE medio", "Nota"],
        [
            [
                e["embargo"],
                e["n_pliegues"],
                _dec(e["mae_media"], 3) if e["mae_media"] is not None else "—",
                e["motivo"] or "",
            ]
            for e in r["sensibilidad_al_embargo"]
        ],
    )
    peores = _tabla(
        ["Provincia", "n", "MAE", "Sesgo"],
        [
            [p["cod_provincia"], p["n"], _dec(p["mae"]), _dec(p["sesgo"], signo=True)]
            for p in r["error_por_provincia"]["peores"]
        ],
    )
    fiab = _tabla(
        ["Tramo", "n", "Promete", "Ocurre"],
        [
            [d["bin"], _miles(d["n"]), _dec(d["prob_media"], 3), _dec(d["frec_observada"], 3)]
            for d in ri["fiabilidad"]
        ],
    )
    descartados = "\n".join(f"- {d['anio_val']}: {d['motivo']}" for d in bt.get("descartados", []))
    maes_embargo = [
        e["mae_media"] for e in r["sensibilidad_al_embargo"] if e["mae_media"] is not None
    ]
    mae_emb2 = _dec(maes_embargo[0], 3) if maes_embargo else "no factible"

    return f"""# Informe de evaluación

> **Generado por `make evaluar`.** No editar a mano: se regenera desde la base de datos.
> Las cifras de este fichero son las que debe citar el README.

Horizonte de predicción: **{r["horizonte"]} años**. Target: variación porcentual de
población entre el año base T y T+{r["horizonte"]}.

## 1. Backtest de origen rodante

Un pliegue por año base de validación, entrenando siempre solo con años anteriores.
Un corte único da una cifra sin dispersión que parece más precisa de lo que es.

{pliegues}

**MAE = {_dec(bt["mae_media"], 3)} ± {_dec(bt["mae_desviacion"], 3)} pp** ({
        bt["n_pliegues"]
    } pliegues,
rango {_dec(bt["mae_min"], 3)}–{_dec(bt["mae_max"], 3)}).

Pliegues descartados y por qué:

{descartados or "- ninguno"}

### El coste del solape

El target mira {r["horizonte"]} años adelante, así que con pliegues contiguos las ventanas
de train y validación comparten trayectoria sobre los mismos municipios. Separarlas exige
un embargo, y la ventana de datos disponible no da para mucho:

{embargo}

Con embargo 1 el MAE es {_dec(bt["mae_media"], 3)}; con embargo 2, {mae_emb2}. La diferencia
es el precio de haber estado midiendo sobre ventanas solapadas. **Un embargo completo
(= el horizonte) no es factible hoy**: la población empieza en 2015 y no quedan años base
suficientes. Es una limitación de los datos, no una decisión de diseño, y se declara en
vez de publicar el número más favorable.

## 2. Dónde falla el modelo

![Error por estrato de población](./{graficos["estratos"]})

{estratos}

Esto es lo que un MAE agregado esconde: el error en los municipios de menos de 500
habitantes es **{
        _dec(r["error_por_estrato"][0]["mae"] / r["error_por_estrato"][-1]["mae"], 1)
    } veces**
el de los de más de 10.000. Y son justo los municipios por los que existe este proyecto.
La comparación honesta no es contra cero, sino contra "no cambia nada" en cada estrato:
ahí el modelo sigue ganando, pero por menos de lo que sugiere la cifra global.

### Las cinco provincias donde peor va

{peores}

## 3. ¿Le sobra estructura espacial al residuo?

Moran's I sobre el error del pliegue más reciente, con {mo["k_vecinos"]} vecinos más
próximos por centroide:

- **I = {_dec(mo["moran_i"], 4)}** (esperado bajo azar: {_dec(mo["esperado_bajo_azar"], 4)}), p = {
        _dec(mo["p"], 3)
    }, n = {_miles(mo["n"])}

El error **no** está repartido al azar en el mapa: municipios vecinos fallan en el mismo
sentido. Queda geografía que las {len(r["importancia"])} features no capturan. Es un
resultado esperable —la despoblación es un fenómeno regional, no municipal— y marca la
dirección de mejora más clara: una feature de contexto comarcal, o un término espacial
explícito.

## 4. Qué mueve la predicción

![Importancia por permutación](./{graficos["importancia"]})

Importancia por permutación sobre el pliegue más reciente. Mide **asociación, no causa**:
que `crec_prev3` pese mucho no significa que la tendencia cause el futuro, sino que
resume información que las demás variables no traen.

## 5. Calibración del semáforo de despoblación

Evento: perder más del 10 % de la población en {r["horizonte"]} años.
Partición de tres tramos, todos temporales: se entrena con {ri["anios_train"][0]}-{
        ri["anios_train"][-1]
    },
se calibra con {ri["anio_calibracion"]} y se mide con **{ri["anio_test"]}**, que el calibrador
no ha visto.

| | |
|---|---|
| AUC | {_dec(ri["auc"], 4)} |
| Brier sin calibrar | {_dec(ri["brier_sin_calibrar"], 5)} |
| Brier calibrado (isotónica) | {_dec(ri["brier_calibrado"], 5)} |
| Tasa base del evento | {_dec(ri["tasa_evento_test"], 4)} |
| n | {_miles(ri["n_test"])} |

![Diagrama de fiabilidad](./{graficos["fiabilidad"]})

{fiab}

**Resultado negativo, y se publica igual.** Medida fuera de la muestra en que se ajusta,
la calibración isotónica **no mejora** el Brier ({_dec(ri["brier_calibrado"], 5)} frente a
{_dec(ri["brier_sin_calibrar"], 5)} sin calibrar). El diagrama enseña por qué: por encima del
40 % el modelo promete más de lo que ocurre, y los tramos altos tienen tan pocos
municipios que la isotónica no tiene con qué corregirlos.

La consecuencia práctica es que **el semáforo ordena bien pero no cuantifica bien**: el
AUC de {_dec(ri["auc"])} dice que separa los municipios en riesgo de los que no, y eso es lo
que usa la interfaz (verde / ámbar / rojo). Lo que no se sostiene es leer la probabilidad
como una frecuencia literal.
"""


def escribir(engine: Engine, destino: Path = DESTINO) -> dict:
    """Calcula el informe y lo deja en disco. Devuelve un resumen de lo escrito."""
    destino.mkdir(parents=True, exist_ok=True)
    r = evaluar(engine)

    graficos = {
        "estratos": grafico_estratos(r["error_por_estrato"], destino),
        "fiabilidad": grafico_fiabilidad(r["riesgo"]["fiabilidad"], destino),
        "importancia": grafico_importancia(r["importancia"], destino),
    }
    (destino / "metricas.json").write_text(
        json.dumps(r, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8"
    )
    (destino / "informe.md").write_text(_markdown(r, graficos), encoding="utf-8")
    return {
        "destino": str(destino),
        "mae_media": r["backtest_contiguo"]["mae_media"],
        "mae_desviacion": r["backtest_contiguo"]["mae_desviacion"],
        "ficheros": ["metricas.json", "informe.md", *graficos.values()],
    }


if __name__ == "__main__":
    from ..db import engine

    print(json.dumps(escribir(engine), indent=2, ensure_ascii=False))
