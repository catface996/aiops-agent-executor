"""State definitions for LangGraph-based hierarchical team execution.

This module defines the state structures used throughout the execution graph,
including supervisor decisions, agent states, and team-wide execution state.
"""

from dataclasses import dataclass, field
from datetime import datetime, UTC
from enum import Enum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage


class RouteAction(str, Enum):
    """Actions that a supervisor can take."""

    DELEGATE = "delegate"      # Delegate to a specific agent/node
    PARALLEL = "parallel"      # Execute multiple agents/nodes in parallel
    FINISH = "finish"          # Mark current scope as complete
    ESCALATE = "escalate"      # Escalate to parent supervisor


class SupervisorDecision(BaseModel):
    """Structured decision from a supervisor.

    This is the schema used for LLM structured output to determine
    which agent or node should execute next.
    """

    action: RouteAction = Field(
        ...,
        description="The action to take: delegate to an agent, run parallel, finish, or escalate"
    )
    next_agent: str | None = Field(
        None,
        description="The agent_id or node_id to delegate to (required if action is 'delegate')"
    )
    parallel_agents: list[str] = Field(
        default_factory=list,
        description="List of agent_ids or node_ids to run in parallel (required if action is 'parallel')"
    )
    reasoning: str = Field(
        ...,
        description="Explanation for why this routing decision was made"
    )
    task_assignment: str = Field(
        default="",
        description="Specific task or sub-task to assign to the selected agent(s)"
    )

    model_config = {"extra": "forbid"}


class GlobalSupervisorDecision(BaseModel):
    """Decision from the global supervisor about which node to execute.

    The global supervisor coordinates across all nodes in the team topology.
    """

    action: RouteAction = Field(
        ...,
        description="The action to take at the global level"
    )
    next_node: str | None = Field(
        None,
        description="The node_id to execute next (required if action is 'delegate')"
    )
    parallel_nodes: list[str] = Field(
        default_factory=list,
        description="List of node_ids to execute in parallel"
    )
    reasoning: str = Field(
        ...,
        description="Reasoning behind the routing decision"
    )
    task_for_node: str = Field(
        default="",
        description="Specific task to assign to the selected node"
    )
    should_continue: bool = Field(
        default=True,
        description="Whether execution should continue after this step"
    )

    model_config = {"extra": "forbid"}


class NodeSupervisorDecision(BaseModel):
    """Decision from a node supervisor about which agent to execute.

    The node supervisor coordinates agents within a single node.
    """

    action: RouteAction = Field(
        ...,
        description="The action to take within this node"
    )
    next_agent: str | None = Field(
        None,
        description="The agent_id to execute next within this node"
    )
    parallel_agents: list[str] = Field(
        default_factory=list,
        description="List of agent_ids to execute in parallel"
    )
    reasoning: str = Field(
        ...,
        description="Reasoning behind the agent selection"
    )
    task_for_agent: str = Field(
        default="",
        description="Specific task to assign to the selected agent"
    )
    node_complete: bool = Field(
        default=False,
        description="Whether this node has completed its work"
    )

    model_config = {"extra": "forbid"}


@dataclass
class AgentResult:
    """Result from a single agent execution."""

    agent_id: str
    output: str
    status: Literal["success", "failed", "timeout"] = "success"
    error: str | None = None
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    tokens_used: int = 0
    execution_time_ms: int = 0
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class NodeResult:
    """Result from a node execution (aggregated from its agents)."""

    node_id: str
    node_name: str
    status: Literal["success", "failed", "timeout", "partial"] = "success"
    output: str = ""
    agent_results: list[AgentResult] = field(default_factory=list)
    supervisor_decisions: list[NodeSupervisorDecision] = field(default_factory=list)
    error: str | None = None
    execution_time_ms: int = 0
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class AgentState:
    """State for a single agent during execution."""

    agent_id: str
    role: str
    model_id: str
    system_prompt: str
    temperature: float = 0.7
    tools: list[str] = field(default_factory=list)
    # Runtime state
    messages: list[BaseMessage] = field(default_factory=list)
    result: AgentResult | None = None


@dataclass
class NodeState:
    """State for a single node during execution."""

    node_id: str
    node_name: str
    node_type: str  # "agent", "supervisor", "aggregator"
    agents: dict[str, AgentState] = field(default_factory=dict)
    supervisor_config: dict[str, Any] = field(default_factory=dict)
    # Runtime state
    current_task: str = ""
    messages: list[BaseMessage] = field(default_factory=list)
    agent_results: list[AgentResult] = field(default_factory=list)
    supervisor_decisions: list[NodeSupervisorDecision] = field(default_factory=list)
    result: NodeResult | None = None
    is_complete: bool = False


