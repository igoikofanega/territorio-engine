from fastapi import FastAPI
from sqlalchemy import text

from .db import engine

app = FastAPI(title="territorio-engine API", version="0.1.0")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/db")
async def health_db() -> dict[str, str]:
    """Comprueba la conexión a PostGIS (prueba de extremo a extremo del stack)."""
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    return {"db": "ok"}
