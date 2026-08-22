"""Provider-neutral LLM interfaces and deterministic test implementations."""

import json
import re
from typing import Any, Iterable, List, Mapping, Protocol

from .protocol import LLMRequest, LLMResponse, ToolCall, UsageMetrics


class RetryableAPIError(RuntimeError):
    """An API failure that a caller may safely retry."""

    def __init__(self, message: str, original: Exception = None):
        super().__init__(message)
        self.original = original


class ModelProtocol(Protocol):
    def complete(self, request: LLMRequest) -> LLMResponse:
        ...


def _get(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


def _normalize_usage(value: Any) -> UsageMetrics:
    value = value or {}
    return UsageMetrics(
        input_tokens=int(
            _get(value, "input_tokens", _get(value, "prompt_tokens", 0)) or 0
        ),
        output_tokens=int(
            _get(value, "output_tokens", _get(value, "completion_tokens", 0)) or 0
        ),
        cached_tokens=int(
            _get(
                value,
                "cached_tokens",
                _get(value, "cache_read_input_tokens", 0),
            )
            or 0
        ),
        cost_usd=float(_get(value, "cost_usd", 0.0) or 0.0),
        requests=int(_get(value, "requests", 1) or 1),
    )


def _normalize_tool_call(value: Any, index: int) -> ToolCall:
    function = _get(value, "function", value)
    arguments = _get(function, "arguments", {}) or {}
    if isinstance(arguments, str):
        arguments = json.loads(arguments) if arguments.strip() else {}
    return ToolCall(
        call_id=str(_get(value, "id", "call-{}".format(index))),
        name=str(_get(function, "name", _get(value, "name", ""))),
        arguments=dict(arguments),
    )


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (list, tuple)):
        parts = []
        for item in value:
            text = _get(item, "text", None)
            if text is not None:
                parts.append(str(text))
        return "".join(parts)
    return str(value)


def normalize_response(response: Any) -> LLMResponse:
    """Convert common mapping/object response shapes to the shared contract."""
    if isinstance(response, LLMResponse):
        return response

    choices = _get(response, "choices", None)
    if choices:
        choice = choices[0]
        message = _get(choice, "message", choice)
        text = _normalize_text(_get(message, "content", ""))
        tool_values = _get(message, "tool_calls", []) or []
        finish_reason = _get(choice, "finish_reason", "stop") or "stop"
        usage_value = _get(response, "usage", {})
    else:
        text = _normalize_text(_get(response, "text", _get(response, "content", "")))
        tool_values = _get(response, "tool_calls", []) or []
        finish_reason = _get(response, "finish_reason", "stop") or "stop"
        usage_value = _get(response, "usage", {})

    return LLMResponse(
        text=text,
        tool_calls=[
            value if isinstance(value, ToolCall) else _normalize_tool_call(value, i)
            for i, value in enumerate(tool_values)
        ],
        finish_reason=str(finish_reason),
        usage=_normalize_usage(usage_value),
    )


def normalize_stream_delta(delta: Any) -> LLMResponse:
    """Normalize one non-streaming-shaped or streaming delta chunk."""
    choices = _get(delta, "choices", []) or []
    if not choices:
        finish_reason = _get(delta, "finish_reason", "stop")
        return LLMResponse(
            text=_normalize_text(_get(delta, "content", "")),
            finish_reason=(
                None if finish_reason is None else str(finish_reason)
            ),
            usage=_normalize_usage(_get(delta, "usage", {})),
        )
    choice = choices[0]
    value = _get(choice, "delta", choice)
    tool_values = _get(value, "tool_calls", []) or []
    finish_reason = _get(choice, "finish_reason", "stop")
    return LLMResponse(
        text=_normalize_text(_get(value, "content", "")),
        tool_calls=[
            item
            if isinstance(item, ToolCall)
            else _normalize_stream_tool_call(item, i)
            for i, item in enumerate(tool_values)
        ],
        finish_reason=(
            None if finish_reason is None else str(finish_reason)
        ),
        usage=_normalize_usage(_get(delta, "usage", {})),
    )


