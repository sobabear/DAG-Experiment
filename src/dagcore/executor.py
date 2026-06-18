"""Topological execution scheduler for a :class:`~dagcore.graph.DAG`.

The :class:`Executor` walks the graph in topological order. For each node it
calls the node's ``func`` (if any), passing in the outputs already produced by
that node's predecessors, and stores the return value. Successors then receive
those values as their inputs -- i.e. data flows along the edges of the DAG.

Node functions are called flexibly based on their declared parameters:

* ``func(inputs)``               -> mapping ``{predecessor_id: output}``
* ``func(inputs, context)``      -> also the shared run-level ``context`` dict
* ``func(inputs, weights)``      -> when ``inject_weights=True``; ``weights`` is
                                    ``{predecessor_id: edge_weight}``
* ``func(inputs, context, weights)`` -> all three

A node without a ``func`` simply yields its ``data`` attribute as its output,
which makes it convenient to use nodes as constant/source values.
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from .graph import DAG, NodeId

# Signature: (round_index, layer_node_ids, outputs_so_far) -> None
LayerCallback = Callable[[int, List[NodeId], Dict[NodeId, Any]], None]


@dataclass
class ExecutionResult:
    """The result of running an :class:`Executor`.

    Attributes:
        outputs: Mapping of node id -> value produced for that node.
        order: The topological order in which nodes were executed.
        generations: The layered grouping used during execution.
    """

    outputs: Dict[NodeId, Any] = field(default_factory=dict)
    order: List[NodeId] = field(default_factory=list)
    generations: List[List[NodeId]] = field(default_factory=list)


class Executor:
    """Runs node functions over a DAG in dependency order."""

    def __init__(self, graph: DAG, inject_weights: bool = False) -> None:
        self.graph = graph
        self.inject_weights = inject_weights

    def run(
        self,
        context: Optional[Dict[str, Any]] = None,
        on_layer: Optional[LayerCallback] = None,
    ) -> ExecutionResult:
        """Execute the whole graph.

        Args:
            context: An optional dict made available to node functions that
                declare a ``context`` parameter.
            on_layer: Optional callback invoked once per topological generation
                with ``(layer_index, node_ids, outputs_so_far)``.

        Returns:
            An :class:`ExecutionResult` with every node's output.
        """
        ctx = context or {}
        outputs: Dict[NodeId, Any] = {}
        order: List[NodeId] = []
        generations = self.graph.topological_generations()

        for layer_index, layer in enumerate(generations):
            for node_id in layer:
                outputs[node_id] = self._run_node(node_id, outputs, ctx)
                order.append(node_id)
            if on_layer is not None:
                on_layer(layer_index, list(layer), outputs)

        return ExecutionResult(outputs=outputs, order=order, generations=generations)

    # -- internal -----------------------------------------------------------

    def _run_node(
        self,
        node_id: NodeId,
        outputs: Dict[NodeId, Any],
        ctx: Dict[str, Any],
    ) -> Any:
        node = self.graph.get_node(node_id)
        inputs = {p: outputs[p] for p in self.graph.predecessors(node_id)}

        if node.func is None:
            return node.data

        kwargs = self._build_kwargs(node.func, node_id, inputs, ctx)
        return node.func(**kwargs)

    def _build_kwargs(
        self,
        func: Callable[..., Any],
        node_id: NodeId,
        inputs: Dict[NodeId, Any],
        ctx: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Map available values onto the function's declared parameters."""
        try:
            params = inspect.signature(func).parameters
        except (TypeError, ValueError):  # builtins without signatures
            return {}

        available: Dict[str, Any] = {
            "inputs": inputs,
            "context": ctx,
            "ctx": ctx,
            "node_id": node_id,
        }
        if self.inject_weights:
            available["weights"] = {
                p: self.graph.get_edge(p, node_id).weight
                for p in inputs
            }

        kwargs: Dict[str, Any] = {}
        for name, param in params.items():
            if name in available:
                kwargs[name] = available[name]
            elif param.default is inspect.Parameter.empty:
                # Required positional we don't recognize: pass inputs by position
                # for the very first such parameter, else leave it unset.
                if name not in kwargs:
                    kwargs[name] = inputs
        return kwargs
