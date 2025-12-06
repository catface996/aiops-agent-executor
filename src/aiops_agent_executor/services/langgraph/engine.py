"""LangGraph-based hierarchical team execution engine.

This module implements the core execution engine using LangGraph for
dynamic supervisor-based routing of tasks to agents.

Architecture:
    Global Supervisor (decides which Node to activate)
           │
           ▼
    ┌──────┴──────┐
    Node A        Node B
    Supervisor    Supervisor
    (decides      (decides
    which Agent)  which Agent)
        │             │
    ┌───┴───┐     ┌───┴───┐
    A1  A2  A3    B1  B2  B3
"""

import asyncio
import json
import logging
import time
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any, Literal

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import END, StateGraph

from aiops_agent_executor.services.langgraph.state import (
    GlobalSupervisorDecision,
    NodeExecutionState,
    NodeSupervisorDecision,
    RouteAction,
    TeamExecutionState,
)
from aiops_agent_executor.services.llm_client import (
    BaseLLMClient,
    LLMClientFactory,
    LLMMessage,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Prompts for Supervisors
# =============================================================================

GLOBAL_SUPERVISOR_SYSTEM_PROMPT = """You are a Global Supervisor coordinating a team of specialized node groups.
Your job is to analyze the task and decide which node should handle it next.

Available nodes and their capabilities:
{node_descriptions}

Current execution state:
- Executed nodes: {executed_nodes}
- Pending results: {pending_results}

Rules:
1. Analyze the task requirements carefully
2. Select the most appropriate node based on its capabilities
3. You can delegate to one node at a time, or run multiple nodes in parallel if their tasks are independent
4. When all necessary work is complete, use action "finish"
5. Always provide clear reasoning for your decisions

You MUST respond with a JSON object matching this exact schema:
{{
    "action": "delegate" | "parallel" | "finish",
    "next_node": "node_id or null",
    "parallel_nodes": ["node_id1", "node_id2"] or [],
    "reasoning": "explanation of your decision",
    "task_for_node": "specific task for the selected node",
    "should_continue": true | false
}}"""

NODE_SUPERVISOR_SYSTEM_PROMPT = """You are a Node Supervisor managing a team of specialized agents.
Your job is to analyze the assigned task and decide which agent should handle it.

Your node: {node_name}
Assigned task: {task}

Available agents in your node:
{agent_descriptions}

Current state:
- Executed agents: {executed_agents}
- Agent results so far: {agent_results}

Rules:
1. Select the agent best suited for the current sub-task
2. You can delegate to one agent, or run multiple in parallel if appropriate
3. When the node's task is complete, use action "finish" and set node_complete to true
4. Synthesize results from agents before marking complete

You MUST respond with a JSON object matching this exact schema:
{{
    "action": "delegate" | "parallel" | "finish",
    "next_agent": "agent_id or null",
    "parallel_agents": ["agent_id1", "agent_id2"] or [],
    "reasoning": "explanation of your decision",
    "task_for_agent": "specific task for the selected agent",
    "node_complete": true | false
}}"""

SYNTHESIS_PROMPT = """You are synthesizing the results from multiple agents/nodes.

Original task: {original_task}

Results to synthesize:
{results}

Please provide a coherent summary that:
1. Integrates all relevant findings
2. Highlights key insights
3. Provides actionable conclusions
4. Notes any conflicts or uncertainties between results"""


class HierarchicalTeamEngine:
    """LangGraph-based execution engine for hierarchical agent teams.

    This engine implements dynamic routing where:
    1. Global Supervisor decides which Node to activate
    2. Node Supervisor decides which Agent within the node to run
    3. Each decision is made by calling an LLM with structured output
    """

    def __init__(
        self,
        llm_client: BaseLLMClient | None = None,
        max_iterations: int = 50,
        node_max_iterations: int = 20,
    ):
        """Initialize the execution engine.

        Args:
            llm_client: Optional LLM client. If not provided, uses factory.
            max_iterations: Maximum global supervisor iterations
            node_max_iterations: Maximum iterations per node
        """
        self._llm_client = llm_client
        self._max_iterations = max_iterations
        self._node_max_iterations = node_max_iterations

    def _get_client(self, provider: str, api_key: str | None = None) -> BaseLLMClient:
        """Get an LLM client."""
        if self._llm_client:
            return self._llm_client
        if not api_key:
            raise ValueError(f"API key required for provider: {provider}")
        return LLMClientFactory.create(provider, api_key=api_key)

    # =========================================================================
    # Global Supervisor Logic
    # =========================================================================

    async def _call_global_supervisor(
        self,
        state: TeamExecutionState,
    ) -> GlobalSupervisorDecision:
        """Call the global supervisor to decide which node to execute next.

        The supervisor uses structured output to return its decision.
        """
        config = state.global_supervisor_config
        provider = config.get("model_provider", "openrouter")
        model = config.get("model_id", "openai/gpt-4o-mini")
        api_key = config.get("api_key")

        client = self._get_client(provider, api_key=api_key)

        # Build node descriptions
        node_descriptions = []
        for node_id, node_config in state.nodes.items():
            name = node_config.get("node_name", node_id)
            node_type = node_config.get("node_type", "agent")
            agents = node_config.get("agents", [])
            agent_info = ", ".join(a.get("role", a.get("agent_id", "unknown")) for a in agents)
            status = "✓ completed" if node_id in state.executed_nodes else "○ available"
            node_descriptions.append(
                f"- {node_id} ({name}): type={node_type}, agents=[{agent_info}] [{status}]"
            )

        # Build pending results summary
        pending_results = []
        for node_id, result in state.node_results.items():
            output = result.get("output", "")[:200]
            pending_results.append(f"- {node_id}: {output}...")

        system_prompt = GLOBAL_SUPERVISOR_SYSTEM_PROMPT.format(
            node_descriptions="\n".join(node_descriptions),
            executed_nodes=state.executed_nodes or "none",
            pending_results="\n".join(pending_results) if pending_results else "none yet",
        )

        messages = [
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(
                role="user",
                content=f"Task: {state.input_task}\n\nContext: {json.dumps(state.input_context)}\n\n"
                        f"Decide which node should execute next.",
            ),
        ]

        content, _ = await client.complete(messages, model, temperature=0.2)

        # Parse structured response
        try:
            decision_data = self._parse_json_response(content)
            decision = GlobalSupervisorDecision(**decision_data)
        except Exception as e:
            logger.warning(f"Failed to parse supervisor decision: {e}, using default")
            # Default: execute first available node
            available = state.get_available_nodes()
            decision = GlobalSupervisorDecision(
                action=RouteAction.DELEGATE if available else RouteAction.FINISH,
                next_node=available[0] if available else None,
                reasoning=f"Default routing due to parse error: {e}",
                task_for_node=state.input_task,
                should_continue=bool(available),
            )

        logger.info(
            f"Global supervisor decision: action={decision.action}, "
            f"next_node={decision.next_node}, reasoning={decision.reasoning[:100]}..."
        )
        return decision

    # =========================================================================
    # Node Supervisor Logic
    # =========================================================================

    async def _call_node_supervisor(
        self,
        node_state: NodeExecutionState,
    ) -> NodeSupervisorDecision:
        """Call the node supervisor to decide which agent to execute next."""
        config = node_state.supervisor_config
        provider = config.get("model_provider", "openrouter")
        model = config.get("model_id", "openai/gpt-4o-mini")
        api_key = config.get("api_key")

        client = self._get_client(provider, api_key=api_key)

        # Build agent descriptions
        agent_descriptions = []
        for agent in node_state.agents:
            agent_id = agent.get("agent_id")
            role = agent.get("role", "unknown")
            tools = agent.get("tools", [])
            status = "✓ executed" if agent_id in node_state.executed_agents else "○ available"
            agent_descriptions.append(
                f"- {agent_id}: role={role}, tools={tools} [{status}]"
            )

        # Build agent results summary
        agent_results_text = []
        for agent_id, result in node_state.agent_results.items():
            output = result.get("output", "")[:150]
            agent_results_text.append(f"- {agent_id}: {output}...")

        system_prompt = NODE_SUPERVISOR_SYSTEM_PROMPT.format(
            node_name=node_state.node_name,
            task=node_state.task,
            agent_descriptions="\n".join(agent_descriptions),
            executed_agents=node_state.executed_agents or "none",
            agent_results="\n".join(agent_results_text) if agent_results_text else "none yet",
        )

        messages = [
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(
                role="user",
                content=f"Decide which agent should handle the task: {node_state.task}",
            ),
        ]

        content, _ = await client.complete(messages, model, temperature=0.2)

        # Parse structured response
        try:
            decision_data = self._parse_json_response(content)
            decision = NodeSupervisorDecision(**decision_data)
        except Exception as e:
            logger.warning(f"Failed to parse node supervisor decision: {e}, using default")
            available = node_state.get_available_agents()
            decision = NodeSupervisorDecision(
                action=RouteAction.DELEGATE if available else RouteAction.FINISH,
                next_agent=available[0] if available else None,
                reasoning=f"Default routing due to parse error: {e}",
                task_for_agent=node_state.task,
                node_complete=not bool(available),
            )

        logger.info(
            f"Node supervisor [{node_state.node_id}] decision: action={decision.action}, "
            f"next_agent={decision.next_agent}"
        )
        return decision

    # =========================================================================
    # Agent Execution
    # =========================================================================

    async def _execute_agent(
        self,
        agent_config: dict[str, Any],
        task: str,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute a single agent with the given task.

        Args:
            agent_config: Agent configuration dict
            task: The task to execute
            context: Additional context

        Returns:
            Agent result dict with output, status, etc.
        """
        start_time = time.time()

        agent_id = agent_config.get("agent_id", "unknown")
        provider = agent_config.get("model_provider", "openrouter")
        model = agent_config.get("model_id", "openai/gpt-4o-mini")
        api_key = agent_config.get("api_key")
        system_prompt = agent_config.get("system_prompt", f"You are agent {agent_id}.")
        temperature = agent_config.get("temperature", 0.7)

        client = self._get_client(provider, api_key=api_key)

        messages = [
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(
                role="user",
                content=f"Task: {task}\n\nContext: {json.dumps(context)}",
            ),
        ]

        try:
            content, _ = await client.complete(messages, model, temperature=temperature)
            execution_time_ms = int((time.time() - start_time) * 1000)

            return {
                "agent_id": agent_id,
                "output": content,
                "status": "success",
                "error": None,
                "execution_time_ms": execution_time_ms,
                "timestamp": datetime.now(UTC).isoformat(),
            }

        except Exception as e:
            execution_time_ms = int((time.time() - start_time) * 1000)
            logger.error(f"Agent {agent_id} execution failed: {e}")
            return {
                "agent_id": agent_id,
                "output": "",
                "status": "failed",
                "error": str(e),
                "execution_time_ms": execution_time_ms,
                "timestamp": datetime.now(UTC).isoformat(),
            }

    # =========================================================================
    # Node Execution (Sub-Graph)
    # =========================================================================

    async def _execute_node(
        self,
        node_id: str,
        node_config: dict[str, Any],
        task: str,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute a single node using its node supervisor.

        This creates a sub-execution loop where the node supervisor
        decides which agents to run until the node's task is complete.
        """
        start_time = time.time()

        node_state = NodeExecutionState(
            node_id=node_id,
            node_name=node_config.get("node_name", node_id),
            task=task,
            context=context,
            agents=node_config.get("agents", []),
            supervisor_config=node_config.get("supervisor_config", {}),
            max_iterations=self._node_max_iterations,
        )

        # Node execution loop
        while not node_state.is_complete and node_state.iteration_count < node_state.max_iterations:
            node_state.iteration_count += 1

            # Get supervisor decision
            decision = await self._call_node_supervisor(node_state)
            node_state.supervisor_decisions.append(decision.model_dump())

            if decision.action == RouteAction.FINISH or decision.node_complete:
                node_state.is_complete = True
                # Synthesize results if we have multiple agents
                if len(node_state.agent_results) > 1:
                    node_state.output = await self._synthesize_results(
                        task,
                        list(node_state.agent_results.values()),
                        node_state.supervisor_config,
                    )
                elif node_state.agent_results:
                    # Single agent - use its output
                    node_state.output = list(node_state.agent_results.values())[0].get("output", "")
                break

            elif decision.action == RouteAction.DELEGATE and decision.next_agent:
                # Execute single agent
                agent_config = next(
                    (a for a in node_state.agents if a.get("agent_id") == decision.next_agent),
                    None
                )
                if agent_config:
                    result = await self._execute_agent(
                        agent_config,
                        decision.task_for_agent or task,
                        context,
                    )
                    node_state.add_agent_result(decision.next_agent, result)
                else:
                    logger.warning(f"Agent {decision.next_agent} not found in node {node_id}")

            elif decision.action == RouteAction.PARALLEL and decision.parallel_agents:
                # Execute multiple agents in parallel
                tasks = []
                for agent_id in decision.parallel_agents:
                    agent_config = next(
                        (a for a in node_state.agents if a.get("agent_id") == agent_id),
                        None
                    )
                    if agent_config:
                        tasks.append(self._execute_agent(
                            agent_config,
                            decision.task_for_agent or task,
                            context,
                        ))

                if tasks:
                    results = await asyncio.gather(*tasks)
                    for result in results:
                        node_state.add_agent_result(result["agent_id"], result)

        execution_time_ms = int((time.time() - start_time) * 1000)

        return {
            "node_id": node_id,
            "node_name": node_state.node_name,
            "status": "success" if node_state.is_complete else "timeout",
            "output": node_state.output,
            "agent_results": node_state.agent_results,
            "supervisor_decisions": node_state.supervisor_decisions,
            "execution_time_ms": execution_time_ms,
            "iterations": node_state.iteration_count,
        }

    # =========================================================================
    # Synthesis
    # =========================================================================

    async def _synthesize_results(
        self,
        original_task: str,
        results: list[dict[str, Any]],
        supervisor_config: dict[str, Any],
    ) -> str:
        """Synthesize results from multiple agents/nodes."""
        provider = supervisor_config.get("model_provider", "openrouter")
        model = supervisor_config.get("model_id", "openai/gpt-4o-mini")
        api_key = supervisor_config.get("api_key")

        client = self._get_client(provider, api_key=api_key)

        results_text = []
        for i, result in enumerate(results, 1):
            agent_id = result.get("agent_id", result.get("node_id", f"source_{i}"))
            output = result.get("output", "")
            results_text.append(f"[{agent_id}]:\n{output}")

        messages = [
            LLMMessage(
                role="system",
                content=SYNTHESIS_PROMPT.format(
                    original_task=original_task,
                    results="\n\n".join(results_text),
                ),
            ),
            LLMMessage(role="user", content="Please synthesize these results."),
        ]

        content, _ = await client.complete(messages, model, temperature=0.3)
        return content

    # =========================================================================
    # Main Execution Entry Points
    # =========================================================================

    async def execute(
        self,
        topology_config: dict[str, Any],
        input_task: str,
        input_context: dict[str, Any] | None = None,
        execution_id: str | None = None,
    ) -> TeamExecutionState:
        """Execute a team with the given topology and task.

        This is the main entry point for non-streaming execution.

        Args:
            topology_config: The team topology configuration
            input_task: The task to execute
            input_context: Optional additional context
            execution_id: Optional execution ID

        Returns:
            Final execution state with results
        """
        # Initialize state
        state = self._init_state(
            topology_config,
            input_task,
            input_context or {},
            execution_id,
        )

        # Main execution loop
        while not state.is_complete and state.iteration_count < state.max_iterations:
            # Get global supervisor decision
            decision = await self._call_global_supervisor(state)
            state.add_supervisor_decision(decision)

            if decision.action == RouteAction.FINISH or not decision.should_continue:
                state.is_complete = True
                break

            elif decision.action == RouteAction.DELEGATE and decision.next_node:
                # Execute single node
                node_config = state.nodes.get(decision.next_node)
                if node_config:
                    result = await self._execute_node(
                        decision.next_node,
                        node_config,
                        decision.task_for_node or input_task,
                        input_context or {},
                    )
                    state.add_node_result(decision.next_node, result)

            elif decision.action == RouteAction.PARALLEL and decision.parallel_nodes:
                # Execute multiple nodes in parallel
                tasks = []
                for node_id in decision.parallel_nodes:
                    node_config = state.nodes.get(node_id)
                    if node_config:
                        tasks.append(self._execute_node(
                            node_id,
                            node_config,
                            decision.task_for_node or input_task,
                            input_context or {},
                        ))

                if tasks:
                    results = await asyncio.gather(*tasks)
                    for result in results:
                        state.add_node_result(result["node_id"], result)

        # Final synthesis
        if state.node_results:
            state.final_output = await self._synthesize_results(
                input_task,
                list(state.node_results.values()),
                state.global_supervisor_config,
            )

        return state

    async def execute_stream(
        self,
        topology_config: dict[str, Any],
        input_task: str,
        input_context: dict[str, Any] | None = None,
        execution_id: str | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Execute with streaming events.

        Yields events during execution for real-time monitoring.

        Args:
            topology_config: The team topology configuration
            input_task: The task to execute
            input_context: Optional additional context
            execution_id: Optional execution ID

        Yields:
            Event dicts with type, data, and timestamp
        """
        state = self._init_state(
            topology_config,
            input_task,
            input_context or {},
            execution_id,
        )

        yield {
            "type": "execution_start",
            "data": {
                "execution_id": state.execution_id,
                "team_id": state.team_id,
                "task": input_task,
            },
            "timestamp": datetime.now(UTC).isoformat(),
        }

        while not state.is_complete and state.iteration_count < state.max_iterations:
            # Global supervisor decision
            yield {
                "type": "global_supervisor_thinking",
                "data": {"iteration": state.iteration_count},
                "timestamp": datetime.now(UTC).isoformat(),
            }

            decision = await self._call_global_supervisor(state)
            state.add_supervisor_decision(decision)

            yield {
                "type": "global_supervisor_decision",
                "data": decision.model_dump(),
                "timestamp": datetime.now(UTC).isoformat(),
            }

            if decision.action == RouteAction.FINISH or not decision.should_continue:
                state.is_complete = True
                break

            # Execute node(s)
            nodes_to_execute = (
                [decision.next_node] if decision.action == RouteAction.DELEGATE
                else decision.parallel_nodes
            )

            for node_id in nodes_to_execute:
                if not node_id:
                    continue

                yield {
                    "type": "node_start",
                    "data": {"node_id": node_id},
                    "timestamp": datetime.now(UTC).isoformat(),
                }

                node_config = state.nodes.get(node_id)
                if node_config:
                    result = await self._execute_node(
                        node_id,
                        node_config,
                        decision.task_for_node or input_task,
                        input_context or {},
                    )
                    state.add_node_result(node_id, result)

                    # Emit agent results
                    for agent_id, agent_result in result.get("agent_results", {}).items():
                        yield {
                            "type": "agent_result",
                            "data": {
                                "node_id": node_id,
                                "agent_id": agent_id,
                                "output": agent_result.get("output", "")[:500],
                                "status": agent_result.get("status"),
                            },
                            "timestamp": datetime.now(UTC).isoformat(),
                        }

                    yield {
                        "type": "node_complete",
                        "data": {
                            "node_id": node_id,
                            "status": result.get("status"),
                            "output": result.get("output", "")[:500],
                        },
                        "timestamp": datetime.now(UTC).isoformat(),
                    }

        # Final synthesis
        if state.node_results:
            yield {
                "type": "synthesis_start",
                "data": {},
                "timestamp": datetime.now(UTC).isoformat(),
            }

            state.final_output = await self._synthesize_results(
                input_task,
                list(state.node_results.values()),
                state.global_supervisor_config,
            )

        yield {
            "type": "execution_complete",
            "data": {
                "execution_id": state.execution_id,
                "status": "success" if state.is_complete else "timeout",
                "output": state.final_output,
                "iterations": state.iteration_count,
            },
            "timestamp": datetime.now(UTC).isoformat(),
        }

    # =========================================================================
    # Helpers
    # =========================================================================

    def _init_state(
        self,
        topology_config: dict[str, Any],
        input_task: str,
        input_context: dict[str, Any],
        execution_id: str | None,
    ) -> TeamExecutionState:
        """Initialize execution state from topology config."""
        nodes = {}
        for node in topology_config.get("nodes", []):
            node_id = node.get("node_id") or node.get("id")
            if node_id:
                nodes[node_id] = node

        return TeamExecutionState(
            execution_id=execution_id or str(uuid.uuid4()),
            team_id=topology_config.get("team_id", "unknown"),
            input_task=input_task,
            input_context=input_context,
            nodes=nodes,
            edges=topology_config.get("edges", []),
            global_supervisor_config=topology_config.get("global_supervisor", {}),
            max_iterations=self._max_iterations,
        )

    def _parse_json_response(self, content: str) -> dict[str, Any]:
        """Parse JSON from LLM response, handling markdown code blocks and mixed text."""
        content = content.strip()

        # Try to extract JSON from markdown code blocks
        if "```json" in content:
            start = content.find("```json") + 7
            end = content.find("```", start)
            if end > start:
                content = content[start:end].strip()
        elif "```" in content:
            start = content.find("```") + 3
            end = content.find("```", start)
            if end > start:
                content = content[start:end].strip()

        # Try to find JSON object anywhere in the content
        json_start = content.find("{")
        if json_start >= 0:
            # Find matching closing brace
            brace_count = 0
            json_end = json_start
            for i, char in enumerate(content[json_start:], start=json_start):
                if char == "{":
                    brace_count += 1
                elif char == "}":
                    brace_count -= 1
                    if brace_count == 0:
                        json_end = i + 1
                        break
            content = content[json_start:json_end]

        return json.loads(content)


# =============================================================================
# Factory function for easy instantiation
# =============================================================================

def create_hierarchical_engine(
    llm_client: BaseLLMClient | None = None,
    max_iterations: int = 50,
) -> HierarchicalTeamEngine:
    """Create a new hierarchical team engine.

    Args:
        llm_client: Optional custom LLM client
        max_iterations: Maximum supervisor iterations

    Returns:
        Configured HierarchicalTeamEngine
    """
    return HierarchicalTeamEngine(
        llm_client=llm_client,
        max_iterations=max_iterations,
    )
