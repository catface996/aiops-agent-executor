"""Unit tests for TeamService."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from aiops_agent_executor.core.exceptions import BadRequestError, ConflictError, NotFoundError
from aiops_agent_executor.db.models.team import Team, TeamStatus
from aiops_agent_executor.schemas.team import (
    AgentConfig,
    EdgeConfig,
    GlobalSupervisorConfig,
    NodeConfig,
    SupervisorConfig,
    TeamCreate,
    TopologyConfig,
)
from aiops_agent_executor.services.team_service import TeamService


@pytest.fixture
def mock_db():
    """Create a mock database session."""
    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.refresh = AsyncMock()
    db.delete = AsyncMock()
    db.get = AsyncMock()
    db.execute = AsyncMock()
    return db


@pytest.fixture
def sample_topology():
    """Create a sample topology configuration."""
    return TopologyConfig(
        nodes=[
            NodeConfig(
                node_id="node-1",
                node_name="Test Node 1",
                node_type="service",
                agents=[
                    AgentConfig(
                        agent_id="agent-1",
                        agent_name="Test Agent",
                        model_provider="openai",
                        model_id="gpt-4",
                        system_prompt="You are a test agent",
                        tools=["search"],
                    )
                ],
                supervisor_config=SupervisorConfig(
                    model_provider="openai",
                    model_id="gpt-4",
                    system_prompt="Coordinate tasks",
                    coordination_strategy="adaptive",
                ),
            ),
            NodeConfig(
                node_id="node-2",
                node_name="Test Node 2",
                node_type="database",
                agents=[
                    AgentConfig(
                        agent_id="agent-2",
                        agent_name="DB Agent",
                        model_provider="anthropic",
                        model_id="claude-3",
                        system_prompt="Analyze database",
                        tools=["query"],
                    )
                ],
                supervisor_config=SupervisorConfig(
                    model_provider="anthropic",
                    model_id="claude-3",
                    system_prompt="Coordinate DB tasks",
                    coordination_strategy="round_robin",
                ),
            ),
        ],
        edges=[
            EdgeConfig(
                source_node_id="node-1",
                target_node_id="node-2",
                relation_type="calls",
            )
        ],
        global_supervisor=GlobalSupervisorConfig(
            model_provider="openai",
            model_id="gpt-4",
            system_prompt="Coordinate all nodes",
            coordination_strategy="hierarchical",
        ),
    )


@pytest.fixture
def sample_team_create(sample_topology):
    """Create a sample TeamCreate schema."""
    return TeamCreate(
        team_name="Test Team",
        description="A test team",
        topology=sample_topology,
        timeout_seconds=300,
        max_iterations=50,
    )


@pytest.fixture
def sample_team():
    """Create a sample Team model."""
    team = Team(
        id=uuid.uuid4(),
        name="Test Team",
        description="A test team",
        topology_config={
            "nodes": [{"node_id": "node-1", "node_name": "Test Node"}],
            "edges": [],
        },
        timeout_seconds=300,
        max_iterations=50,
        status=TeamStatus.ACTIVE,
    )
    return team


class TestTeamServiceCreate:
    """Tests for TeamService.create_team method."""

    @pytest.mark.asyncio
    async def test_create_team_success(self, mock_db, sample_team_create):
        """Test successful team creation."""
        # Mock no existing team with same name
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        service = TeamService(mock_db)

        # Mock the refresh to set the ID
        async def mock_refresh(team):
            team.id = uuid.uuid4()

        mock_db.refresh = mock_refresh

        team = await service.create_team(sample_team_create)

        assert team.name == "Test Team"
        assert team.description == "A test team"
        assert team.status == TeamStatus.ACTIVE
        mock_db.add.assert_called_once()
        mock_db.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_team_duplicate_name(self, mock_db, sample_team_create, sample_team):
        """Test team creation with duplicate name fails."""
        # Mock existing team with same name
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_team
        mock_db.execute.return_value = mock_result

        service = TeamService(mock_db)

        with pytest.raises(ConflictError) as exc_info:
            await service.create_team(sample_team_create)

        assert "already exists" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_create_team_invalid_topology(self, mock_db, sample_team_create):
        """Test team creation with invalid topology fails."""
        # Mock no existing team
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        # Create invalid topology with cycle
        sample_team_create.topology.edges = [
            EdgeConfig(source_node_id="node-1", target_node_id="node-2", relation_type="calls"),
            EdgeConfig(source_node_id="node-2", target_node_id="node-1", relation_type="calls"),
        ]

        service = TeamService(mock_db)

        with pytest.raises(BadRequestError) as exc_info:
            await service.create_team(sample_team_create)

        assert "INVALID_TOPOLOGY" in str(exc_info.value.code)


class TestTeamServiceGet:
    """Tests for TeamService.get_team method."""

    @pytest.mark.asyncio
    async def test_get_team_success(self, mock_db, sample_team):
        """Test successful team retrieval."""
        mock_db.get.return_value = sample_team

        service = TeamService(mock_db)
        team = await service.get_team(sample_team.id)

        assert team.id == sample_team.id
        assert team.name == sample_team.name

    @pytest.mark.asyncio
    async def test_get_team_not_found(self, mock_db):
        """Test team retrieval when not found."""
        mock_db.get.return_value = None

        service = TeamService(mock_db)
        team_id = uuid.uuid4()

        with pytest.raises(NotFoundError) as exc_info:
            await service.get_team(team_id)

        assert "Team" in str(exc_info.value)


class TestTeamServiceList:
    """Tests for TeamService.list_teams method."""

    @pytest.mark.asyncio
    async def test_list_teams_success(self, mock_db, sample_team):
        """Test successful team listing."""
        # Mock count query
        count_result = MagicMock()
        count_result.scalar.return_value = 1

        # Mock teams query
        teams_result = MagicMock()
        teams_result.scalars.return_value.all.return_value = [sample_team]

        mock_db.execute.side_effect = [count_result, teams_result]

        service = TeamService(mock_db)
        teams, total = await service.list_teams()

        assert len(teams) == 1
        assert total == 1
        assert teams[0].name == sample_team.name

    @pytest.mark.asyncio
    async def test_list_teams_with_status_filter(self, mock_db, sample_team):
        """Test team listing with status filter."""
        count_result = MagicMock()
        count_result.scalar.return_value = 1

        teams_result = MagicMock()
        teams_result.scalars.return_value.all.return_value = [sample_team]

        mock_db.execute.side_effect = [count_result, teams_result]

        service = TeamService(mock_db)
        teams, total = await service.list_teams(status=TeamStatus.ACTIVE)

        assert len(teams) == 1

    @pytest.mark.asyncio
    async def test_list_teams_empty(self, mock_db):
        """Test team listing when no teams exist."""
        count_result = MagicMock()
        count_result.scalar.return_value = 0

        teams_result = MagicMock()
        teams_result.scalars.return_value.all.return_value = []

        mock_db.execute.side_effect = [count_result, teams_result]

        service = TeamService(mock_db)
        teams, total = await service.list_teams()

        assert len(teams) == 0
        assert total == 0


class TestTeamServiceUpdate:
    """Tests for TeamService.update_team method."""

    @pytest.mark.asyncio
    async def test_update_team_success(self, mock_db, sample_team):
        """Test successful team update."""
        mock_db.get.return_value = sample_team

        # Mock no duplicate name
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        service = TeamService(mock_db)
        update_data = {
            "team_name": "Updated Team",
            "description": "Updated description",
        }

        team = await service.update_team(sample_team.id, update_data)

        assert team.name == "Updated Team"
        assert team.description == "Updated description"
        mock_db.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_team_not_found(self, mock_db):
        """Test team update when team not found."""
        mock_db.get.return_value = None

        service = TeamService(mock_db)
        team_id = uuid.uuid4()

        with pytest.raises(NotFoundError):
            await service.update_team(team_id, {"team_name": "New Name"})

    @pytest.mark.asyncio
    async def test_update_team_duplicate_name(self, mock_db, sample_team):
        """Test team update with duplicate name."""
        mock_db.get.return_value = sample_team

        # Mock existing team with same name
        existing_team = Team(
            id=uuid.uuid4(),
            name="Existing Team",
            description="Existing",
            topology_config={},
            status=TeamStatus.ACTIVE,
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_team
        mock_db.execute.return_value = mock_result

        service = TeamService(mock_db)

        with pytest.raises(ConflictError):
            await service.update_team(sample_team.id, {"team_name": "Existing Team"})


class TestTeamServiceDelete:
    """Tests for TeamService.delete_team method."""

    @pytest.mark.asyncio
    async def test_delete_team_success(self, mock_db, sample_team):
        """Test successful team deletion."""
        mock_db.get.return_value = sample_team

        # Mock no running executions
        count_result = MagicMock()
        count_result.scalar.return_value = 0
        mock_db.execute.return_value = count_result

        service = TeamService(mock_db)
        await service.delete_team(sample_team.id)

        mock_db.delete.assert_called_once_with(sample_team)
        mock_db.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_team_not_found(self, mock_db):
        """Test team deletion when not found."""
        mock_db.get.return_value = None

        service = TeamService(mock_db)
        team_id = uuid.uuid4()

        with pytest.raises(NotFoundError):
            await service.delete_team(team_id)

    @pytest.mark.asyncio
    async def test_delete_team_has_running_executions(self, mock_db, sample_team):
        """Test team deletion fails when has running executions."""
        mock_db.get.return_value = sample_team

        # Mock running executions exist
        count_result = MagicMock()
        count_result.scalar.return_value = 1
        mock_db.execute.return_value = count_result

        service = TeamService(mock_db)

        with pytest.raises(ConflictError) as exc_info:
            await service.delete_team(sample_team.id)

        assert "running executions" in str(exc_info.value).lower()


class TestTeamServiceValidateTopology:
    """Tests for TeamService.validate_topology method."""

    def test_validate_topology_valid(self, mock_db):
        """Test valid topology validation."""
        service = TeamService(mock_db)

        topology = {
            "nodes": [
                {"node_id": "node-1", "node_name": "Node 1"},
                {"node_id": "node-2", "node_name": "Node 2"},
            ],
            "edges": [
                {"source_node_id": "node-1", "target_node_id": "node-2"},
            ],
        }

        result = service.validate_topology(topology)

        assert result.valid is True
        assert len(result.errors) == 0

    def test_validate_topology_with_cycle(self, mock_db):
        """Test topology validation with cycle detection."""
        service = TeamService(mock_db)

        topology = {
            "nodes": [
                {"node_id": "node-1", "node_name": "Node 1"},
                {"node_id": "node-2", "node_name": "Node 2"},
            ],
            "edges": [
                {"source_node_id": "node-1", "target_node_id": "node-2"},
                {"source_node_id": "node-2", "target_node_id": "node-1"},
            ],
        }

        result = service.validate_topology(topology)

        assert result.valid is False
        assert any("cycle" in err.lower() for err in result.errors)

    def test_validate_topology_invalid_edge_reference(self, mock_db):
        """Test topology validation with invalid edge reference."""
        service = TeamService(mock_db)

        topology = {
            "nodes": [
                {"node_id": "node-1", "node_name": "Node 1"},
            ],
            "edges": [
                {"source_node_id": "node-1", "target_node_id": "node-nonexistent"},
            ],
        }

        result = service.validate_topology(topology)

        assert result.valid is False
        assert any("node-nonexistent" in err for err in result.errors)

    def test_validate_topology_empty(self, mock_db):
        """Test topology validation with empty topology is invalid."""
        service = TeamService(mock_db)

        topology = {"nodes": [], "edges": []}

        result = service.validate_topology(topology)

        # Empty topology should be invalid (no nodes defined)
        assert result.valid is False
        assert any("no valid nodes" in err.lower() for err in result.errors)
