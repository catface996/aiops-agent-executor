"""Endpoint service layer for CRUD and health check operations.

Handles all business logic for API endpoint management.
"""

import time
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from aiops_agent_executor.core.exceptions import BadRequestError, NotFoundError
from aiops_agent_executor.db.models import Endpoint, HealthStatus, Provider
from aiops_agent_executor.schemas import EndpointCreate, EndpointUpdate, HealthCheckResult


class EndpointService:
    """Service class for endpoint operations."""

    def __init__(self, db: AsyncSession) -> None:
        """Initialize the service with a database session."""
        self.db = db

    async def create_endpoint(
        self,
        provider_id: uuid.UUID,
        endpoint_in: EndpointCreate,
    ) -> Endpoint:
        """Create a new endpoint for a provider.

        Args:
            provider_id: The provider's UUID
            endpoint_in: Endpoint creation data

        Returns:
            The created endpoint

        Raises:
            NotFoundError: If the provider doesn't exist
        """
        # Verify provider exists
        provider = await self.db.get(Provider, provider_id)
        if not provider:
            raise NotFoundError(resource="Provider", resource_id=str(provider_id))

        # If this is the first endpoint or is_default is True, handle default logic
        if endpoint_in.is_default:
            await self._clear_default_endpoint(provider_id)

        # If this is the first endpoint, make it default
        existing_count = await self._count_endpoints(provider_id)
        is_default = endpoint_in.is_default or existing_count == 0

        endpoint = Endpoint(
            provider_id=provider_id,
            name=endpoint_in.name,
            base_url=endpoint_in.base_url,
            api_version=endpoint_in.api_version,
            region=endpoint_in.region,
            timeout_connect=endpoint_in.timeout_connect,
            timeout_read=endpoint_in.timeout_read,
            retry_count=endpoint_in.retry_count,
            retry_interval=endpoint_in.retry_interval,
            is_default=is_default,
            is_active=True,
            health_status=HealthStatus.HEALTHY,
        )
        self.db.add(endpoint)
        await self.db.flush()
        await self.db.refresh(endpoint)
        return endpoint

    async def list_endpoints(self, provider_id: uuid.UUID) -> Sequence[Endpoint]:
        """List all endpoints for a provider.

        Args:
            provider_id: The provider's UUID

        Returns:
            List of endpoints

        Raises:
            NotFoundError: If the provider doesn't exist
        """
        # Verify provider exists
        provider = await self.db.get(Provider, provider_id)
        if not provider:
            raise NotFoundError(resource="Provider", resource_id=str(provider_id))

        query = (
            select(Endpoint)
            .where(Endpoint.provider_id == provider_id)
            .order_by(Endpoint.is_default.desc(), Endpoint.created_at.desc())
        )
        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_endpoint(self, endpoint_id: uuid.UUID) -> Endpoint:
        """Get an endpoint by ID.

        Args:
            endpoint_id: The endpoint's UUID

        Returns:
            The endpoint

        Raises:
            NotFoundError: If the endpoint doesn't exist
        """
        endpoint = await self.db.get(Endpoint, endpoint_id)
        if not endpoint:
            raise NotFoundError(resource="Endpoint", resource_id=str(endpoint_id))
        return endpoint

    async def update_endpoint(
        self,
        endpoint_id: uuid.UUID,
        endpoint_in: EndpointUpdate,
    ) -> Endpoint:
        """Update an existing endpoint.

        Args:
            endpoint_id: The endpoint's UUID
            endpoint_in: Updated endpoint data

        Returns:
            The updated endpoint

        Raises:
            NotFoundError: If the endpoint doesn't exist
        """
        endpoint = await self.get_endpoint(endpoint_id)

        # Handle default endpoint change
        if endpoint_in.is_default is True and not endpoint.is_default:
            await self._clear_default_endpoint(endpoint.provider_id)

        # Update fields
        update_data = endpoint_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(endpoint, field, value)

        await self.db.flush()
        await self.db.refresh(endpoint)
        return endpoint

    async def delete_endpoint(self, endpoint_id: uuid.UUID) -> None:
        """Delete an endpoint.

        Args:
            endpoint_id: The endpoint's UUID

        Raises:
            NotFoundError: If the endpoint doesn't exist
            BadRequestError: If this is the last endpoint for the provider
        """
        endpoint = await self.get_endpoint(endpoint_id)

        # Check if this is the last endpoint
        count = await self._count_endpoints(endpoint.provider_id)
        if count <= 1:
            raise BadRequestError(
                message="Cannot delete the last endpoint. Each provider must have at least one endpoint.",
                code="LAST_ENDPOINT",
            )

        # If deleting default endpoint, assign default to another
        if endpoint.is_default:
            await self._reassign_default_endpoint(endpoint.provider_id, endpoint.id)

        await self.db.delete(endpoint)
        await self.db.flush()

    async def health_check(self, endpoint_id: uuid.UUID) -> HealthCheckResult:
        """Perform a health check on an endpoint.

        Args:
            endpoint_id: The endpoint's UUID

        Returns:
            Health check result

        Raises:
            NotFoundError: If the endpoint doesn't exist
        """
        endpoint = await self.get_endpoint(endpoint_id)

        start_time = time.time()
        checked_at = datetime.now(UTC)
        details = {}

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    endpoint.base_url,
                    timeout=httpx.Timeout(
                        connect=endpoint.timeout_connect,
                        read=endpoint.timeout_read,
                    ),
                )
                latency_ms = int((time.time() - start_time) * 1000)

                # Determine health status based on response and latency
                if response.status_code < 400:
                    status = HealthStatus.HEALTHY if latency_ms < 1000 else HealthStatus.DEGRADED
                    details["http_status"] = response.status_code
                else:
                    status = HealthStatus.UNHEALTHY
                    details["http_status"] = response.status_code
                    details["error"] = f"HTTP {response.status_code}"

        except httpx.TimeoutException:
            latency_ms = int((time.time() - start_time) * 1000)
            status = HealthStatus.UNHEALTHY
            details["error"] = "Connection timeout"

        except httpx.ConnectError as e:
            latency_ms = int((time.time() - start_time) * 1000)
            status = HealthStatus.UNHEALTHY
            details["error"] = f"Connection error: {str(e)}"

        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            status = HealthStatus.UNHEALTHY
            details["error"] = str(e)

        # Update endpoint health status
        endpoint.health_status = status
        endpoint.last_health_check = checked_at
        await self.db.flush()

        return HealthCheckResult(
            status=status,
            latency_ms=latency_ms,
            checked_at=checked_at,
            details=details if details else None,
        )

    async def _count_endpoints(self, provider_id: uuid.UUID) -> int:
        """Count endpoints for a provider."""
        query = select(func.count()).select_from(Endpoint).where(Endpoint.provider_id == provider_id)
        result = await self.db.execute(query)
        return result.scalar() or 0

    async def _clear_default_endpoint(self, provider_id: uuid.UUID) -> None:
        """Clear the default flag on all endpoints for a provider."""
        query = (
            select(Endpoint)
            .where(Endpoint.provider_id == provider_id)
            .where(Endpoint.is_default == True)  # noqa: E712
        )
        result = await self.db.execute(query)
        for endpoint in result.scalars():
            endpoint.is_default = False

    async def _reassign_default_endpoint(
        self,
        provider_id: uuid.UUID,
        exclude_id: uuid.UUID,
    ) -> None:
        """Reassign default to another endpoint."""
        query = (
            select(Endpoint)
            .where(Endpoint.provider_id == provider_id)
            .where(Endpoint.id != exclude_id)
            .order_by(Endpoint.created_at)
            .limit(1)
        )
        result = await self.db.execute(query)
        other_endpoint = result.scalar_one_or_none()
        if other_endpoint:
            other_endpoint.is_default = True
