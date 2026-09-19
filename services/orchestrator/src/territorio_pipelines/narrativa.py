"""Informe narrativo municipal con grounding determinista.

Genera 120-180 palabras desde los datos ya calculados de la ficha del municipio. Se
precalcula offline en un asset de Dagster y se persiste, de modo que la API sigue siendo
estrictamente de lectura.

**Grounding con tres candados deterministas, cero LLM-judge:**
1. Cifras: se extraen los números del texto y cada uno debe existir en el JSON de entrada.
2. Nombres: cualquier nombre de `dim_municipio` que aparezca en el texto y no sea del
   contexto dado (el municipio, sus similares, su gemelo) es violación.
3. Prompt: prohibición explícita de inventar cifras o citar municipios no dados.

Si hay violaciones se reintenta una vez. Si persisten, no se publica: la ficha cae a la
plantilla determinista del frontend.
"""

from __future__ import annotations

import functools
import hashlib
import json
import re
from collections.abc import Callable, Iterable, Mapping
from typing import Any

from . import llm

SISTEMA = """Eres un analista territorial español. Generas un informe breve (120-180 palabras)
sobre un municipio a partir de datos estructurados que te proporciono.

Reglas estrictas:
- Solo puedes usar las cifras que aparecen en los datos. NO inventes, estimes ni redondees
  cifras que no estén en la entrada. Si un dato no está, no lo menciones.
- Solo puedes nombrar los municipios que aparecen en los datos (el propio, sus similares y
  su gemelo). NO cites ningún otro municipio.
- Los campos con "previsto" o "proyeccion" son lo que el modelo espera que ocurra,
  no un hecho: redáctalos en futuro o condicional y di entre qué años (proyeccion_desde
  y proyeccion_hasta). El mínimo y el máximo previstos son la banda de esa proyección.
- parados_media_anual es un número de personas, no una tasa: escribe "N personas en
  paro", nunca "una tasa del N por ciento".
- Cada cifra de la situación actual lleva su propio año (anio_poblacion, anio_paro,
  anio_renta): cítala con ese año, no con otro.
- Escribe en español, en tercera persona, tono informativo y conciso.
- Estructura: situación actual → proyección → factores clave.
- NO uses comillas, ni listas con viñetas, ni cabeceras. Es un párrafo continuo.
- Si la proyección es negativa, no la suavices. Si es positiva, no la exageres."""


def _prompt_datos(datos: dict) -> str:
    """Serializa los datos de la ficha como contexto para el LLM."""
    return f"Datos del municipio:\n```json\n{json.dumps(datos, ensure_ascii=False, indent=2)}\n```"


def _numeros_del_contexto(datos: dict) -> set[float]:
    """Todos los valores numéricos del contexto, incluidos redondeos razonables."""
    nums: set[float] = set()

    def _extraer(obj: Any) -> None:
        if isinstance(obj, (int, float)) and not isinstance(obj, bool):
            v = float(obj)
            nums.add(v)
            nums.add(abs(v))
            nums.add(round(v))
            nums.add(round(v, 1))
            nums.add(round(v, 2))
            nums.add(round(abs(v)))
            nums.add(round(abs(v), 1))
            nums.add(round(abs(v), 2))
        elif isinstance(obj, dict):
            for val in obj.values():
                _extraer(val)
        elif isinstance(obj, (list, tuple)):
            for item in obj:
                _extraer(item)

    _extraer(datos)
    for anio in range(2000, 2041):
        nums.add(float(anio))
    return nums


def _lecturas(token: str) -> set[float]:
    """Todas las lecturas razonables de una cifra tal como aparece en el texto.

    Con coma solo cabe la española (1.234,5 → 1234.5). Con punto y sin coma hay dos: la
    española, donde el punto separa miles (18.318 → 18318), y la del propio JSON, donde es
    el decimal (8.7 → 8.7). El modelo copia los números de los datos tal cual, así que la
    segunda es la habitual. Solo con la primera, el candado rechazaba las cifras exactas.
    """
    s = token.rstrip("%")
    lecturas = set()
    for candidato in (s.replace(".", "").replace(",", "."), s if "," not in s else None):
        if candidato is None:
            continue
        try:
            lecturas.add(float(candidato))
        except ValueError:
            continue
    return lecturas


def verificar_cifras(texto: str, datos: dict) -> list[str]:
    """Devuelve las cifras del texto que no aparecen en los datos.

    Una cifra vale si **alguna** de sus lecturas (ver `_lecturas`) está en los datos. Una
    inventada no está en ninguna: 9.3 no es ni 93 ni 9,3 si el dato es 8,7.
    """
    permitidos = _numeros_del_contexto(datos)
    violaciones = []
    for m in re.finditer(r"-?\d[\d.]*,?\d*%?", texto):
        lecturas = _lecturas(m.group())
        if lecturas and not lecturas & permitidos:
            violaciones.append(m.group())
    return violaciones


@functools.cache
def _como_palabra(nombre: str) -> re.Pattern[str]:
    """El nombre como palabra completa: "Ares" no está dentro de "Areso"."""
    return re.compile(rf"(?<!\w){re.escape(nombre)}(?!\w)")


