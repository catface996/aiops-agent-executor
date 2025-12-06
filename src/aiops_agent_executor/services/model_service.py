"""Model service layer for CRUD and sync operations.

Handles all business logic for LLM model management.
"""

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aiops_agent_executor.adapters.registry import get_adapter_registry
from aiops_agent_executor.core.exceptions import BadRequestError, NotFoundError
from aiops_agent_executor.core.security import get_encryption_service
from aiops_agent_executor.db.models import Credential, Model, ModelStatus, ModelType, Provider
from aiops_agent_executor.schemas import ModelCreate, ModelUpdate


class ModelService:
    """Service class for model operations."""

    def __init__(self, db: AsyncSession) -> None:
        """Initialize the service with a database session."""
        self.db = db
        self._registry = get_adapter_registry()
        self._encryption = get_encryption_service()

    async def sync_models(self, provider_id: uuid.UUID) -> list[Model]:
        """Sync models from a provider.

        Fetches the model list from the provider API and updates the database.

        Args:
            provider_id: The provider's UUID

        Returns:
            List of synced models

        Raises:
            NotFoundError: If the provider doesn't exist
            BadRequestError: If the provider has no valid credentials or no adapter
        """
        # Get provider
        provider = await self.db.get(Provider, provider_id)
        if not provider:
            raise NotFoundError(resource="Provider", resource_id=str(provider_id))

        # Check if adapter exists for this provider type
        adapter = self._registry.get(provider.type)
        if not adapter:
            raise BadRequestError(
                message=f"No adapter available for provider type: {provider.type.value}",
                code="NO_ADAPTER",
            )

        # Get active credential
        credential = await self._get_active_credential(provider_id)
        if not credential:
            raise BadRequestError(
                message="Provider has no active credentials configured",
                code="NO_CREDENTIALS",
            )

        # Decrypt credentials
        api_key = self._encryption.decrypt(credential.api_key_encrypted)
        secret_key = None
        if credential.secret_key_encrypted:
            secret_key = self._encryption.decrypt(credential.secret_key_encrypted)

        # Get base URL from default endpoint
        base_url = await self._get_default_endpoint_url(provider_id)

        # Fetch models from provider
        model_infos = await adapter.list_models(api_key, secret_key, base_url)

        # Upsert models
        synced_models = []
        for info in model_infos:
            model = await self._upsert_model(provider_id, info)
            synced_models.append(model)

        await self.db.flush()

        # Refresh all models
        for model in synced_models:
            await self.db.refresh(model)

        return synced_models

    async def create_model(
        self,
        provider_id: uuid.UUID,
        model_in: ModelCreate,
    ) -> Model:
        """Create a new model manually.

        Args:
            provider_id: The provider's UUID
            model_in: Model creation data

        Returns:
            The created model

        Raises:
            NotFoundError: If the provider doesn't exist
            BadRequestError: If model_id already exists for this provider
        """
        # Verify provider exists
        provider = await self.db.get(Provider, provider_id)
        if not provider:
            raise NotFoundError(resource="Provider", resource_id=str(provider_id))

        # Check for duplicate model_id
        existing = await self._get_model_by_model_id(provider_id, model_in.model_id)
        if existing:
            raise BadRequestError(
                message=f"Model with ID '{model_in.model_id}' already exists for this provider",
                code="DUPLICATE_MODEL_ID",
            )

        model = Model(
            provider_id=provider_id,
            model_id=model_in.model_id,
            name=model_in.name,
            version=model_in.version,
            type=model_in.type,
            context_window=model_in.context_window,
            max_output_tokens=model_in.max_output_tokens,
            input_price=model_in.input_price,
            output_price=model_in.output_price,
            capabilities=model_in.capabilities,
            status=model_in.status,
        )
        self.db.add(model)
        await self.db.flush()
        await self.db.refresh(model)
        return model

    async def list_models(
        self,
        provider_id: uuid.UUID | None = None,
        model_type: ModelType | None = None,
        capability: str | None = None,
        status: ModelStatus | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> Sequence[Model]:
        """List models with optional filters.

        Args:
            provider_id: Filter by provider
            model_type: Filter by model type
            capability: Filter by capability
            status: Filter by status
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of models matching the filters
        """
        query = select(Model)

        if provider_id:
            query = query.where(Model.provider_id == provider_id)
        if model_type:
            query = query.where(Model.type == model_type)
        if status:
            query = query.where(Model.status == status)

        # Order by provider then name
        query = query.order_by(Model.provider_id, Model.name)
        query = query.offset(skip).limit(limit)

        result = await self.db.execute(query)
        models = list(result.scalars().all())

        # Filter by capability if specified
        if capability:
            models = [
                m
                for m in models
                if m.capabilities and m.capabilities.get(capability) is True
            ]

        return models

    async def get_model(self, model_id: uuid.UUID) -> Model:
        """Get a model by ID.

        Args:
            model_id: The model's UUID (database ID, not model_id string)

        Returns:
            The model

        Raises:
            NotFoundError: If the model doesn't exist
        """
        model = await self.db.get(Model, model_id)
        if not model:
            raise NotFoundError(resource="Model", resource_id=str(model_id))
        return model

    async def update_model(
        self,
        model_id: uuid.UUID,
        model_in: ModelUpdate,
    ) -> Model:
        """Update a model.

        Args:
            model_id: The model's UUID
            model_in: Updated model data

        Returns:
            The updated model

        Raises:
            NotFoundError: If the model doesn't exist
        """
        model = await self.get_model(model_id)

        update_data = model_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(model, field, value)

        await self.db.flush()
        await self.db.refresh(model)
        return model

    async def get_models_by_capability(self, capability: str) -> Sequence[Model]:
        """Get all models with a specific capability.

        Args:
            capability: The capability to filter by

        Returns:
            List of models with the specified capability
        """
        query = (
            select(Model)
            .where(Model.status == ModelStatus.AVAILABLE)
            .order_by(Model.provider_id, Model.name)
        )
        result = await self.db.execute(query)
        models = result.scalars().all()

        # Filter by capability
        return [
            m
            for m in models
            if m.capabilities and m.capabilities.get(capability) is True
        ]

    async def _get_active_credential(self, provider_id: uuid.UUID) -> Credential | None:
        """Get the first active credential for a provider."""
        query = (
            select(Credential)
            .where(Credential.provider_id == provider_id)
            .where(Credential.is_active == True)  # noqa: E712
            .limit(1)
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def _get_default_endpoint_url(self, provider_id: uuid.UUID) -> str | None:
        """Get the base URL from the default endpoint."""
        from aiops_agent_executor.db.models import Endpoint

        query = (
            select(Endpoint)
            .where(Endpoint.provider_id == provider_id)
            .where(Endpoint.is_active == True)  # noqa: E712
            .where(Endpoint.is_default == True)  # noqa: E712
            .limit(1)
        )
        result = await self.db.execute(query)
        endpoint = result.scalar_one_or_none()

        if endpoint:
            return endpoint.base_url
        return None

    async def _get_model_by_model_id(
        self, provider_id: uuid.UUID, model_id: str
    ) -> Model | None:
        """Get a model by its model_id string."""
        query = (
            select(Model)
            .where(Model.provider_id == provider_id)
            .where(Model.model_id == model_id)
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def _upsert_model(
        self, provider_id: uuid.UUID, info: "ModelInfo"  # noqa: F821
    ) -> Model:
        """Insert or update a model based on model_id."""
        existing = await self._get_model_by_model_id(provider_id, info.model_id)

        if existing:
            # Update existing model
            existing.name = info.name
            existing.type = info.type
            existing.context_window = info.context_window
            existing.max_output_tokens = info.max_output_tokens
            existing.input_price = info.input_price
            existing.output_price = info.output_price
            existing.capabilities = info.capabilities
            existing.version = info.version
            # Don't update status - let admin control that
            return existing
        else:
            # Create new model
            model = Model(
                provider_id=provider_id,
                model_id=info.model_id,
                name=info.name,
                version=info.version,
                type=info.type,
                context_window=info.context_window,
                max_output_tokens=info.max_output_tokens,
                input_price=info.input_price,
                output_price=info.output_price,
                capabilities=info.capabilities,
                status=info.status,
            )
            self.db.add(model)
            return model
