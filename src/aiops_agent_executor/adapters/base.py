"""Base adapter class for LLM provider integrations.

Defines the interface that all provider adapters must implement.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal

from aiops_agent_executor.db.models import ModelStatus, ModelType


@dataclass
class ModelInfo:
    """Data class representing model information from a provider."""

    model_id: str
    name: str
    type: ModelType
    context_window: int | None = None
    max_output_tokens: int | None = None
    input_price: Decimal | None = None
    output_price: Decimal | None = None
    capabilities: dict = field(default_factory=dict)
    status: ModelStatus = ModelStatus.AVAILABLE
    version: str | None = None


class BaseProviderAdapter(ABC):
    """Abstract base class for provider adapters.

    Each provider adapter is responsible for:
    1. Fetching available models from the provider API
    2. Normalizing model information to a standard format
    3. Validating credentials

    Adapters should handle provider-specific API quirks and
    translate them into our standard ModelInfo format.
    """

    @property
    @abstractmethod
    def provider_type(self) -> str:
        """Return the provider type identifier.

        Returns:
            Provider type string (e.g., "openai", "anthropic")
        """
        ...

    @abstractmethod
    async def list_models(
        self,
        api_key: str,
        secret_key: str | None = None,
        base_url: str | None = None,
    ) -> list[ModelInfo]:
        """Fetch available models from the provider.

        Args:
            api_key: The API key for authentication
            secret_key: Optional secret key (for AWS, Baidu, etc.)
            base_url: Optional custom base URL

        Returns:
            List of ModelInfo objects

        Raises:
            ProviderConnectionError: If connection to provider fails
            ProviderAuthError: If authentication fails
        """
        ...

    @abstractmethod
    async def validate_credentials(
        self,
        api_key: str,
        secret_key: str | None = None,
        base_url: str | None = None,
    ) -> bool:
        """Validate that the provided credentials are valid.

        Args:
            api_key: The API key to validate
            secret_key: Optional secret key
            base_url: Optional custom base URL

        Returns:
            True if credentials are valid, False otherwise
        """
        ...

    def _normalize_capabilities(self, raw_capabilities: dict | None) -> dict:
        """Normalize provider-specific capabilities to standard format.

        Args:
            raw_capabilities: Provider-specific capability data

        Returns:
            Normalized capabilities dict
        """
        if not raw_capabilities:
            return {}

        # Standard capability keys
        standard_keys = {
            "text_generation",
            "chat",
            "code_generation",
            "function_calling",
            "vision",
            "embedding",
            "json_mode",
            "streaming",
        }

        normalized = {}
        for key in standard_keys:
            if key in raw_capabilities:
                normalized[key] = bool(raw_capabilities[key])

        return normalized
