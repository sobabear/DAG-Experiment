"""Tests for the core DAG data structures and queries."""

import pytest

from dagcore import DAG, CycleError, NodeNotFoundError


# --- Node management -------------------------------------------------------

def test_add_and_get_node():
    g = DAG()
    node = g.add_node("a", data={"x": 1})
    assert node.id == "a"
    assert node.data == {"x": 1}
    assert g.has_node("a")
    assert g.get_node("a") is node
    assert len(g) == 1
    assert "a" in g


def test_add_duplicate_node_raises():
    g = DAG()
    g.add_node("a")
    with pytest.raises(Exception):
        g.add_node("a")


def test_add_node_idempotent_with_flag():
    g = DAG()
    g.add_node("a", data=1)
    # exist_ok lets you re-declare without error and returns existing node
    node = g.add_node("a", exist_ok=True)
    assert node.data == 1
    assert len(g) == 1


def test_get_missing_node_raises():
    g = DAG()
    with pytest.raises(NodeNotFoundError):
        g.get_node("nope")


def test_remove_node_removes_incident_edges():
    g = DAG()
    g.add_nodes_from(["a", "b", "c"])
    g.add_edge("a", "b")
    g.add_edge("b", "c")
    g.remove_node("b")
    assert not g.has_node("b")
    assert not g.has_edge("a", "b")
    assert not g.has_edge("b", "c")
    assert g.successors("a") == []
    assert g.predecessors("c") == []


def test_add_nodes_from():
    g = DAG()
    g.add_nodes_from(["a", "b", "c"])
    assert set(g.node_ids()) == {"a", "b", "c"}


# --- Edge management -------------------------------------------------------

def test_add_edge_creates_relationship():
    g = DAG()
    g.add_nodes_from(["a", "b"])
    edge = g.add_edge("a", "b")
    assert edge.source == "a"
    assert edge.target == "b"
    assert g.has_edge("a", "b")
    assert g.successors("a") == ["b"]
    assert g.predecessors("b") == ["a"]
    assert g.edge_count() == 1


def test_add_edge_autocreates_nodes():
    g = DAG()
    g.add_edge("a", "b", create_missing=True)
    assert g.has_node("a") and g.has_node("b")


def test_add_edge_missing_node_raises_by_default():
    g = DAG()
    g.add_node("a")
    with pytest.raises(NodeNotFoundError):
        g.add_edge("a", "b")


def test_edge_weight_and_sign():
    g = DAG()
    g.add_nodes_from(["a", "b", "c"])
    g.add_edge("a", "b", weight=1)
    g.add_edge("a", "c", weight=-1)
    assert g.get_edge("a", "b").weight == 1
    assert g.get_edge("a", "c").weight == -1


def test_self_loop_is_a_cycle():
    g = DAG()
    g.add_node("a")
    with pytest.raises(CycleError):
        g.add_edge("a", "a")


def test_adding_edge_that_creates_cycle_raises():
    g = DAG()
    g.add_nodes_from(["a", "b", "c"])
    g.add_edge("a", "b")
    g.add_edge("b", "c")
    with pytest.raises(CycleError):
        g.add_edge("c", "a")  # would close the loop
    # graph must be unchanged after the failed insert
    assert not g.has_edge("c", "a")
    assert g.edge_count() == 2


def test_duplicate_edge_updates_weight():
    g = DAG()
    g.add_nodes_from(["a", "b"])
    g.add_edge("a", "b", weight=1)
    g.add_edge("a", "b", weight=5)
    assert g.get_edge("a", "b").weight == 5
    assert g.edge_count() == 1


def test_remove_edge():
    g = DAG()
    g.add_nodes_from(["a", "b"])
    g.add_edge("a", "b")
    g.remove_edge("a", "b")
    assert not g.has_edge("a", "b")


def test_in_out_degree():
    g = DAG()
    g.add_nodes_from(["a", "b", "c"])
    g.add_edge("a", "c")
    g.add_edge("b", "c")
    assert g.in_degree("c") == 2
    assert g.out_degree("a") == 1
    assert g.in_degree("a") == 0


# --- Queries ---------------------------------------------------------------

def _diamond():
    # a -> b -> d ; a -> c -> d
    g = DAG()
    g.add_nodes_from(["a", "b", "c", "d"])
    g.add_edge("a", "b")
    g.add_edge("a", "c")
    g.add_edge("b", "d")
    g.add_edge("c", "d")
    return g


def test_roots_and_leaves():
    g = _diamond()
    assert g.roots() == ["a"]
    assert g.leaves() == ["d"]


def test_ancestors_and_descendants():
    g = _diamond()
    assert g.descendants("a") == {"b", "c", "d"}
    assert g.ancestors("d") == {"a", "b", "c"}
    assert g.ancestors("a") == set()
    assert g.descendants("d") == set()


def test_edges_listing():
    g = _diamond()
    edges = {(e.source, e.target) for e in g.edges()}
    assert edges == {("a", "b"), ("a", "c"), ("b", "d"), ("c", "d")}
