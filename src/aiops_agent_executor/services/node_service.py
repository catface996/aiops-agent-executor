"""Node service layer for CRUD operations.

Handles all business logic for Node management within teams.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from aiops_agent_executor.core.exceptions import ConflictError, NotFoundError
from aiops_agent_executor.db.models.agent import (
    Agent,
    Node,
    NodeAgent,
    NodeStatus,
    NodeType,
)


class NodeService:
    """Service class for node operations."""

    def __init__(self, db: AsyncSession) -> None:
        """Initialize the service with a database session."""
        self.db = db

    async def create(
        self,
        name: str,
        team_id: uuid.UUID,
        node_type: NodeType = NodeType.SUPERVISOR,
        description: str | None = None,
        supervisor_provider_id: uuid.UUID | None = None,
        supervisor_model_id: str | None = None,
        supervisor_prompt: str | None = None,
        max_iterations: int = 20,
        parallel_execution: bool = False,
        order_index: int = 0,
        extra_config: dict | None = None,
    ) -> Node:
        """Create a new node.

        Args:
            name: Node display name
            team_id: Parent team UUID
            node_type: Type of node (supervisor, worker, aggregator)
            description: Optional description
            supervisor_provider_id: LLM provider for supervisor
            supervisor_model_id: Model ID for supervisor
            supervisor_prompt: Custom prompt for supervisor
            max_iterations: Maximum iterations for node execution
            parallel_execution: Whether to execute agents in parallel
            order_index: Execution order within team
            extra_config: Additional configuration

        Returns:
            The created node

        Raises:
            ConflictError: If a node with the same name exists in the team
        """
        existing = await self._get_by_name_in_team(name, team_id)
        if existing:
            raise ConflictError(
                resource="Node",
                reason=f"Node with name '{name}' already exists in this team",
            )

        node = Node(
            name=name,
            team_id=team_id,
            node_type=node_type,
            description=description,
            supervisor_provider_id=supervisor_provider_id,
            supervisor_model_id=supervisor_model_id,
            supervisor_prompt=supervisor_prompt,
            max_iterations=max_iterations,
            parallel_execution=parallel_execution,
            order_index=order_index,
            extra_config=extra_config,
            status=NodeStatus.ACTIVE,
        )
        self.db.add(node)
        await self.db.flush()
        await self.db.refresh(node)
        return node

    async def get(self, node_id: uuid.UUID) -> Node:
        """Get a node by ID.

        Args:
            node_id: The node's UUID

        Returns:
            The node

        Raises:
            NotFoundError: If the node doesn't exist
        """
        node = await self.db.get(Node, node_id)
        if not node:
            raise NotFoundError(resource="Node", resource_id=str(node_id))
        return node

    async def get_with_agents(self, node_id: uuid.UUID) -> Node:
        """Get a node with its agents eagerly loaded.

        Args:
            node_id: The node's UUID

        Returns:
            The node with agents loaded

        Raises:
            NotFoundError: If the node doesn't exist
        """
        query = (
            select(Node)
            .where(Node.id == node_id)
            .options(
                selectinload(Node.node_agents).selectinload(NodeAgent.agent)
            )
        )
        result = await self.db.execute(query)
        node = result.scalar_one_or_none()
        if not node:
            raise NotFoundError(resource="Node", resource_id=str(node_id))
        return node

    async def list_by_team(
        self,
        team_id: uuid.UUID,
        status: NodeStatus | None = None,
    ) -> Sequence[Node]:
        """List nodes in a team.

        Args:
            team_id: The team's UUID
            status: Optional status filter

        Returns:
            List of nodes ordered by order_index
        """
        query = select(Node).where(Node.team_id == team_id)

        if status is not None:
            query = query.where(Node.status == status)

        query = query.order_by(Node.order_index)
        result = await self.db.execute(query)
        return result.scalars().all()

    async def update(
        self,
        node_id: uuid.UUID,
        name: str | None = None,
        description: str | None = None,
        node_type: NodeType | None = None,
        supervisor_provider_id: uuid.UUID | None = None,
        supervisor_model_id: str | None = None,
        supervisor_prompt: str | None = None,
        max_iterations: int | None = None,
        parallel_execution: bool | None = None,
        order_index: int | None = None,
        extra_config: dict | None = None,
        status: NodeStatus | None = None,
    ) -> Node:
        """Update a node.

        Args:
            node_id: The node's UUID
            **kwargs: Fields to update

        Returns:
            The updated node

        Raises:
            NotFoundError: If the node doesn't exist
            ConflictError: If the new name conflicts
        """
        node = await self.get(node_id)

        # Check name conflict
        if name is not None and name != node.name:
            existing = await self._get_by_name_in_team(name, node.team_id)
            if existing:
                raise ConflictError(
                    resource="Node",
                    reason=f"Node with name '{name}' already exists in this team",
                )
            node.name = name

        # Update fields
        if description is not None:
            node.description = description
        if node_type is not None:
            node.node_type = node_type
        if supervisor_provider_id is not None:
            node.supervisor_provider_id = supervisor_provider_id
        if supervisor_model_id is not None:
            node.supervisor_model_id = supervisor_model_id
        if supervisor_prompt is not None:
            node.supervisor_prompt = supervisor_prompt
        if max_iterations is not None:
            node.max_iterations = max_iterations
        if parallel_execution is not None:
            node.parallel_execution = parallel_execution
        if order_index is not None:
            node.order_index = order_index
        if extra_config is not None:
            node.extra_config = extra_config
        if status is not None:
            node.status = status

        await self.db.flush()
        await self.db.refresh(node)
        return node

    async def delete(self, node_id: uuid.UUID) -> None:
        """Delete a node.

        Args:
            node_id: The node's UUID

        Raises:
            NotFoundError: If the node doesn't exist
        """
        node = await self.get(node_id)
        await self.db.delete(node)
        await self.db.flush()

    # =========================================================================
    # Agent Association Methods
    # =========================================================================

    async def add_agent(
        self,
        node_id: uuid.UUID,
        agent_id: uuid.UUID,
        order_index: int = 0,
        config_override: dict | None = None,
    ) -> NodeAgent:
        """Add an agent to a node.

        Args:
            node_id: The node's UUID
            agent_id: The agent's UUID
            order_index: Execution order within node
            config_override: Optional configuration overrides

        Returns:
            The created association

        Raises:
            NotFoundError: If node or agent doesn't exist
            ConflictError: If agent is already in node
        """
        # Verify node exists
        await self.get(node_id)

        # Verify agent exists
        agent = await self.db.get(Agent, agent_id)
        if not agent:
            raise NotFoundError(resource="Agent", resource_id=str(agent_id))

        # Check if already associated
        existing = await self._get_node_agent(node_id, agent_id)
        if existing:
            raise ConflictError(
                resource="NodeAgent",
                reason="Agent is already assigned to this node",
            )

        node_agent = NodeAgent(
            node_id=node_id,
            agent_id=agent_id,
            order_index=order_index,
            config_override=config_override,
        )
        self.db.add(node_agent)
        await self.db.flush()
        await self.db.refresh(node_agent)
        return node_agent

    async def remove_agent(
        self,
        node_id: uuid.UUID,
        agent_id: uuid.UUID,
    ) -> None:
        """Remove an agent from a node.

        Args:
            node_id: The node's UUID
            agent_id: The agent's UUID

        Raises:
            NotFoundError: If the association doesn't exist
        """
        node_agent = await self._get_node_agent(node_id, agent_id)
        if not node_agent:
            raise NotFoundError(
                resource="NodeAgent",
                resource_id=f"node={node_id}, agent={agent_id}",
            )
        await self.db.delete(node_agent)
        await self.db.flush()

    async def update_agent_order(
        self,
        node_id: uuid.UUID,
        agent_id: uuid.UUID,
        order_index: int,
    ) -> NodeAgent:
        """Update agent order within a node.

        Args:
            node_id: The node's UUID
            agent_id: The agent's UUID
            order_index: New order index

        Returns:
            The updated association

        Raises:
            NotFoundError: If the association doesn't exist
        """
        node_agent = await self._get_node_agent(node_id, agent_id)
        if not node_agent:
            raise NotFoundError(
                resource="NodeAgent",
                resource_id=f"node={node_id}, agent={agent_id}",
            )
        node_agent.order_index = order_index
        await self.db.flush()
        await self.db.refresh(node_agent)
        return node_agent

    async def list_agents(self, node_id: uuid.UUID) -> Sequence[Agent]:
        """List agents in a node ordered by order_index.

        Args:
            node_id: The node's UUID

        Returns:
            List of agents in execution order
        """
        query = (
            select(Agent)
            .join(NodeAgent)
            .where(NodeAgent.node_id == node_id)
            .order_by(NodeAgent.order_index)
        )
        result = await self.db.execute(query)
        return result.scalars().all()

    # =========================================================================
    # Topology Conversion
    # =========================================================================

    async def to_topology_config(self, node_id: uuid.UUID) -> dict:
        """Convert node to topology configuration format.

        Args:
            node_id: The node's UUID

        Returns:
            Dict suitable for use in topology_config
        """
        node = await self.get_with_agents(node_id)
        agents = []

        for na in sorted(node.node_agents, key=lambda x: x.order_index):
            agent = na.agent
            agent_config = {
                "agent_id": str(agent.id),
                "name": agent.name,
                "role": agent.role,
                "system_prompt": agent.system_prompt,
                "temperature": agent.temperature,
            }
            if agent.provider_id:
                agent_config["provider_id"] = str(agent.provider_id)
            if agent.model_id:
                agent_config["model_id"] = agent.model_id
            if agent.max_tokens:
                agent_config["max_tokens"] = agent.max_tokens
            if agent.tools:
                agent_config["tools"] = agent.tools

            # Apply config overrides
            if na.config_override:
                agent_config.update(na.config_override)

            agents.append(agent_config)

        config = {
            "node_id": str(node.id),
            "node_name": node.name,
            "node_type": node.node_type.value,
            "agents": agents,
            "max_iterations": node.max_iterations,
            "parallel_execution": node.parallel_execution,
        }

        if node.supervisor_provider_id:
            config["supervisor_config"] = {
                "provider_id": str(node.supervisor_provider_id),
                "model_id": node.supervisor_model_id,
            }
            if node.supervisor_prompt:
                config["supervisor_config"]["prompt"] = node.supervisor_prompt

        return config

    # =========================================================================
    # Internal Helpers
    # =========================================================================

    async def _get_by_name_in_team(
        self,
        name: str,
        team_id: uuid.UUID,
    ) -> Node | None:
        """Get a node by name within a team."""
        query = select(Node).where(Node.name == name, Node.team_id == team_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def _get_node_agent(
        self,
        node_id: uuid.UUID,
        agent_id: uuid.UUID,
    ) -> NodeAgent | None:
        """Get a node-agent association."""
        query = select(NodeAgent).where(
            NodeAgent.node_id == node_id,
            NodeAgent.agent_id == agent_id,
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