class TeamExecutionState(BaseModel):
    """Complete state for a hierarchical team execution.

    This is the main state object passed through the LangGraph execution.
    Uses Pydantic for validation and serialization.
    """

    # Identity
    execution_id: str = Field(..., description="Unique execution identifier")
    team_id: str = Field(..., description="Team identifier")

    # Input/Output
    input_task: str = Field(..., description="The original task to execute")
    input_context: dict[str, Any] = Field(default_factory=dict, description="Additional context")
    final_output: str = Field(default="", description="Final synthesized output")

    # Messages (for LangGraph message passing)
    messages: Annotated[list[BaseMessage], add_messages] = Field(default_factory=list)

    # Topology
    nodes: dict[str, dict[str, Any]] = Field(default_factory=dict, description="Node configurations")
    edges: list[dict[str, Any]] = Field(default_factory=list, description="Edge configurations")
    global_supervisor_config: dict[str, Any] = Field(default_factory=dict)

    # Execution tracking
    current_node: str | None = Field(None, description="Currently executing node")
    executed_nodes: list[str] = Field(default_factory=list, description="Nodes that have completed")
    pending_nodes: list[str] = Field(default_factory=list, description="Nodes waiting to execute")

    # Results
    node_results: dict[str, dict[str, Any]] = Field(default_factory=dict)
    global_supervisor_decisions: list[dict[str, Any]] = Field(default_factory=list)

    # Control flow
    iteration_count: int = Field(default=0, description="Number of supervisor iterations")
    max_iterations: int = Field(default=50, description="Maximum iterations allowed")
    is_complete: bool = Field(default=False, description="Whether execution is complete")
    error: str | None = Field(None, description="Error message if failed")

    # Metadata
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    model_config = {"arbitrary_types_allowed": True}

    def get_available_nodes(self) -> list[str]:
        """Get nodes that are available for execution (not yet executed)."""
        return [
            node_id for node_id in self.nodes.keys()
            if node_id not in self.executed_nodes
        ]

    def get_node_agents(self, node_id: str) -> list[dict[str, Any]]:
        """Get the agents configured for a specific node."""
        node = self.nodes.get(node_id, {})
        return node.get("agents", [])

    def add_node_result(self, node_id: str, result: dict[str, Any]) -> None:
        """Add a result for a node."""
        self.node_results[node_id] = result
        if node_id not in self.executed_nodes:
            self.executed_nodes.append(node_id)
        if node_id in self.pending_nodes:
            self.pending_nodes.remove(node_id)

    def add_supervisor_decision(self, decision: GlobalSupervisorDecision) -> None:
        """Record a global supervisor decision."""
        self.global_supervisor_decisions.append(decision.model_dump())
        self.iteration_count += 1


# Type alias for node-level state used in sub-graphs
class NodeExecutionState(BaseModel):
    """State for executing a single node's sub-graph."""

    node_id: str
    node_name: str
    task: str
    context: dict[str, Any] = Field(default_factory=dict)

    # Agent configurations
    agents: list[dict[str, Any]] = Field(default_factory=list)
    supervisor_config: dict[str, Any] = Field(default_factory=dict)

    # Messages
    messages: Annotated[list[BaseMessage], add_messages] = Field(default_factory=list)

    # Execution tracking
    current_agent: str | None = None
    executed_agents: list[str] = Field(default_factory=list)
    agent_results: dict[str, dict[str, Any]] = Field(default_factory=dict)
    supervisor_decisions: list[dict[str, Any]] = Field(default_factory=list)

    # Control
    iteration_count: int = 0
    max_iterations: int = 20
    is_complete: bool = False
    output: str = ""
    error: str | None = None

    model_config = {"arbitrary_types_allowed": True}

    def get_available_agents(self) -> list[str]:
        """Get agents that haven't been executed yet."""
        return [
            agent.get("agent_id")
            for agent in self.agents
            if agent.get("agent_id") not in self.executed_agents
        ]

    def add_agent_result(self, agent_id: str, result: dict[str, Any]) -> None:
        """Add a result for an agent."""
        self.agent_results[agent_id] = result
        if agent_id not in self.executed_agents:
            self.executed_agents.append(agent_id)
