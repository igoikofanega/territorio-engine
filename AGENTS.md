# AGENTS.md — contexto para agentes de IA (harness)

Este fichero es la **fuente de verdad legible por máquina** del proyecto. Léelo antes
de escribir código. Si algo no está aquí ni en `docs/`, asúmelo no decidido: pregunta.

## Qué es esto
`territorio-engine` es un **motor de fusión de datos territoriales** de España.
Núcleo = armonizar fuentes públicas heterogéneas a la clave **`municipio × año`** y
servir cruces + ML. Pregunta-bandera: *¿hacia dónde va este pueblo (crece o se vacía)?*
Alma: bien público / civic tech.

## Principios de trabajo (no negociables)
1. **Código mínimo (ponytail).** Antes de escribir, recorre la escalera: ¿hace falta?
   ¿ya existe en el repo? ¿stdlib? ¿plataforma? ¿dependencia ya instalada? ¿one-liner?
   Solo entonces, la solución mínima que funcione. No añadas dependencias ni
   abstracciones "por si acaso".
2. **MVP primero.** El alcance está congelado (ver más abajo). No implementes capas
   futuras (SAE bayesiano, Kriging, NDVI, GDELT, los cruces avanzados) hasta que la
   matriz `core` esté viva y validada.
3. **Datos crudos inmutables.** Toda ingesta aterriza el fichero original en `raw/`
   (o el volumen `/data/raw`) **antes** de transformar. Validar esquema entrante.
4. **Honestidad sobre los datos.** Marca con flags lo imputado/enmascarado/estimado.
   `cod_municipio` es **texto de 5 dígitos** (ceros a la izquierda importan).

## Arquitectura (5 servicios)
Ver detalle en [`docs/architecture.md`](docs/architecture.md).
- **db** PostgreSQL+PostGIS · **api** FastAPI async (solo lectura) ·
  **orchestrator** Dagster (único que escribe) · **mlflow** tracking · **frontend** React+Vite.
- Regla dura: **los JOIN espaciales se precalculan offline** en pipelines. La API no
  calcula geometría en tiempo de petición: solo `ST_AsGeoJSON` sobre geometría ya
  simplificada. (No hay vistas materializadas; ver [ADR 0004](docs/adr/0004-alcance-y-arquitectura-reales.md).)

## Modelo de datos
Especificación completa en [`docs/matrix-spec.md`](docs/matrix-spec.md).
21 tablas. Núcleo: `dim_municipio` (geometría; **aún no es SCD2**, deuda conocida),
`fact_municipio_anual`, `fact_piramide`, `fact_provincia_anual`. El resto son atributos
casi-estáticos (`municipio_*`) y salidas de modelo. Grano de hechos:
`(cod_municipio, anio)`, ventana **2015→**. `municipio_vecinos` de la spec nunca se creó:
LISA usa KNN sobre centroides.

**Los años no se fijan a mano.** `calendario.py` los deriva de la cobertura real; la
matriz contiene años a medio cargar (2026 tiene paro pero no población) y un `max(anio)`
ingenuo produce datasets vacíos en silencio.

## Convenciones
- **Python** 3.12, gestionado con **uv**. Lint/formato: **ruff** (`ruff.toml`). Layout
  `src/`. Cada servicio es un proyecto uv independiente con su `pyproject.toml`.
- **Nombres de columnas y entidades de datos en español** (es un proyecto de datos
  españoles): `cod_municipio`, `poblacion_total`, `renta_neta_media_persona`…
- **Frontend** React + TypeScript + Vite.
- Migraciones de BD con **Alembic** (se añade al crear el primer DDL).
- Tests con **pytest** (Python). Todo cambio debe pasar `make lint` y `make test`.

## Comandos
```bash
make up      # levanta la plataforma          make test   # pytest
make down    # la para                        make lint   # ruff
make logs    # logs                           make fmt    # formatea
make hooks   # instala pre-commit
```

## Alcance vigente
**14 fuentes** y varias capas de ML. El alcance real lo documenta el README; el ADR 0001
quedó superado y el [ADR 0004](docs/adr/0004-alcance-y-arquitectura-reales.md) registra
qué cambió. Modelo bandera de facto: **HistGradientBoosting** con backtest temporal
(el cohorte-componente se mantiene como contraste metodológico).

Regla vigente para fuentes nuevas: basta con registrarlas en `NOTICE` (licencia) y en el
README. **Solo requieren ADR** si cambian el grano, añaden un servicio o meten una
dependencia pesada.

## ponytail
La disciplina de código mínimo la refuerza el plugin **ponytail** (instálalo aparte:
`/plugin marketplace add DietrichGebert/ponytail` → `/plugin install ponytail@ponytail`).
Comandos útiles: `/ponytail-review` (revisa sobre-ingeniería del diff), `/ponytail-audit`.
