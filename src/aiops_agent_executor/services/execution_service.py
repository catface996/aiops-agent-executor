"""Execution service for running Agent team tasks.

Handles the orchestration of agent teams using a hierarchical supervisor pattern:
Global Supervisor -> Node Supervisors -> Agents
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
from aiops_agent_executor.services.llm_client import LLMClientFactory, LLMMessage, LLMResponse


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
    """Service for executing Agent team tasks."""

    def __init__(self, db: AsyncSession) -> None:
        """Initialize the service with a database session."""
        self.db = db
        self._running_executions: dict[uuid.UUID, bool] = {}

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
        """Run the actual execution logic.

        This implements the three-tier architecture:
        1. Global Supervisor coordinates overall task
        2. Node Supervisors manage agents within each node
        3. Agents execute specific tasks
        """
        topology = execution.topology_snapshot
        nodes = topology.get("nodes", [])
        edges = topology.get("edges", [])
        global_supervisor = topology.get("global_supervisor", {})

        result = ExecutionResult(
            execution_id=execution.id,
            team_id=execution.team_id,
            status=ExecutionStatus.RUNNING,
            output="",
        )

        # Step 1: Global Supervisor plans the execution
        global_plan = await self._call_global_supervisor(
            global_supervisor,
            execution.input_data,
            nodes,
            edges,
        )

        # Step 2: Execute each node based on topology
        all_outputs = []
        for node in nodes:
            node_id = node.get("node_id") or node.get("id")
            node_name = node.get("node_name") or node.get("name", node_id)

            node_result = await self._execute_node(node, execution.input_data, global_plan)
            result.node_results[node_id] = node_result
            all_outputs.append(f"[{node_name}]: {node_result.output}")

        # Step 3: Global Supervisor synthesizes results
        final_output = await self._synthesize_results(
            global_supervisor,
            execution.input_data,
            all_outputs,
        )

        result.output = final_output
        result.status = ExecutionStatus.SUCCESS
        result.completed_at = datetime.utcnow()

        return result

    async def _run_execution_streaming(
        self,
        execution: Execution,
    ) -> AsyncIterator[SSEEvent]:
        """Run execution with streaming events."""
        topology = execution.topology_snapshot
        nodes = topology.get("nodes", [])
        edges = topology.get("edges", [])
        global_supervisor = topology.get("global_supervisor", {})

        # Step 1: Global Supervisor plans
        yield SSEEvent(
            event=SSEEventType.GLOBAL_SUPERVISOR_MESSAGE,
            data={
                "execution_id": str(execution.id),
                "message": "Analyzing task and planning execution...",
            },
        )

        global_plan = await self._call_global_supervisor(
            global_supervisor,
            execution.input_data,
            nodes,
            edges,
        )

        yield SSEEvent(
            event=SSEEventType.GLOBAL_SUPERVISOR_DECISION,
            data={
                "execution_id": str(execution.id),
                "plan": global_plan,
                "nodes_to_execute": [n.get("node_id") or n.get("id") for n in nodes],
            },
        )

        # Step 2: Execute nodes
        all_outputs = []
        for node in nodes:
            node_id = node.get("node_id") or node.get("id")
            node_name = node.get("node_name") or node.get("name", node_id)

            # Node supervisor message
            yield SSEEvent(
                event=SSEEventType.NODE_SUPERVISOR_MESSAGE,
                data={
                    "execution_id": str(execution.id),
                    "node_id": node_id,
                    "message": f"Starting execution for node: {node_name}",
                },
            )

            # Execute agents in the node
            agents = node.get("agents", [])
            agent_outputs = []

            for agent in agents:
                agent_id = agent.get("agent_id")
                agent_output = await self._execute_agent(agent, execution.input_data)

                yield SSEEvent(
                    event=SSEEventType.AGENT_MESSAGE,
                    data={
                        "execution_id": str(execution.id),
                        "node_id": node_id,
                        "agent_id": agent_id,
                        "message": agent_output,
                    },
                )

                agent_outputs.append({"agent_id": agent_id, "output": agent_output})

            # Node complete
            node_output = "\n".join(ao["output"] for ao in agent_outputs)
            all_outputs.append(f"[{node_name}]: {node_output}")

            yield SSEEvent(
                event=SSEEventType.NODE_COMPLETE,
                data={
                    "execution_id": str(execution.id),
                    "node_id": node_id,
                    "status": "success",
                    "output": node_output[:500],  # Truncate for SSE
                },
            )

        # Step 3: Synthesize
        yield SSEEvent(
            event=SSEEventType.GLOBAL_SUPERVISOR_MESSAGE,
            data={
                "execution_id": str(execution.id),
                "message": "Synthesizing results from all nodes...",
            },
        )

        final_output = await self._synthesize_results(
            global_supervisor,
            execution.input_data,
            all_outputs,
        )

        # Update execution
        execution.output_data = {"result": final_output}
        await self.db.flush()

    async def _call_global_supervisor(
        self,
        supervisor_config: dict[str, Any],
        input_data: dict[str, Any],
        nodes: list[dict],
        edges: list[dict],
    ) -> str:
        """Call the global supervisor to plan execution."""
        provider = supervisor_config.get("model_provider", "mock")
        model = supervisor_config.get("model_id", "mock-model")
        system_prompt = supervisor_config.get(
            "system_prompt",
            "You are a global supervisor coordinating agent teams.",
        )

        client = LLMClientFactory.get_client(provider)

        task = input_data.get("task", str(input_data))
        node_info = ", ".join(
            n.get("node_name") or n.get("name", n.get("node_id") or n.get("id"))
            for n in nodes
        )

        messages = [
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(
                role="user",
                content=f"Plan the execution for this task: {task}\n\nAvailable nodes: {node_info}",
            ),
        ]

        response = await client.chat(messages, model)
        return response.content

    async def _execute_node(
        self,
        node: dict[str, Any],
        input_data: dict[str, Any],
        global_plan: str,
    ) -> NodeResult:
        """Execute a single node with its agents."""
        import time

        start_time = time.time()

        node_id = node.get("node_id") or node.get("id")
        node_name = node.get("node_name") or node.get("name", node_id)
        agents = node.get("agents", [])

        agent_outputs = []
        combined_output = []

        for agent in agents:
            agent_output = await self._execute_agent(agent, input_data)
            agent_outputs.append({
                "agent_id": agent.get("agent_id"),
                "output": agent_output,
            })
            combined_output.append(agent_output)

        duration_ms = int((time.time() - start_time) * 1000)

        return NodeResult(
            node_id=node_id,
            node_name=node_name,
            status="success",
            output="\n\n".join(combined_output),
            agent_outputs=agent_outputs,
            duration_ms=duration_ms,
        )

    async def _execute_agent(
        self,
        agent: dict[str, Any],
        input_data: dict[str, Any],
    ) -> str:
        """Execute a single agent."""
        provider = agent.get("model_provider", "mock")
        model = agent.get("model_id", "mock-model")
        system_prompt = agent.get("system_prompt", "You are a helpful agent.")
        temperature = agent.get("temperature", 0.7)

        client = LLMClientFactory.get_client(provider)

        task = input_data.get("task", str(input_data))
        context = input_data.get("context", {})

        messages = [
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(
                role="user",
                content=f"Task: {task}\n\nContext: {context}",
            ),
        ]

        response = await client.chat(messages, model, temperature=temperature)
        return response.content

    async def _synthesize_results(
        self,
        supervisor_config: dict[str, Any],
        input_data: dict[str, Any],
        node_outputs: list[str],
    ) -> str:
        """Synthesize results from all nodes into final output."""
        provider = supervisor_config.get("model_provider", "mock")
        model = supervisor_config.get("model_id", "mock-model")
        system_prompt = supervisor_config.get(
            "system_prompt",
            "You are synthesizing results from multiple agents.",
        )

        client = LLMClientFactory.get_client(provider)

        task = input_data.get("task", str(input_data))
        results_text = "\n\n".join(node_outputs)

        messages = [
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(
                role="user",
                content=f"Original task: {task}\n\nResults from agents:\n{results_text}\n\nPlease synthesize these results into a final summary.",
            ),
        ]

        response = await client.chat(messages, model)
        return response.content

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
