"""Team service layer for CRUD operations.

Handles all business logic for Agent team management including topology validation.
"""

import uuid
from collections.abc import Sequence
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from aiops_agent_executor.core.exceptions import BadRequestError, ConflictError, NotFoundError
from aiops_agent_executor.db.models.team import ExecutionStatus, Team, TeamStatus
from aiops_agent_executor.schemas.team import TeamCreate
from aiops_agent_executor.utils.topology import ValidationResult, validate_topology


class TeamService:
    """Service class for team operations."""

    def __init__(self, db: AsyncSession) -> None:
        """Initialize the service with a database session."""
        self.db = db

    async def create_team(self, team_in: TeamCreate) -> Team:
        """Create a new team with topology validation.

        Args:
            team_in: Team creation data including topology configuration

        Returns:
            The created team

        Raises:
            ConflictError: If a team with the same name already exists
            BadRequestError: If topology validation fails
        """
        # Check for duplicate name
        existing = await self._get_team_by_name(team_in.team_name)
        if existing:
            raise ConflictError(
                resource="Team",
                reason=f"Team with name '{team_in.team_name}' already exists",
            )

        # Validate topology
        validation_result = self.validate_topology(team_in.topology.model_dump())
        if not validation_result.valid:
            raise BadRequestError(
                message="Topology validation failed",
                code="INVALID_TOPOLOGY",
                details={"errors": validation_result.errors},
            )

        team = Team(
            name=team_in.team_name,
            description=team_in.description,
            topology_config=team_in.topology.model_dump(),
            timeout_seconds=team_in.timeout_seconds,
            max_iterations=team_in.max_iterations,
            status=TeamStatus.ACTIVE,
        )
        self.db.add(team)
        await self.db.flush()
        await self.db.refresh(team)
        return team

    async def get_team(self, team_id: uuid.UUID) -> Team:
        """Get a team by ID.

        Args:
            team_id: The team's UUID

        Returns:
            The team

        Raises:
            NotFoundError: If the team doesn't exist
        """
        team = await self.db.get(Team, team_id)
        if not team:
            raise NotFoundError(resource="Team", resource_id=str(team_id))
        return team

    async def list_teams(
        self,
        skip: int = 0,
        limit: int = 20,
        status: TeamStatus | None = None,
    ) -> tuple[Sequence[Team], int]:
        """List teams with optional filtering.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return
            status: Filter by team status (None = no filter)

        Returns:
            Tuple of (list of teams, total count)
        """
        # Build query
        query = select(Team).order_by(Team.created_at.desc())

        if status is not None:
            query = query.where(Team.status == status)

        # Get total count
        count_query = select(func.count()).select_from(Team)
        if status is not None:
            count_query = count_query.where(Team.status == status)
        count_result = await self.db.execute(count_query)
        total = count_result.scalar() or 0

        # Get paginated results
        query = query.offset(skip).limit(limit)
        result = await self.db.execute(query)
        teams = result.scalars().all()

        return teams, total

    async def update_team(
        self,
        team_id: uuid.UUID,
        update_data: dict[str, Any],
    ) -> Team:
        """Update an existing team.

        Args:
            team_id: The team's UUID
            update_data: Dictionary of fields to update

        Returns:
            The updated team

        Raises:
            NotFoundError: If the team doesn't exist
            ConflictError: If the new name conflicts with existing team
            BadRequestError: If topology validation fails
        """
        team = await self.get_team(team_id)

        # Check for name conflict if name is being updated
        if "team_name" in update_data and update_data["team_name"] != team.name:
            existing = await self._get_team_by_name(update_data["team_name"])
            if existing:
                raise ConflictError(
                    resource="Team",
                    reason=f"Team with name '{update_data['team_name']}' already exists",
                )
            team.name = update_data["team_name"]

        # Validate topology if being updated
        if "topology" in update_data:
            topology_data = update_data["topology"]
            if isinstance(topology_data, dict):
                validation_result = self.validate_topology(topology_data)
                if not validation_result.valid:
                    raise BadRequestError(
                        message="Topology validation failed",
                        code="INVALID_TOPOLOGY",
                        details={"errors": validation_result.errors},
                    )
                team.topology_config = topology_data

        # Update other fields
        if "description" in update_data:
            team.description = update_data["description"]
        if "timeout_seconds" in update_data:
            team.timeout_seconds = update_data["timeout_seconds"]
        if "max_iterations" in update_data:
            team.max_iterations = update_data["max_iterations"]
        if "status" in update_data:
            team.status = update_data["status"]

        await self.db.flush()
        await self.db.refresh(team)
        return team

    async def delete_team(self, team_id: uuid.UUID) -> None:
        """Delete a team.

        Args:
            team_id: The team's UUID

        Raises:
            NotFoundError: If the team doesn't exist
            ConflictError: If the team has running executions
        """
        team = await self.get_team(team_id)

        # Check for running executions
        has_running = await self._has_running_executions(team_id)
        if has_running:
            raise ConflictError(
                resource="Team",
                reason="Cannot delete team with running executions. Cancel them first.",
            )

        await self.db.delete(team)
        await self.db.flush()

    def validate_topology(self, topology_config: dict[str, Any]) -> ValidationResult:
        """Validate a topology configuration.

        Args:
            topology_config: The topology configuration dict

        Returns:
            ValidationResult with valid flag and errors
        """
        nodes = topology_config.get("nodes", [])
        edges = topology_config.get("edges", [])

        # Convert nodes to the format expected by validate_topology
        node_list = []
        for node in nodes:
            node_id = node.get("node_id") or node.get("id")
            if node_id:
                node_list.append({"id": node_id, **node})

        # Convert edges to the format expected by validate_topology
        edge_list = []
        for edge in edges:
            source = edge.get("source_node_id") or edge.get("source")
            target = edge.get("target_node_id") or edge.get("target")
            if source and target:
                edge_list.append({"source": source, "target": target, **edge})

        return validate_topology(node_list, edge_list)

    async def _get_team_by_name(self, name: str) -> Team | None:
        """Get a team by name.

        Args:
            name: The team name

        Returns:
            The team if found, None otherwise
        """
        query = select(Team).where(Team.name == name)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def _has_running_executions(self, team_id: uuid.UUID) -> bool:
        """Check if a team has running executions.

        Args:
            team_id: The team's UUID

        Returns:
            True if there are running executions, False otherwise
        """
        from aiops_agent_executor.db.models.team import Execution

        query = (
            select(func.count())
            .select_from(Execution)
            .where(Execution.team_id == team_id)
            .where(Execution.status == ExecutionStatus.RUNNING)
        )
        result = await self.db.execute(query)
        count = result.scalar() or 0
        return count > 0
