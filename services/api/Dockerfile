FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
RUN uv sync

EXPOSE 8000
CMD ["uv", "run", "uvicorn", "territorio_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
