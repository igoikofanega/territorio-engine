# ADR 0003 — Topología de la arquitectura

- **Estado:** aceptado
- **Fecha:** 2026-06-25

## Decisión
Topología MVP de **4 servicios** en Docker Compose: `db` (PostgreSQL+PostGIS),
`api` (FastAPI async, solo lectura), `orchestrator` (Dagster) y `frontend` (React+Vite),
con un volumen `raw/` como landing zone. Python con **uv**.

## Por qué (frente a la propuesta de 7 servicios)
- **Celery + broker:** descartado en v1. El trabajo es por lotes/programado → es del
  orquestador. Celery entra solo cuando haya jobs disparados por el usuario.
- **API Gateway (Traefik/Nginx):** diferido a la fase de despliegue (un solo backend).
- **Servidor MLflow dedicado:** diferido; tracking en fichero al principio.
- **Orquestador = Dagster** (no Airflow): modelo de *assets* que encaja con "la matriz
  es un asset derivado"; más ligero de operar en solitario.

## Reglas duras
- JOIN espaciales **precalculados offline**; la API solo lee vistas materializadas
  (particionadas por año).
- Crudo inmutable en `raw/` antes de transformar; validación de esquema entrante.

## Crece hacia
Traefik (deploy) → MLflow server → Celery (jobs on-demand) → MinIO/S3 → ECS/K8s.
