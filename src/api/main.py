"""Aplicación FastAPI del Smart Tourism Engine.

T039 — Expone el endpoint `GET /health` para verificación de disponibilidad.
"""

from fastapi import FastAPI

app = FastAPI(
    title="Smart Tourism Engine API",
    description="API de recuperación de información turística.",
    version="0.1.0",
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
