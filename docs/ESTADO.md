# Estado del proyecto y por dónde seguir

> **Documento de traspaso.** Última actualización: **2026-09-05**.
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
| Tests | 225 (107 API · 102 orchestrator · 16 frontend) |
| Licencia | Apache-2.0, con `NOTICE` de las 14 fuentes |
| Secretos | 0 filtraciones (gitleaks + trufflehog sobre todo el historial) |
| Protecciones | Escaneo de secretos, push protection, sin force-push en `main` |

Base de datos de desarrollo poblada: **8.217 municipios**, 96.585 filas de hechos,
ventana 2015-2026.

### Métricas del modelo (backtest temporal, corte único)

| Modelo | MAE (pp) | R² |
|---|---|---|
| Persistencia (baseline) | 7.65 | — |
| Tendencia (baseline) | 10.02 | — |
| **HistGradientBoosting** | **5.98** | **0.30** |

> **Estas cifras cambiaron el 2026-09-05 y son peores que las anteriores a propósito.**
> Hasta esa fecha se publicaba MAE 5.79 / R² 0.34; ese número salía de un dataset con
> fuga temporal (ver abajo). Sigue siendo un corte único sin dispersión: pendiente el
> backtest de origen rodante.

---

## Fase 4 — Rigor de la evaluación (en curso, 2026-09-05)

El objetivo de esta fase no es mejorar el MAE, es medirlo bien.

### La fuga temporal de `pct_extranjeros` (resuelta)

`ml/features.py` leía el % de extranjeros con `DISTINCT ON ... ORDER BY anio DESC`, es
decir el valor **más reciente**, y lo aplicaba a todos los años base incluidos los de
entrenamiento — pese a que `fact_municipio_anual` tiene serie anual 2015-2022.

Medido sobre la base real (8.117 municipios), correlación con el cambio de población
2015→2020:

| Valor usado | corr. con el target |
|---|---|
| `pct_extranjeros` de 2015 (contemporáneo) | 0.159 |
| `pct_extranjeros` de 2022 (futuro) | 0.275 |

Y el efecto en el backtest, mismo corte y mismos datos:

| | MAE (pp) | R² |
|---|---|---|
| Con fuga (lo que se publicaba) | 5.790 | 0.340 |
| **Corregido (`_asof`)** | **5.981** | **0.301** |

La regla ahora es una sola, igual en entrenamiento y en inferencia: para el año base T
vale el dato más reciente con año ≤ T. Lo protege `tests/test_features.py`, que falla si
se reintroduce el fallo (comprobado revirtiéndolo).

### Lo que sí es estático, y lo que sólo lo parece

No todo lo invariante en el tiempo es una fuga:

- **Clima**: AEMET publica una *normal climática*, no una serie anual municipal. Una
  normal de 30 años no codifica el cambio de población de 2015-2020. Es legítimo.
- **Cobertura de fibra**: SETELECO publica una **foto** del despliegue actual, sin
  histórico. Esto sí es un riesgo de fuga (la fibra llegó antes a los municipios que
  crecían) y **no se puede desfasar con los datos que hay**.

Medido, quitando cada grupo del modelo corregido:

| | k | MAE (pp) | R² |
|---|---|---|---|
| todas | 17 | 5.981 | 0.301 |
| sin fibra | 16 | 6.043 | 0.284 |
| sin clima | 13 | 6.122 | 0.259 |
| sin ambas | 12 | 6.261 | 0.228 |

Las dos aportan señal, así que **se quedan, con la limitación declarada** en el código y
en el README. Si algún día SETELECO publica histórico, `pct_fibra` debe pasar por `_asof`
como los extranjeros.

### Dos fallos visibles que encontró la primera captura de pantalla

Intentar ilustrar el README destapó lo que ningún test miraba, porque nadie había mirado
la aplicación desde cero:

1. **El mapa abría vacío.** `/poblacion/anios` era el único endpoint de años que **no
   filtraba por su propia columna**: devolvía `DISTINCT anio` de `fact_municipio_anual`,
   así que 2026 salía el primero —tiene 7.030 filas de paro y cero de población— y el
   frontend lo tomaba como año por defecto. La misma trampa que `calendario.py` resuelve
   en el orquestador, colada en la API. Cubierto ahora por un test parametrizado sobre
   los tres endpoints de años.
2. **El mapa base pedía clave.** CARTO dejó de servir `basemaps.cartocdn.com` sin API
   key, así que el fondo salía cubierto de marcas "API KEY REQUIRED". El defecto es ahora
   OpenStreetMap, que no pide clave, configurable por `VITE_TILES_URL`. Va **atenuado al
   45%** a propósito: el estilo estándar de OSM compite con los azules del coroplético.

### Capturas: Firefox headless ya no sirve

`firefox --headless --screenshot` **pinta la interfaz pero no el mapa** en este servidor:
ni teselas ni polígonos, aunque la escala salga bien (es decir, `fitBounds` sí corre).
Da el mismo resultado con Xvfb y sin iframe, así que no es el envoltorio.

Lo que funciona es la imagen de Playwright, que además permite esperar a una condición
real del DOM en vez de al evento `load`:

