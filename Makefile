.PHONY: help up down logs build test lint fmt hooks

help: ## Muestra esta ayuda
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

up: ## Levanta toda la plataforma (docker compose)
	docker compose up --build -d

down: ## Para y elimina los contenedores
	docker compose down

logs: ## Sigue los logs de todos los servicios
	docker compose logs -f

build: ## Reconstruye las imágenes
	docker compose build

test: ## Tests de los servicios Python
	cd services/api && uv run pytest -q
	cd services/orchestrator && uv run pytest -q

lint: ## Lint del monorepo (ruff)
	uvx ruff check .
	uvx ruff format --check .

fmt: ## Formatea el código
	uvx ruff format .
	uvx ruff check --fix .

hooks: ## Instala los hooks de pre-commit
	uvx pre-commit install

migrate: ## Aplica las migraciones de BD (Alembic) en el contenedor
	docker compose run --rm orchestrator uv run alembic upgrade head

ingest-municipios: ## Ingesta geometrías IGN → dim_municipio
	docker compose run --rm orchestrator uv run dagster asset materialize --select dim_municipio -m territorio_pipelines.definitions

ingest-padron: ## Ingesta población INE (29005) → fact_municipio_anual
	docker compose run --rm orchestrator uv run dagster asset materialize --select padron -m territorio_pipelines.definitions

ingest-piramide: ## Ingesta pirámide de edad INE (bucle 52 provincias) → fact_piramide
	docker compose run --rm orchestrator uv run dagster asset materialize --select piramide -m territorio_pipelines.definitions

ingest-mnp: ## Ingesta tasas vitales provinciales INE (1470/1482) → fact_provincia_anual
	docker compose run --rm orchestrator uv run dagster asset materialize --select mnp -m territorio_pipelines.definitions

ingest-paro: ## Ingesta paro registrado SEPE → fact_municipio_anual
	docker compose run --rm orchestrator uv run dagster asset materialize --select paro_sepe -m territorio_pipelines.definitions

ingest-renta: ## Ingesta renta INE/ADRH (bucle por provincia) → fact_municipio_anual
	docker compose run --rm orchestrator uv run dagster asset materialize --select renta_adrh -m territorio_pipelines.definitions

ingest-alquiler: ## Ingesta alquiler SERPAVI → fact_municipio_anual
	docker compose run --rm orchestrator uv run dagster asset materialize --select alquiler -m territorio_pipelines.definitions

ingest-clima: ## Ingesta clima AEMET (lento ~20 min) → fact_municipio_anual
	docker compose run --rm orchestrator uv run dagster asset materialize --select clima -m territorio_pipelines.definitions

indice: ## Calcula el índice "¿dónde vivir?" → indice_municipio
	docker compose run --rm orchestrator uv run dagster asset materialize --select indice -m territorio_pipelines.definitions

proyectar: ## Calcula la proyección demográfica → proyeccion_municipio
	docker compose run --rm orchestrator uv run dagster asset materialize --select proyeccion -m territorio_pipelines.definitions

entrenar-ml: ## Entrena el modelo ML (backtest + MLflow) y predice → prediccion_ml
	docker compose run --rm orchestrator uv run dagster asset materialize --select prediccion_ml -m territorio_pipelines.definitions

arquetipos: ## Clustering de municipios en arquetipos → arquetipo_municipio
	docker compose run --rm orchestrator uv run dagster asset materialize --select arquetipos -m territorio_pipelines.definitions
