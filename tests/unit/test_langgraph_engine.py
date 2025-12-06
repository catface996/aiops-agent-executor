"""Unit tests for the LangGraph-based hierarchical team execution engine.

Tests cover:
1. Supervisor decision schema validation
2. Global supervisor routing logic
3. Node supervisor agent selection
4. End-to-end execution flow
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from aiops_agent_executor.services.langgraph import (
    HierarchicalTeamEngine,
    SupervisorDecision,
    TeamExecutionState,
    NodeExecutionState,
)
from aiops_agent_executor.services.langgraph.state import (
    GlobalSupervisorDecision,
    NodeSupervisorDecision,
    RouteAction,
)
from aiops_agent_executor.services.llm_client import LLMMessage


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def sample_topology():
    """Sample topology configuration for testing."""
    return {
        "team_id": "test-team-001",
        "nodes": [
            {
                "node_id": "db-node",
                "node_name": "Database Analysis Node",
                "node_type": "agent",
                "agents": [
                    {
                        "agent_id": "log-analyzer",
                        "role": "Log Analyzer",
                        "model_provider": "mock",
                        "model_id": "mock-model",
                        "system_prompt": "You are a log analysis expert.",
                        "tools": ["search_logs", "parse_error"],
                    },
                    {
                        "agent_id": "query-analyzer",
                        "role": "Query Performance Analyzer",
                        "model_provider": "mock",
                        "model_id": "mock-model",
                        "system_prompt": "You analyze database query performance.",
                        "tools": ["explain_query", "suggest_index"],
                    },
                ],
                "supervisor_config": {
                    "model_provider": "mock",
                    "model_id": "mock-model",
                    "system_prompt": "Coordinate database analysis tasks.",
                },
            },
            {
                "node_id": "app-node",
                "node_name": "Application Analysis Node",
                "node_type": "agent",
                "agents": [
                    {
                        "agent_id": "metrics-collector",
                        "role": "Metrics Collector",
                        "model_provider": "mock",
                        "model_id": "mock-model",
                        "system_prompt": "You collect and analyze application metrics.",
                    },
                ],
                "supervisor_config": {
                    "model_provider": "mock",
                    "model_id": "mock-model",
                },
            },
        ],
        "edges": [
            {"source": "app-node", "target": "db-node", "relation_type": "calls"},
        ],
        "global_supervisor": {
            "model_provider": "mock",
            "model_id": "mock-model",
            "system_prompt": "You coordinate all nodes to diagnose system issues.",
        },
    }


@pytest.fixture
def mock_llm_client():
    """Create a mock LLM client with configurable responses."""
    client = AsyncMock()
    # Default mock response: (content, tool_calls)
    client.complete.return_value = (
        '{"action": "finish", "reasoning": "Task complete", "should_continue": false}',
        [],
    )
    return client


# =============================================================================
# Test Supervisor Decision Schemas
# =============================================================================

class TestSupervisorDecisionSchemas:
    """Tests for supervisor decision schema validation."""

    def test_global_supervisor_decision_delegate(self):
        """Test GlobalSupervisorDecision with delegate action."""
        decision = GlobalSupervisorDecision(
            action=RouteAction.DELEGATE,
            next_node="db-node",
            reasoning="Database analysis is needed first",
            task_for_node="Analyze slow queries",
            should_continue=True,
        )

        assert decision.action == RouteAction.DELEGATE
        assert decision.next_node == "db-node"
        assert decision.should_continue is True

    def test_global_supervisor_decision_parallel(self):
        """Test GlobalSupervisorDecision with parallel action."""
        decision = GlobalSupervisorDecision(
            action=RouteAction.PARALLEL,
            parallel_nodes=["db-node", "app-node"],
            reasoning="Both nodes can run independently",
            task_for_node="Collect metrics",
        )

        assert decision.action == RouteAction.PARALLEL
        assert len(decision.parallel_nodes) == 2
        assert "db-node" in decision.parallel_nodes

    def test_global_supervisor_decision_finish(self):
        """Test GlobalSupervisorDecision with finish action."""
        decision = GlobalSupervisorDecision(
            action=RouteAction.FINISH,
            reasoning="All required analysis is complete",
            should_continue=False,
        )

        assert decision.action == RouteAction.FINISH
        assert decision.should_continue is False

    def test_node_supervisor_decision_delegate(self):
        """Test NodeSupervisorDecision with delegate action."""
        decision = NodeSupervisorDecision(
            action=RouteAction.DELEGATE,
            next_agent="log-analyzer",
            reasoning="Log analysis should be done first",
            task_for_agent="Search for error patterns",
            node_complete=False,
        )

        assert decision.action == RouteAction.DELEGATE
        assert decision.next_agent == "log-analyzer"
        assert decision.node_complete is False

    def test_node_supervisor_decision_finish(self):
        """Test NodeSupervisorDecision with finish action."""
        decision = NodeSupervisorDecision(
            action=RouteAction.FINISH,
            reasoning="All agents have completed their tasks",
            node_complete=True,
        )

        assert decision.action == RouteAction.FINISH
        assert decision.node_complete is True


# =============================================================================
# Test Team Execution State
# =============================================================================

class TestTeamExecutionState:
    """Tests for TeamExecutionState management."""

    def test_init_state(self, sample_topology):
        """Test state initialization from topology."""
        state = TeamExecutionState(
            execution_id="exec-001",
            team_id="team-001",
            input_task="Diagnose system slowness",
            nodes={
                "db-node": sample_topology["nodes"][0],
                "app-node": sample_topology["nodes"][1],
            },
            edges=sample_topology["edges"],
            global_supervisor_config=sample_topology["global_supervisor"],
        )

        assert state.execution_id == "exec-001"
        assert len(state.nodes) == 2
        assert state.is_complete is False
        assert state.iteration_count == 0

    def test_get_available_nodes(self, sample_topology):
        """Test getting available nodes."""
        state = TeamExecutionState(
            execution_id="exec-001",
            team_id="team-001",
            input_task="Test task",
            nodes={
                "db-node": sample_topology["nodes"][0],
                "app-node": sample_topology["nodes"][1],
            },
        )

        available = state.get_available_nodes()
        assert len(available) == 2
        assert "db-node" in available
        assert "app-node" in available

        # Mark one as executed
        state.executed_nodes.append("db-node")
        available = state.get_available_nodes()
        assert len(available) == 1
        assert "app-node" in available

    def test_add_node_result(self, sample_topology):
        """Test adding node results."""
        state = TeamExecutionState(
            execution_id="exec-001",
            team_id="team-001",
            input_task="Test task",
            nodes={
                "db-node": sample_topology["nodes"][0],
            },
        )

        result = {
            "node_id": "db-node",
            "status": "success",
            "output": "Analysis complete",
        }
        state.add_node_result("db-node", result)

        assert "db-node" in state.node_results
        assert "db-node" in state.executed_nodes

    def test_add_supervisor_decision(self):
        """Test recording supervisor decisions."""
        state = TeamExecutionState(
            execution_id="exec-001",
            team_id="team-001",
            input_task="Test task",
        )

        decision = GlobalSupervisorDecision(
            action=RouteAction.DELEGATE,
            next_node="db-node",
            reasoning="Test reasoning",
        )
        state.add_supervisor_decision(decision)

        assert len(state.global_supervisor_decisions) == 1
        assert state.iteration_count == 1


# =============================================================================
# Test Node Execution State
# =============================================================================

class TestNodeExecutionState:
    """Tests for NodeExecutionState management."""

    def test_get_available_agents(self, sample_topology):
        """Test getting available agents in a node."""
        node_config = sample_topology["nodes"][0]
        state = NodeExecutionState(
            node_id="db-node",
            node_name="Database Analysis Node",
            task="Analyze database issues",
            agents=node_config["agents"],
        )

        available = state.get_available_agents()
        assert len(available) == 2
        assert "log-analyzer" in available
        assert "query-analyzer" in available

        # Mark one as executed
        state.executed_agents.append("log-analyzer")
        available = state.get_available_agents()
        assert len(available) == 1
        assert "query-analyzer" in available

    def test_add_agent_result(self, sample_topology):
        """Test adding agent results."""
        node_config = sample_topology["nodes"][0]
        state = NodeExecutionState(
            node_id="db-node",
            node_name="Database Analysis Node",
            task="Analyze database issues",
            agents=node_config["agents"],
        )

        result = {
            "agent_id": "log-analyzer",
            "output": "Found 5 errors",
            "status": "success",
        }
        state.add_agent_result("log-analyzer", result)

        assert "log-analyzer" in state.agent_results
        assert "log-analyzer" in state.executed_agents


# =============================================================================
# Test Hierarchical Team Engine
# =============================================================================

class TestHierarchicalTeamEngine:
    """Tests for the HierarchicalTeamEngine."""

    @pytest.fixture
    def engine(self, mock_llm_client):
        """Create an engine with mock client."""
        return HierarchicalTeamEngine(
            llm_client=mock_llm_client,
            max_iterations=10,
            node_max_iterations=5,
        )

    def test_parse_json_response_direct(self, engine):
        """Test JSON parsing from direct JSON."""
        content = '{"action": "delegate", "next_node": "db-node", "reasoning": "test"}'
        result = engine._parse_json_response(content)

        assert result["action"] == "delegate"
        assert result["next_node"] == "db-node"

    def test_parse_json_response_markdown(self, engine):
        """Test JSON parsing from markdown code block."""
        content = '''Here is my decision:
```json
{"action": "delegate", "next_node": "db-node", "reasoning": "test"}
```
'''
        result = engine._parse_json_response(content)

        assert result["action"] == "delegate"
        assert result["next_node"] == "db-node"

    def test_parse_json_response_with_extra_text(self, engine):
        """Test JSON parsing with surrounding text."""
        content = '''I will delegate to the database node.
{"action": "delegate", "next_node": "db-node", "reasoning": "analysis needed", "should_continue": true}
This completes my decision.'''
        result = engine._parse_json_response(content)

        assert result["action"] == "delegate"
        assert result["next_node"] == "db-node"

    def test_init_state(self, engine, sample_topology):
        """Test state initialization."""
        state = engine._init_state(
            topology_config=sample_topology,
            input_task="Test task",
            input_context={"key": "value"},
            execution_id="test-exec-001",
        )

        assert state.execution_id == "test-exec-001"
        assert state.input_task == "Test task"
        assert len(state.nodes) == 2
        assert "db-node" in state.nodes
        assert "app-node" in state.nodes

    @pytest.mark.asyncio
    async def test_execute_agent(self, engine, sample_topology):
        """Test single agent execution."""
        agent_config = sample_topology["nodes"][0]["agents"][0]

        result = await engine._execute_agent(
            agent_config=agent_config,
            task="Analyze logs for errors",
            context={"time_range": "1h"},
        )

        assert result["agent_id"] == "log-analyzer"
        assert result["status"] == "success"
        assert "output" in result
        assert result["execution_time_ms"] >= 0

    @pytest.mark.asyncio
    async def test_execute_node(self, engine, sample_topology):
        """Test single node execution with supervisor routing."""
        node_config = sample_topology["nodes"][0]

        result = await engine._execute_node(
            node_id="db-node",
            node_config=node_config,
            task="Analyze database performance",
            context={},
        )

        assert result["node_id"] == "db-node"
        assert result["status"] in ["success", "timeout"]
        assert "agent_results" in result
        assert "supervisor_decisions" in result

    @pytest.mark.asyncio
    async def test_full_execution(self, engine, sample_topology):
        """Test full team execution flow."""
        state = await engine.execute(
            topology_config=sample_topology,
            input_task="Diagnose why the system is slow",
            input_context={"severity": "high"},
            execution_id="full-test-001",
        )

        assert state.execution_id == "full-test-001"
        assert state.is_complete is True or state.iteration_count >= state.max_iterations
        assert len(state.global_supervisor_decisions) > 0
        # At least one node should have been executed
        assert len(state.node_results) > 0 or state.iteration_count > 0

    @pytest.mark.asyncio
    async def test_streaming_execution(self, engine, sample_topology):
        """Test streaming execution produces events."""
        events = []

        async for event in engine.execute_stream(
            topology_config=sample_topology,
            input_task="Diagnose system issues",
            input_context={},
            execution_id="stream-test-001",
        ):
            events.append(event)

        # Should have at least start and complete events
        event_types = [e["type"] for e in events]
        assert "execution_start" in event_types
        assert "execution_complete" in event_types
        # Should have at least one supervisor decision
        assert "global_supervisor_decision" in event_types or "global_supervisor_thinking" in event_types


# =============================================================================
# Test LLM Client Integration
# =============================================================================

class TestLLMClientIntegration:
    """Tests for LLM client with structured output."""

    @pytest.mark.asyncio
    async def test_mock_client_returns_valid_response(self, mock_llm_client):
        """Test that mocked client returns usable responses."""
        messages = [
            LLMMessage(role="system", content="You are a coordinator."),
            LLMMessage(role="user", content="Route this task."),
        ]

        content, tool_calls = await mock_llm_client.complete(messages, "mock-model")

        assert content is not None
        assert len(content) > 0
        assert isinstance(tool_calls, list)


# =============================================================================
# Test Edge Cases
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_empty_topology(self, mock_llm_client):
        """Test handling of empty topology."""
        engine = HierarchicalTeamEngine(llm_client=mock_llm_client, max_iterations=3)

        state = await engine.execute(
            topology_config={"nodes": [], "edges": []},
            input_task="Test with empty topology",
            input_context={},
        )

        # Should complete without errors
        assert state.is_complete is True or state.iteration_count >= 3

    @pytest.mark.asyncio
    async def test_single_node_topology(self, mock_llm_client):
        """Test topology with single node."""
        # Configure mock to return delegate then finish: (content, tool_calls)
        mock_llm_client.complete.side_effect = [
            # Global supervisor: delegate to single-node
            ('{"action": "delegate", "next_node": "single-node", "reasoning": "Only one node", "task_for_node": "Do task", "should_continue": true}', []),
            # Node supervisor: delegate to agent-1
            ('{"action": "delegate", "next_agent": "agent-1", "reasoning": "Only agent", "task_for_agent": "Execute", "node_complete": false}', []),
            # Agent response
            ("Task completed successfully", []),
            # Node supervisor: finish
            ('{"action": "finish", "reasoning": "Done", "node_complete": true}', []),
            # Node synthesis
            ("Node results synthesized: task completed", []),
            # Global supervisor: finish
            ('{"action": "finish", "reasoning": "All done", "should_continue": false}', []),
            # Final synthesis
            ("Final output: All tasks completed successfully", []),
        ]

        engine = HierarchicalTeamEngine(llm_client=mock_llm_client, max_iterations=5)

        topology = {
            "nodes": [
                {
                    "node_id": "single-node",
                    "node_name": "Single Node",
                    "agents": [
                        {
                            "agent_id": "agent-1",
                            "role": "General Agent",
                        }
                    ],
                    "supervisor_config": {},
                }
            ],
            "edges": [],
            "global_supervisor": {},
        }

        state = await engine.execute(
            topology_config=topology,
            input_task="Test single node",
            input_context={},
        )

        # Should be able to execute the single node
        assert state.iteration_count > 0

    @pytest.mark.asyncio
    async def test_max_iterations_limit(self, mock_llm_client):
        """Test that max iterations limit is respected."""
        # Always delegate to trigger iteration limit
        mock_llm_client.complete.return_value = (
            '{"action": "delegate", "next_node": "node-1", "reasoning": "Keep going", "task_for_node": "Do work", "should_continue": true}',
            [],
        )

        engine = HierarchicalTeamEngine(llm_client=mock_llm_client, max_iterations=2)

        topology = {
            "nodes": [
                {
                    "node_id": "node-1",
                    "node_name": "Node 1",
                    "agents": [{"agent_id": "a1"}],
                    "supervisor_config": {},
                },
                {
                    "node_id": "node-2",
                    "node_name": "Node 2",
                    "agents": [{"agent_id": "a2"}],
                    "supervisor_config": {},
                },
            ],
            "global_supervisor": {},
        }

        state = await engine.execute(
            topology_config=topology,
            input_task="Test iteration limit",
            input_context={},
        )

        assert state.iteration_count <= 2
