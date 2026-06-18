"""Tests for the topological execution scheduler."""

import pytest

from dagcore import DAG, Executor


def test_linear_pipeline_pipes_outputs():
    g = DAG()
    g.add_node("a", func=lambda inputs: 1)
    g.add_node("b", func=lambda inputs: inputs["a"] + 1)
    g.add_node("c", func=lambda inputs: inputs["b"] * 10)
    g.add_edge("a", "b")
    g.add_edge("b", "c")

    result = Executor(g).run()
    assert result.outputs == {"a": 1, "b": 2, "c": 20}
    assert result.order == ["a", "b", "c"]


def test_diamond_merges_predecessor_outputs():
    g = DAG()
    g.add_node("a", func=lambda inputs: 2)
    g.add_node("b", func=lambda inputs: inputs["a"] + 1)   # 3
    g.add_node("c", func=lambda inputs: inputs["a"] * 5)   # 10
    g.add_node("d", func=lambda inputs: inputs["b"] + inputs["c"])  # 13
    g.add_edge("a", "b")
    g.add_edge("a", "c")
    g.add_edge("b", "d")
    g.add_edge("c", "d")

    result = Executor(g).run()
    assert result.outputs["d"] == 13


def test_executor_passes_context():
    g = DAG()
    g.add_node("a", func=lambda inputs, ctx: ctx["base"])
    g.add_node("b", func=lambda inputs, ctx: inputs["a"] + ctx["base"])
    g.add_edge("a", "b")

    result = Executor(g).run(context={"base": 100})
    assert result.outputs == {"a": 100, "b": 200}


def test_node_without_func_defaults_to_data():
    g = DAG()
    g.add_node("a", data="hello")  # no func -> output is data
    g.add_node("b", func=lambda inputs: inputs["a"].upper())
    g.add_edge("a", "b")

    result = Executor(g).run()
    assert result.outputs == {"a": "hello", "b": "HELLO"}


def test_run_by_layer_callback_receives_generations():
    g = DAG()
    g.add_node("a", func=lambda inputs: 1)
    g.add_node("b", func=lambda inputs: 1)
    g.add_node("c", func=lambda inputs: inputs["a"] + inputs["b"])
    g.add_edge("a", "c")
    g.add_edge("b", "c")

    seen_layers = []
    ex = Executor(g)
    ex.run(on_layer=lambda i, layer, outputs: seen_layers.append(list(layer)))
    assert seen_layers == [["a", "b"], ["c"]]


def test_function_receiving_predecessor_edge_weights():
    # The node func can inspect the graph via the executor's edge weights.
    g = DAG()
    g.add_node("a", func=lambda inputs: 10)
    g.add_node("b", func=lambda inputs: 20)

    def combine(inputs, weights):
        return sum(inputs[p] * weights[p] for p in inputs)

    g.add_node("c", func=combine)
    g.add_edge("a", "c", weight=1)
    g.add_edge("b", "c", weight=-1)

    result = Executor(g, inject_weights=True).run()
    assert result.outputs["c"] == 10 * 1 + 20 * -1  # -10


def test_empty_graph_runs_to_empty_result():
    result = Executor(DAG()).run()
    assert result.outputs == {}
    assert result.order == []
