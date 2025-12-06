"""Pydantic schemas for LLM Provider management."""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from aiops_agent_executor.db.models import (
    HealthStatus,
    ModelStatus,
    ModelType,
    ProviderType,
    ValidationStatus,
)


# ============== Provider Schemas ==============
class ProviderBase(BaseModel):
    """Base schema for provider."""

    name: str = Field(..., max_length=100, description="Provider name")
    type: ProviderType = Field(..., description="Provider type")
    description: str | None = Field(None, description="Provider description")


class ProviderCreate(ProviderBase):
    """Schema for creating a provider."""

    pass


class ProviderUpdate(BaseModel):
    """Schema for updating a provider."""

    name: str | None = Field(None, max_length=100)
    description: str | None = None
    is_active: bool | None = None


class ProviderResponse(ProviderBase):
    """Schema for provider response."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime


# ============== Endpoint Schemas ==============
class EndpointBase(BaseModel):
    """Base schema for endpoint."""

    name: str = Field(..., max_length=100)
    base_url: str = Field(..., max_length=500)
    api_version: str | None = Field(None, max_length=50)
    region: str | None = Field(None, max_length=50)
    timeout_connect: int = Field(30, ge=1, le=300)
    timeout_read: int = Field(120, ge=1, le=600)
    retry_count: int = Field(3, ge=0, le=10)
    retry_interval: int = Field(1, ge=1, le=60)
    is_default: bool = False


class EndpointCreate(EndpointBase):
    """Schema for creating an endpoint."""

    pass


class EndpointUpdate(BaseModel):
    """Schema for updating an endpoint."""

    name: str | None = Field(None, max_length=100)
    base_url: str | None = Field(None, max_length=500)
    api_version: str | None = None
    region: str | None = None
    timeout_connect: int | None = Field(None, ge=1, le=300)
    timeout_read: int | None = Field(None, ge=1, le=600)
    retry_count: int | None = Field(None, ge=0, le=10)
    retry_interval: int | None = Field(None, ge=1, le=60)
    is_default: bool | None = None
    is_active: bool | None = None


class EndpointResponse(EndpointBase):
    """Schema for endpoint response."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    provider_id: uuid.UUID
    is_active: bool
    health_status: HealthStatus = HealthStatus.HEALTHY
    last_health_check: datetime | None = None
    created_at: datetime
    updated_at: datetime


class HealthCheckResult(BaseModel):
    """Schema for health check result."""

    status: HealthStatus
    latency_ms: int
    checked_at: datetime
    details: dict | None = None


# ============== Credential Schemas ==============
class CredentialBase(BaseModel):
    """Base schema for credential."""

    alias: str = Field(..., max_length=100)
    expires_at: datetime | None = None
    quota_limit: int | None = Field(None, ge=0)


class CredentialCreate(CredentialBase):
    """Schema for creating a credential."""

    api_key: str = Field(..., max_length=500)
    secret_key: str | None = Field(None, max_length=500)


class CredentialUpdate(BaseModel):
    """Schema for updating a credential."""

    alias: str | None = Field(None, max_length=100)
    api_key: str | None = Field(None, max_length=500)
    secret_key: str | None = Field(None, max_length=500)
    expires_at: datetime | None = None
    quota_limit: int | None = Field(None, ge=0)
    is_active: bool | None = None


class CredentialResponse(BaseModel):
    """Schema for credential response (with masked keys)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    provider_id: uuid.UUID
    alias: str
    api_key_hint: str = Field(..., description="Masked API key (****xxxx)")
    has_secret_key: bool
    expires_at: datetime | None = None
    quota_limit: int | None = None
    quota_used: int = 0
    is_active: bool
    last_validated_at: datetime | None = None
    validation_status: ValidationStatus | None = None
    created_at: datetime
    updated_at: datetime


class ValidationResult(BaseModel):
    """Schema for credential validation result."""

    valid: bool
    validated_at: datetime
    details: dict | None = None
    error: dict | None = None


# ============== Model Schemas ==============
class ModelBase(BaseModel):
    """Base schema for model."""

    model_id: str = Field(..., max_length=100)
    name: str = Field(..., max_length=100)
    version: str | None = Field(None, max_length=50)
    type: ModelType
    context_window: int | None = Field(None, ge=0)
    max_output_tokens: int | None = Field(None, ge=0)
    input_price: Decimal | None = Field(None, ge=0)
    output_price: Decimal | None = Field(None, ge=0)
    capabilities: dict | None = None
    status: ModelStatus = ModelStatus.AVAILABLE


class ModelCreate(ModelBase):
    """Schema for creating a model."""

    pass


class ModelUpdate(BaseModel):
    """Schema for updating a model."""

    name: str | None = Field(None, max_length=100)
    version: str | None = None
    context_window: int | None = Field(None, ge=0)
    max_output_tokens: int | None = Field(None, ge=0)
    input_price: Decimal | None = Field(None, ge=0)
    output_price: Decimal | None = Field(None, ge=0)
    capabilities: dict | None = None
    status: ModelStatus | None = None


class ModelResponse(ModelBase):
    """Schema for model response."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    provider_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
