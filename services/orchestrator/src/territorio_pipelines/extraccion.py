"""Etiquetado de titulares con LLM: pertenencia, tema y signo.

La tarea principal **no** es el análisis de sentimiento: es decidir si un titular habla
del municipio por el que se preguntó. La consulta a GDELT es por nombre, y España está
llena de homónimos —"Tudela" trae noticias de Tudela de Duero (Valladolid)—, así que sin
este filtro la mitad del material sería de otra provincia. Ver ADR 0005.

El dominio del medio entra en el prompt a propósito: `diariodenavarra.es` es una pista
mucho más fuerte sobre de qué Tudela se habla que cualquier cosa que diga el titular.

Nada de esto se cree sin medirlo: `docs/` recoge el golden set y las métricas de acierto.
"""

from __future__ import annotations

from . import llm

#: Temas cerrados. `deporte`, `cultura` y `sucesos` están porque **dominan** la prensa
#: local: sin poder identificarlos no se puede separar el ruido de la señal económica.
TEMAS = (
    "empleo",
    "empresa",
    "vivienda",
    "poblacion",
    "servicios",
    "infraestructura",
    "agro",
    "turismo",
    "cultura",
    "deporte",
    "sucesos",
    "politica",
    "otros",
)

#: Titulares por petición. Suficiente para que salga barato, corto para que el modelo no
#: pierda la correspondencia entre índice y titular.
LOTE = 25

SISTEMA = f"""Eres un analista de prensa local española. Clasificas titulares de noticias.

Para cada titular decides tres cosas:

1. `pertenece`: si el titular se refiere al municipio concreto que se te indica, con su
   provincia. España tiene muchos municipios homónimos: "Tudela" existe en Navarra y
   "Tudela de Duero" en Valladolid; "Sada" existe en Navarra y en A Coruña. Si el titular
   habla de otro lugar con el mismo nombre o parecido, `pertenece` es false. El dominio
   del medio es una pista importante: un medio de otra comunidad autónoma hablando de un
   pueblo pequeño suele indicar que es un homónimo. Si el nombre aparece como apellido de
   persona, nombre de empresa o de equipo deportivo y no como lugar, también es false.
2. `confianza`: entre 0 y 1, tu seguridad sobre `pertenece`.
3. `tema` y `signo`: el tema, de esta lista cerrada: {", ".join(TEMAS)}. Y el signo del
   efecto sobre el municipio: -1 si es malo (cierres, despidos, despoblación, sucesos),
   0 si es neutro o meramente informativo, 1 si es bueno (inversión, empleo, servicios
   nuevos). El signo se refiere al municipio, no a las personas de la noticia.

Responde SOLO con un array JSON, un objeto por titular, en el mismo orden, con la forma:
{{"i": <índice>, "pertenece": <bool>, "confianza": <0-1>, "tema": "<tema>", "signo": <-1|0|1>}}

Sin explicaciones, sin texto antes ni después."""


def prompt(municipio: str, provincia: str, titulares: list[dict]) -> str:
    """Mensaje de usuario con el municipio y el lote de titulares numerados."""
    lineas = [
        f"Municipio: {municipio} (provincia de {provincia}, España)",
        "",
        "Titulares:",
    ]
    for i, t in enumerate(titulares):
        medio = t.get("medio") or "medio desconocido"
        lineas.append(f"{i}. [{medio}] {t['titular']}")
    return "\n".join(lineas)


def _signo(v: object) -> float | None:
    try:
        n = float(v)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return max(-1.0, min(1.0, n))


def _confianza(v: object) -> float | None:
    try:
        n = float(v)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return max(0.0, min(1.0, n))


def parsear(respuesta: str, n: int) -> dict[int, dict]:
    """Etiquetas por índice de titular. Descarta lo que no se entienda, no lo inventa.

    Un modelo puede devolver menos objetos de los pedidos, repetir índices o salirse de
    la lista de temas. Todo eso se tolera dejando fuera la fila afectada: una etiqueta
    inventada por el parser sería peor que una fila sin etiquetar, porque entraría en las
    métricas como si fuese una decisión del modelo.
    """
    datos = llm.json_de(respuesta)
    if isinstance(datos, dict):  # algunos modelos envuelven el array en una clave
        datos = next((v for v in datos.values() if isinstance(v, list)), None)
    if not isinstance(datos, list):
        return {}
    out: dict[int, dict] = {}
    for item in datos:
        if not isinstance(item, dict):
            continue
        try:
            i = int(item["i"])
        except (KeyError, TypeError, ValueError):
            continue
        if not 0 <= i < n or i in out:
            continue
        pertenece = item.get("pertenece")
        if not isinstance(pertenece, bool):
            continue
        tema = str(item.get("tema", "")).strip().lower()
        out[i] = {
            "pertenece": pertenece,
            "confianza": _confianza(item.get("confianza")),
            "tema": tema if tema in TEMAS else "otros",
            "signo": _signo(item.get("signo")),
        }
    return out


def etiquetar(
    client, modelo: str, municipio: str, provincia: str, titulares: list[dict]
) -> dict[int, dict]:
    """Etiqueta un lote de titulares del mismo municipio. Devuelve {índice: etiquetas}."""
    if not titulares:
        return {}
    respuesta = llm.completar(client, modelo, SISTEMA, prompt(municipio, provincia, titulares))
    return parsear(respuesta, len(titulares))
