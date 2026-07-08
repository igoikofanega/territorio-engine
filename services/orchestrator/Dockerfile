FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

# libexpat1: dependencia de runtime de la GDAL que trae la rueda de rasterio (calidad
# del aire: muestreo de rasters GeoTIFF de la EEA). Sin ella, `import rasterio` falla.
RUN apt-get update && apt-get install -y --no-install-recommends libexpat1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
COPY alembic.ini ./
COPY migrations ./migrations
RUN uv sync

EXPOSE 3000
# Dagster UI (dev). DAGSTER_HOME en /tmp para desarrollo.
ENV DAGSTER_HOME=/tmp/dagster_home
RUN mkdir -p $DAGSTER_HOME
CMD ["uv", "run", "dagster", "dev", "-h", "0.0.0.0", "-p", "3000", "-m", "territorio_pipelines.definitions"]
