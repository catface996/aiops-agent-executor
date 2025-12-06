"""Global exception handlers for FastAPI application.

Provides consistent error response format for all exceptions.
"""

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from aiops_agent_executor.core.exceptions import AppException

logger = logging.getLogger(__name__)


def create_error_response(
    status_code: int,
    detail: str,
    code: str,
    details: dict[str, Any] | None = None,
) -> JSONResponse:
    """Create a standardized error response."""
    content: dict[str, Any] = {
        "detail": detail,
        "code": code,
    }
    if details:
        content["details"] = details
    return JSONResponse(status_code=status_code, content=content)


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    """Handle custom application exceptions."""
    logger.warning(
        "Application error: %s (code=%s, status=%d)",
        exc.message,
        exc.code,
        exc.status_code,
        extra={"path": request.url.path, "method": request.method},
    )
    return create_error_response(
        status_code=exc.status_code,
        detail=exc.message,
        code=exc.code,
        details=exc.details if exc.details else None,
    )


async def http_exception_handler(
    request: Request, exc: StarletteHTTPException  # noqa: ARG001
) -> JSONResponse:
    """Handle standard HTTP exceptions."""
    return create_error_response(
        status_code=exc.status_code,
        detail=str(exc.detail),
        code="HTTP_ERROR",
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError  # noqa: ARG001
) -> JSONResponse:
    """Handle Pydantic validation errors."""
    errors = exc.errors()
    error_messages = []
    for error in errors:
        loc = ".".join(str(part) for part in error["loc"])
        error_messages.append(f"{loc}: {error['msg']}")

    detail = "; ".join(error_messages) if error_messages else "Validation error"

    return create_error_response(
        status_code=422,
        detail=detail,
        code="VALIDATION_ERROR",
        details={"errors": errors},
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected exceptions."""
    logger.exception(
        "Unexpected error: %s",
        str(exc),
        extra={"path": request.url.path, "method": request.method},
    )
    return create_error_response(
        status_code=500,
        detail="An unexpected error occurred",
        code="INTERNAL_ERROR",
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Register all exception handlers with the FastAPI application."""
    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, generic_exception_handler)
