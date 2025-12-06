"""Anthropic provider adapter for model sync.

Handles fetching model information from Anthropic's API.
Note: Anthropic doesn't have a models list endpoint, so we use static model data.
"""

from decimal import Decimal

import httpx

from aiops_agent_executor.adapters.base import BaseProviderAdapter, ModelInfo
from aiops_agent_executor.core.exceptions import ProviderAuthError, ProviderConnectionError
from aiops_agent_executor.db.models import ModelStatus, ModelType

# Anthropic models with their specifications
ANTHROPIC_MODELS = [
    {
        "model_id": "claude-opus-4-20250514",
        "name": "Claude Opus 4",
        "context_window": 200000,
        "max_output_tokens": 32000,
        "input_price": Decimal("15.00"),
        "output_price": Decimal("75.00"),
        "capabilities": {
            "text_generation": True,
            "chat": True,
            "function_calling": True,
            "vision": True,
            "streaming": True,
            "json_mode": True,
            "code_generation": True,
        },
    },
    {
        "model_id": "claude-sonnet-4-20250514",
        "name": "Claude Sonnet 4",
        "context_window": 200000,
        "max_output_tokens": 64000,
        "input_price": Decimal("3.00"),
        "output_price": Decimal("15.00"),
        "capabilities": {
            "text_generation": True,
            "chat": True,
            "function_calling": True,
            "vision": True,
            "streaming": True,
            "json_mode": True,
            "code_generation": True,
        },
    },
    {
        "model_id": "claude-3-5-sonnet-20241022",
        "name": "Claude 3.5 Sonnet",
        "context_window": 200000,
        "max_output_tokens": 8192,
        "input_price": Decimal("3.00"),
        "output_price": Decimal("15.00"),
        "capabilities": {
            "text_generation": True,
            "chat": True,
            "function_calling": True,
            "vision": True,
            "streaming": True,
            "json_mode": True,
            "code_generation": True,
        },
    },
    {
        "model_id": "claude-3-5-haiku-20241022",
        "name": "Claude 3.5 Haiku",
        "context_window": 200000,
        "max_output_tokens": 8192,
        "input_price": Decimal("0.80"),
        "output_price": Decimal("4.00"),
        "capabilities": {
            "text_generation": True,
            "chat": True,
            "function_calling": True,
            "streaming": True,
            "json_mode": True,
        },
    },
    {
        "model_id": "claude-3-opus-20240229",
        "name": "Claude 3 Opus",
        "context_window": 200000,
        "max_output_tokens": 4096,
        "input_price": Decimal("15.00"),
        "output_price": Decimal("75.00"),
        "capabilities": {
            "text_generation": True,
            "chat": True,
            "function_calling": True,
            "vision": True,
            "streaming": True,
        },
    },
    {
        "model_id": "claude-3-sonnet-20240229",
        "name": "Claude 3 Sonnet",
        "context_window": 200000,
        "max_output_tokens": 4096,
        "input_price": Decimal("3.00"),
        "output_price": Decimal("15.00"),
        "capabilities": {
            "text_generation": True,
            "chat": True,
            "function_calling": True,
            "vision": True,
            "streaming": True,
        },
    },
    {
        "model_id": "claude-3-haiku-20240307",
        "name": "Claude 3 Haiku",
        "context_window": 200000,
        "max_output_tokens": 4096,
        "input_price": Decimal("0.25"),
        "output_price": Decimal("1.25"),
        "capabilities": {
            "text_generation": True,
            "chat": True,
            "function_calling": True,
            "vision": True,
            "streaming": True,
        },
    },
]

DEFAULT_BASE_URL = "https://api.anthropic.com"


class AnthropicAdapter(BaseProviderAdapter):
    """Adapter for Anthropic API."""

    @property
    def provider_type(self) -> str:
        return "anthropic"

    async def list_models(
        self,
        api_key: str,
        secret_key: str | None = None,  # noqa: ARG002
        base_url: str | None = None,
    ) -> list[ModelInfo]:
        """Return available Anthropic models.

        Note: Anthropic doesn't have a models list endpoint, so we return
        static model data after validating the API key.

        Args:
            api_key: Anthropic API key
            secret_key: Not used for Anthropic
            base_url: Custom base URL

        Returns:
            List of ModelInfo objects
        """
        # Validate credentials first
        is_valid = await self.validate_credentials(api_key, base_url=base_url)
        if not is_valid:
            raise ProviderAuthError(
                provider="Anthropic",
                message="Invalid API key",
            )

        # Return static model list
        return [
            ModelInfo(
                model_id=m["model_id"],
                name=m["name"],
                type=ModelType.CHAT,
                context_window=m["context_window"],
                max_output_tokens=m["max_output_tokens"],
                input_price=m["input_price"],
                output_price=m["output_price"],
                capabilities=m["capabilities"],
                status=ModelStatus.AVAILABLE,
            )
            for m in ANTHROPIC_MODELS
        ]

    async def validate_credentials(
        self,
        api_key: str,
        secret_key: str | None = None,  # noqa: ARG002
        base_url: str | None = None,
    ) -> bool:
        """Validate Anthropic API key.

        Makes a minimal API call to check if the key is valid.

        Args:
            api_key: Anthropic API key to validate
            secret_key: Not used for Anthropic
            base_url: Custom base URL

        Returns:
            True if the API key is valid
        """
        url = f"{base_url or DEFAULT_BASE_URL}/v1/messages"

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Make a minimal request to validate the key
                response = await client.post(
                    url,
                    headers={
                        "x-api-key": api_key,
                        "anthropic-version": "2023-06-01",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": "claude-3-haiku-20240307",
                        "max_tokens": 1,
                        "messages": [{"role": "user", "content": "hi"}],
                    },
                )

                # 200 means success, 401 means bad key
                # Other errors (400, 429, etc.) still indicate a valid key
                return response.status_code != 401

        except httpx.ConnectError:
            raise ProviderConnectionError(
                provider="Anthropic",
                message="Failed to connect to Anthropic API",
            )
        except httpx.TimeoutException:
            raise ProviderConnectionError(
                provider="Anthropic",
                message="Connection timed out",
            )
