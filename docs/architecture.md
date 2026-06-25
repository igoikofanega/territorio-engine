# Arquitectura

## Topología MVP (4 servicios)

```
        ┌──────────────┐   React + Vite (mapa)
        │  frontend    │   :5173 — en local habla directo a la API
        └──────┬───────┘
               │ HTTP
        ┌──────▼───────┐   FastAPI + async SQLAlchemy + asyncpg
        │     api      │   :8000 — SOLO lectura de vistas materializadas
        └──────┬───────┘
        ┌──────▼───────┐   PostgreSQL + PostGIS
        │     db       │   :5432 — matriz + geometrías + mat. views
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
  persisten. La API nunca calcula geometría en tiempo de petición: lee de **vistas
  materializadas** particionadas por año.
- Toda ingesta **aterriza el crudo en `raw/` antes de transformar** y valida esquema.
- Python con **uv**; cada servicio es una imagen Docker independiente.

## Crece por fases (no implementar antes de tiempo)
- **Fase deploy:** Traefik/Nginx como gateway + paso a AWS ECS.
- **MLOps:** servidor MLflow dedicado (al principio, tracking en fichero).
- **Async bajo demanda:** Celery + broker SOLO cuando el usuario dispare jobs
  (p. ej. simulaciones "¿qué pasaría si…?").
- **Almacenamiento:** MinIO → S3 cuando el volumen lo pida.

Decisión registrada en [`adr/0003-architecture-topology.md`](adr/0003-architecture-topology.md).
