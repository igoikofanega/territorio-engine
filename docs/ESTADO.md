# Estado del proyecto y por dónde seguir

> **Documento de traspaso.** Última actualización: **2026-08-14**.
> Si eres un agente empezando una conversación nueva: lee esto y
> [`AGENTS.md`](../AGENTS.md) antes de tocar nada. Aquí está el *estado* y el *plan*;
> en `AGENTS.md`, las reglas.

---

## Dónde estamos

El repositorio está **publicado y verde**: <https://github.com/igoikofanega/territorio-engine>

| | |
|---|---|
| Commits | 54, todos atribuidos a `igoikofanega <i.goikofanega@gmail.com>` |
| CI | 7 jobs, todos en verde |
| Imágenes | `api`, `orchestrator`, `frontend` en GHCR (amd64 + arm64) |
| Tests | 147 (101 API · 46 orchestrator · 16 frontend) |
| Licencia | Apache-2.0, con `NOTICE` de las 14 fuentes |
| Secretos | 0 filtraciones (gitleaks + trufflehog sobre todo el historial) |
| Protecciones | Escaneo de secretos, push protection, sin force-push en `main` |

Base de datos de desarrollo poblada: **8.217 municipios**, 96.585 filas de hechos,
ventana 2015-2026.

### Métricas del modelo (backtest temporal, de MLflow)

| Modelo | MAE (pp) | R² |
|---|---|---|
| Persistencia (baseline) | 7.65 | — |
| Tendencia (baseline) | 10.02 | — |
| **HistGradientBoosting** | **5.79** | **0.34** |

---

## Lo hecho en esta sesión (fases 0 a 2)

**Fase 0-1 · Publicación e infraestructura.** Historial reescrito a la autoría correcta,
Apache-2.0 + NOTICE + CONTRIBUTING + SECURITY + plantillas, CI reescrito (7 jobs con
caché, cobertura, mypy, tests de frontend, integración con PostGIS real y publicación
multi-arch), eslint + vitest + mypy donde no había nada, README en inglés con insignias.

**Fase 2 · Deuda técnica.** Registro declarativo de capas en la API (`main.py`: 1671 →
797 líneas), años derivados de la cobertura real (`calendario.py`), deriva ORM↔Alembic
saneada, y documentación reconciliada con la realidad (ADR 0004).

### Fallos reales encontrados por el camino

Vale la pena conocerlos porque explican decisiones del código:

1. **El lint no era reproducible.** `uvx ruff` sin versión en CI mientras pre-commit
   fijaba otra. Los hooks pasaban y el CI fallaba. Ahora ruff está fijado en los tres
   sitios; **si lo cambias, cámbialo en los tres**.
2. **Los builds ignoraban el lockfile.** Los Dockerfile copiaban `pyproject.toml` pero no
   `uv.lock`. Ahora usan `uv sync --frozen`.
3. **`max(anio)` no sirve.** La matriz contiene años a medio cargar: **2026 tiene 7.030
   filas de paro y cero de población**, porque el CSV del SEPE del año en curso sale antes
   que el Padrón. Por eso existe `calendario.py`. **No sustituyas sus llamadas por
   `max(anio)`.**
4. **El CI tenía un punto ciego en ML.** Ningún test entrenaba un modelo, así que un PR
   que subía mlflow a 3.x —saltándose el tope `<3`— pasó los 8 jobs en verde. Lo cubre
   ahora `test_ml_humo.py`.
5. **`matriz_municipio_anual` era un stub** que devolvía 0, declarado en la documentación
   como "el objetivo del MVP". Eliminado: la fusión ya la hacen los `load_*` por UPSERT.

---

## Por dónde seguir

### Fase 3 — Capa de LLM y noticias (siguiente, sin empezar)

El plan detallado está en la conversación previa; esto es el resumen operativo.

**Decisiones ya tomadas por el usuario, no re-preguntar:**

- **Proveedor**: SDK `openai` de Python contra un `base_url` configurable, para que sirva
  cualquier proveedor compatible **y Ollama**. NO el SDK de Anthropic.
- **Alcance**: Navarra (272 municipios) primero, diseño escalable a España.
- **Sin despliegue cloud.**

**Dos restricciones verificadas empíricamente que condicionan el diseño:**

| Fuente | Hallazgo |
|---|---|
| Google News RSS | Funciona (100 artículos, 30 medios), pero **solo ~4 meses de histórico**. Inútil para features de ML. |
| GDELT DOC 2.0 | Tiene histórico, pero **arranca en 2017** y limita a **1 petición cada 5 segundos** (devuelve 429). |

**Consecuencia crítica:** los años base del modelo son 2015-2020. Con GDELT desde 2017 y
ventana `[T-2, T]`, solo 2019 y 2020 tendrían cobertura completa — **y son justo los años
de validación**. Por eso la ablación necesita su propia configuración (años base
2018-2021, horizonte 3), cuyo MAE **no es comparable** con el titular del modelo.

**Predicción honesta: es probable que las features de noticias NO mejoren el MAE.** Tres
razones estructurales: >70 % de los municipios navarros probablemente no aparecen en GDELT
ni una vez; la desalineación temporal de arriba; y la redundancia —"cierra la fábrica"
llega el mismo año que sube el paro, y `paro_1000` ya lo captura antes y para los 8.131
municipios—.

