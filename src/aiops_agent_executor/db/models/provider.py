"""LLM Provider related database models."""

import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from aiops_agent_executor.db.base import Base, TimestampMixin, UUIDMixin


class ProviderType(str, enum.Enum):
    """Supported LLM provider types."""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    AWS_BEDROCK = "aws_bedrock"
    AZURE_OPENAI = "azure_openai"
    ALIYUN_DASHSCOPE = "aliyun_dashscope"
    BAIDU_QIANFAN = "baidu_qianfan"
    OLLAMA = "ollama"
    VLLM = "vllm"
    OPENROUTER = "openrouter"  # OpenRouter API aggregator


class ModelType(str, enum.Enum):
    """Model capability types."""

    CHAT = "chat"
    COMPLETION = "completion"
    EMBEDDING = "embedding"
    VISION = "vision"


class ModelStatus(str, enum.Enum):
    """Model availability status."""

    AVAILABLE = "available"
    MAINTENANCE = "maintenance"
    DEPRECATED = "deprecated"


class HealthStatus(str, enum.Enum):
    """Endpoint health status."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class ValidationStatus(str, enum.Enum):
    """Credential validation status."""

    VALID = "valid"
    INVALID = "invalid"
    EXPIRED = "expired"
    QUOTA_EXCEEDED = "quota_exceeded"


class Provider(Base, UUIDMixin, TimestampMixin):
    """LLM Provider entity."""

    __tablename__ = "providers"

    name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    type: Mapped[ProviderType] = mapped_column(Enum(ProviderType), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    endpoints: Mapped[list["Endpoint"]] = relationship(
        "Endpoint", back_populates="provider", cascade="all, delete-orphan"
    )
    credentials: Mapped[list["Credential"]] = relationship(
        "Credential", back_populates="provider", cascade="all, delete-orphan"
    )
    models: Mapped[list["Model"]] = relationship(
        "Model", back_populates="provider", cascade="all, delete-orphan"
    )
    agents: Mapped[list["Agent"]] = relationship(
        "Agent", back_populates="provider"
    )


class Endpoint(Base, UUIDMixin, TimestampMixin):
    """API Endpoint configuration for a provider."""

    __tablename__ = "endpoints"

    provider_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("providers.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    base_url: Mapped[str] = mapped_column(String(500), nullable=False)
    api_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    region: Mapped[str | None] = mapped_column(String(50), nullable=True)
    timeout_connect: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    timeout_read: Mapped[int] = mapped_column(Integer, default=120, nullable=False)
    retry_count: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    retry_interval: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    health_status: Mapped[HealthStatus] = mapped_column(
        Enum(HealthStatus), default=HealthStatus.HEALTHY, nullable=False
    )
    last_health_check: Mapped[datetime | None] = mapped_column(nullable=True)

    # Relationships
    provider: Mapped["Provider"] = relationship("Provider", back_populates="endpoints")


class Credential(Base, UUIDMixin, TimestampMixin):
    """API credentials for a provider."""

    __tablename__ = "credentials"

    provider_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("providers.id", ondelete="CASCADE"), nullable=False
    )
    alias: Mapped[str] = mapped_column(String(100), nullable=False)
    api_key_encrypted: Mapped[str] = mapped_column(String(1000), nullable=False)
    secret_key_encrypted: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    api_key_hint: Mapped[str] = mapped_column(String(20), nullable=False)
    has_secret_key: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(nullable=True)
    quota_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    quota_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_validated_at: Mapped[datetime | None] = mapped_column(nullable=True)
    validation_status: Mapped[ValidationStatus | None] = mapped_column(
        Enum(ValidationStatus), nullable=True
    )

    # Relationships
    provider: Mapped["Provider"] = relationship("Provider", back_populates="credentials")


class Model(Base, UUIDMixin, TimestampMixin):
    """LLM Model configuration."""

    __tablename__ = "models"

    provider_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("providers.id", ondelete="CASCADE"), nullable=False
    )
    model_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    type: Mapped[ModelType] = mapped_column(Enum(ModelType), nullable=False)
    context_window: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    input_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    output_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    capabilities: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[ModelStatus] = mapped_column(
        Enum(ModelStatus), default=ModelStatus.AVAILABLE, nullable=False
    )

    # Relationships
    provider: Mapped["Provider"] = relationship("Provider", back_populates="models")


# Import for type hints (avoid circular imports)
from aiops_agent_executor.db.models.agent import Agent  # noqa: E402, F401
