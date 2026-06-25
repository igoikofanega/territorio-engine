# territorio-engine

Motor de fusión de datos territoriales de España. Ingiere fuentes públicas
heterogéneas, las armoniza a una clave común (**`municipio × año`**, con sección
censal como grano fino) y, sobre esa matriz, responde preguntas con ML.

**Pregunta-bandera:** *¿Hacia dónde va este pueblo — crece o se vacía?*
Vocación de bien público / civic tech. Ángulo "España vaciada".

> Documentación viva para humanos y agentes: ver [`AGENTS.md`](AGENTS.md),
> [`docs/architecture.md`](docs/architecture.md) y [`docs/matrix-spec.md`](docs/matrix-spec.md).

## Stack (MVP)
- **db** — PostgreSQL + PostGIS (matriz + geometrías + vistas materializadas)
- **api** — FastAPI + SQLAlchemy async (solo lectura para el frontend)
- **orchestrator** — Dagster (assets: ingesta → matriz; entrena el modelo)
- **frontend** — React + Vite (mapa)
- Python con **uv**; todo reproducible vía **Docker Compose**.

## Arranque rápido
```bash
cp .env.example .env
make up          # levanta db + api + orchestrator + frontend
```
- API:          http://localhost:8000/health
- Dagster UI:   http://localhost:3000
- Frontend:     http://localhost:5173

## Desarrollo
```bash
make hooks   # instala pre-commit
make lint    # ruff
make test    # pytest de los servicios
```

## Alcance
MVP = 5 fuentes con clave municipal limpia (IGN, Padrón, Renta ADRH, Paro SEPE,
AEMET) **+ MNP** (natalidad/mortalidad, necesaria para el modelo). Ventana **2015→**.
Lo que queda fuera de v1 está en [`docs/adr/0001-mvp-scope-and-discipline.md`](docs/adr/0001-mvp-scope-and-discipline.md).
