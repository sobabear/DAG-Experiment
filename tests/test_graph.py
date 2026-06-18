import pytest

from dagcore import EdgeGraph, InvalidEdgeError, NodeNotFoundError


class TestEdgeGraphLayout:
    def test_tracks_round_layout_and_total_nodes(self):
        graph = EdgeGraph([2, 3, 1])

        assert graph.agents_per_round == [2, 3, 1]
        assert graph.total_nodes == 6
        assert graph.connections == [[0] * 6 for _ in range(6)]

    def test_node_index_maps_round_and_one_based_agent_id(self):
        graph = EdgeGraph([2, 3, 1])

        assert graph.node_index(0, 1) == 0
        assert graph.node_index(0, 2) == 1
        assert graph.node_index(1, 1) == 2
        assert graph.node_index(1, 3) == 4
        assert graph.node_index(2, 1) == 5

    @pytest.mark.parametrize(
        "round_idx,agent_id",
        [(-1, 1), (3, 1), (0, 0), (0, 3), (1, 4)],
    )
    def test_node_index_rejects_out_of_range_nodes(self, round_idx, agent_id):
        graph = EdgeGraph([2, 3, 1])

        with pytest.raises(NodeNotFoundError):
            graph.node_index(round_idx, agent_id)

    @pytest.mark.parametrize("agents_per_round", [[], [2, 0], [1, -1]])
    def test_rejects_invalid_layout(self, agents_per_round):
        with pytest.raises(ValueError):
            EdgeGraph(agents_per_round)


class TestEdgeUpdates:
    def test_update_edge_stores_score_by_receiver_row_and_sender_column(self):
        graph = EdgeGraph([2, 1])

        graph.update_edge(0, 2, 1, 1, -1)

        sender_idx = graph.node_index(0, 2)
        receiver_idx = graph.node_index(1, 1)
        assert graph.connections[receiver_idx][sender_idx] == -1

    def test_update_edge_overwrites_existing_score(self):
        graph = EdgeGraph([1, 1])

        graph.update_edge(0, 1, 1, 1, -1)
        graph.update_edge(0, 1, 1, 1, 1)

        assert graph.connections[1][0] == 1

    def test_zero_score_removes_edge(self):
        graph = EdgeGraph([1, 1])

        graph.update_edge(0, 1, 1, 1, 1)
        graph.update_edge(0, 1, 1, 1, 0)

        assert graph.connections[1][0] == 0
        assert graph.outgoing_edges(0) == []
        assert graph.incoming_edges(1) == []

    def test_sender_round_minus_one_is_ignored_like_bpd(self):
        graph = EdgeGraph([1])

        graph.update_edge(-1, 1, 0, 1, 1)

        assert graph.connections == [[0]]

    @pytest.mark.parametrize(
        "sender_round,receiver_round",
        [(0, 0), (1, 0), (1, 1)],
    )
    def test_rejects_edges_that_do_not_move_to_a_later_round(
        self, sender_round, receiver_round
    ):
        graph = EdgeGraph([1, 1])

        with pytest.raises(InvalidEdgeError):
            graph.update_edge(sender_round, 1, receiver_round, 1, 1)


class TestEdgeQueries:
    def test_outgoing_edges_returns_receiver_index_and_score(self):
        graph = EdgeGraph([1, 2])
        graph.update_edge(0, 1, 1, 1, 1)
        graph.update_edge(0, 1, 1, 2, -1)

        assert graph.outgoing_edges(0) == [(1, 1), (2, -1)]

    def test_incoming_edges_returns_sender_index_and_score(self):
        graph = EdgeGraph([2, 1])
        graph.update_edge(0, 1, 1, 1, 1)
        graph.update_edge(0, 2, 1, 1, -1)

        assert graph.incoming_edges(2) == [(0, 1), (1, -1)]

    @pytest.mark.parametrize("node_idx", [-1, 2])
    def test_outgoing_edges_rejects_out_of_range_index(self, node_idx):
        graph = EdgeGraph([2])

        with pytest.raises(NodeNotFoundError):
            graph.outgoing_edges(node_idx)

    @pytest.mark.parametrize("node_idx", [-1, 2])
    def test_incoming_edges_rejects_out_of_range_index(self, node_idx):
        graph = EdgeGraph([2])

        with pytest.raises(NodeNotFoundError):
            graph.incoming_edges(node_idx)
