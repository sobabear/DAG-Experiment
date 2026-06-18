"""dagcore: a Core / Vanilla DAG system.

A small, dependency-free, generic Directed Acyclic Graph (DAG) engine providing:

* Typed nodes carrying arbitrary payloads.
* Directed, optionally weighted/signed edges.
* Cycle-safe edge insertion (adding an edge that would create a cycle raises).
* Graph queries: predecessors, successors, roots, leaves, ancestors, descendants.
* Topological ordering (Kahn's algorithm) and layered ("round") grouping.
* A topological execution scheduler that runs node functions and pipes each
  node's output to its successors.

This is the reusable "core" abstraction that higher-level systems (such as the
multi-agent signed-DAG in the BPD reference project) can be built on top of.
"""

from .graph import DAG, Edge, Node
from .errors import CycleError, GraphError, NodeNotFoundError
from .executor import Executor, ExecutionResult

__all__ = [
    "DAG",
    "Node",
    "Edge",
    "Executor",
    "ExecutionResult",
    "GraphError",
    "CycleError",
    "NodeNotFoundError",
]

__version__ = "0.1.0"
