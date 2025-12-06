"""Pydantic schemas package."""

from aiops_agent_executor.schemas.common import (
    ErrorDetail,
    ErrorResponse,
    HealthResponse,
    PaginatedResponse,
    PaginationParams,
)
from aiops_agent_executor.schemas.provider import (
    CredentialCreate,
    CredentialResponse,
    CredentialUpdate,
    EndpointCreate,
    EndpointResponse,
    EndpointUpdate,
    HealthCheckResult,
    ModelCreate,
    ModelResponse,
    ModelUpdate,
    ProviderCreate,
    ProviderResponse,
    ProviderUpdate,
    ValidationResult,
)
from aiops_agent_executor.schemas.team import (
    ExecutionInput,
    ExecutionRequest,
    ExecutionResponse,
    StructuredOutputRequest,
    StructuredOutputResponse,
    TeamCreate,
    TeamCreatedResponse,
    TeamResponse,
)

__all__ = [
    # Common
    "PaginationParams",
    "PaginatedResponse",
    "HealthResponse",
    "ErrorDetail",
    "ErrorResponse",
    # Provider
    "ProviderCreate",
    "ProviderUpdate",
    "ProviderResponse",
    "EndpointCreate",
    "EndpointUpdate",
    "EndpointResponse",
    "HealthCheckResult",
    "CredentialCreate",
    "CredentialUpdate",
    "CredentialResponse",
    "ValidationResult",
    "ModelCreate",
    "ModelUpdate",
    "ModelResponse",
    # Team
    "TeamCreate",
    "TeamResponse",
    "TeamCreatedResponse",
    "ExecutionInput",
    "ExecutionRequest",
    "ExecutionResponse",
    "StructuredOutputRequest",
    "StructuredOutputResponse",
]
