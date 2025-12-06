"""Agent service layer for CRUD operations.

Handles all business logic for Agent management.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from aiops_agent_executor.core.exceptions import ConflictError, NotFoundError
from aiops_agent_executor.db.models.agent import Agent, AgentStatus


class AgentService:
    """Service class for agent operations."""

    def __init__(self, db: AsyncSession) -> None:
        """Initialize the service with a database session."""
        self.db = db

    async def create(
        self,
        name: str,
        role: str,
        system_prompt: str,
        description: str | None = None,
        provider_id: uuid.UUID | None = None,
        model_id: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        tools: list[str] | None = None,
        tool_config: dict | None = None,
        tags: list[str] | None = None,
        extra_config: dict | None = None,
    ) -> Agent:
        """Create a new agent.

        Args:
            name: Agent display name
            role: Agent role description
            system_prompt: System prompt for the agent
            description: Optional description
            provider_id: LLM provider UUID
            model_id: Model identifier
            temperature: LLM temperature (0-1)
            max_tokens: Maximum output tokens
            tools: List of tool names
            tool_config: Tool configuration
            tags: Agent tags for filtering
            extra_config: Additional configuration

        Returns:
            The created agent

        Raises:
            ConflictError: If an agent with the same name already exists
        """
        existing = await self._get_by_name(name)
        if existing:
            raise ConflictError(
                resource="Agent",
                reason=f"Agent with name '{name}' already exists",
            )

        agent = Agent(
            name=name,
            role=role,
            system_prompt=system_prompt,
            description=description,
            provider_id=provider_id,
            model_id=model_id,
            temperature=temperature,
            max_tokens=max_tokens,
            tools=tools,
            tool_config=tool_config,
            tags=tags,
            extra_config=extra_config,
            status=AgentStatus.ACTIVE,
            version=1,
        )
        self.db.add(agent)
        await self.db.flush()
        await self.db.refresh(agent)
        return agent

    async def get(self, agent_id: uuid.UUID) -> Agent:
        """Get an agent by ID.

        Args:
            agent_id: The agent's UUID

        Returns:
            The agent

        Raises:
            NotFoundError: If the agent doesn't exist
        """
        agent = await self.db.get(Agent, agent_id)
        if not agent:
            raise NotFoundError(resource="Agent", resource_id=str(agent_id))
        return agent

    async def get_by_name(self, name: str) -> Agent:
        """Get an agent by name.

        Args:
            name: The agent's name

        Returns:
            The agent

        Raises:
            NotFoundError: If the agent doesn't exist
        """
        agent = await self._get_by_name(name)
        if not agent:
            raise NotFoundError(resource="Agent", resource_id=name)
        return agent

    async def list(
        self,
        skip: int = 0,
        limit: int = 20,
        status: AgentStatus | None = None,
        provider_id: uuid.UUID | None = None,
        tags: list[str] | None = None,
    ) -> Sequence[Agent]:
        """List agents with optional filtering.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return
            status: Filter by status
            provider_id: Filter by provider
            tags: Filter by tags (any match)

        Returns:
            List of agents
        """
        query = select(Agent).offset(skip).limit(limit)

        if status is not None:
            query = query.where(Agent.status == status)
        if provider_id is not None:
            query = query.where(Agent.provider_id == provider_id)
        if tags:
            query = query.where(Agent.tags.overlap(tags))

        query = query.order_by(Agent.created_at.desc())
        result = await self.db.execute(query)
        return result.scalars().all()

    async def update(
        self,
        agent_id: uuid.UUID,
        name: str | None = None,
        role: str | None = None,
        system_prompt: str | None = None,
        description: str | None = None,
        provider_id: uuid.UUID | None = None,
        model_id: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        tools: list[str] | None = None,
        tool_config: dict | None = None,
        tags: list[str] | None = None,
        extra_config: dict | None = None,
        status: AgentStatus | None = None,
    ) -> Agent:
        """Update an agent.

        Args:
            agent_id: The agent's UUID
            **kwargs: Fields to update

        Returns:
            The updated agent

        Raises:
            NotFoundError: If the agent doesn't exist
            ConflictError: If the new name conflicts with existing agent
        """
        agent = await self.get(agent_id)

        # Check name conflict
        if name is not None and name != agent.name:
            existing = await self._get_by_name(name)
            if existing:
                raise ConflictError(
                    resource="Agent",
                    reason=f"Agent with name '{name}' already exists",
                )
            agent.name = name

        # Update fields
        if role is not None:
            agent.role = role
        if system_prompt is not None:
            agent.system_prompt = system_prompt
            agent.version += 1  # Increment version on prompt change
        if description is not None:
            agent.description = description
        if provider_id is not None:
            agent.provider_id = provider_id
        if model_id is not None:
            agent.model_id = model_id
        if temperature is not None:
            agent.temperature = temperature
        if max_tokens is not None:
            agent.max_tokens = max_tokens
        if tools is not None:
            agent.tools = tools
        if tool_config is not None:
            agent.tool_config = tool_config
        if tags is not None:
            agent.tags = tags
        if extra_config is not None:
            agent.extra_config = extra_config
        if status is not None:
            agent.status = status

        await self.db.flush()
        await self.db.refresh(agent)
        return agent

    async def delete(self, agent_id: uuid.UUID) -> None:
        """Delete an agent.

        Args:
            agent_id: The agent's UUID

        Raises:
            NotFoundError: If the agent doesn't exist
        """
        agent = await self.get(agent_id)
        await self.db.delete(agent)
        await self.db.flush()

    async def _get_by_name(self, name: str) -> Agent | None:
        """Get an agent by name (internal helper)."""
        query = select(Agent).where(Agent.name == name)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    def to_topology_config(self, agent: Agent) -> dict:
        """Convert agent to topology configuration format.

        Args:
            agent: The agent entity

        Returns:
            Dict suitable for use in topology_config
        """
        config = {
            "agent_id": str(agent.id),
            "name": agent.name,
            "role": agent.role,
            "system_prompt": agent.system_prompt,
            "temperature": agent.temperature,
        }
        if agent.provider_id:
            config["provider_id"] = str(agent.provider_id)
        if agent.model_id:
            config["model_id"] = agent.model_id
        if agent.max_tokens:
            config["max_tokens"] = agent.max_tokens
        if agent.tools:
            config["tools"] = agent.tools
        if agent.tool_config:
            config["tool_config"] = agent.tool_config
        return config
