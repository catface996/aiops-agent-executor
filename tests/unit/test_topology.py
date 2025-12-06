"""Unit tests for topology validation utilities."""

import pytest

from aiops_agent_executor.utils.topology import validate_topology


class TestValidateTopology:
    """Tests for validate_topology function."""

    def test_valid_linear_topology(self):
        """Test a valid linear topology: A -> B -> C."""
        nodes = [
            {"id": "A", "name": "Node A"},
            {"id": "B", "name": "Node B"},
            {"id": "C", "name": "Node C"},
        ]
        edges = [
            {"source": "A", "target": "B"},
            {"source": "B", "target": "C"},
        ]

        result = validate_topology(nodes, edges)

        assert result.valid is True
        assert len(result.errors) == 0

    def test_valid_dag_topology(self):
        """Test a valid DAG topology with branching."""
        nodes = [
            {"id": "start", "name": "Start"},
            {"id": "branch1", "name": "Branch 1"},
            {"id": "branch2", "name": "Branch 2"},
            {"id": "merge", "name": "Merge"},
        ]
        edges = [
            {"source": "start", "target": "branch1"},
            {"source": "start", "target": "branch2"},
            {"source": "branch1", "target": "merge"},
            {"source": "branch2", "target": "merge"},
        ]

        result = validate_topology(nodes, edges)

        assert result.valid is True
        assert len(result.errors) == 0

    def test_cycle_detection_simple(self):
        """Test detection of a simple cycle: A -> B -> A."""
        nodes = [
            {"id": "A", "name": "Node A"},
            {"id": "B", "name": "Node B"},
        ]
        edges = [
            {"source": "A", "target": "B"},
            {"source": "B", "target": "A"},
        ]

        result = validate_topology(nodes, edges)

        assert result.valid is False
        assert any("Cycle detected" in err for err in result.errors)

    def test_cycle_detection_complex(self):
        """Test detection of a longer cycle: A -> B -> C -> A."""
        nodes = [
            {"id": "A", "name": "Node A"},
            {"id": "B", "name": "Node B"},
            {"id": "C", "name": "Node C"},
        ]
        edges = [
            {"source": "A", "target": "B"},
            {"source": "B", "target": "C"},
            {"source": "C", "target": "A"},
        ]

        result = validate_topology(nodes, edges)

        assert result.valid is False
        assert any("Cycle detected" in err for err in result.errors)

    def test_self_loop_detection(self):
        """Test detection of self-loop: A -> A."""
        nodes = [{"id": "A", "name": "Node A"}]
        edges = [{"source": "A", "target": "A"}]

        result = validate_topology(nodes, edges)

        assert result.valid is False
        assert any("Cycle detected" in err for err in result.errors)

    def test_orphan_node_detection(self):
        """Test detection of orphan nodes with no connections."""
        nodes = [
            {"id": "A", "name": "Node A"},
            {"id": "B", "name": "Node B"},
            {"id": "orphan", "name": "Orphan"},
        ]
        edges = [
            {"source": "A", "target": "B"},
        ]

        result = validate_topology(nodes, edges)

        assert result.valid is False
        assert any("Orphan node" in err and "orphan" in err for err in result.errors)

    def test_single_node_not_orphan(self):
        """Test that a single node is not considered orphan."""
        nodes = [{"id": "single", "name": "Single Node"}]
        edges = []

        result = validate_topology(nodes, edges)

        assert result.valid is True
        assert len(result.errors) == 0

    def test_invalid_source_reference(self):
        """Test detection of invalid source node reference."""
        nodes = [
            {"id": "A", "name": "Node A"},
            {"id": "B", "name": "Node B"},
        ]
        edges = [
            {"source": "nonexistent", "target": "B"},
        ]

        result = validate_topology(nodes, edges)

        assert result.valid is False
        assert any("Invalid source node" in err for err in result.errors)

    def test_invalid_target_reference(self):
        """Test detection of invalid target node reference."""
        nodes = [
            {"id": "A", "name": "Node A"},
            {"id": "B", "name": "Node B"},
        ]
        edges = [
            {"source": "A", "target": "nonexistent"},
        ]

        result = validate_topology(nodes, edges)

        assert result.valid is False
        assert any("Invalid target node" in err for err in result.errors)

    def test_empty_nodes(self):
        """Test validation with no valid nodes."""
        nodes = []
        edges = []

        result = validate_topology(nodes, edges)

        assert result.valid is False
        assert any("No valid nodes" in err for err in result.errors)

    def test_missing_edge_fields(self):
        """Test handling of edges with missing source or target."""
        nodes = [
            {"id": "A", "name": "Node A"},
            {"id": "B", "name": "Node B"},
        ]
        edges = [
            {"source": "A"},  # Missing target
            {"target": "B"},  # Missing source
        ]

        result = validate_topology(nodes, edges)

        assert result.valid is False
        assert any("missing source or target" in err for err in result.errors)

    def test_root_node_not_orphan(self):
        """Test that root nodes (only outgoing edges) are not orphans."""
        nodes = [
            {"id": "root", "name": "Root"},
            {"id": "child", "name": "Child"},
        ]
        edges = [
            {"source": "root", "target": "child"},
        ]

        result = validate_topology(nodes, edges)

        assert result.valid is True

    def test_leaf_node_not_orphan(self):
        """Test that leaf nodes (only incoming edges) are not orphans."""
        nodes = [
            {"id": "parent", "name": "Parent"},
            {"id": "leaf", "name": "Leaf"},
        ]
        edges = [
            {"source": "parent", "target": "leaf"},
        ]

        result = validate_topology(nodes, edges)

        assert result.valid is True
