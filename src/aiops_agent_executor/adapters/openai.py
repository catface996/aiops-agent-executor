"""OpenAI provider adapter for model sync.

Handles fetching model information from OpenAI's API.
"""

from decimal import Decimal

import httpx

from aiops_agent_executor.adapters.base import BaseProviderAdapter, ModelInfo
from aiops_agent_executor.core.exceptions import ProviderAuthError, ProviderConnectionError
from aiops_agent_executor.db.models import ModelStatus, ModelType

# OpenAI model pricing (per 1M tokens, as of 2024)
OPENAI_PRICING = {
    "gpt-4o": {"input": Decimal("2.50"), "output": Decimal("10.00")},
    "gpt-4o-mini": {"input": Decimal("0.15"), "output": Decimal("0.60")},
    "gpt-4-turbo": {"input": Decimal("10.00"), "output": Decimal("30.00")},
    "gpt-4": {"input": Decimal("30.00"), "output": Decimal("60.00")},
    "gpt-3.5-turbo": {"input": Decimal("0.50"), "output": Decimal("1.50")},
    "text-embedding-3-small": {"input": Decimal("0.02"), "output": Decimal("0.00")},
    "text-embedding-3-large": {"input": Decimal("0.13"), "output": Decimal("0.00")},
    "text-embedding-ada-002": {"input": Decimal("0.10"), "output": Decimal("0.00")},
}

# Model capabilities
OPENAI_CAPABILITIES = {
    "gpt-4o": {
        "text_generation": True,
        "chat": True,
        "function_calling": True,
        "vision": True,
        "streaming": True,
        "json_mode": True,
    },
    "gpt-4o-mini": {
        "text_generation": True,
        "chat": True,
        "function_calling": True,
        "vision": True,
        "streaming": True,
        "json_mode": True,
    },
    "gpt-4-turbo": {
        "text_generation": True,
        "chat": True,
        "function_calling": True,
        "vision": True,
        "streaming": True,
        "json_mode": True,
    },
    "gpt-4": {
        "text_generation": True,
        "chat": True,
        "function_calling": True,
        "streaming": True,
    },
    "gpt-3.5-turbo": {
        "text_generation": True,
        "chat": True,
        "function_calling": True,
        "streaming": True,
        "json_mode": True,
    },
}

# Context windows
OPENAI_CONTEXT_WINDOWS = {
    "gpt-4o": 128000,
    "gpt-4o-mini": 128000,
    "gpt-4-turbo": 128000,
    "gpt-4": 8192,
    "gpt-3.5-turbo": 16385,
}

DEFAULT_BASE_URL = "https://api.openai.com/v1"


class OpenAIAdapter(BaseProviderAdapter):
    """Adapter for OpenAI API."""

    @property
    def provider_type(self) -> str:
        return "openai"

    async def list_models(
        self,
        api_key: str,
        secret_key: str | None = None,  # noqa: ARG002
        base_url: str | None = None,
    ) -> list[ModelInfo]:
        """Fetch available models from OpenAI.

        Args:
            api_key: OpenAI API key
            secret_key: Not used for OpenAI
            base_url: Custom base URL (for Azure OpenAI or proxies)

        Returns:
            List of ModelInfo objects
        """
        url = f"{base_url or DEFAULT_BASE_URL}/models"

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    url,
                    headers={"Authorization": f"Bearer {api_key}"},
                )

                if response.status_code == 401:
                    raise ProviderAuthError(
                        provider="OpenAI",
                        message="Invalid API key",
                    )

                if response.status_code != 200:
                    raise ProviderConnectionError(
                        provider="OpenAI",
                        message=f"API returned status {response.status_code}",
                    )

                data = response.json()
                return self._parse_models(data.get("data", []))

        except httpx.ConnectError as e:
            raise ProviderConnectionError(
                provider="OpenAI",
                message=f"Failed to connect: {e}",
            ) from e
        except httpx.TimeoutException as e:
            raise ProviderConnectionError(
                provider="OpenAI",
                message="Connection timed out",
            ) from e

    async def validate_credentials(
        self,
        api_key: str,
        secret_key: str | None = None,  # noqa: ARG002
        base_url: str | None = None,
    ) -> bool:
        """Validate OpenAI API key.

        Args:
            api_key: OpenAI API key to validate
            secret_key: Not used for OpenAI
            base_url: Custom base URL

        Returns:
            True if the API key is valid
        """
        url = f"{base_url or DEFAULT_BASE_URL}/models"

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    url,
                    headers={"Authorization": f"Bearer {api_key}"},
                )
                return response.status_code == 200
        except (httpx.ConnectError, httpx.TimeoutException):
            return False

    def _parse_models(self, models_data: list[dict]) -> list[ModelInfo]:
        """Parse OpenAI models response into ModelInfo objects.

        Args:
            models_data: List of model data from OpenAI API

        Returns:
            List of ModelInfo objects
        """
        models = []
        relevant_prefixes = ("gpt-", "text-embedding-", "dall-e", "whisper", "tts-")

        for model_data in models_data:
            model_id = model_data.get("id", "")

            # Filter to only relevant models
            if not any(model_id.startswith(prefix) for prefix in relevant_prefixes):
                continue

            # Determine model type
            model_type = self._determine_model_type(model_id)

            # Get pricing info
            pricing = self._get_pricing(model_id)

            # Get capabilities
            capabilities = self._get_capabilities(model_id)

            # Get context window
            context_window = self._get_context_window(model_id)

            models.append(
                ModelInfo(
                    model_id=model_id,
                    name=model_id,
                    type=model_type,
                    context_window=context_window,
                    max_output_tokens=4096 if model_type == ModelType.CHAT else None,
                    input_price=pricing.get("input"),
                    output_price=pricing.get("output"),
                    capabilities=capabilities,
                    status=ModelStatus.AVAILABLE,
                )
            )

        return models

    def _determine_model_type(self, model_id: str) -> ModelType:
        """Determine the model type from model ID."""
        if model_id.startswith("text-embedding-"):
            return ModelType.EMBEDDING
        if model_id.startswith("dall-e"):
            return ModelType.VISION
        if model_id.startswith(("gpt-4o", "gpt-4-vision")):
            return ModelType.VISION
        if model_id.startswith("gpt-"):
            return ModelType.CHAT
        return ModelType.COMPLETION

    def _get_pricing(self, model_id: str) -> dict:
        """Get pricing for a model."""
        # Try exact match first
        if model_id in OPENAI_PRICING:
            return OPENAI_PRICING[model_id]

        # Try prefix match
        for key, pricing in OPENAI_PRICING.items():
            if model_id.startswith(key):
                return pricing

        return {}

    def _get_capabilities(self, model_id: str) -> dict:
        """Get capabilities for a model."""
        # Try exact match first
        if model_id in OPENAI_CAPABILITIES:
            return OPENAI_CAPABILITIES[model_id]

        # Try prefix match
        for key, caps in OPENAI_CAPABILITIES.items():
            if model_id.startswith(key):
                return caps

        # Default capabilities for embedding models
        if model_id.startswith("text-embedding-"):
            return {"embedding": True}

        return {}

    def _get_context_window(self, model_id: str) -> int | None:
        """Get context window size for a model."""
        # Try exact match first
        if model_id in OPENAI_CONTEXT_WINDOWS:
            return OPENAI_CONTEXT_WINDOWS[model_id]

        # Try prefix match
        for key, window in OPENAI_CONTEXT_WINDOWS.items():
            if model_id.startswith(key):
                return window

        return None
