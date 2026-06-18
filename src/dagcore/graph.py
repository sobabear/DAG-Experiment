"""Core DAG data structures: Node, Edge, and the DAG container.

The :class:`DAG` is the central abstraction of this package.  It stores nodes
keyed by a hashable id and directed edges between them, guaranteeing at all
times that the graph stays acyclic: any edge insertion that would create a
cycle raises :class:`~dagcore.errors.CycleError` and leaves the graph
unchanged.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import (
    Any,
    Dict,
    Hashable,
    Iterable,
    Iterator,
    List,
    Optional,
    Set,
)

from .errors import CycleError, NodeNotFoundError

NodeId = Hashable


@dataclass
class Node:
    """A vertex in the DAG.

    Attributes:
        id: The unique, hashable identifier of the node.
        data: An arbitrary payload associated with the node.
        func: An optional callable used by :class:`~dagcore.executor.Executor`.
    """

    id: NodeId
    data: Any = None
    func: Optional[Any] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return f"Node({self.id!r})"


@dataclass
class Edge:
    """A directed, optionally weighted/signed edge ``source -> target``.

    The ``weight`` is fully generic. It can be omitted (``None``), used as a
    plain numeric weight, or restricted by the caller to a signed value such as
    ``{-1, 0, 1}`` (as in the BPD reference project).
    """

    source: NodeId
    target: NodeId
    weight: Any = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        if self.weight is None:
            return f"Edge({self.source!r} -> {self.target!r})"
        return f"Edge({self.source!r} -> {self.target!r}, w={self.weight!r})"


class DAG:
    """A directed acyclic graph.

    Internally maintains adjacency maps for O(1) successor/predecessor lookup
    and preserves insertion order of nodes (used as a deterministic tie-break
    in topological ordering).
    """

    def __init__(self) -> None:
        self._nodes: "Dict[NodeId, Node]" = {}
        # successors[u][v] = Edge(u -> v)
        self._succ: "Dict[NodeId, Dict[NodeId, Edge]]" = {}
        # predecessors[v][u] = Edge(u -> v)  (mirror of _succ for fast reverse)
        self._pred: "Dict[NodeId, Dict[NodeId, Edge]]" = {}

    # -- Node API -----------------------------------------------------------

    def add_node(
        self,
        node_id: NodeId,
        data: Any = None,
        func: Optional[Any] = None,
        exist_ok: bool = False,
        **metadata: Any,
    ) -> Node:
        """Add a node and return it.

        Raises :class:`ValueError` if the node already exists unless
        ``exist_ok=True``, in which case the existing node is returned untouched.
        """
        if node_id in self._nodes:
            if exist_ok:
                return self._nodes[node_id]
            raise ValueError(f"Node already exists: {node_id!r}")
        node = Node(id=node_id, data=data, func=func, metadata=dict(metadata))
        self._nodes[node_id] = node
        self._succ[node_id] = {}
        self._pred[node_id] = {}
        return node

    def add_nodes_from(self, node_ids: Iterable[NodeId]) -> None:
        """Add several nodes (ignoring any that already exist)."""
        for node_id in node_ids:
            self.add_node(node_id, exist_ok=True)

    def get_node(self, node_id: NodeId) -> Node:
        """Return the :class:`Node`, raising :class:`NodeNotFoundError` if absent."""
        try:
            return self._nodes[node_id]
        except KeyError:
            raise NodeNotFoundError(node_id) from None

    def has_node(self, node_id: NodeId) -> bool:
        return node_id in self._nodes

    def remove_node(self, node_id: NodeId) -> None:
        """Remove a node and every edge incident to it."""
        self._require_node(node_id)
        for pred in list(self._pred[node_id]):
            del self._succ[pred][node_id]
        for succ in list(self._succ[node_id]):
            del self._pred[succ][node_id]
        del self._succ[node_id]
        del self._pred[node_id]
        del self._nodes[node_id]

    def node_ids(self) -> List[NodeId]:
        """Return node ids in insertion order."""
        return list(self._nodes.keys())

    def nodes(self) -> List[Node]:
        return list(self._nodes.values())

    # -- Edge API -----------------------------------------------------------

    def add_edge(
        self,
        source: NodeId,
        target: NodeId,
        weight: Any = None,
        create_missing: bool = False,
        **metadata: Any,
    ) -> Edge:
        """Add (or update) a directed edge ``source -> target``.

        If the edge already exists its weight/metadata are updated. Adding an
        edge that would create a cycle raises :class:`CycleError` and leaves the
        graph unchanged.
        """
        if create_missing:
            self.add_node(source, exist_ok=True)
            self.add_node(target, exist_ok=True)
        else:
            self._require_node(source)
            self._require_node(target)

        if source == target:
            raise CycleError(f"Self-loop is not allowed: {source!r}")

        # Updating an existing edge can never introduce a new cycle.
        if target in self._succ[source]:
            edge = self._succ[source][target]
            edge.weight = weight
            if metadata:
                edge.metadata.update(metadata)
            return edge

        # A new edge u -> v creates a cycle iff u is reachable from v.
        if self._reaches(target, source):
            raise CycleError(
                f"Adding edge {source!r} -> {target!r} would create a cycle"
            )

        edge = Edge(source=source, target=target, weight=weight, metadata=dict(metadata))
        self._succ[source][target] = edge
        self._pred[target][source] = edge
        return edge

    def get_edge(self, source: NodeId, target: NodeId) -> Edge:
        self._require_node(source)
        self._require_node(target)
        try:
            return self._succ[source][target]
        except KeyError:
            raise KeyError(f"No edge {source!r} -> {target!r}") from None

    def has_edge(self, source: NodeId, target: NodeId) -> bool:
        return source in self._succ and target in self._succ[source]

    def remove_edge(self, source: NodeId, target: NodeId) -> None:
        if not self.has_edge(source, target):
            raise KeyError(f"No edge {source!r} -> {target!r}")
        del self._succ[source][target]
        del self._pred[target][source]

    def edges(self) -> List[Edge]:
        """Return all edges."""
        out: List[Edge] = []
        for succ_map in self._succ.values():
            out.extend(succ_map.values())
        return out

    def edge_count(self) -> int:
        return sum(len(s) for s in self._succ.values())

    # -- Relationship queries ----------------------------------------------

    def successors(self, node_id: NodeId) -> List[NodeId]:
        self._require_node(node_id)
        return list(self._succ[node_id].keys())

    def predecessors(self, node_id: NodeId) -> List[NodeId]:
        self._require_node(node_id)
        return list(self._pred[node_id].keys())

    def in_degree(self, node_id: NodeId) -> int:
        self._require_node(node_id)
        return len(self._pred[node_id])

    def out_degree(self, node_id: NodeId) -> int:
        self._require_node(node_id)
        return len(self._succ[node_id])

    def roots(self) -> List[NodeId]:
        """Nodes with no incoming edges (in insertion order)."""
        return [n for n in self._nodes if not self._pred[n]]

    def leaves(self) -> List[NodeId]:
        """Nodes with no outgoing edges (in insertion order)."""
        return [n for n in self._nodes if not self._succ[n]]

    def ancestors(self, node_id: NodeId) -> Set[NodeId]:
        """All nodes that can reach ``node_id`` (excluding itself)."""
        self._require_node(node_id)
        seen: Set[NodeId] = set()
        stack = list(self._pred[node_id].keys())
        while stack:
            cur = stack.pop()
            if cur in seen:
                continue
            seen.add(cur)
            stack.extend(self._pred[cur].keys())
        return seen

    def descendants(self, node_id: NodeId) -> Set[NodeId]:
        """All nodes reachable from ``node_id`` (excluding itself)."""
        self._require_node(node_id)
        seen: Set[NodeId] = set()
        stack = list(self._succ[node_id].keys())
        while stack:
            cur = stack.pop()
            if cur in seen:
                continue
            seen.add(cur)
            stack.extend(self._succ[cur].keys())
        return seen

    # -- Ordering / traversal ----------------------------------------------

    def topological_sort(self) -> List[NodeId]:
        """Return all nodes in a topological order (Kahn's algorithm).

        Ties between nodes with equal in-degree break by insertion order, which
        makes the output deterministic.
        """
        indegree = {n: len(self._pred[n]) for n in self._nodes}
        # Seed the queue in insertion order for determinism.
        queue = deque(n for n in self._nodes if indegree[n] == 0)
        order: List[NodeId] = []
        while queue:
            node = queue.popleft()
            order.append(node)
            for succ in self._succ[node]:
                indegree[succ] -= 1
                if indegree[succ] == 0:
                    queue.append(succ)
        if len(order) != len(self._nodes):  # pragma: no cover - invariant guard
            raise CycleError("Graph contains a cycle")
        return order

    def topological_generations(self) -> List[List[NodeId]]:
        """Group nodes into layers ("generations" / rounds).

        Each layer contains nodes whose predecessors all appear in earlier
        layers. Mirrors the round-by-round layout used by layered DAG systems.
        """
        indegree = {n: len(self._pred[n]) for n in self._nodes}
        current = [n for n in self._nodes if indegree[n] == 0]
        layers: List[List[NodeId]] = []
        seen = 0
        while current:
            layers.append(current)
            seen += len(current)
            nxt: List[NodeId] = []
            for node in current:
                for succ in self._succ[node]:
                    indegree[succ] -= 1
                    if indegree[succ] == 0:
                        nxt.append(succ)
            current = nxt
        if seen != len(self._nodes):  # pragma: no cover - invariant guard
            raise CycleError("Graph contains a cycle")
        return layers

    def is_acyclic(self) -> bool:
        """Always True for a successfully constructed DAG; provided for clarity."""
        try:
            self.topological_sort()
            return True
        except CycleError:  # pragma: no cover - cannot happen via public API
            return False

    def bfs(self, start: NodeId) -> List[NodeId]:
        """Breadth-first traversal following outgoing edges from ``start``."""
        self._require_node(start)
        seen = {start}
        order = [start]
        queue = deque([start])
        while queue:
            node = queue.popleft()
            for succ in self._succ[node]:
                if succ not in seen:
                    seen.add(succ)
                    order.append(succ)
                    queue.append(succ)
        return order

    def dfs(self, start: NodeId) -> List[NodeId]:
        """Depth-first traversal following outgoing edges from ``start``."""
        self._require_node(start)
        seen: Set[NodeId] = set()
        order: List[NodeId] = []

        def _visit(node: NodeId) -> None:
            seen.add(node)
            order.append(node)
            for succ in self._succ[node]:
                if succ not in seen:
                    _visit(succ)

        _visit(start)
        return order

    # -- dunder / helpers ---------------------------------------------------

    def _require_node(self, node_id: NodeId) -> None:
        if node_id not in self._nodes:
            raise NodeNotFoundError(node_id)

    def _reaches(self, start: NodeId, goal: NodeId) -> bool:
        """Return True if ``goal`` is reachable from ``start`` via outgoing edges."""
        if start == goal:
            return True
        stack = [start]
        seen: Set[NodeId] = set()
        while stack:
            cur = stack.pop()
            if cur == goal:
                return True
            if cur in seen:
                continue
            seen.add(cur)
            stack.extend(self._succ[cur].keys())
        return False

    def __len__(self) -> int:
        return len(self._nodes)

    def __contains__(self, node_id: object) -> bool:
        return node_id in self._nodes

    def __iter__(self) -> Iterator[NodeId]:
        return iter(self._nodes)

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return f"DAG(nodes={len(self._nodes)}, edges={self.edge_count()})"
