"""Topology configuration schemas for Agent teams."""

from typing import Any

from pydantic import BaseModel, Field


class AgentConfig(BaseModel):
    """Configuration for an individual agent within a node."""

    agent_id: str = Field(..., description="Unique identifier for the agent")
    role: str = Field(..., description="Role description for the agent")
    model_id: str = Field(..., description="Reference to model configuration")
    system_prompt: str | None = Field(None, description="Optional system prompt override")
    temperature: float = Field(0.7, ge=0.0, le=2.0, description="Sampling temperature")
    max_tokens: int | None = Field(None, description="Maximum output tokens")
    tools: list[str] = Field(default_factory=list, description="List of tool names available")

    model_config = {"extra": "forbid"}


class NodeConfig(BaseModel):
    """Configuration for a node in the topology graph."""

    id: str = Field(..., description="Unique node identifier")
    name: str = Field(..., description="Display name for the node")
    type: str = Field(
        "agent",
        description="Node type: 'agent', 'supervisor', or 'aggregator'",
    )
    agents: list[AgentConfig] = Field(
        default_factory=list,
        description="Agents assigned to this node",
    )
    supervisor_config: dict[str, Any] | None = Field(
        None,
        description="Supervisor configuration if type is 'supervisor'",
    )
    retry_count: int = Field(3, ge=0, le=10, description="Number of retries on failure")
    timeout_seconds: int = Field(60, ge=1, le=3600, description="Node execution timeout")

    model_config = {"extra": "forbid"}


class EdgeConfig(BaseModel):
    """Configuration for an edge connecting nodes."""

    source: str = Field(..., description="Source node ID")
    target: str = Field(..., description="Target node ID")
    condition: str | None = Field(
        None,
        description="Optional condition expression for conditional routing",
    )

    model_config = {"extra": "forbid"}


class TopologyConfig(BaseModel):
    """Complete topology configuration for an Agent team."""

    nodes: list[NodeConfig] = Field(..., min_length=1, description="List of nodes")
    edges: list[EdgeConfig] = Field(default_factory=list, description="List of edges")
    global_supervisor: AgentConfig | None = Field(
        None,
        description="Optional global supervisor agent",
    )
    entry_node: str | None = Field(None, description="Entry point node ID (defaults to first)")
    exit_nodes: list[str] = Field(
        default_factory=list,
        description="Exit point node IDs (defaults to nodes with no outgoing edges)",
    )

    model_config = {"extra": "forbid"}


class TopologyValidationError(BaseModel):
    """Single validation error."""

    message: str = Field(..., description="Error message")
    location: str | None = Field(None, description="Location of the error")


class TopologyValidationResult(BaseModel):
    """Result of topology validation."""

    valid: bool = Field(..., description="Whether the topology is valid")
    errors: list[TopologyValidationError] = Field(
        default_factory=list,
        description="List of validation errors",
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="List of validation warnings",
    )
