import json
from pathlib import Path

import pytest

from impl_comparison.protocol import (
    ExecutionPolicy,
    LLMRequest,
    LLMResponse,
    ModelConfig,
    RunLimits,
    RunRequest,
    RunResult,
    TaskSpec,
    ToolCall,
    UsageMetrics,
    VerifierResult,
)


def test_protocol_dataclasses_round_trip_through_json():
    request = RunRequest(
        task=TaskSpec(
            task_id="task-1",
            prompt="Fix the bug",
            benchmark="terminal",
            workspace_snapshot="snapshot-1",
            verifier="pytest",
            timeout=12.0,
        ),
        model=ModelConfig(provider="fake", model="test-model"),
        policy=ExecutionPolicy(headless=True),
        workspace=Path("/tmp/workspace"),
        limits=RunLimits(max_turns=3),
        attempt_id="attempt-1",
        attempt="attempt-1",
    )
    response = LLMResponse(
        text="done",
        tool_calls=[ToolCall(call_id="c1", name="read", arguments={"path": "x"})],
        usage=UsageMetrics(input_tokens=2, output_tokens=3),
    )

    restored_request = RunRequest.from_dict(json.loads(json.dumps(request.to_dict())))
    restored_response = LLMResponse.from_dict(
        json.loads(json.dumps(response.to_dict()))
    )

    assert restored_request == request
    assert restored_response == response


def test_run_result_has_approved_fields_and_serializes_paths():
    result = RunResult(
        run_id="run-1",
        status="passed",
        final_text="finished",
        transcript_path=Path("/tmp/transcript.jsonl"),
        event_path=Path("/tmp/events.jsonl"),
        verifier_result=VerifierResult(passed=True, score=1.0),
        turns=2,
        usage=UsageMetrics(output_tokens=3),
        wall_time=1.25,
    )

    restored = RunResult.from_dict(json.loads(result.to_json()))

    assert restored == result
    assert restored.passed is True
    assert restored.verifier == result.verifier_result
    assert restored.events_path == result.event_path


def test_protocol_rejects_invalid_limits_and_empty_task_ids():
    with pytest.raises(ValueError):
        TaskSpec(task_id="", prompt="prompt")
    with pytest.raises(ValueError):
        RunLimits(max_turns=0)
    with pytest.raises(ValueError):
        TaskSpec(task_id="task", prompt="prompt", timeout=0)


def test_task_spec_from_dict_defaults_omitted_area_and_verifier_name():
    spec = TaskSpec.from_dict({"task_id": "legacy-task", "prompt": "Fix the bug"})
    assert spec.task_id == "legacy-task"
    assert spec.prompt == "Fix the bug"
    assert spec.area == ""
    assert spec.verifier_name == ""
