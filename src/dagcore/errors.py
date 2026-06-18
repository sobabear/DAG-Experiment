"""Exception types raised by dagcore."""

from __future__ import annotations


class GraphError(Exception):
    """Base class for all dagcore errors."""


class NodeNotFoundError(GraphError, IndexError):
    """Raised when a round/agent pair or node index is outside the graph."""

    def __init__(self, node: object) -> None:
        super().__init__(f"Node not found: {node!r}")
        self.node = node


class InvalidEdgeError(GraphError, ValueError):
    """Raised when an edge is invalid for a layered DAG."""
