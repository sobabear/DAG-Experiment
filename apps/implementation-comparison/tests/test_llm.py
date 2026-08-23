import json

import pytest

from impl_comparison.events import EventLog
from impl_comparison.llm import (
    OpenAICompatibleLLM,
    RetryableAPIError,
    FakeLLM,
    ToolCallAccumulator,
    accumulate_tool_calls,
    normalize_response,
    normalize_stream_delta,
)
from impl_comparison.loop import run_tool_loop
from impl_comparison.protocol import (
    ExecutionPolicy,
    LLMRequest,
    ModelConfig,
    RunLimits,
    RunRequest,
    TaskSpec,
    ToolCall,
)
from impl_comparison.runner import RunnerContext
from impl_comparison.telemetry import MetricsAccumulator


def test_fake_llm_normalizes_queued_mapping_and_records_requests():
    llm = FakeLLM(
        [
            {
                "content": "answer",
                "tool_calls": [
                    {"id": "call-1", "name": "read", "arguments": {"path": "a.txt"}}
                ],
                "finish_reason": "tool_calls",
                "usage": {"prompt_tokens": 4, "completion_tokens": 2},
            }
        ]
    )
    request = LLMRequest(
        messages=[{"role": "user", "content": "hello"}],
        model=ModelConfig(provider="fake", model="deterministic"),
    )

    response = llm.complete(request)

    assert response.text == "answer"
    assert response.tool_calls[0].call_id == "call-1"
    assert response.tool_calls[0].arguments == {"path": "a.txt"}
    assert response.finish_reason == "tool_calls"
    assert response.usage.input_tokens == 4
    assert response.usage.output_tokens == 2
    assert llm.requests == [request]


def test_normalize_response_accepts_empty_content_and_usage_aliases():
    response = normalize_response(
        {"content": None, "usage": {"input_tokens": 1, "output_tokens": 2}}
    )

    assert response.text == ""
    assert response.finish_reason == "stop"
    assert response.usage.input_tokens == 1
    assert response.usage.output_tokens == 2


