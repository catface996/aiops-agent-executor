"""Adapter registry for managing provider adapters.

Provides a centralized way to get the appropriate adapter for each provider type.
"""

from aiops_agent_executor.adapters.base import BaseProviderAdapter
from aiops_agent_executor.db.models import ProviderType


class AdapterRegistry:
    """Registry for provider adapters.

    Maintains a mapping of provider types to their adapters.
    """

    def __init__(self) -> None:
        """Initialize the registry with default adapters."""
        self._adapters: dict[ProviderType, BaseProviderAdapter] = {}
        self._register_default_adapters()

    def _register_default_adapters(self) -> None:
        """Register the default set of adapters."""
        from aiops_agent_executor.adapters.anthropic import AnthropicAdapter
        from aiops_agent_executor.adapters.openai import OpenAIAdapter

        self._adapters[ProviderType.OPENAI] = OpenAIAdapter()
        self._adapters[ProviderType.ANTHROPIC] = AnthropicAdapter()
        # Azure OpenAI uses the OpenAI adapter with different base URL
        self._adapters[ProviderType.AZURE_OPENAI] = OpenAIAdapter()

    def register(self, provider_type: ProviderType, adapter: BaseProviderAdapter) -> None:
        """Register an adapter for a provider type.

        Args:
            provider_type: The provider type to register
            adapter: The adapter instance to use
        """
        self._adapters[provider_type] = adapter

    def get(self, provider_type: ProviderType) -> BaseProviderAdapter | None:
        """Get the adapter for a provider type.

        Args:
            provider_type: The provider type to get the adapter for

        Returns:
            The adapter instance, or None if not registered
        """
        return self._adapters.get(provider_type)

    def has_adapter(self, provider_type: ProviderType) -> bool:
        """Check if an adapter is registered for a provider type.

        Args:
            provider_type: The provider type to check

        Returns:
            True if an adapter is registered
        """
        return provider_type in self._adapters

    @property
    def supported_providers(self) -> list[ProviderType]:
        """Get list of provider types with registered adapters.

        Returns:
            List of supported provider types
        """
        return list(self._adapters.keys())


# Global registry instance
_registry: AdapterRegistry | None = None


def get_adapter_registry() -> AdapterRegistry:
    """Get the global adapter registry instance.

    Returns:
        The global AdapterRegistry instance
    """
    global _registry
    if _registry is None:
        _registry = AdapterRegistry()
    return _registry
