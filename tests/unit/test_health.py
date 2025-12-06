"""Tests for health check endpoint."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient) -> None:
    """Test health check endpoint returns healthy status."""
    response = await client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data
    assert "environment" in data


@pytest.mark.asyncio
async def test_health_check_response_format(client: AsyncClient) -> None:
    """Test health check response has correct format."""
    response = await client.get("/health")

    assert response.status_code == 200
    data = response.json()

    # Verify all expected fields are present
    expected_fields = {"status", "version", "environment"}
    assert set(data.keys()) == expected_fields