def test_openai_adapter_sends_system_prompt_and_normalizes_object_response():
    class Completions:
        def create(self, **kwargs):
            self.kwargs = kwargs
            return {
                "choices": [
                    {
                        "message": {"content": None, "tool_calls": []},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 2, "completion_tokens": 1},
            }

    class Chat:
        def __init__(self):
            self.completions = Completions()

    class Client:
        def __init__(self):
            self.chat = Chat()

    client = Client()
    adapter = OpenAICompatibleLLM(
        ModelConfig(provider="openai-compatible", model="m"),
        client=client,
    )
    request = LLMRequest(
        messages=[{"role": "user", "content": "question"}],
        model=ModelConfig(provider="openai-compatible", model="m"),
        system_prompt="You are precise.",
    )

    response = adapter.complete(request)

    assert client.chat.completions.kwargs["messages"][0] == {
        "role": "system",
        "content": "You are precise.",
    }
    assert response.text == ""
    assert response.usage.input_tokens == 2


def test_openai_adapter_marks_retryable_api_errors():
    class Completions:
        def create(self, **kwargs):
            error = RuntimeError("rate limited")
            error.status_code = 429
            raise error

    class Client:
        class chat:
            completions = Completions()

    adapter = OpenAICompatibleLLM(
        ModelConfig(provider="openai-compatible", model="m"),
        client=Client(),
    )

    with pytest.raises(RetryableAPIError):
        adapter.complete(
            LLMRequest(
                messages=[],
                model=ModelConfig(provider="openai-compatible", model="m"),
            )
        )


def test_stream_delta_helper_normalizes_text_and_finish_reason():
    delta = normalize_stream_delta(
        {
            "choices": [
                {
                    "delta": {"content": "part"},
                    "finish_reason": None,
                }
            ]
        }
    )

    assert delta.text == "part"
    assert delta.finish_reason is None
    completed = normalize_stream_delta(
        {
            "choices": [
                {
                    "delta": {"content": ""},
                    "finish_reason": "stop",
                }
            ]
        }
    )
    assert completed.finish_reason == "stop"


def test_tool_call_accumulator_combines_fragmented_json_arguments():
    fragments = [
        {
            "index": 0,
            "id": "call-1",
            "function": {"name": "read", "arguments": '{"path":"'},
        },
        {
            "index": 0,
            "function": {"arguments": "notes.txt"},
        },
        {
            "index": 0,
            "function": {"arguments": '"}'},
        },
    ]

    calls = accumulate_tool_calls(fragments)

    assert calls == [
        ToolCallAccumulator.complete_call(
            "call-1", "read", {"path": "notes.txt"}
        )
    ]


def test_tool_call_accumulator_preserves_complete_calls():
    calls = accumulate_tool_calls(
        [
            {
                "id": "call-2",
                "function": {"name": "glob", "arguments": '{"pattern":"*.py"}'},
            }
        ]
    )

    assert calls[0].name == "glob"
    assert calls[0].arguments == {"pattern": "*.py"}


def test_stream_delta_keeps_partial_arguments_for_accumulator():
    first = normalize_stream_delta(
        {
            "choices": [
                {
                    "delta": {
                        "tool_calls": [
                            {
                                "index": 0,
                                "id": "call-stream",
                                "function": {
                                    "name": "read",
                                    "arguments": '{"path":"',
                                },
                            }
                        ]
                    }
                }
            ]
        }
    )
    second = normalize_stream_delta(
        {
            "choices": [
                {
                    "delta": {
                        "tool_calls": [
                            {
                                "index": 0,
                                "function": {"arguments": "notes.txt\"}"},
                            }
                        ]
                    }
                }
            ]
        }
    )
    accumulator = ToolCallAccumulator()
    accumulator.add(first.tool_calls[0])
    accumulator.add(second.tool_calls[0])

    assert accumulator.finish()[0].arguments == {"path": "notes.txt"}


def test_stream_delta_supports_direct_content_and_empty_argument_fragment():
    assert normalize_stream_delta({"content": "direct"}).text == "direct"

    first = normalize_stream_delta(
        {
            "choices": [
                {
                    "delta": {
                        "tool_calls": [
                            {
                                "index": 0,
                                "id": "call-empty",
                                "function": {"name": "read", "arguments": ""},
                            }
                        ]
                    }
                }
            ]
        }
    )
    second = normalize_stream_delta(
        {
            "choices": [
                {
                    "delta": {
                        "tool_calls": [
                            {
                                "index": 0,
                                "function": {"arguments": '{"path":"x.txt"}'},
                            }
                        ]
                    }
                }
            ]
        }
    )
    accumulator = ToolCallAccumulator()
    accumulator.add(first.tool_calls[0])
    accumulator.add(second.tool_calls[0])

    assert accumulator.finish()[0].arguments == {"path": "x.txt"}


def test_openai_adapter_forwards_safe_extra_options_and_metadata():
    class Completions:
        def create(self, **kwargs):
            self.kwargs = kwargs
            return {"choices": [{"message": {"content": "ok"}}]}

    class Client:
        class chat:
            completions = Completions()

    client = Client()
    adapter = OpenAICompatibleLLM(
        ModelConfig(
            provider="openai-compatible",
            model="m",
            extra={"top_p": 0.2, "api_key": "must-not-forward"},
        ),
        client=client,
    )
    adapter.complete(
        LLMRequest(
            messages=[],
            model=ModelConfig(provider="openai-compatible", model="m"),
            metadata={"trace_id": "trace-1"},
        )
    )

    assert client.chat.completions.kwargs["top_p"] == 0.2
    assert client.chat.completions.kwargs["metadata"] == {"trace_id": "trace-1"}
    assert "api_key" not in client.chat.completions.kwargs


def test_openai_adapter_filters_nested_sensitive_options():
    class Completions:
        def create(self, **kwargs):
            self.kwargs = kwargs
            return {"choices": [{"message": {"content": "ok"}}]}

    class Client:
        class chat:
            completions = Completions()

    client = Client()
    adapter = OpenAICompatibleLLM(
        ModelConfig(
            provider="openai-compatible",
            model="m",
            extra={
                "private_key": "private-value",
                "nested": {
                    "credential": "credential-value",
                    "safe": "kept",
                },
            },
        ),
        client=client,
    )
    adapter.complete(
        LLMRequest(
            messages=[],
            model=ModelConfig(provider="openai-compatible", model="m"),
            metadata={
                "nested": {"api_token": "token-value", "trace": "kept"},
                "safe": "kept",
            },
        )
    )

    forwarded = repr(client.chat.completions.kwargs)
    assert "private-value" not in forwarded
    assert "credential-value" not in forwarded
    assert "token-value" not in forwarded
    assert client.chat.completions.kwargs["nested"]["safe"] == "kept"
    assert client.chat.completions.kwargs["metadata"]["nested"]["trace"] == "kept"


def _tool_schema_names(tools):
    names = set()
    for item in tools or []:
        function = item.get("function") if isinstance(item, dict) else None
        if isinstance(function, dict) and function.get("name"):
            names.add(function["name"])
        elif isinstance(item, dict) and item.get("name"):
            names.add(item["name"])
    return names


def test_run_tool_loop_advertises_default_tools_on_every_request(tmp_path):
    llm = FakeLLM([{"content": "done"}])
    context = RunnerContext(
        artifact_dir=tmp_path,
        transcript_path=tmp_path / "transcript.jsonl",
        event_log=EventLog(tmp_path / "events.jsonl"),
        metrics=MetricsAccumulator(),
        workspace_root=tmp_path,
    )
    request = RunRequest(
        task=TaskSpec(task_id="loop-tools", prompt="say hi"),
        model=ModelConfig(provider="fake", model="spy"),
        policy=ExecutionPolicy(headless=True, workspace_root=str(tmp_path)),
        limits=RunLimits(max_turns=2),
        workspace=tmp_path,
    )

    run_tool_loop(llm, request, context)

    assert llm.requests
    tools = llm.requests[0].tools
    assert tools
    names = _tool_schema_names(tools)
    assert {"read", "write", "shell"} <= names


def test_openai_adapter_converts_internal_tool_messages_to_provider_shape():
    class Completions:
        def create(self, **kwargs):
            self.kwargs = kwargs
            return {"choices": [{"message": {"content": "ok"}}]}

    class Chat:
        def __init__(self):
            self.completions = Completions()

    class Client:
        def __init__(self):
            self.chat = Chat()

    client = Client()
    adapter = OpenAICompatibleLLM(
        ModelConfig(provider="openai-compatible", model="m"),
        client=client,
    )
    adapter.complete(
        LLMRequest(
            messages=[
                {"role": "user", "content": "edit the file"},
                {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "call_id": "call-1",
                            "name": "read",
                            "arguments": {"path": "foo.py"},
                        }
                    ],
                },
                {
                    "role": "tool",
                    "name": "read",
                    "tool_call_id": "call-1",
                    "content": '{"content": "x"}',
                },
            ],
            model=ModelConfig(provider="openai-compatible", model="m"),
        )
    )

    messages = client.chat.completions.kwargs["messages"]
    tool_call = messages[1]["tool_calls"][0]
    assert "call_id" not in tool_call
    assert tool_call["id"] == "call-1"
    assert tool_call["type"] == "function"
    assert tool_call["function"]["name"] == "read"
    assert isinstance(tool_call["function"]["arguments"], str)
    assert json.loads(tool_call["function"]["arguments"]) == {"path": "foo.py"}
    tool_msg = messages[2]
    assert tool_msg["role"] == "tool"
    assert tool_msg["tool_call_id"] == "call-1"
    assert tool_msg["content"] == '{"content": "x"}'


