"""T042 — Middleware de logging y manejo unificado de errores de la API.

Centraliza dos responsabilidades transversales del servicio FastAPI:

- Un middleware que loguea cada request (método, ruta, status, duración) y
  expone un ``X-Request-ID`` por respuesta para correlación en observabilidad.
- Handlers de excepciones que uniforman el cuerpo de error a
  ``{"code": str, "message": str}`` con un ``status_code`` consistente, de modo
  que la UI y los clientes externos puedan procesar errores sin ramificar por
  shape de payload.
"""
from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("smart_tourism_engine.api")


_HTTP_CODE_MAP: dict[int, str] = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    409: "conflict",
    422: "validation_error",
    503: "service_unavailable",
}


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Loguea cada request con su duración y adjunta ``X-Request-ID``."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request_id = uuid.uuid4().hex[:12]
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            logger.exception(
                "request failed",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "duration_ms": duration_ms,
                },
            )
            raise
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        logger.info(
            "request handled",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
            },
        )
        response.headers["X-Request-ID"] = request_id
        return response


def _error(code: str, message: str, status_code: int) -> JSONResponse:
    return JSONResponse(
        status_code=status_code, content={"code": code, "message": message}
    )


async def http_exception_handler(
    request: Request, exc: HTTPException
) -> JSONResponse:
    code = _HTTP_CODE_MAP.get(exc.status_code, "http_error")
    return _error(code, str(exc.detail), exc.status_code)


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    return _error("validation_error", "Request payload inválido.", 422)


async def unhandled_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    logger.exception(
        "unhandled exception on %s %s", request.method, request.url.path
    )
    return _error("internal_error", "Error interno del servidor.", 500)


def install(app: FastAPI) -> None:
    """Registra middleware y handlers en la aplicación FastAPI."""
    app.add_middleware(RequestLoggingMiddleware)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(
        RequestValidationError, validation_exception_handler
    )
    app.add_exception_handler(Exception, unhandled_exception_handler)
