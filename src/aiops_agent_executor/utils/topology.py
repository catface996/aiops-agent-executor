"""Topology validation utilities for Agent team configuration.

Provides functions to validate topology graphs for cycles, orphan nodes,
and invalid references.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ValidationResult:
    """Result of topology validation."""

    valid: bool
    errors: list[str] = field(default_factory=list)


def validate_topology(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
) -> ValidationResult:
    """Validate topology configuration for cycles, orphans, and invalid references.

    Args:
        nodes: List of node configurations with 'id' field
        edges: List of edge configurations with 'source' and 'target' fields

    Returns:
        ValidationResult with valid flag and list of errors
    """
    errors: list[str] = []

    # Extract node IDs
    node_ids = {node.get("id") for node in nodes if node.get("id")}

    if not node_ids:
        errors.append("No valid nodes defined in topology")
        return ValidationResult(valid=False, errors=errors)

    # Build adjacency list and check for invalid references
    adjacency: dict[str, list[str]] = defaultdict(list)
    incoming_edges: dict[str, int] = defaultdict(int)

    for edge in edges:
        source = edge.get("source")
        target = edge.get("target")

        if not source or not target:
            errors.append(f"Edge missing source or target: {edge}")
            continue

        if source not in node_ids:
            errors.append(f"Invalid source node reference: '{source}'")
            continue

        if target not in node_ids:
            errors.append(f"Invalid target node reference: '{target}'")
            continue

        adjacency[source].append(target)
        incoming_edges[target] += 1

    # Check for cycles using DFS
    cycle_errors = _detect_cycles(node_ids, adjacency)
    errors.extend(cycle_errors)

    # Check for orphan nodes (no incoming or outgoing edges, except for root nodes)
    orphan_errors = _detect_orphans(node_ids, adjacency, incoming_edges)
    errors.extend(orphan_errors)

    return ValidationResult(valid=len(errors) == 0, errors=errors)


def _detect_cycles(
    node_ids: set[str],
    adjacency: dict[str, list[str]],
) -> list[str]:
    """Detect cycles in the topology graph using DFS.

    Args:
        node_ids: Set of all node IDs
        adjacency: Adjacency list representation of the graph

    Returns:
        List of error messages for detected cycles
    """
    errors: list[str] = []

    # Track visited state: 0=unvisited, 1=visiting, 2=visited
    state: dict[str, int] = {node_id: 0 for node_id in node_ids}
    path: list[str] = []

    def dfs(node: str) -> bool:
        """DFS to detect cycle. Returns True if cycle found."""
        if state[node] == 1:  # Currently visiting - cycle detected
            cycle_start = path.index(node)
            cycle = path[cycle_start:] + [node]
            errors.append(f"Cycle detected: {' -> '.join(cycle)}")
            return True

        if state[node] == 2:  # Already fully visited
            return False

        state[node] = 1  # Mark as visiting
        path.append(node)

        for neighbor in adjacency.get(node, []):
            if dfs(neighbor):
                return True

        path.pop()
        state[node] = 2  # Mark as fully visited
        return False

    for node_id in node_ids:
        if state[node_id] == 0:
            if dfs(node_id):
                break  # Stop after first cycle found

    return errors


def _detect_orphans(
    node_ids: set[str],
    adjacency: dict[str, list[str]],
    incoming_edges: dict[str, int],
) -> list[str]:
    """Detect orphan nodes that have no connections.

    A node is orphan if it has no incoming edges AND no outgoing edges,
    unless it's the only node in the graph.

    Args:
        node_ids: Set of all node IDs
        adjacency: Adjacency list representation
        incoming_edges: Count of incoming edges per node

    Returns:
        List of error messages for orphan nodes
    """
    errors: list[str] = []

    # If only one node, it's not an orphan
    if len(node_ids) <= 1:
        return errors

    for node_id in node_ids:
        has_outgoing = len(adjacency.get(node_id, [])) > 0
        has_incoming = incoming_edges.get(node_id, 0) > 0

        if not has_outgoing and not has_incoming:
            errors.append(f"Orphan node detected: '{node_id}' has no connections")

    return errors
