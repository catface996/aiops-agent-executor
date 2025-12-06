"""Provider service layer for CRUD operations.

Handles all business logic for LLM provider management.
"""

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aiops_agent_executor.core.exceptions import ConflictError, NotFoundError
from aiops_agent_executor.db.models import Provider
from aiops_agent_executor.schemas import ProviderCreate, ProviderUpdate


class ProviderService:
    """Service class for provider operations."""

    def __init__(self, db: AsyncSession) -> None:
        """Initialize the service with a database session."""
        self.db = db

    async def create_provider(self, provider_in: ProviderCreate) -> Provider:
        """Create a new provider.

        Args:
            provider_in: Provider creation data

        Returns:
            The created provider

        Raises:
            ConflictError: If a provider with the same name already exists
        """
        # Check for duplicate name
        existing = await self._get_provider_by_name(provider_in.name)
        if existing:
            raise ConflictError(
                resource="Provider",
                reason=f"Provider with name '{provider_in.name}' already exists",
            )

        provider = Provider(
            name=provider_in.name,
            type=provider_in.type,
            description=provider_in.description,
            is_active=True,
        )
        self.db.add(provider)
        await self.db.flush()
        await self.db.refresh(provider)
        return provider

    async def get_provider(self, provider_id: uuid.UUID) -> Provider:
        """Get a provider by ID.

        Args:
            provider_id: The provider's UUID

        Returns:
            The provider

        Raises:
            NotFoundError: If the provider doesn't exist
        """
        provider = await self.db.get(Provider, provider_id)
        if not provider:
            raise NotFoundError(resource="Provider", resource_id=str(provider_id))
        return provider

    async def list_providers(
        self,
        skip: int = 0,
        limit: int = 20,
        is_active: bool | None = None,
    ) -> Sequence[Provider]:
        """List providers with optional filtering.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return
            is_active: Filter by active status (None = no filter)

        Returns:
            List of providers
        """
        query = select(Provider).order_by(Provider.created_at.desc())

        if is_active is not None:
            query = query.where(Provider.is_active == is_active)

        query = query.offset(skip).limit(limit)
        result = await self.db.execute(query)
        return result.scalars().all()

    async def update_provider(
        self,
        provider_id: uuid.UUID,
        provider_in: ProviderUpdate,
    ) -> Provider:
        """Update an existing provider.

        Args:
            provider_id: The provider's UUID
            provider_in: Updated provider data

        Returns:
            The updated provider

        Raises:
            NotFoundError: If the provider doesn't exist
            ConflictError: If the new name conflicts with an existing provider
        """
        provider = await self.get_provider(provider_id)

        # Check for name conflict if name is being updated
        if provider_in.name is not None and provider_in.name != provider.name:
            existing = await self._get_provider_by_name(provider_in.name)
            if existing:
                raise ConflictError(
                    resource="Provider",
                    reason=f"Provider with name '{provider_in.name}' already exists",
                )

        # Update fields
        update_data = provider_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(provider, field, value)

        await self.db.flush()
        await self.db.refresh(provider)
        return provider

    async def delete_provider(self, provider_id: uuid.UUID) -> None:
        """Delete a provider.

        Args:
            provider_id: The provider's UUID

        Raises:
            NotFoundError: If the provider doesn't exist
            ConflictError: If the provider is in use by teams
        """
        provider = await self.get_provider(provider_id)

        # Check if provider is in use by any teams
        is_in_use = await self._check_provider_in_use(provider_id)
        if is_in_use:
            raise ConflictError(
                resource="Provider",
                reason="Provider is in use by one or more agent teams and cannot be deleted",
            )

        await self.db.delete(provider)
        await self.db.flush()

    async def update_provider_status(
        self,
        provider_id: uuid.UUID,
        is_active: bool,
    ) -> Provider:
        """Update a provider's active status.

        Args:
            provider_id: The provider's UUID
            is_active: The new active status

        Returns:
            The updated provider

        Raises:
            NotFoundError: If the provider doesn't exist
        """
        provider = await self.get_provider(provider_id)
        provider.is_active = is_active
        await self.db.flush()
        await self.db.refresh(provider)
        return provider

    async def _get_provider_by_name(self, name: str) -> Provider | None:
        """Get a provider by name.

        Args:
            name: The provider name

        Returns:
            The provider if found, None otherwise
        """
        query = select(Provider).where(Provider.name == name)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def _check_provider_in_use(self, provider_id: uuid.UUID) -> bool:  # noqa: ARG002
        """Check if a provider is in use by any teams.

        Args:
            provider_id: The provider's UUID

        Returns:
            True if the provider is in use, False otherwise

        Note:
            Current Team model doesn't have provider_id. This check is a placeholder
            for future implementation when Team-Provider relationship is established.
        """
        # TODO: Implement when Team model has provider_id field
        # For now, providers can always be deleted
        return False