```bash
docker run --rm --network host -v /tmp/shots:/w -v /tmp/shots/out:/salida \
  -w /w mcr.microsoft.com/playwright:v1.48.0-jammy node capturar.js
```

El script espera a `.leaflet-overlay-pane path` (>50 elementos) e informa de cuántos
polígonos y teselas cargaron, que es lo que delata un mapa roto.

### Trampa de entorno descubierta aquí

`docker compose exec orchestrator` **no entra necesariamente en el contenedor del
servicio**: si hay un `docker compose run --rm orchestrator` vivo (el etiquetado de
noticias corre así, durante horas), compose puede resolver el nombre a ese contenedor,
que lleva la imagen antigua. Se pierde mucho tiempo creyendo que el rebuild no funciona.
Para verificar código dentro del contenedor, usa el nombre exacto:

```bash
docker exec -i territorio-engine-orchestrator-1 ...
```

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

### Fase 3 — Capa de LLM y noticias (en curso, 2026-08-15)

Todas las decisiones están en el [ADR 0005](adr/0005-capa-de-noticias-y-llm.md), incluido
el **criterio de aceptación de la ablación**, escrito antes de ver ningún resultado.

**Hecho:**

| Bloque | Estado |
|---|---|
| ADR 0005 | ✅ |
| Ingesta GDELT (migración 0029, adaptador, loader, asset, targets) | ✅ |
| Cliente LLM + extracción de etiquetas | ✅ ejecutado (Gemini 3.1 Flash Lite) |
| Panel de noticias en la ficha + endpoint | ✅ |
| Golden set (exportación + métricas) | ✅ herramientas; falta etiquetar el golden set |
| Observabilidad de la ingesta | ✅ |
| Piloto + puerta de decisión | ⏳ etiquetado corriendo (11.056/34.126, 32,4%) |
| Features de noticias (migración 0030, `features_noticias.py`) | ✅ código + 23 tests |
| Ablación de tres brazos (`ablacion.py`) | ✅ código; pendiente ejecución con datos |
| Informe narrativo (migración 0031, `narrativa.py`, endpoint) | ✅ código + 17 tests |
| Agregación noticias_anual | ✅ parcial (57 filas, 15 municipios) |

**En progreso:** el etiquetado masivo de ~30k artículos se ejecuta en background
(Gemini 3.1 Flash Lite via API de Google). Una vez completo, hay que re-agregar
`noticias_anual`, ejecutar la ablación, y generar las narrativas.

#### Lo que se aprendió midiendo, y que cambia el plan

**1. El límite de GDELT no es de cadencia, es de carga.** La documentación dice "1
petición cada 5 segundos"; medido contra la API real, con 10 s de separación responde 2 de
cada 5 veces y con 40 s, 1 de cada 4. Tras 5 minutos sin pedir nada, la primera petición
también puede fallar. **Esperar más no mejora nada**: hay que insistir.

Consecuencia práctica: **~1 consulta con éxito por minuto**. El piloto (272 municipios × 2
años = 544 consultas) son unas 9 h, no los 50 min estimados; la serie completa (2017-2025)
serían ~40 h. La ingesta es reanudable y no aborta ante un fallo, así que relanzarla
continúa donde iba y reintenta solo los huecos.

**2. Rechaza con 429, no con 200.** El primer intento de ingesta murió entero en el primer
municipio por dar por hecho lo contrario. Si vuelves a tocar esto: el aviso llega con
estado 429 y cuerpo en texto plano, y `httpx` no lanza ante un 4xx.

**3. La homonimia es la tarea, no un preproceso.** La consulta de "Tudela" devuelve
noticias de Tudela de Duero (Valladolid) desde `elnortedecastilla.es`. Por eso el prompt
lleva el dominio del medio, que desambigua mejor que el propio titular.

**4. Se recorre por población descendente**, no por código INE. Con nueve horas por
delante y cortes probables, lo descargado cuando se corte debe ser lo que tiene noticias:
por código, las primeras horas se iban en Abáigar, Abárzuza y Abaurregaina, que devuelven
cero artículos.

#### Cómo vigilar la ingesta

```bash
make noticias-progreso   # artículos, municipios cubiertos, consultas resueltas
```

La UI de Dagster (<http://localhost:3010>) muestra el run y su log de progreso, que se
publica cada 10 municipios. **Esto no funcionaba hasta esta sesión**: `DAGSTER_HOME`
apuntaba a `/tmp` dentro del contenedor, así que cada `docker compose run` creaba su
propia instancia vacía y la ejecución no salía en ninguna parte. Ahora es un volumen
compartido. Si añades otro asset lento, no lo lances sin pasar por ahí.

#### Deuda que deja esta fase

- **Dagster guarda su historial en SQLite sobre un volumen.** Lo correcto sería Postgres,
  que ya está levantado, pero `dagster-postgres` crearía sus tablas en la base
  `territorio` y eso **rompería `test_esquema.py`** (toda tabla de la BD debe estar en
  `models.py`). Requiere una base de datos aparte para Dagster.
- **El golden set lo etiquetará un modelo, no una persona.** Si se hace así, hay que
  decirlo en el informe: es una referencia cuidadosa frente a un clasificador barato, no
  una verdad humana.

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
