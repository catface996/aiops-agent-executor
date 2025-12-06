"""Common Pydantic schemas used across the application."""

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PaginationParams(BaseModel):
    """Pagination parameters."""

    page: int = Field(1, ge=1, description="Page number")
    size: int = Field(20, ge=1, le=100, description="Items per page")


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response."""

    items: list[T]
    total: int
    page: int
    size: int
    pages: int


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = "healthy"
    version: str
    environment: str


class ErrorDetail(BaseModel):
    """Error detail schema."""

    loc: list[str] | None = None
    msg: str
    type: str


class ErrorResponse(BaseModel):
    """Standard error response."""

    error_code: str
    error_message: str
    details: dict | list[ErrorDetail] | None = None
