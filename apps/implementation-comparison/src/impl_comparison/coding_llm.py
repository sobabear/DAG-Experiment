"""Deterministic coding model shared by all three systems.

Correct SE patches are emitted only after test failure text is in context.
Without a forced test node, the first patch stays wrong and the model stops.
"""

from __future__ import annotations

import json
import re
from typing import Any, List

from .protocol import LLMRequest, LLMResponse, ToolCall, UsageMetrics

_DIGEST = re.compile(r"\b[a-f0-9]{64}\b")
_CALL = 0


def _next_id() -> str:
    global _CALL
    _CALL += 1
    return "call-{}".format(_CALL)


def _flatten(request: LLMRequest) -> str:
    parts: List[str] = [request.system_prompt or ""]
    for message in request.messages:
        parts.append(str(message.get("role", "")))
        parts.append(str(message.get("name", "")))
        content = message.get("content", "")
        if isinstance(content, (dict, list)):
            parts.append(json.dumps(content))
        else:
            parts.append(str(content))
        calls = message.get("tool_calls") or []
        if calls:
            parts.append(json.dumps(calls, default=str))
    return "\n".join(parts)


def _usage(blob: str) -> UsageMetrics:
    return UsageMetrics(
        input_tokens=max(1, len(blob) // 4),
        output_tokens=16,
        requests=1,
    )


def _call(name: str, **arguments: Any) -> ToolCall:
    return ToolCall(call_id=_next_id(), name=name, arguments=arguments)


class WorkspaceAwareLLM:
    """Same complete() for every system; architecture only changes the transcript."""

    def complete(self, request: LLMRequest) -> LLMResponse:
        blob = _flatten(request)
        usage = _usage(blob)
        last_tool = _last_tool_name(request.messages)

        if _is_qna(blob, request):
            if last_tool == "write":
                return LLMResponse(text="done", usage=usage)
            if "ALPHA-42" in blob:
                return LLMResponse(
                    text="found token",
                    tool_calls=[_call("write", path="answer.txt", content="ALPHA-42\n")],
                    usage=usage,
                )
            return LLMResponse(
                text="reading notes",
                tool_calls=[_call("read", path="NOTES.md")],
                usage=usage,
            )

        if _is_terminal(blob, request):
            if last_tool == "write":
                return LLMResponse(text="done", usage=usage)
            digest = _DIGEST.search(blob)
            if digest:
                return LLMResponse(
                    text="recording hash",
                    tool_calls=[
                        _call("write", path="answer.txt", content=digest.group(0) + "\n")
                    ],
                    usage=usage,
                )
            if last_tool in {"list", "glob", "read"} or "compute.py" in blob:
                return LLMResponse(
                    text="running compute.py",
                    tool_calls=[_call("shell", command="python3 compute.py")],
                    usage=usage,
                )
            return LLMResponse(
                text="listing workspace",
                tool_calls=[_call("list", path=".")],
                usage=usage,
            )

        # SE analog
        if last_tool == "write":
            return LLMResponse(text="done", usage=usage)
        if "FAILED" in blob or "AssertionError" in blob:
            return LLMResponse(
                text="repairing add",
                tool_calls=[
                    _call(
                        "write",
                        path="add.py",
                        content="def add(a, b):\n    return a + b\n",
                    )
                ],
                usage=usage,
            )
        if "return a - b" in blob or "return a-b" in blob:
            return LLMResponse(
                text="first patch",
                tool_calls=[
                    _call(
                        "write",
                        path="add.py",
                        content="def add(a, b):\n    return a * b\n",
                    )
                ],
                usage=usage,
            )
        if "return a * b" in blob:
            return LLMResponse(text="proposal already applied", usage=usage)
        return LLMResponse(
            text="reading add.py",
            tool_calls=[_call("read", path="add.py")],
            usage=usage,
        )


def _last_tool_name(messages: List[Any]) -> str:
    for message in reversed(messages):
        name = str(message.get("name") or "")
        if message.get("role") == "tool" and name:
            return name
    return ""


def _is_qna(blob: str, request: LLMRequest) -> bool:
    text = blob.lower() + (request.system_prompt or "").lower()
    return "project token" in text or "notes.md" in text or "qna" in text


def _is_terminal(blob: str, request: LLMRequest) -> bool:
    text = blob.lower() + (request.system_prompt or "").lower()
    return "compute.py" in text or "sha256" in text or "terminal-hash" in text
