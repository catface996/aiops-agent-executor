"""Execution service for running Agent team tasks.

Handles the orchestration of agent teams using a hierarchical supervisor pattern:
Global Supervisor -> Node Supervisors -> Agents

This module now uses the LangGraph-based execution engine for dynamic routing
where supervisors use structured LLM output to decide which agent/node to execute.
"""

import asyncio
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aiops_agent_executor.core.exceptions import BadRequestError, ConflictError, NotFoundError
from aiops_agent_executor.db.models.team import Execution, ExecutionStatus, Team
from aiops_agent_executor.services.langgraph import HierarchicalTeamEngine
from aiops_agent_executor.services.llm_client import LLMClientFactory, LLMMessage


class SSEEventType(str, Enum):
    """Types of SSE events emitted during execution."""

    EXECUTION_START = "execution_start"
    GLOBAL_SUPERVISOR_MESSAGE = "global_supervisor_message"
    GLOBAL_SUPERVISOR_DECISION = "global_supervisor_decision"
    NODE_SUPERVISOR_MESSAGE = "node_supervisor_message"
    NODE_SUPERVISOR_DECISION = "node_supervisor_decision"
    AGENT_MESSAGE = "agent_message"
    TOOL_CALL = "tool_call"
    NODE_COMPLETE = "node_complete"
    EXECUTION_COMPLETE = "execution_complete"
    EXECUTION_ERROR = "execution_error"
    HEARTBEAT = "heartbeat"


@dataclass
class SSEEvent:
    """Server-Sent Event data structure."""

    event: SSEEventType
    data: dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_sse_format(self) -> str:
        """Convert to SSE wire format."""
        import json

        data_with_ts = {**self.data, "timestamp": self.timestamp.isoformat()}
        return f"event: {self.event.value}\ndata: {json.dumps(data_with_ts)}\n\n"


@dataclass
class NodeResult:
    """Result from a single node execution."""

    node_id: str
    node_name: str
    status: str  # "success", "failed", "timeout"
    output: str
    agent_outputs: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None
    duration_ms: int = 0


@dataclass
class ExecutionResult:
    """Complete execution result."""

    execution_id: uuid.UUID
    team_id: uuid.UUID
    status: ExecutionStatus
    output: str
    node_results: dict[str, NodeResult] = field(default_factory=dict)
    error: str | None = None
    started_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: datetime | None = None


