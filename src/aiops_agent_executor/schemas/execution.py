"""Execution-related schemas."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, model_validator

from aiops_agent_executor.db.models.team import ExecutionStatus
from aiops_agent_executor.utils.masking import mask_sensitive_data


class ExecutionCreate(BaseModel):
    """Schema for creating a new execution."""

    input_data: dict[str, Any] = Field(..., description="Input data for the execution")
    output_schema: dict[str, Any] | None = Field(
        None,
        description="Optional JSON Schema for structured output validation",
    )

    model_config = {"extra": "forbid"}


class ExecutionResponse(BaseModel):
    """Basic execution response schema."""

    id: uuid.UUID
    team_id: uuid.UUID
    status: ExecutionStatus
    started_at: datetime | None
    completed_at: datetime | None
    duration_ms: int | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class NodeResultResponse(BaseModel):
    """Response for a single node's execution result."""

    node_id: str
    status: str
    output: Any | None = None
    error: str | None = None
    duration_ms: int | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


class ExecutionDetailResponse(BaseModel):
    """Detailed execution response with masked sensitive data."""

    id: uuid.UUID
    team_id: uuid.UUID
    input_data: dict[str, Any]
    output_data: dict[str, Any] | None
    topology_snapshot: dict[str, Any]
    output_schema: dict[str, Any] | None
    node_results: dict[str, Any] | None
    status: ExecutionStatus
    started_at: datetime | None
    completed_at: datetime | None
    duration_ms: int | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @model_validator(mode="after")
    def mask_sensitive_fields(self) -> "ExecutionDetailResponse":
        """Mask sensitive data in response fields."""
        # Mask input_data
        if self.input_data:
            object.__setattr__(self, "input_data", mask_sensitive_data(self.input_data))

        # Mask output_data
        if self.output_data:
            object.__setattr__(self, "output_data", mask_sensitive_data(self.output_data))

        # Mask node_results
        if self.node_results:
            object.__setattr__(self, "node_results", mask_sensitive_data(self.node_results))

        return self


class ExecutionLogResponse(BaseModel):
    """Response schema for execution logs."""

    id: uuid.UUID
    execution_id: uuid.UUID
    event_type: str
    node_id: str | None
    agent_id: str | None
    supervisor_id: str | None
    message: str | None
    extra_data: dict[str, Any] | None
    timestamp: datetime

    model_config = {"from_attributes": True}

    @model_validator(mode="after")
    def mask_sensitive_fields(self) -> "ExecutionLogResponse":
        """Mask sensitive data in extra_data."""
        if self.extra_data:
            object.__setattr__(self, "extra_data", mask_sensitive_data(self.extra_data))
        return self


class ExecutionListResponse(BaseModel):
    """Paginated list of executions."""

    items: list[ExecutionResponse]
    total: int
    skip: int
    limit: int


class ExecutionLogsListResponse(BaseModel):
    """Paginated list of execution logs."""

    items: list[ExecutionLogResponse]
    total: int
    skip: int
    limit: int


class ExecutionCancelResponse(BaseModel):
    """Response for execution cancellation."""

    id: uuid.UUID
    status: ExecutionStatus
    message: str
