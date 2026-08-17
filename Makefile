.PHONY: help up down logs build test lint fmt hooks typecheck front-lint front-test front-check check

# Node no hace falta en el host: el tooling de frontend corre en un contenedor
# efímero con el UID del usuario, para no dejar ficheros de root en el repo.
NODE_RUN = docker run --rm --user "$$(id -u):$$(id -g)" -e HOME=/tmp \
	-v "$$PWD/frontend":/app -w /app node:22-alpine

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
	uvx ruff@0.16.3 check .
	uvx ruff@0.16.3 format --check .

fmt: ## Formatea el código
	uvx ruff@0.16.3 format .
	uvx ruff@0.16.3 check --fix .

typecheck: ## Comprobación de tipos (mypy) de los servicios Python
	cd services/api && uv run mypy
	cd services/orchestrator && uv run mypy

front-lint: ## Lint + tipos del frontend (en contenedor)
	$(NODE_RUN) sh -c "npm ci --silent && npx tsc --noEmit && npx eslint ."

front-test: ## Tests del frontend (vitest, en contenedor)
	$(NODE_RUN) sh -c "npm ci --silent && npx vitest run"

front-check: front-lint front-test ## Todas las comprobaciones del frontend

check: lint typecheck test front-check ## Todo lo que valida el CI, en local

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

ingest-nacionalidad: ## Población extranjera y % por municipio (INE 33571) → fact_municipio_anual
	docker compose run --rm orchestrator uv run dagster asset materialize --select nacionalidad -m territorio_pipelines.definitions

ingest-fibra: ## Cobertura de banda ancha (SETELECO) → municipio_conectividad
	docker compose run --rm orchestrator uv run dagster asset materialize --select fibra -m territorio_pipelines.definitions

ingest-aire: ## Calidad del aire (rasters EEA: PM2.5, NO2, PM10, O3) → municipio_aire
	docker compose run --rm orchestrator uv run dagster asset materialize --select aire -m territorio_pipelines.definitions

ingest-noticias: ## Piloto de noticias GDELT (Navarra, 2018 y 2024, ~50 min) → noticia_municipio
	docker compose run --rm orchestrator uv run dagster asset materialize --select noticias -m territorio_pipelines.definitions

ingest-noticias-serie: ## Serie completa de noticias GDELT (Navarra, 2017-2025, ~4 h) → noticia_municipio
	docker compose run --rm -e GDELT_ANIOS=2017-2025 orchestrator uv run dagster asset materialize --select noticias -m territorio_pipelines.definitions

etiquetar-noticias: ## Etiqueta titulares con el LLM (pertenencia, tema, signo) → noticia_municipio
	docker compose run --rm orchestrator uv run dagster asset materialize --select noticias_etiquetadas -m territorio_pipelines.definitions

noticias-progreso: ## Estado de la ingesta y del etiquetado de noticias
	@docker compose exec -T db psql -U $${POSTGRES_USER:-territorio} -d $${POSTGRES_DB:-territorio} -c "SELECT count(*) AS articulos, count(DISTINCT cod_municipio) AS con_noticias, (SELECT count(*) FROM dim_municipio WHERE cod_provincia = '31') AS ambito, count(*) FILTER (WHERE modelo IS NOT NULL) AS etiquetados, count(*) FILTER (WHERE modelo IS NULL) AS pendientes, count(*) FILTER (WHERE pertenece) AS pertenecen, count(DISTINCT cod_municipio) FILTER (WHERE pertenece) AS con_noticias_propias FROM noticia_municipio;"
	@echo "consultas GDELT resueltas (crudos): $$(find raw/gdelt -name '*.json' 2>/dev/null | wc -l) de $$(( $$(docker compose exec -T db psql -U $${POSTGRES_USER:-territorio} -d $${POSTGRES_DB:-territorio} -tAc "SELECT count(*) FROM dim_municipio WHERE cod_provincia = '31'") * 2 ))"

golden-export: ## Exporta la muestra de titulares para etiquetar a mano → raw/golden/
	docker compose run --rm orchestrator uv run python -c "from territorio_pipelines.db import engine; from territorio_pipelines import golden; print(golden.exportar(engine), 'filas en', golden.PARA_ETIQUETAR)"

golden-metricas: ## Mide la extracción del LLM contra el golden set etiquetado
	docker compose run --rm orchestrator uv run python -c "from territorio_pipelines.db import engine; from territorio_pipelines import golden; import json; print(json.dumps(golden.metricas(engine), indent=2, ensure_ascii=False))"

ingest-wikidata: ## Hechos Wikidata por municipio → municipio_wiki
	docker compose run --rm orchestrator uv run dagster asset materialize --select wikidata -m territorio_pipelines.definitions

ingest-wikipedia: ## Descripciones Wikipedia por municipio → municipio_wiki
	docker compose run --rm orchestrator uv run dagster asset materialize --select wikipedia -m territorio_pipelines.definitions

ingest-servicios: ## Servicios OSM por municipio → municipio_servicios
	docker compose run --rm orchestrator uv run dagster asset materialize --select servicios -m territorio_pipelines.definitions

similares: ## 'Pueblos como el tuyo' (vecinos en features) → similar_municipio
	docker compose run --rm orchestrator uv run dagster asset materialize --select similares -m territorio_pipelines.definitions

rendimiento: ## Residuos out-of-sample (municipios contra pronóstico) → rendimiento_municipio
	docker compose run --rm orchestrator uv run dagster asset materialize --select rendimiento -m territorio_pipelines.definitions

gemelos: ## Gemelos divergentes → gemelo_municipio
	docker compose run --rm orchestrator uv run dagster asset materialize --select gemelos -m territorio_pipelines.definitions

ingest-aislamiento: ## Distancias a servicios y capital (PostGIS) → municipio_aislamiento
	docker compose run --rm orchestrator uv run dagster asset materialize --select aislamiento -m territorio_pipelines.definitions

lisa: ## Hot spots LISA (Moran local) → lisa_municipio
	docker compose run --rm orchestrator uv run dagster asset materialize --select lisa -m territorio_pipelines.definitions

riesgo: ## Semáforo de despoblación (probabilidad calibrada) → riesgo_municipio
	docker compose run --rm orchestrator uv run dagster asset materialize --select riesgo -m territorio_pipelines.definitions

inflexiones: ## Puntos de inflexión de la población (change points) → inflexion_municipio
	docker compose run --rm orchestrator uv run dagster asset materialize --select inflexiones -m territorio_pipelines.definitions

demografia: ## Descomposición vegetativo vs migratorio → demografia_municipio
	docker compose run --rm orchestrator uv run dagster asset materialize --select demografia -m territorio_pipelines.definitions
