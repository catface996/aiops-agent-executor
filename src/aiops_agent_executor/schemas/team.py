"""Pydantic schemas for Agent Team management."""

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from aiops_agent_executor.db.models import ExecutionStatus, TeamStatus


# ============== Agent Configuration ==============
class AgentConfig(BaseModel):
    """Configuration for a single agent."""

    agent_id: str = Field(..., max_length=100)
    agent_name: str = Field(..., max_length=200)
    model_provider: str = Field(..., description="Reference to provider name")
    model_id: str = Field(..., description="Reference to model ID")
    system_prompt: str
    user_prompt_template: str | None = None
    tools: list[str] = Field(default_factory=list)
    temperature: float = Field(0.7, ge=0, le=2)
    max_tokens: int = Field(4096, ge=1, le=100000)


class SupervisorConfig(BaseModel):
    """Configuration for a node supervisor."""

    model_provider: str
    model_id: str
    system_prompt: str
    coordination_strategy: Literal["round_robin", "priority", "adaptive"] = "round_robin"


class GlobalSupervisorConfig(BaseModel):
    """Configuration for the global supervisor."""

    model_provider: str
    model_id: str
    system_prompt: str
    coordination_strategy: Literal["hierarchical", "parallel", "sequential"] = "hierarchical"


# ============== Topology Configuration ==============
class NodeConfig(BaseModel):
    """Configuration for a topology node."""

    node_id: str = Field(..., max_length=100)
    node_name: str = Field(..., max_length=200)
    node_type: str = Field(..., max_length=50)
    attributes: dict[str, Any] = Field(default_factory=dict)
    agents: list[AgentConfig]
    supervisor_config: SupervisorConfig


class EdgeConfig(BaseModel):
    """Configuration for an edge between nodes."""

    source_node_id: str
    target_node_id: str
    relation_type: Literal["calls", "depends_on", "integrates", "monitors", "data_flow"]
    attributes: dict[str, Any] = Field(default_factory=dict)


class TopologyConfig(BaseModel):
    """Complete topology configuration."""

    nodes: list[NodeConfig]
    edges: list[EdgeConfig] = Field(default_factory=list)
    global_supervisor: GlobalSupervisorConfig


# ============== Team Schemas ==============
class TeamCreate(BaseModel):
    """Schema for creating a team."""

    topology: TopologyConfig
    team_name: str = Field(..., max_length=200)
    description: str | None = None
    timeout_seconds: int = Field(300, ge=1, le=1800)
    max_iterations: int = Field(50, ge=1, le=500)


class TeamResponse(BaseModel):
    """Schema for team response."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None
    status: TeamStatus
    timeout_seconds: int
    max_iterations: int
    created_at: datetime
    updated_at: datetime


class TeamCreatedResponse(BaseModel):
    """Schema for team creation response."""

    team_id: uuid.UUID
    status: str = "created"
    created_at: datetime
    topology_summary: dict


# ============== Execution Schemas ==============
class ExecutionInput(BaseModel):
    """Input for team execution."""

    task: str = Field(..., description="Task description")
    context: dict[str, Any] = Field(default_factory=dict)


class ExecutionRequest(BaseModel):
    """Schema for execution request."""

    input: ExecutionInput
    timeout_seconds: int = Field(300, ge=1, le=1800)
    stream: bool = True


class ExecutionResponse(BaseModel):
    """Schema for execution response."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    team_id: uuid.UUID
    status: ExecutionStatus
    input_data: dict
    output_data: dict | None
    started_at: datetime | None
    completed_at: datetime | None
    duration_ms: int | None
    error_message: str | None
    created_at: datetime


# ============== Structured Output ==============
class StructuredOutputRequest(BaseModel):
    """Schema for structured output request."""

    execution_id: uuid.UUID | None = None
    output_schema: dict = Field(..., description="JSON Schema for output")
    include_raw_output: bool = False


class StructuredOutputResponse(BaseModel):
    """Schema for structured output response."""

    team_id: uuid.UUID
    execution_id: uuid.UUID
    structured_output: dict
    schema_validation: dict


# ============== Common Schemas ==============
class PaginatedResponse(BaseModel):
    """Generic paginated response."""

    items: list[Any]
    total: int
    page: int
    size: int
    pages: int


class ErrorResponse(BaseModel):
    """Error response schema."""

    error_code: str
    error_message: str
    details: dict | None = None
