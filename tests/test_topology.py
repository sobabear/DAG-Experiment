"""Tests for topological ordering, layering, and traversal."""

import pytest

from dagcore import DAG


def _diamond():
    g = DAG()
    g.add_nodes_from(["a", "b", "c", "d"])
    g.add_edge("a", "b")
    g.add_edge("a", "c")
    g.add_edge("b", "d")
    g.add_edge("c", "d")
    return g


def _is_valid_topo_order(g, order):
    pos = {n: i for i, n in enumerate(order)}
    assert set(order) == set(g.node_ids())
    for e in g.edges():
        assert pos[e.source] < pos[e.target]
    return True


def test_topological_sort_valid():
    g = _diamond()
    order = g.topological_sort()
    assert _is_valid_topo_order(g, order)
    assert order[0] == "a"
    assert order[-1] == "d"


def test_topological_sort_deterministic_tiebreak():
    # With no constraints between them, ties should break by insertion order.
    g = DAG()
    g.add_nodes_from(["x", "y", "z"])
    assert g.topological_sort() == ["x", "y", "z"]


def test_topological_generations_layers():
    g = _diamond()
    layers = g.topological_generations()
    assert layers == [["a"], ["b", "c"], ["d"]]


def test_is_acyclic_true_for_dag():
    g = _diamond()
    assert g.is_acyclic() is True


def test_bfs_order():
    g = _diamond()
    assert g.bfs("a") == ["a", "b", "c", "d"]


def test_dfs_order():
    g = _diamond()
    # DFS visits a, then b's subtree before c's
    assert g.dfs("a") == ["a", "b", "d", "c"]


def test_topological_sort_single_node():
    g = DAG()
    g.add_node("solo")
    assert g.topological_sort() == ["solo"]


def test_topological_sort_empty_graph():
    g = DAG()
    assert g.topological_sort() == []
    assert g.topological_generations() == []