def _normalize_stream_tool_call(value: Any, index: int) -> ToolCall:
    function = _get(value, "function", value)
    arguments = _get(function, "arguments", "") or ""
    if isinstance(arguments, Mapping):
        return ToolCall(
            call_id=str(_get(value, "id", "call-{}".format(index))),
            name=str(_get(function, "name", _get(value, "name", ""))),
            arguments=dict(arguments),
            fragment_index=_get(value, "index", index),
        )
    return ToolCall(
        call_id=str(_get(value, "id", "call-{}".format(index))),
        name=str(_get(function, "name", _get(value, "name", ""))),
        arguments_fragment=str(arguments),
        fragment_index=_get(value, "index", index),
    )


class ToolCallAccumulator:
    """Combine provider-neutral tool-call fragments before JSON decoding."""

    def __init__(self):
        self._calls = {}
        self._indices = {}

    @staticmethod
    def complete_call(call_id, name, arguments):
        return ToolCall(call_id=call_id, name=name, arguments=arguments)

    def add(self, fragment: Any) -> None:
        if isinstance(fragment, ToolCall):
            index = fragment.fragment_index
            key = self._indices.get(index) or fragment.call_id or index
            if key is None:
                key = len(self._calls)
            if index is not None:
                self._indices[index] = key
            state = self._calls.setdefault(
                key,
                {"id": fragment.call_id, "name": fragment.name, "text": ""},
            )
            if fragment.name:
                state["name"] = fragment.name
            if fragment.arguments_fragment or (
                fragment.fragment_index is not None and not fragment.arguments
            ):
                state["text"] += fragment.arguments_fragment
            else:
                state["arguments"] = dict(fragment.arguments)
                state["complete"] = True
            return
        function = _get(fragment, "function", fragment)
        index = _get(fragment, "index", None)
        call_id = _get(fragment, "id", None)
        key = call_id or self._indices.get(index) or index
        if key is None:
            key = len(self._calls)
        if index is not None:
            self._indices[index] = key
        state = self._calls.setdefault(
            key,
            {"id": call_id or "call-{}".format(key), "name": "", "text": ""},
        )
        state["id"] = call_id or state["id"]
        state["name"] = _get(function, "name", "") or state["name"]
        arguments = _get(function, "arguments", "") or ""
        if isinstance(arguments, Mapping):
            state["arguments"] = dict(arguments)
            state["complete"] = True
        else:
            state["text"] = state.get("text", "") + str(arguments)

    def finish(self) -> List[ToolCall]:
        calls = []
        for state in self._calls.values():
            if state.get("complete"):
                arguments = state.get("arguments", {})
            else:
                text = state.get("text", "")
                arguments = json.loads(text) if text.strip() else {}
            calls.append(
                ToolCall(
                    call_id=state["id"],
                    name=state["name"],
                    arguments=dict(arguments),
                )
            )
        return calls


def accumulate_tool_calls(fragments: Iterable[Any]) -> List[ToolCall]:
    accumulator = ToolCallAccumulator()
    for fragment in fragments:
        accumulator.add(fragment)
    return accumulator.finish()


