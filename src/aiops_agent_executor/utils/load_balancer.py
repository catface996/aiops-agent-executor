"""Round-robin load balancer for endpoint selection.

Provides fair distribution of requests across healthy endpoints.
"""

import asyncio
from typing import Generic, TypeVar

T = TypeVar("T")


class RoundRobinLoadBalancer(Generic[T]):
    """Thread-safe round-robin load balancer.

    Selects items from a list in a circular fashion, ensuring even
    distribution of selections across all available items.

    Example:
        >>> lb = RoundRobinLoadBalancer[Endpoint]()
        >>> endpoint = await lb.get_next(healthy_endpoints)
    """

    def __init__(self) -> None:
        """Initialize the load balancer."""
        self._index = 0
        self._lock = asyncio.Lock()

    async def get_next(self, items: list[T]) -> T | None:
        """Get the next item in round-robin order.

        Args:
            items: List of items to select from. Should contain only
                   healthy/available items.

        Returns:
            The next item, or None if the list is empty.
        """
        if not items:
            return None

        async with self._lock:
            # Ensure index wraps around
            index = self._index % len(items)
            self._index = (self._index + 1) % len(items)
            return items[index]

    async def reset(self) -> None:
        """Reset the index to start from the beginning."""
        async with self._lock:
            self._index = 0


class EndpointLoadBalancer(RoundRobinLoadBalancer):
    """Load balancer specifically for endpoint selection.

    Filters endpoints by health status before selection.
    """

    async def get_healthy_endpoint(self, endpoints: list) -> object | None:
        """Get the next healthy endpoint.

        Args:
            endpoints: List of Endpoint objects with is_active and
                      health_status attributes.

        Returns:
            The next healthy endpoint, or None if no healthy endpoints.
        """
        # Filter to only healthy and active endpoints
        healthy = [
            e for e in endpoints
            if getattr(e, "is_active", True) and
            getattr(e, "health_status", "healthy") in ("healthy", "degraded")
        ]
        return await self.get_next(healthy)


# Singleton instance for application-wide use
_endpoint_load_balancer: EndpointLoadBalancer | None = None


def get_endpoint_load_balancer() -> EndpointLoadBalancer:
    """Get the singleton endpoint load balancer instance."""
    global _endpoint_load_balancer
    if _endpoint_load_balancer is None:
        _endpoint_load_balancer = EndpointLoadBalancer()
    return _endpoint_load_balancer
