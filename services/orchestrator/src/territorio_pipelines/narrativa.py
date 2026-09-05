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

import hashlib
import json
import re
from typing import Any

from . import llm

SISTEMA = """Eres un analista territorial español. Generas un informe breve (120-180 palabras)
sobre un municipio a partir de datos estructurados que te proporciono.

Reglas estrictas:
- Solo puedes usar las cifras que aparecen en los datos. NO inventes, estimes ni redondees
  cifras que no estén en la entrada. Si un dato no está, no lo menciones.
- Solo puedes nombrar los municipios que aparecen en los datos (el propio, sus similares y
  su gemelo). NO cites ningún otro municipio.
- Escribe en español, en tercera persona, tono informativo y conciso.
- Estructura: situación actual → tendencia reciente → proyección → factores clave.
- NO uses comillas, ni listas con viñetas, ni cabeceras. Es un párrafo continuo.
- Si la proyección es negativa, no la suavices. Si es positiva, no la exageres."""


def _prompt_datos(datos: dict) -> str:
    """Serializa los datos de la ficha como contexto para el LLM."""
    return f"Datos del municipio:\n```json\n{json.dumps(datos, ensure_ascii=False, indent=2)}\n```"


def _extraer_numeros(texto: str) -> list[float]:
    """Extrae números del texto en formato español (1.234,5 → 1234.5)."""
    patron = re.compile(r"-?\d[\d.]*,?\d*%?")
    nums = []
    for m in patron.finditer(texto):
        s = m.group().rstrip("%")
        s = s.replace(".", "").replace(",", ".")
        try:
            nums.append(float(s))
        except ValueError:
            continue
    return nums


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


def verificar_cifras(texto: str, datos: dict) -> list[str]:
    """Devuelve las cifras del texto que no aparecen en los datos."""
    permitidos = _numeros_del_contexto(datos)
    violaciones = []
    for n in _extraer_numeros(texto):
        if n not in permitidos:
            violaciones.append(str(n))
    return violaciones


def verificar_nombres(
    texto: str,
    nombres_permitidos: set[str],
    todos_los_municipios: set[str],
) -> list[str]:
    """Nombres de municipios que aparecen en el texto sin estar en el contexto."""
    violaciones = []
    for nombre in todos_los_municipios:
        if nombre in texto and nombre not in nombres_permitidos:
            violaciones.append(nombre)
    return violaciones


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
