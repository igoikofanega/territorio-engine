# Arquitectura

## Topología MVP (4 servicios)

```
        ┌──────────────┐   React + Vite (mapa)
        │  frontend    │   :5173 — en local habla directo a la API
        └──────┬───────┘
               │ HTTP
        ┌──────▼───────┐   FastAPI + async SQLAlchemy + asyncpg
        │     api      │   :8000 — SOLO lectura (sin cálculo de geometría)
        └──────┬───────┘
        ┌──────▼───────┐   PostgreSQL + PostGIS
        │     db       │   :5432 — matriz + geometrías
        └──────▲───────┘   (Alembic para migraciones)
               │ escribe
        ┌──────┴───────┐   Dagster (assets)
        │ orchestrator │   :3000 — ingesta → matriz → entrena modelo
        └──────┬───────┘   (MLflow file-based al principio)
               │ aterriza crudo
        ┌──────▼───────┐
        │  raw/ (vol)  │   landing zone inmutable (→ MinIO/S3 en el futuro)
        └──────────────┘
```

## Reglas duras
- **Los JOIN espaciales se precalculan offline** en pipelines de Dagster y se
  persisten. La API nunca calcula geometría en tiempo de petición: solo aplica
  `ST_AsGeoJSON` sobre geometría ya simplificada.
  Los JOIN por clave con índice sobre `(cod_municipio, anio)` sí ocurren en tiempo de
  petición y no son un problema medido. Las vistas materializadas quedan como
  optimización para cuando haya que servir el coroplético nacional completo en lugar de
  una provincia (ver [ADR 0004](adr/0004-alcance-y-arquitectura-reales.md)).
- Toda ingesta **aterriza el crudo en `raw/` antes de transformar** y valida esquema.
- Python con **uv**; cada servicio es una imagen Docker independiente.

## Crece por fases (no implementar antes de tiempo)
- **Fase deploy:** Traefik/Nginx como gateway + paso a AWS ECS.
- **MLOps:** servidor MLflow dedicado (al principio, tracking en fichero).
- **Async bajo demanda:** Celery + broker SOLO cuando el usuario dispare jobs
  (p. ej. simulaciones "¿qué pasaría si…?").
- **Almacenamiento:** MinIO → S3 cuando el volumen lo pida.
- **Mapa:** `react-leaflet` (mapa base actual) → **deck.gl** cuando haga falta el
  coroplético de toda España con rendimiento sobre miles de polígonos.

Decisión registrada en [`adr/0003-architecture-topology.md`](adr/0003-architecture-topology.md).
