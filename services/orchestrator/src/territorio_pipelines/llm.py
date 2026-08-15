"""Cliente de LLM: SDK `openai` contra un `base_url` configurable.

No es una decisión sobre qué modelo es mejor, sino sobre el protocolo: el de OpenAI se ha
convertido en el denominador común, así que el mismo código sirve para OpenAI, Groq,
DeepSeek, OpenRouter, vLLM o un Ollama local. Ver ADR 0005.

Tres variables de entorno, sin valores por defecto que gasten dinero:
`LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODELO`.

**Los tests no necesitan ninguna de las tres.** Todo lo que se prueba aquí —el parseo de
la respuesta, que es donde de verdad falla esto— es función pura.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

# El SDK se importa dentro de `cliente()` a propósito: así el módulo se puede importar
# (y testear el parseo) sin tener el paquete instalado ni una clave configurada.

#: Respuesta envuelta en un bloque de código markdown. Ocurre con casi todos los
#: proveedores por mucho que el prompt pida JSON pelado.
_VALLA = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


def config() -> dict[str, str]:
    """Configuración del proveedor. Falla si falta algo, en vez de asumir OpenAI."""
    cfg = {
        "base_url": os.environ.get("LLM_BASE_URL", "").strip(),
        "api_key": os.environ.get("LLM_API_KEY", "").strip(),
        "modelo": os.environ.get("LLM_MODELO", "").strip(),
    }
    faltan = [k for k, v in cfg.items() if not v]
    if faltan:
        raise RuntimeError(
            f"Falta configuración del LLM en el entorno: {faltan}. "
            "Se necesitan LLM_BASE_URL, LLM_API_KEY y LLM_MODELO (ver .env.example)."
        )
    return cfg


def cliente(cfg: dict[str, str] | None = None):
    """Cliente del SDK `openai` apuntando al proveedor configurado."""
    from openai import OpenAI

    cfg = cfg or config()
    return OpenAI(base_url=cfg["base_url"], api_key=cfg["api_key"], timeout=120, max_retries=3)


def completar(
    client,
    modelo: str,
    sistema: str,
    usuario: str,
    temperatura: float = 0.0,
    max_tokens: int = 4000,
) -> str:
    """Una respuesta del modelo, en texto. Temperatura 0: esto es clasificación."""
    resp = client.chat.completions.create(
        model=modelo,
        temperature=temperatura,
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": sistema},
            {"role": "user", "content": usuario},
        ],
    )
    return resp.choices[0].message.content or ""


def json_de(texto: str) -> Any:
    """Extrae el JSON de una respuesta, tolerando el envoltorio habitual.

    No se usa `response_format={"type": "json_object"}` porque no todos los proveedores
    compatibles lo implementan, y el objetivo del ADR 0005 es que este código funcione
    contra cualquiera de ellos. Sale más barato ser tolerante al parsear.

    Devuelve `None` si no hay JSON reconocible, en vez de lanzar: una respuesta mala de
    un lote no debe tumbar una ejecución de miles de titulares.
    """
    if not texto:
        return None
    if m := _VALLA.search(texto):
        texto = m.group(1)
    texto = texto.strip()
    try:
        return json.loads(texto)
    except json.JSONDecodeError:
        pass
    # Modelos habladores: "Aquí tienes el resultado: [...]". Se busca el primer objeto o
    # lista completos por el par de delimitadores más externo.
    for abre, cierra in (("[", "]"), ("{", "}")):
        i, j = texto.find(abre), texto.rfind(cierra)
        if i != -1 and j > i:
            try:
                return json.loads(texto[i : j + 1])
            except json.JSONDecodeError:
                continue
    return None
