"""API v1 router aggregating all endpoints."""

from fastapi import APIRouter

from aiops_agent_executor.api.v1.endpoints import (
    credentials,
    endpoints,
    models,
    providers,
    teams,
)

api_router = APIRouter(prefix="/api/v1")

# Include all endpoint routers
api_router.include_router(providers.router)
api_router.include_router(endpoints.router)
api_router.include_router(credentials.router)
api_router.include_router(models.router)
api_router.include_router(teams.router)
