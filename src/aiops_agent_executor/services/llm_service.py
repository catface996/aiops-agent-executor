"""LLM Service for creating LLM clients from database configuration.

This service bridges the database configuration (providers, credentials, endpoints)
with the LLM client factory.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aiops_agent_executor.core.exceptions import NotFoundError
from aiops_agent_executor.db.models import Credential, Endpoint, Provider
from aiops_agent_executor.services.credential_service import CredentialService
from aiops_agent_executor.services.llm_client import BaseLLMClient, LLMClientFactory


class LLMService:
    """Service to create LLM clients from database configuration."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self._credential_service = CredentialService(db)

    async def create_client_by_provider_name(self, provider_name: str) -> BaseLLMClient:
        """Create LLM client using provider name.

        Args:
            provider_name: Provider name (e.g., "OpenRouter")

        Returns:
            Configured LLM client
        """
        provider = await self._get_provider_by_name(provider_name)
        return await self._create_client_for_provider(provider)

    async def create_client_by_provider_id(self, provider_id: uuid.UUID) -> BaseLLMClient:
        """Create LLM client using provider ID.

        Args:
            provider_id: Provider UUID

        Returns:
            Configured LLM client
        """
        provider = await self.db.get(Provider, provider_id)
        if not provider:
            raise NotFoundError(resource="Provider", resource_id=str(provider_id))
        return await self._create_client_for_provider(provider)

    async def _get_provider_by_name(self, name: str) -> Provider:
        """Get provider by name."""
        query = select(Provider).where(Provider.name == name)
        result = await self.db.execute(query)
        provider = result.scalar_one_or_none()
        if not provider:
            raise NotFoundError(resource="Provider", resource_id=name)
        return provider

    async def _get_active_credential(self, provider_id: uuid.UUID) -> Credential:
        """Get active credential for provider."""
        query = (
            select(Credential)
            .where(Credential.provider_id == provider_id)
            .where(Credential.is_active == True)  # noqa: E712
            .order_by(Credential.created_at.desc())
            .limit(1)
        )
        result = await self.db.execute(query)
        credential = result.scalar_one_or_none()
        if not credential:
            raise NotFoundError(
                resource="Credential",
                resource_id=f"active credential for provider {provider_id}",
            )
        return credential

    async def _get_default_endpoint(self, provider_id: uuid.UUID) -> Endpoint | None:
        """Get default endpoint for provider."""
        query = (
            select(Endpoint)
            .where(Endpoint.provider_id == provider_id)
            .where(Endpoint.is_active == True)  # noqa: E712
            .where(Endpoint.is_default == True)  # noqa: E712
            .limit(1)
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def _create_client_for_provider(self, provider: Provider) -> BaseLLMClient:
        """Create LLM client for a provider."""
        # Get active credential
        credential = await self._get_active_credential(provider.id)

        # Get endpoint (for base_url)
        endpoint = await self._get_default_endpoint(provider.id)
        base_url = endpoint.base_url if endpoint else None

        # Decrypt API key
        api_key = self._credential_service.decrypt_api_key(credential)

        # Create client
        return LLMClientFactory.create(
            provider=provider.type.value.lower(),
            api_key=api_key,
            base_url=base_url,
        )
