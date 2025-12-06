"""Agent Team related database models."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from aiops_agent_executor.db.base import Base, TimestampMixin, UUIDMixin


class TeamStatus(str, enum.Enum):
    """Team status."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"


class ExecutionStatus(str, enum.Enum):
    """Execution status."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


class Team(Base, UUIDMixin, TimestampMixin):
    """Agent Team entity representing a topology of agents."""

    __tablename__ = "teams"

    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    topology_config: Mapped[dict] = mapped_column(JSONB, nullable=False)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=300, nullable=False)
    max_iterations: Mapped[int] = mapped_column(Integer, default=50, nullable=False)
    status: Mapped[TeamStatus] = mapped_column(
        Enum(TeamStatus), default=TeamStatus.ACTIVE, nullable=False
    )

    # Relationships
    executions: Mapped[list["Execution"]] = relationship(
        "Execution", back_populates="team", cascade="all, delete-orphan"
    )


class Execution(Base, UUIDMixin, TimestampMixin):
    """Execution record for a team run."""

    __tablename__ = "executions"

    team_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("teams.id", ondelete="CASCADE"), nullable=False
    )
    input_data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    output_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[ExecutionStatus] = mapped_column(
        Enum(ExecutionStatus), default=ExecutionStatus.PENDING, nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    team: Mapped["Team"] = relationship("Team", back_populates="executions")
    logs: Mapped[list["ExecutionLog"]] = relationship(
        "ExecutionLog", back_populates="execution", cascade="all, delete-orphan"
    )


class ExecutionLog(Base, UUIDMixin):
    """Log entry for execution events."""

    __tablename__ = "execution_logs"

    execution_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("executions.id", ondelete="CASCADE"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    node_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    agent_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    supervisor_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    extra_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(nullable=False)

    # Relationships
    execution: Mapped["Execution"] = relationship("Execution", back_populates="logs")
