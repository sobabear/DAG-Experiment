"""dagcore: minimal BPD-style layered signed DAG core.

Only the core graph structure from ChengcanWu/BPD's ``mas/graph.py`` is exposed:
layered node indexing, signed edge storage, edge updates, and edge queries.
No agents, LLM calls, schedulers, detection, or repair algorithms are included.
"""

from .errors import GraphError, InvalidEdgeError, NodeNotFoundError
from .graph import EdgeGraph

__all__ = [
    "EdgeGraph",
    "GraphError",
    "InvalidEdgeError",
    "NodeNotFoundError",
]

__version__ = "0.1.0"
