"""Minimal BPD-style layered signed DAG core.

The reference BPD project stores its agent communication graph as a layered
adjacency matrix where rows are receivers, columns are senders, and non-zero
cell values are signed edge scores. This module implements only that DAG core:
round/agent indexing, signed edge updates, and incoming/outgoing edge queries.
"""

from __future__ import annotations

from typing import List, Tuple

from .errors import InvalidEdgeError, NodeNotFoundError


class EdgeGraph:
    """Layered signed DAG represented by an adjacency matrix.

    Args:
        agents_per_round: Number of one-based agent nodes in each round.

    Attributes:
        agents_per_round: Copy of the round layout.
        total_nodes: Total node count.
        connections: Matrix where ``connections[receiver][sender]`` is the
            signed edge score. ``0`` means no edge. Direct mutation of this
            matrix bypasses DAG validation; prefer ``update_edge`` for changes.

    """

    def __init__(self, agents_per_round: List[int]) -> None:
        if not agents_per_round:
            raise ValueError("agents_per_round must contain at least one round")
        if any(count <= 0 for count in agents_per_round):
            raise ValueError("each round must contain at least one agent")

        self.agents_per_round = list(agents_per_round)
        self.total_nodes = sum(self.agents_per_round)
        self.connections: List[List[int]] = [
            [0 for _ in range(self.total_nodes)]
            for _ in range(self.total_nodes)
        ]

    def node_index(self, round_idx: int, agent_id: int) -> int:
        """Return the zero-based node index for a round and one-based agent id."""
        self._require_round_agent(round_idx, agent_id)
        return sum(self.agents_per_round[:round_idx]) + agent_id - 1

    def update_edge(
        self,
        sender_round: int,
        sender_id: int,
        receiver_round: int,
        receiver_id: int,
        score: int,
    ) -> None:
        """Add, update, or remove a signed edge.

        This mirrors BPD's ``EdgeGraph.update_edge`` behavior, including the
        ``sender_round < 0`` no-op for initial turns with no sender. To keep the
        structure a DAG, real edges must point from an earlier round to a later
        round. A score of ``0`` leaves/removes the edge because ``0`` is the
        matrix representation for "no edge" in the reference implementation.
        """
        if sender_round < 0:
            return
        if sender_round >= receiver_round:
            raise InvalidEdgeError(
                "DAG edges must point from an earlier round to a later round"
            )

        sender_idx = self.node_index(sender_round, sender_id)
        receiver_idx = self.node_index(receiver_round, receiver_id)
        self.connections[receiver_idx][sender_idx] = score

    def outgoing_edges(self, sender_idx: int) -> List[Tuple[int, int]]:
        """Return ``(receiver_idx, score)`` pairs for non-zero outgoing edges."""
        self._require_node_index(sender_idx)
        pairs: List[Tuple[int, int]] = []
        for receiver_idx in range(self.total_nodes):
            score = self.connections[receiver_idx][sender_idx]
            if score != 0:
                pairs.append((receiver_idx, score))
        return pairs

    def incoming_edges(self, receiver_idx: int) -> List[Tuple[int, int]]:
        """Return ``(sender_idx, score)`` pairs for non-zero incoming edges."""
        self._require_node_index(receiver_idx)
        pairs: List[Tuple[int, int]] = []
        for sender_idx, score in enumerate(self.connections[receiver_idx]):
            if score != 0:
                pairs.append((sender_idx, score))
        return pairs

    def _require_round_agent(self, round_idx: int, agent_id: int) -> None:
        if round_idx < 0 or round_idx >= len(self.agents_per_round):
            raise NodeNotFoundError((round_idx, agent_id))
        if agent_id < 1 or agent_id > self.agents_per_round[round_idx]:
            raise NodeNotFoundError((round_idx, agent_id))

    def _require_node_index(self, node_idx: int) -> None:
        if node_idx < 0 or node_idx >= self.total_nodes:
            raise NodeNotFoundError(node_idx)
