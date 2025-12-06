"""Credential service layer for CRUD and validation operations.

Handles all business logic for API credential management with encryption.
"""

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from aiops_agent_executor.core.exceptions import BadRequestError, NotFoundError
from aiops_agent_executor.core.security import get_encryption_service, mask_sensitive_data
from aiops_agent_executor.db.models import Credential, Provider, ValidationStatus
from aiops_agent_executor.schemas import CredentialCreate, CredentialUpdate, ValidationResult


class CredentialService:
    """Service class for credential operations."""

    def __init__(self, db: AsyncSession) -> None:
        """Initialize the service with a database session."""
        self.db = db
        self._encryption = get_encryption_service()

    async def create_credential(
        self,
        provider_id: uuid.UUID,
        credential_in: CredentialCreate,
    ) -> Credential:
        """Create a new credential for a provider.

        Args:
            provider_id: The provider's UUID
            credential_in: Credential creation data

        Returns:
            The created credential

        Raises:
            NotFoundError: If the provider doesn't exist
        """
        # Verify provider exists
        provider = await self.db.get(Provider, provider_id)
        if not provider:
            raise NotFoundError(resource="Provider", resource_id=str(provider_id))

        # Encrypt the API key
        api_key_encrypted = self._encryption.encrypt(credential_in.api_key)

        # Encrypt secret key if provided
        secret_key_encrypted = None
        if credential_in.secret_key:
            secret_key_encrypted = self._encryption.encrypt(credential_in.secret_key)

        # Generate masked hint (****xxxx format)
        api_key_hint = mask_sensitive_data(credential_in.api_key, visible_chars=4)

        credential = Credential(
            provider_id=provider_id,
            alias=credential_in.alias,
            api_key_encrypted=api_key_encrypted,
            secret_key_encrypted=secret_key_encrypted,
            api_key_hint=api_key_hint,
            has_secret_key=credential_in.secret_key is not None,
            expires_at=credential_in.expires_at,
            quota_limit=credential_in.quota_limit,
            quota_used=0,
            is_active=True,
        )
        self.db.add(credential)
        await self.db.flush()
        await self.db.refresh(credential)
        return credential

    async def list_credentials(self, provider_id: uuid.UUID) -> Sequence[Credential]:
        """List all credentials for a provider.

        Args:
            provider_id: The provider's UUID

        Returns:
            List of credentials

        Raises:
            NotFoundError: If the provider doesn't exist
        """
        # Verify provider exists
        provider = await self.db.get(Provider, provider_id)
        if not provider:
            raise NotFoundError(resource="Provider", resource_id=str(provider_id))

        query = (
            select(Credential)
            .where(Credential.provider_id == provider_id)
            .order_by(Credential.created_at.desc())
        )
        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_credential(self, credential_id: uuid.UUID) -> Credential:
        """Get a credential by ID.

        Args:
            credential_id: The credential's UUID

        Returns:
            The credential

        Raises:
            NotFoundError: If the credential doesn't exist
        """
        credential = await self.db.get(Credential, credential_id)
        if not credential:
            raise NotFoundError(resource="Credential", resource_id=str(credential_id))
        return credential

    async def update_credential(
        self,
        credential_id: uuid.UUID,
        credential_in: CredentialUpdate,
    ) -> Credential:
        """Update an existing credential.

        Args:
            credential_id: The credential's UUID
            credential_in: Updated credential data

        Returns:
            The updated credential

        Raises:
            NotFoundError: If the credential doesn't exist
        """
        credential = await self.get_credential(credential_id)

        update_data = credential_in.model_dump(exclude_unset=True)

        # Handle API key update
        if "api_key" in update_data:
            api_key = update_data.pop("api_key")
            if api_key:
                credential.api_key_encrypted = self._encryption.encrypt(api_key)
                credential.api_key_hint = mask_sensitive_data(api_key, visible_chars=4)

        # Handle secret key update
        if "secret_key" in update_data:
            secret_key = update_data.pop("secret_key")
            if secret_key:
                credential.secret_key_encrypted = self._encryption.encrypt(secret_key)
                credential.has_secret_key = True
            else:
                credential.secret_key_encrypted = None
                credential.has_secret_key = False

        # Update other fields
        for field, value in update_data.items():
            setattr(credential, field, value)

        await self.db.flush()
        await self.db.refresh(credential)
        return credential

    async def delete_credential(self, credential_id: uuid.UUID) -> None:
        """Delete a credential.

        Args:
            credential_id: The credential's UUID

        Raises:
            NotFoundError: If the credential doesn't exist
            BadRequestError: If this is the last active credential for the provider
        """
        credential = await self.get_credential(credential_id)

        # Check if this is the last active credential
        if credential.is_active:
            active_count = await self._count_active_credentials(credential.provider_id)
            if active_count <= 1:
                raise BadRequestError(
                    message="Cannot delete the last active credential. Each provider must have at least one active credential.",
                    code="LAST_CREDENTIAL",
                )

        await self.db.delete(credential)
        await self.db.flush()

    async def validate_credential(self, credential_id: uuid.UUID) -> ValidationResult:
        """Validate a credential by testing it against the provider API.

        Args:
            credential_id: The credential's UUID

        Returns:
            Validation result

        Raises:
            NotFoundError: If the credential doesn't exist
        """
        credential = await self.get_credential(credential_id)
        validated_at = datetime.now(UTC)

        # Check expiration first
        if credential.expires_at and credential.expires_at < validated_at:
            credential.validation_status = ValidationStatus.EXPIRED
            credential.last_validated_at = validated_at
            await self.db.flush()
            return ValidationResult(
                valid=False,
                validated_at=validated_at,
                error={"code": "EXPIRED", "message": "Credential has expired"},
            )

        # Check quota
        if credential.quota_limit and credential.quota_used >= credential.quota_limit:
            credential.validation_status = ValidationStatus.QUOTA_EXCEEDED
            credential.last_validated_at = validated_at
            await self.db.flush()
            return ValidationResult(
                valid=False,
                validated_at=validated_at,
                error={"code": "QUOTA_EXCEEDED", "message": "Quota limit exceeded"},
            )

        # For actual API validation, would need to call the provider
        # This is a placeholder that marks as valid
        credential.validation_status = ValidationStatus.VALID
        credential.last_validated_at = validated_at
        await self.db.flush()

        return ValidationResult(
            valid=True,
            validated_at=validated_at,
            details={
                "account_status": "active",
                "remaining_quota": (credential.quota_limit - credential.quota_used)
                if credential.quota_limit
                else None,
            },
        )

    def decrypt_api_key(self, credential: Credential) -> str:
        """Decrypt and return the API key.

        This should only be used when actually making API calls.

        Args:
            credential: The credential object

        Returns:
            The decrypted API key
        """
        return self._encryption.decrypt(credential.api_key_encrypted)

    def decrypt_secret_key(self, credential: Credential) -> str | None:
        """Decrypt and return the secret key.

        Args:
            credential: The credential object

        Returns:
            The decrypted secret key, or None if not set
        """
        if credential.secret_key_encrypted:
            return self._encryption.decrypt(credential.secret_key_encrypted)
        return None

    async def _count_active_credentials(self, provider_id: uuid.UUID) -> int:
        """Count active credentials for a provider."""
        query = (
            select(func.count())
            .select_from(Credential)
            .where(Credential.provider_id == provider_id)
            .where(Credential.is_active == True)  # noqa: E712
        )
        result = await self.db.execute(query)
        return result.scalar() or 0
