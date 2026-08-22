"""BPD-inspired layered DAG: proposal workers → tests → one repair."""

from __future__ import annotations

from typing import Any, Dict, List

from ..coding_llm import WorkspaceAwareLLM
from ..loop import run_tool_loop
from ..protocol import RunRequest
from ..runner import RunnerContext
from .workspace_tests import run_workspace_pytest

try:
    from dagcore import EdgeGraph
except ImportError:
    EdgeGraph = None  # type: ignore


class BpdDagSystem:
    def __init__(self, model: Any = None, workers: int = 3) -> None:
        self.model = model or WorkspaceAwareLLM()
        self.workers = workers

    def run(self, request: RunRequest, context: RunnerContext) -> Dict[str, Any]:
        graph = None
        if EdgeGraph is not None:
            graph = EdgeGraph([self.workers, 1, 1])
        worker_notes: List[str] = []
        for index in range(self.workers):
            context.emit("child_started", worker=index)
            result = run_tool_loop(
                self.model,
                request,
                context,
                system_prompt=(
                    "Proposal worker {}. Edit files to solve the task. "
                    "Do not run tests.".format(index + 1)
                ),
            )
            worker_notes.append(str(result.get("final_text", "")))
            context.emit("child_finished", worker=index)
            if graph is not None:
                graph.update_edge(0, index + 1, 1, 1, -1)
        test_output = run_workspace_pytest(context.workspace_root)
        if "FAILED" in test_output or "AssertionError" in test_output:
            if graph is not None:
                graph.update_edge(1, 1, 2, 1, 1)
            repair = run_tool_loop(
                self.model,
                request,
                context,
                system_prompt="Advisor detected failing tests. Repair once.",
                extra_messages=[
                    {
                        "role": "user",
                        "content": "Test results:\n{}".format(test_output),
                    }
                ],
            )
            return {
                "final_text": repair.get("final_text", ""),
                "workers": worker_notes,
                "edges": getattr(graph, "connections", None),
            }
        return {
            "final_text": worker_notes[-1] if worker_notes else "",
            "workers": worker_notes,
            "edges": getattr(graph, "connections", None),
        }
