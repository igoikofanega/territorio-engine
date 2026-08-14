# Contributing

Thanks for your interest. This is a civic-tech project about Spanish
municipalities, so contributions that add data sources or improve data quality
are especially welcome.

## Language convention

This project is deliberately **bilingual**, and the split is not accidental:

- **English**: `README.md`, issue and PR discussion.
- **Spanish**: source code, column names, data entities, docstrings, commit
  messages, ADRs and the rest of `docs/`.

The data is Spanish and its vocabulary has no clean English equivalent
(`cod_municipio`, `renta_neta_media_persona`, `padrón`, `paro registrado`).
Translating it would add a lossy mapping layer between the code and the official
sources it mirrors. Please follow the existing convention rather than mixing.

## Getting started

Requirements: Docker and Docker Compose. Everything else runs in containers.

```bash
cp .env.example .env
make up
```

| Service     | URL                     |
|-------------|-------------------------|
| API         | http://localhost:8000   |
| Dagster UI  | http://localhost:3010   |
| MLflow      | http://localhost:5055   |
| Frontend    | http://localhost:5173   |

Ports are configurable in `.env` — they only affect the host side, since
services talk to each other over the internal Docker network by service name.

Then create the schema and load data (order matters — see the README for the
full ingestion sequence):

```bash
make migrate
make ingest-municipios
make ingest-padron
```

## Development workflow

```bash
make lint    # ruff check + format --check
make fmt     # ruff format + fix
make test    # pytest for both Python services
make hooks   # install pre-commit hooks (do this once)
```

**Rebuilds are per-service.** After changing code in a service you must rebuild
its image; restarting is not enough:

```bash
docker compose up --build -d api
```

## Principles

These are non-negotiable and predate any individual contribution. The long form
lives in [`AGENTS.md`](AGENTS.md).

1. **Minimal code.** Before writing something new, walk the ladder: is it
   needed? does it already exist in the repo? standard library? a dependency
   already installed? a one-liner? Only then, the smallest thing that works. Do
   not add dependencies or abstractions "just in case".
2. **Raw data is immutable.** Every ingestion lands the original file in `raw/`
   (or the `/data/raw` volume) *before* transforming anything, and validates the
   incoming schema.
3. **Honesty about data.** Flag anything imputed, masked or estimated. Never
   present an estimate as a measurement. `cod_municipio` is a **5-character
   string** — leading zeros are significant.
4. **Spatial joins are precomputed offline** in pipelines. The API only reads;
   PostGIS does not compute geometry at request time.

## Adding a data source

This is the most common kind of contribution, and there is a shape to follow:

1. Open an issue using the **"Nueva fuente de datos"** template first, so the
   licence and the municipal key can be discussed before you write code.
2. Add an adapter in `services/orchestrator/src/territorio_pipelines/sources/`.
   Model it on `sources/wikipedia.py` — small, with a **pure, testable**
   parsing function separated from the network call.
3. Land the raw file in `/data/raw` before transforming.
4. Add an Alembic migration if you need new columns or tables. Keep the ORM
   models in `models.py` in sync — there is a CI check for drift.
5. Add a Dagster asset in `assets.py` and a `make ingest-<source>` target.
6. Add tests against a **recorded fixture**, not the live network. CI has no
   network access to third-party sources.
7. Add the source to the table in `NOTICE` with its licence, and to the README.

## Tests

Tests must pass **without network access and without API keys**. Anything that
talks to an external service is exercised through recorded fixtures in
`tests/fixtures/`. This is what keeps the repository reproducible for someone
who just cloned it.

## Commits

Conventional Commits, in Spanish, scoped by area:

```
feat(datos): cobertura de banda ancha — fibra, 100 Mbps y 5G
fix(api): corrige el filtro de provincia en /renta.geojson
docs(adr): 0004 ampliación de fuentes más allá del MVP
```

Every change must pass `make lint` and `make test` before being pushed.
