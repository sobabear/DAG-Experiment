"""Exception types raised by dagcore."""

from __future__ import annotations


class GraphError(Exception):
    """Base class for all dagcore errors."""


class NodeNotFoundError(GraphError, KeyError):
    """Raised when an operation references a node id that does not exist."""

    def __init__(self, node_id: object) -> None:
        super().__init__(f"Node not found: {node_id!r}")
        self.node_id = node_id


class CycleError(GraphError):
    """Raised when an operation would introduce a cycle into the DAG."""
