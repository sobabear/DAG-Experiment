"""Bounded model/tool loop used by the three agent systems."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from .llm import ModelProtocol
from .protocol import LLMRequest, RunRequest
from .runner import RunnerContext
from .tools import ToolContext, default_registry, default_tool_schemas


def run_tool_loop(
    model: ModelProtocol,
    request: RunRequest,
    context: RunnerContext,
    system_prompt: str = "",
    extra_messages: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    registry = default_registry()
    tool_schemas = default_tool_schemas()
    tool_context = ToolContext(
        workspace_root=context.workspace_root,
        policy=request.policy,
        limits=request.limits,
        metrics=context.metrics,
        approval_callback=lambda _name, _arguments: True,
    )
    messages: List[Dict[str, Any]] = []
    if extra_messages:
        messages.extend(extra_messages)
    messages.append({"role": "user", "content": request.task.prompt})
    final_text = ""
    for _ in range(request.limits.max_turns):
        context.metrics.record_turn()
        context.emit("turn_started", task_id=request.task.task_id)
        llm_request = LLMRequest(
            messages=messages,
            model=request.model,
            system_prompt=system_prompt,
            tools=tool_schemas,
        )
        context.emit("model_request", task_id=request.task.task_id)
        response = model.complete(llm_request)
        context.metrics.add_usage(response.usage)
        context.emit("model_response", task_id=request.task.task_id)
        if not response.tool_calls:
            final_text = response.text
            break
        messages.append(
            {
                "role": "assistant",
                "content": response.text,
                "tool_calls": [call.to_dict() for call in response.tool_calls],
            }
        )
        for call in response.tool_calls:
            context.emit("tool_requested", name=call.name)
            context.emit("tool_started", name=call.name)
            try:
                output = registry.execute(call.name, call.arguments, tool_context)
                success = True
                error = None
            except Exception as exc:
                output = {"error": "{}: {}".format(type(exc).__name__, exc)}
                success = False
                error = str(exc)
            context.emit(
                "tool_finished",
                name=call.name,
                success=success,
                error=error,
            )
            messages.append(
                {
                    "role": "tool",
                    "name": call.name,
                    "tool_call_id": call.call_id,
                    "content": json.dumps(output, default=str),
                }
            )
    return {"final_text": final_text, "messages": messages}