def verificar_nombres(
    texto: str,
    nombres_permitidos: set[str],
    todos_los_municipios: set[str],
) -> list[str]:
    """Nombres de municipios que aparecen en el texto sin estar en el contexto.

    Antes se buscaba cada municipio como subcadena, y el nombre propio aparece siempre en
    el texto: "Areso" contiene "Ares", "Los Arcos" contiene "Arcos", "Oroz-Betelu"
    contiene "Betelu". Los 24 rechazados de la primera tanda completa lo eran por esto, y
    por nada más: el candado bloqueaba textos correctos.

    Dos pasos. Se tapan primero los nombres permitidos, de más largo a más corto, para
    que "Arcos" no se vea dentro de "Los Arcos". Después se buscan los demás como palabra
    completa. Una mención real a otro municipio sigue saltando: "Arcos" suelto no lo
    tapa nada.
    """
    tapado = texto
    for nombre in sorted(nombres_permitidos, key=len, reverse=True):
        tapado = _como_palabra(nombre).sub(" ", tapado)
    return [
        nombre
        for nombre in todos_los_municipios
        if nombre not in nombres_permitidos and _como_palabra(nombre).search(tapado)
    ]


def normalizar(datos: dict) -> dict:
    """Los valores tal como los diría una persona: 18949, no `np.float64(18949.0)`.

    Una columna de enteros con un solo hueco pasa a float en pandas, así que la renta de
    todos los municipios llegaba como 18949.0 en cuanto a uno le faltaba. Eso cambiaba el
    hash de los 272 —y se regeneraban todos los informes aunque nada hubiese cambiado— y
    el modelo escribía "18949.0 euros". Se normaliza antes del hash y antes del prompt.
    """
    salida = {}
    for clave, valor in datos.items():
        if hasattr(valor, "item"):  # escalar de numpy
            valor = valor.item()
        if isinstance(valor, float) and valor.is_integer():
            valor = int(valor)
        salida[clave] = valor
    return salida


def hash_datos(datos: dict) -> str:
    """SHA1 del JSON de entrada, para saber si hay que regenerar."""
    return hashlib.sha1(json.dumps(datos, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def generar(
    client,
    modelo: str,
    datos: dict,
    nombres_permitidos: set[str] | None = None,
    todos_los_municipios: set[str] | None = None,
) -> dict:
    """Genera el informe y lo valida. Devuelve {texto, hash, violaciones, aceptado}."""
    h = hash_datos(datos)
    texto = llm.completar(client, modelo, SISTEMA, _prompt_datos(datos), max_tokens=600)

    cifras_malas = verificar_cifras(texto, datos)
    nombres_malos = (
        verificar_nombres(texto, nombres_permitidos, todos_los_municipios)
        if nombres_permitidos and todos_los_municipios
        else []
    )

    if cifras_malas or nombres_malos:
        correccion = "El texto contiene errores que hay que corregir:\n"
        if cifras_malas:
            correccion += f"- Cifras no presentes en los datos: {cifras_malas}\n"
        if nombres_malos:
            correccion += f"- Municipios no autorizados: {nombres_malos}\n"
        correccion += "\nReescribe el informe corrigiendo estos errores. " + _prompt_datos(datos)

        texto = llm.completar(client, modelo, SISTEMA, correccion, max_tokens=600)
        cifras_malas = verificar_cifras(texto, datos)
        nombres_malos = (
            verificar_nombres(texto, nombres_permitidos, todos_los_municipios)
            if nombres_permitidos and todos_los_municipios
            else []
        )

    aceptado = not cifras_malas and not nombres_malos
    return {
        "texto": texto if aceptado else None,
        "hash": h,
        "aceptado": aceptado,
        "violaciones_cifras": cifras_malas,
        "violaciones_nombres": nombres_malos,
    }


def recorrer(
    candidatos: Iterable[tuple[str, dict]],
    hashes_previos: Mapping[str, str],
    generar: Callable[[dict], dict],
    guardar: Callable[[str, str, dict], None],
    limite: int | None = None,
) -> dict:
    """Recorre los municipios y genera el informe de los que lo necesitan.

    Separado de la base de datos y del LLM (`generar` y `guardar` los pone quien llama)
    para poder probar las decisiones, que es donde estaban los fallos:

    - **Incremental.** Un municipio cuyos datos no han cambiado (mismo `hash_datos`) no
      se vuelve a pedir. Eso vale también para los rechazados: se guardan, y no se paga
      otra vez por ellos hasta que cambien sus datos.
    - **`limite` cuenta informes nuevos, no candidatos.** Aplicado a la lista, cada tanda
      miraba siempre los mismos primeros municipios —ya hechos— y no avanzaba nunca.
    - **Cuota agotada → para limpio.** Solo `llm.CuotaAgotada`, no cualquier error cuyo
      mensaje contenga "rate": eso también está en "generate". Lo generado hasta ahí ya
      está guardado, y la siguiente tanda continúa donde quedó esta.

    Los municipios que quedan sin hacer se siguen recorriendo, sin llamar al modelo,
    para que `pendientes` sea la cuenta exacta y no una estimación.
    """
    generados = rechazados = sin_cambio = pendientes = 0
    parado = False
    for cod, datos in candidatos:
        h = hash_datos(datos)
        if hashes_previos.get(cod) == h:
            sin_cambio += 1
            continue
        if parado or (limite and generados + rechazados >= limite):
            pendientes += 1
            continue
        try:
            resultado = generar(datos)
        except llm.CuotaAgotada:
            parado = True
            pendientes += 1
            continue
        guardar(cod, h, resultado)
        if resultado["aceptado"]:
            generados += 1
        else:
            rechazados += 1
    return {
        "generados": generados,
        "rechazados": rechazados,
        "sin_cambio": sin_cambio,
        "pendientes": pendientes,
        "parado_por_cuota": parado,
    }