**El valor no está en que funcione, sino en medirlo bien.** Ablación de tres brazos
(sin / con / **permutadas**), 5 semillas, criterio de aceptación fijado **antes** de ver
el resultado, y publicar el negativo si sale negativo. El brazo de permutación es lo que
hace creíble el resultado: sin él, un delta pequeño es indistinguible del azar.

**Puerta de decisión:** medir `n_municipios_con_cobertura` tras la ingesta. **Si salen
menos de 60, cancelar la parte de ML** y dejarlo como capa de producto.

**Orden sugerido:** ADR → ingesta GDELT → cliente LLM + extracción → **golden set y
métricas** → features + ablación → panel de noticias en la ficha → informe narrativo.
El golden set va antes que las features a propósito: no se construyen features sobre una
extracción cuya calidad no está medida.

**Legal:** almacenar y servir solo **titular, fecha, medio, URL y etiquetas derivadas**.
Nunca el cuerpo del artículo. Esto debe quedar en un ADR.

### Datos abiertos de Navarra (oportunidad nueva, sin evaluar a fondo)

<https://datosabiertos.navarra.es> — **es CKAN con API estándar**, ya verificado:

```bash
curl "https://datosabiertos.navarra.es/api/3/action/package_search?q=municipio&rows=10"
```

**1.927 datasets.** Por temas: salud 191, transporte 269, municipio 65, empleo 43,
vivienda 38, turismo 38, empresa 36.

Lo más prometedor encontrado: **"Históricos de municipios (2001-2025)"** (SHP, CC BY 4.0,
`https://idena.navarra.es/descargas/DIADMI_Pol_Municipio_DT.zip`) — **podría resolver la
deuda del linaje SCD2**, que es una de las limitaciones declaradas del proyecto.

**Tensión de diseño que hay que resolver antes de tirar por aquí:** el proyecto es
**nacional** (8.217 municipios) y estas fuentes son **solo de Navarra**. Añadirlas crea un
dataset de dos niveles: capas que existen para 272 municipios y no para los otros 7.945.
Eso no es descalificante —Navarra es el ámbito por defecto del frontend— pero **hay que
decidirlo explícitamente** y marcar esas capas como regionales en la interfaz, no dejar
que el usuario crea que un municipio de Cuenca no tiene puntos de recarga cuando lo que
pasa es que no hay dato. **Pregúntale al usuario antes de ingerir nada de aquí.**

Nota práctica: la mayoría de recursos son **SHP**, no CSV. Requiere `geopandas` o
`pyogrio`, que hoy no son dependencias. Eso sí exigiría ADR (dependencia pesada).

### Deuda conocida, no resuelta

Ordenada por lo que más contradice los principios declarados del proyecto:

1. **Faltan las banderas de calidad de dato** (`flag_imputado_paro`,
   `flag_renta_secreto`, `flag_alteracion_municipal`). `AGENTS.md` declara "honestidad
   sobre los datos" como principio no negociable, y hoy no hay forma de distinguir un dato
   medido de uno enmascarado por secreto estadístico. **Es la deuda más incoherente con
   los valores del proyecto.**
2. **`dim_municipio` no es SCD2.** Sin linaje, fusiones y segregaciones rompen la
   continuidad de las series sin avisar. (Ver el dataset de Navarra de arriba.)
3. **Tasas vitales provinciales aplicadas a municipios** en `ml/demografia.py`. Es una
   estimación, no una medición, y el error es mayor justo en los municipios pequeños, que
   son el objeto del proyecto. Está documentado en el README.
4. **Tokens de datashare de la EEA fijados en el código** (`sources/aire.py`). No son
   credenciales —son identificadores de enlaces públicos— pero la EEA puede rotarlos y
   romper la ingesta. Deberían ser configuración.
5. **`ml/gemelos.py` sigue con `ANIO_BASE` fijado.** Se quedó fuera del refactor de
   `calendario.py`; conviene alinearlo.
6. **Sin cobertura de tests en `loaders.py`** (928 líneas), que es donde vive todo el SQL
   de carga.

---

## Cómo trabajar aquí

```bash
make check     # todo lo que valida el CI, en local
make up        # levanta los 5 servicios
make help      # ~30 targets de ingesta y modelos
```

- **El rebuild es por servicio**: `docker compose up --build -d api`. Reiniciar no basta.
- **Los tests deben pasar sin red y sin API keys.** Todo lo externo va con fixtures
  grabadas. Es lo que hace el repo reproducible para quien lo clone.
- **Node no hace falta en el host**: `make front-check` lo corre en contenedor.
- El puerto de la API en el `.env` local es **8010**, no 8000.

### Trampas del entorno

- Hay una regla `deny: Bash(git push *)` en `.claude/settings.json`: **los push los hace
  el usuario a mano**, a propósito. No la quites sin permiso explícito.
- `gh` está en `/home/ubuntu/.local/bin/gh` y ya está autenticado.
- La máquina es **aarch64**. De ahí el pin `greenlet<3.5` y la imagen `imresamu/postgis`.
- Dependabot está agrupado por ecosistema y con `ignore` para pines deliberados
  (mlflow `<3`, node 22, python 3.12, greenlet). **Esos ignore no son pereza**: cada uno
  protege algo que el CI no detectaría.

### Verificar un refactor de la API

Hay una técnica que funcionó muy bien y conviene reutilizar: capturar las respuestas de
todos los endpoints **antes y después** contra la base de datos real y compararlas.
Detectó dos fallos que los tests no habrían pillado. El script está en el scratchpad de la
sesión; reconstruirlo son 15 líneas de `curl` sobre una lista de endpoints.
