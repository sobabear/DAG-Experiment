"""Claude Code–like single bounded tool loop (no copied source)."""

from __future__ import annotations

from typing import Any, Dict

from ..coding_llm import WorkspaceAwareLLM
from ..loop import run_tool_loop
from ..protocol import RunRequest
from ..runner import RunnerContext


class GeneralAgentSystem:
    def __init__(self, model: Any = None) -> None:
        self.model = model or WorkspaceAwareLLM()

    def run(self, request: RunRequest, context: RunnerContext) -> Dict[str, Any]:
        return run_tool_loop(
            self.model,
            request,
            context,
            system_prompt=(
                "You are a general coding agent. Solve the task, then stop "
                "when you believe you are done. Tests are optional."
            ),
        )