def _spy_openai_client():
    class Completions:
        def create(self, **kwargs):
            self.kwargs = kwargs
            return {"choices": [{"message": {"content": "ok"}}]}

    class Chat:
        def __init__(self):
            self.completions = Completions()

    class Client:
        def __init__(self):
            self.chat = Chat()

    return Client()


def test_openai_adapter_gpt56_luna_omits_unsupported_sampling_params():
    client = _spy_openai_client()
    adapter = OpenAICompatibleLLM(
        ModelConfig(provider="openai-compatible", model="gpt-5.6-luna"),
        client=client,
    )
    adapter.complete(
        LLMRequest(
            messages=[{"role": "user", "content": "hi"}],
            model=ModelConfig(
                provider="openai-compatible",
                model="gpt-5.6-luna",
                temperature=0.0,
                max_tokens=128,
            ),
        )
    )

    kwargs = client.chat.completions.kwargs
    assert "temperature" not in kwargs
    assert "max_tokens" not in kwargs
    assert kwargs["max_completion_tokens"] == 128


def test_openai_adapter_gpt56_luna_disables_reasoning_for_chat_tools():
    client = _spy_openai_client()
    adapter = OpenAICompatibleLLM(
        ModelConfig(provider="openai-compatible", model="gpt-5.6-luna"),
        client=client,
    )
    adapter.complete(
        LLMRequest(
            messages=[{"role": "user", "content": "edit"}],
            model=ModelConfig(provider="openai-compatible", model="gpt-5.6-luna"),
            tools=[
                {
                    "type": "function",
                    "function": {
                        "name": "read",
                        "parameters": {"type": "object", "properties": {}},
                    },
                }
            ],
        )
    )

    kwargs = client.chat.completions.kwargs
    assert kwargs["reasoning_effort"] == "none"
    assert "temperature" not in kwargs


def test_openai_adapter_gpt56_luna_keeps_explicit_reasoning_effort():
    client = _spy_openai_client()
    adapter = OpenAICompatibleLLM(
        ModelConfig(
            provider="openai-compatible",
            model="gpt-5.6-luna",
            extra={"reasoning_effort": "low"},
        ),
        client=client,
    )
    adapter.complete(
        LLMRequest(
            messages=[],
            model=ModelConfig(provider="openai-compatible", model="gpt-5.6-luna"),
            tools=[{"type": "function", "function": {"name": "read"}}],
        )
    )

    assert client.chat.completions.kwargs["reasoning_effort"] == "low"