class FakeLLM:
    """A deterministic queued model for offline tests and local experiments."""

    def __init__(self, responses: Iterable[Any]):
        self._responses: List[Any] = list(responses)
        self.requests: List[LLMRequest] = []

    def complete(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        if not self._responses:
            raise RuntimeError("FakeLLM response queue is exhausted")
        return normalize_response(self._responses.pop(0))


def _is_retryable_error(exc: Exception) -> bool:
    status = getattr(exc, "status_code", None)
    if status is None:
        response = getattr(exc, "response", None)
        status = getattr(response, "status_code", None)
    if status is not None and int(status) in (408, 409, 425, 429):
        return True
    if status is not None and int(status) >= 500:
        return True
    return type(exc).__name__.lower() in {
        "ratelimiterror",
        "apiconnectionerror",
        "timeout",
        "timeouterror",
    }


class OpenAICompatibleLLM:
    """Optional adapter; importing the OpenAI SDK is deferred until construction."""

    def __init__(self, config: Any, client: Any = None):
        self.config = config
        if client is not None:
            self._client = client
        else:
            try:
                from openai import OpenAI
            except ImportError as exc:
                raise RuntimeError(
                    "OpenAICompatibleLLM requires the optional openai package"
                ) from exc
            kwargs = {}
            if getattr(config, "endpoint", None):
                kwargs["base_url"] = config.endpoint
            self._client = OpenAI(**kwargs)

    def complete(self, request: LLMRequest) -> LLMResponse:
        messages = list(request.messages)
        if request.system_prompt:
            if messages and _get(messages[0], "role") == "system":
                messages[0] = dict(messages[0], content=request.system_prompt)
            else:
                messages.insert(0, {"role": "system", "content": request.system_prompt})
        messages = _to_openai_messages(messages)
        kwargs = {
            "model": request.model.model,
            "messages": messages,
        }
        if request.tools:
            kwargs["tools"] = request.tools
        if request.model.temperature is not None:
            kwargs["temperature"] = request.model.temperature
        if request.model.max_tokens is not None:
            kwargs["max_tokens"] = request.model.max_tokens
        reserved = set(kwargs)
        for options in (getattr(self.config, "extra", {}), request.model.extra):
            for key, value in _safe_options(options).items():
                if key not in reserved:
                    kwargs[key] = value
        if request.metadata:
            kwargs["metadata"] = _safe_options(request.metadata)
        try:
            response = self._client.chat.completions.create(**kwargs)
        except Exception as exc:
            if _is_retryable_error(exc):
                raise RetryableAPIError(
                    "retryable model API error: {}".format(exc), exc
                ) from exc
            raise
        return normalize_response(response)


def _to_openai_messages(messages):
    converted = []
    for message in messages:
        role = _get(message, "role")
        if role == "assistant":
            converted.append(_to_openai_assistant_message(message))
        elif role == "tool":
            converted.append(_to_openai_tool_message(message))
        elif isinstance(message, Mapping):
            converted.append(dict(message))
        else:
            converted.append(message)
    return converted


def _to_openai_assistant_message(message):
    converted = {
        "role": "assistant",
        "content": _get(message, "content"),
    }
    tool_calls = _get(message, "tool_calls") or []
    if tool_calls:
        converted["tool_calls"] = [
            _to_openai_tool_call(call) for call in tool_calls
        ]
    return converted


def _to_openai_tool_call(call):
    function = _get(call, "function")
    if function:
        name = _get(function, "name", "") or ""
        arguments = _get(function, "arguments", {}) or {}
    else:
        name = _get(call, "name", "") or ""
        arguments = _get(call, "arguments", {}) or {}
    if not isinstance(arguments, str):
        arguments = json.dumps(arguments)
    return {
        "id": str(_get(call, "id") or _get(call, "call_id") or ""),
        "type": "function",
        "function": {"name": str(name), "arguments": arguments},
    }


def _to_openai_tool_message(message):
    converted = {
        "role": "tool",
        "tool_call_id": str(
            _get(message, "tool_call_id") or _get(message, "call_id") or ""
        ),
        "content": _get(message, "content"),
    }
    if converted["content"] is None:
        converted["content"] = ""
    name = _get(message, "name")
    if name:
        converted["name"] = name
    return converted


def _safe_options(options):
    safe = {}
    for key, value in options.items():
        if re.search(
            r"(api[_-]?key|private[_-]?key|token|secret|password|credential|"
            r"authorization|bearer)",
            str(key),
            re.I,
        ):
            continue
        if isinstance(value, Mapping):
            safe[key] = _safe_options(value)
        elif isinstance(value, list):
            safe[key] = [
                _safe_options(item) if isinstance(item, Mapping) else item
                for item in value
            ]
        else:
            safe[key] = value
    return safe
