"""Agent and Node database models.

This module defines the Agent and Node entities for managing
reusable agent configurations and team topology nodes.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from aiops_agent_executor.db.base import Base, TimestampMixin, UUIDMixin


class AgentStatus(str, enum.Enum):
    """Agent status."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    DEPRECATED = "deprecated"


class Agent(Base, UUIDMixin, TimestampMixin):
    """Agent entity representing a reusable agent configuration.

    Agents can be shared across multiple nodes and teams.
    """

    __tablename__ = "agents"

    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    role: Mapped[str] = mapped_column(String(200), nullable=False)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)

    # Model configuration
    provider_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("providers.id", ondelete="SET NULL"), nullable=True
    )
    model_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    temperature: Mapped[float] = mapped_column(Float, default=0.7, nullable=False)
    max_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Tools and capabilities
    tools: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    tool_config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Status and metadata
    status: Mapped[AgentStatus] = mapped_column(
        Enum(AgentStatus), default=AgentStatus.ACTIVE, nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    tags: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    extra_config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Relationships
    provider: Mapped["Provider"] = relationship("Provider", back_populates="agents")
    node_agents: Mapped[list["NodeAgent"]] = relationship(
        "NodeAgent", back_populates="agent", cascade="all, delete-orphan"
    )


class NodeType(str, enum.Enum):
    """Node type in team topology."""

    SUPERVISOR = "supervisor"  # Node with supervisor routing agents
    WORKER = "worker"          # Node with worker agents (no sub-routing)
    AGGREGATOR = "aggregator"  # Node that aggregates results


class NodeStatus(str, enum.Enum):
    """Node status."""

    ACTIVE = "active"
    INACTIVE = "inactive"


class Node(Base, UUIDMixin, TimestampMixin):
    """Node entity representing a group of agents in team topology.

    Nodes organize agents into logical groups within a team.
    Each node can have a supervisor that routes tasks to its agents.
    """

    __tablename__ = "nodes"

    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    node_type: Mapped[NodeType] = mapped_column(
        Enum(NodeType), default=NodeType.SUPERVISOR, nullable=False
    )

    # Team association
    team_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("teams.id", ondelete="CASCADE"), nullable=False
    )

    # Supervisor configuration (for supervisor-type nodes)
    supervisor_provider_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("providers.id", ondelete="SET NULL"), nullable=True
    )
    supervisor_model_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    supervisor_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Execution settings
    max_iterations: Mapped[int] = mapped_column(Integer, default=20, nullable=False)
    parallel_execution: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Status and ordering
    status: Mapped[NodeStatus] = mapped_column(
        Enum(NodeStatus), default=NodeStatus.ACTIVE, nullable=False
    )
    order_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    extra_config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Relationships
    team: Mapped["Team"] = relationship("Team", back_populates="nodes")
    supervisor_provider: Mapped["Provider"] = relationship("Provider", foreign_keys=[supervisor_provider_id])
    node_agents: Mapped[list["NodeAgent"]] = relationship(
        "NodeAgent", back_populates="node", cascade="all, delete-orphan"
    )


class NodeAgent(Base, UUIDMixin, TimestampMixin):
    """Association table between Node and Agent with ordering.

    This allows the same agent to be used in multiple nodes
    with different ordering and configuration overrides.
    """

    __tablename__ = "node_agents"

    node_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("nodes.id", ondelete="CASCADE"), nullable=False
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False
    )

    # Ordering within the node
    order_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Configuration overrides (optional, merges with agent defaults)
    config_override: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Relationships
    node: Mapped["Node"] = relationship("Node", back_populates="node_agents")
    agent: Mapped["Agent"] = relationship("Agent", back_populates="node_agents")


# Import for type hints (avoid circular imports)
from aiops_agent_executor.db.models.provider import Provider  # noqa: E402
from aiops_agent_executor.db.models.team import Team  # noqa: E402
