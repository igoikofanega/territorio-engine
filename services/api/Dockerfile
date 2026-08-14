FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app
# uv.lock se copia para que el build use las versiones exactas del repo (--frozen falla
# si el lock no está sincronizado con pyproject.toml). Sin él, uv resolvería de nuevo en
# cada build y la imagen no sería reproducible.
COPY pyproject.toml uv.lock ./
COPY src ./src
RUN uv sync --frozen

EXPOSE 8000
CMD ["uv", "run", "uvicorn", "territorio_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