class ExecutionService:
    """Service for executing Agent team tasks.

    This service now uses the LangGraph-based HierarchicalTeamEngine for
    dynamic supervisor routing. The engine allows supervisors to make
    structured decisions about which agent or node to execute next.
    """

    def __init__(self, db: AsyncSession) -> None:
        """Initialize the service with a database session."""
        self.db = db
        self._running_executions: dict[uuid.UUID, bool] = {}
        self._engine = HierarchicalTeamEngine()

    async def start_execution(
        self,
        team_id: uuid.UUID,
        input_data: dict[str, Any],
        timeout_seconds: int | None = None,
        output_schema: dict[str, Any] | None = None,
    ) -> Execution:
        """Start a new execution for a team.

        Args:
            team_id: The team to execute
            input_data: Input data for the execution
            timeout_seconds: Override default timeout
            output_schema: Optional JSON schema for structured output

        Returns:
            The created Execution record

        Raises:
            NotFoundError: If the team doesn't exist
            ConflictError: If the team already has a running execution
        """
        # Get team
        team = await self.db.get(Team, team_id)
        if not team:
            raise NotFoundError(resource="Team", resource_id=str(team_id))

        # Check for existing running execution
        running_query = (
            select(Execution)
            .where(Execution.team_id == team_id)
            .where(Execution.status == ExecutionStatus.RUNNING)
        )
        result = await self.db.execute(running_query)
        if result.scalar_one_or_none():
            raise ConflictError(
                resource="Team",
                reason="Team already has a running execution",
            )

        # Create execution record
        # Note: timeout_seconds is stored on Team, not Execution
        execution = Execution(
            team_id=team_id,
            status=ExecutionStatus.PENDING,
            input_data=input_data,
            topology_snapshot=team.topology_config,
            output_schema=output_schema,
        )
        self.db.add(execution)
        await self.db.flush()
        await self.db.refresh(execution)

        return execution

    async def execute_sync(
        self,
        execution_id: uuid.UUID,
    ) -> ExecutionResult:
        """Execute a team task synchronously (non-streaming).

        Args:
            execution_id: The execution to run

        Returns:
            The execution result
        """
        execution = await self.db.get(Execution, execution_id)
        if not execution:
            raise NotFoundError(resource="Execution", resource_id=str(execution_id))

        # Mark as running
        execution.status = ExecutionStatus.RUNNING
        execution.started_at = datetime.utcnow()
        await self.db.flush()

        try:
            # Run the execution
            result = await self._run_execution(execution)

            # Update execution record
            execution.status = result.status
            execution.output_data = {"result": result.output}
            execution.node_results = {
                node_id: {
                    "node_id": nr.node_id,
                    "node_name": nr.node_name,
                    "status": nr.status,
                    "output": nr.output,
                    "agent_outputs": nr.agent_outputs,
                    "error": nr.error,
                    "duration_ms": nr.duration_ms,
                }
                for node_id, nr in result.node_results.items()
            }
            execution.completed_at = datetime.utcnow()
            execution.error_message = result.error
            await self.db.flush()

            return result

        except Exception as e:
            execution.status = ExecutionStatus.FAILED
            execution.error_message = str(e)
            execution.completed_at = datetime.utcnow()
            await self.db.flush()
            raise

    async def execute_stream(
        self,
        execution_id: uuid.UUID,
    ) -> AsyncIterator[SSEEvent]:
        """Execute a team task with streaming SSE events.

        Args:
            execution_id: The execution to run

        Yields:
            SSE events during execution
        """
        execution = await self.db.get(Execution, execution_id)
        if not execution:
            raise NotFoundError(resource="Execution", resource_id=str(execution_id))

        # Mark as running
        execution.status = ExecutionStatus.RUNNING
        execution.started_at = datetime.utcnow()
        await self.db.flush()

        self._running_executions[execution_id] = True

        try:
            # Emit start event
            yield SSEEvent(
                event=SSEEventType.EXECUTION_START,
                data={
                    "execution_id": str(execution_id),
                    "team_id": str(execution.team_id),
                    "input": execution.input_data,
                },
            )

            # Run with streaming events
            async for event in self._run_execution_streaming(execution):
                if not self._running_executions.get(execution_id, False):
                    break
                yield event

            # Emit completion
            yield SSEEvent(
                event=SSEEventType.EXECUTION_COMPLETE,
                data={
                    "execution_id": str(execution_id),
                    "status": "success",
                },
            )

            execution.status = ExecutionStatus.SUCCESS
            execution.completed_at = datetime.utcnow()
            await self.db.flush()

        except asyncio.TimeoutError:
            yield SSEEvent(
                event=SSEEventType.EXECUTION_ERROR,
                data={
                    "execution_id": str(execution_id),
                    "error": "Execution timed out",
                },
            )
            execution.status = ExecutionStatus.TIMEOUT
            execution.error_message = "Execution timed out"
            execution.completed_at = datetime.utcnow()
            await self.db.flush()

        except Exception as e:
            yield SSEEvent(
                event=SSEEventType.EXECUTION_ERROR,
                data={
                    "execution_id": str(execution_id),
                    "error": str(e),
                },
            )
            execution.status = ExecutionStatus.FAILED
            execution.error_message = str(e)
            execution.completed_at = datetime.utcnow()
            await self.db.flush()

        finally:
            self._running_executions.pop(execution_id, None)

    async def cancel_execution(self, execution_id: uuid.UUID) -> None:
        """Cancel a running execution.

        Args:
            execution_id: The execution to cancel
        """
        if execution_id in self._running_executions:
            self._running_executions[execution_id] = False

        execution = await self.db.get(Execution, execution_id)
        if execution and execution.status == ExecutionStatus.RUNNING:
            execution.status = ExecutionStatus.CANCELLED
            execution.completed_at = datetime.utcnow()
            await self.db.flush()

    async def _run_execution(self, execution: Execution) -> ExecutionResult:
        """Run the actual execution logic using LangGraph engine.

        This implements dynamic hierarchical routing:
        1. Global Supervisor decides which Node to execute (via structured LLM output)
        2. Node Supervisors decide which Agent to run (via structured LLM output)
        3. Process continues until Global Supervisor decides to finish

        The key difference from static execution is that supervisors make
        real-time decisions about routing based on the task and intermediate results.
        """
        topology = execution.topology_snapshot
        task = execution.input_data.get("task", str(execution.input_data))
        context = execution.input_data.get("context", {})

        result = ExecutionResult(
            execution_id=execution.id,
            team_id=execution.team_id,
            status=ExecutionStatus.RUNNING,
            output="",
        )

        try:
            # Execute using LangGraph engine's streaming execution and collect results
            final_output = ""
            node_results_data: dict[str, dict[str, Any]] = {}

            async for event in self._engine.execute(
                topology_config=topology,
                input_task=task,
                input_context=context,
                execution_id=str(execution.id),
            ):
                event_type = event.get("type", "")
                event_data = event.get("data", {})

                if event_type == "node_complete":
                    node_id = event_data.get("node_id", "")
                    if node_id:
                        node_results_data[node_id] = event_data

                elif event_type == "execution_complete":
                    final_output = event_data.get("output", "")
                    result.status = (
                        ExecutionStatus.SUCCESS
                        if event_data.get("status") == "success"
                        else ExecutionStatus.TIMEOUT
                    )

            # Convert collected node results to ExecutionResult format
            for node_id, node_data in node_results_data.items():
                node_result = NodeResult(
                    node_id=node_id,
                    node_name=node_data.get("node_name", node_id),
                    status=node_data.get("status", "success"),
                    output=node_data.get("output", ""),
                    agent_outputs=[],
                    duration_ms=node_data.get("execution_time_ms", 0),
                )
                result.node_results[node_id] = node_result

            result.output = final_output
            result.completed_at = datetime.utcnow()

        except Exception as e:
            result.status = ExecutionStatus.FAILED
            result.error = str(e)
            result.completed_at = datetime.utcnow()

        return result

    async def _run_execution_streaming(
        self,
        execution: Execution,
    ) -> AsyncIterator[SSEEvent]:
        """Run execution with streaming events using LangGraph engine.

        This method uses the LangGraph engine's streaming capability to provide
        real-time updates on supervisor decisions and agent executions.
        """
        topology = execution.topology_snapshot
        task = execution.input_data.get("task", str(execution.input_data))
        context = execution.input_data.get("context", {})

        # Use LangGraph engine's streaming execution
        async for event in self._engine.execute(
            topology_config=topology,
            input_task=task,
            input_context=context,
            execution_id=str(execution.id),
        ):
            event_type = event.get("type", "unknown")
            event_data = event.get("data", {})

            # Map engine events to SSE events
            if event_type == "execution_start":
                yield SSEEvent(
                    event=SSEEventType.EXECUTION_START,
                    data={
                        "execution_id": str(execution.id),
                        "team_id": str(execution.team_id),
                        "input": execution.input_data,
                    },
                )

            elif event_type == "global_supervisor_thinking":
                yield SSEEvent(
                    event=SSEEventType.GLOBAL_SUPERVISOR_MESSAGE,
                    data={
                        "execution_id": str(execution.id),
                        "message": f"Global supervisor analyzing task (iteration {event_data.get('iteration', 0)})...",
                    },
                )

            elif event_type == "global_supervisor_decision":
                yield SSEEvent(
                    event=SSEEventType.GLOBAL_SUPERVISOR_DECISION,
                    data={
                        "execution_id": str(execution.id),
                        "action": event_data.get("action"),
                        "next_node": event_data.get("next_node"),
                        "parallel_nodes": event_data.get("parallel_nodes", []),
                        "reasoning": event_data.get("reasoning", ""),
                        "task_for_node": event_data.get("task_for_node", ""),
                    },
                )

            elif event_type == "node_start":
                yield SSEEvent(
                    event=SSEEventType.NODE_SUPERVISOR_MESSAGE,
                    data={
                        "execution_id": str(execution.id),
                        "node_id": event_data.get("node_id"),
                        "message": f"Starting node: {event_data.get('node_id')}",
                    },
                )

            elif event_type == "agent_result":
                yield SSEEvent(
                    event=SSEEventType.AGENT_MESSAGE,
                    data={
                        "execution_id": str(execution.id),
                        "node_id": event_data.get("node_id"),
                        "agent_id": event_data.get("agent_id"),
                        "message": event_data.get("output", ""),
                        "status": event_data.get("status"),
                    },
                )

            elif event_type == "node_complete":
                yield SSEEvent(
                    event=SSEEventType.NODE_COMPLETE,
                    data={
                        "execution_id": str(execution.id),
                        "node_id": event_data.get("node_id"),
                        "status": event_data.get("status", "success"),
                        "output": event_data.get("output", "")[:500],
                    },
                )

            elif event_type == "synthesis_start":
                yield SSEEvent(
                    event=SSEEventType.GLOBAL_SUPERVISOR_MESSAGE,
                    data={
                        "execution_id": str(execution.id),
                        "message": "Synthesizing results from all nodes...",
                    },
                )

            elif event_type == "execution_complete":
                # Update execution record with final output
                execution.output_data = {"result": event_data.get("output", "")}
                await self.db.flush()

    # =========================================================================
    # NOTE: The following methods have been moved to the LangGraph engine:
    #   - _call_global_supervisor -> HierarchicalTeamEngine._call_global_supervisor
    #   - _execute_node -> HierarchicalTeamEngine._execute_node
    #   - _execute_agent -> HierarchicalTeamEngine._execute_agent
    #   - _synthesize_results -> HierarchicalTeamEngine._synthesize_results
    #
    # The LangGraph engine provides:
    #   1. Dynamic supervisor routing via structured LLM output
    #   2. Node-level supervisor decisions for agent selection
    #   3. Support for parallel execution of nodes/agents
    #   4. Iterative execution until supervisors decide to finish
    # =========================================================================

    async def get_execution(self, execution_id: uuid.UUID) -> Execution:
        """Get an execution by ID.

        Args:
            execution_id: The execution's UUID

        Returns:
            The execution

        Raises:
            NotFoundError: If the execution doesn't exist
        """
        execution = await self.db.get(Execution, execution_id)
        if not execution:
            raise NotFoundError(resource="Execution", resource_id=str(execution_id))
        return execution

    async def list_executions(
        self,
        team_id: uuid.UUID | None = None,
        status: ExecutionStatus | None = None,
        skip: int = 0,
        limit: int = 20,
    ) -> list[Execution]:
        """List executions with optional filtering.

        Args:
            team_id: Filter by team (optional)
            status: Filter by status (optional)
            skip: Number of records to skip
            limit: Maximum records to return

        Returns:
            List of executions
        """
        query = select(Execution).order_by(Execution.created_at.desc())

        if team_id:
            query = query.where(Execution.team_id == team_id)
        if status:
            query = query.where(Execution.status == status)

        query = query.offset(skip).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())
