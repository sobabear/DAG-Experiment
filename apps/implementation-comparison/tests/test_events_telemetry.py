import json
import time

import pytest

from impl_comparison.events import EVENT_TYPES, EventLog
from impl_comparison.protocol import UsageMetrics
from impl_comparison.security import MAX_SCAN_BYTES, redact_sensitive, sanitize_artifact_tree
from impl_comparison.telemetry import MetricsAccumulator, RunLimitExceeded


def test_event_log_appends_jsonl_records(tmp_path):
    event_log = EventLog(tmp_path / "events.jsonl")

    event_log.append("run_started", run_id="r1", task_id="t1")
    event_log.append("tool_finished", tool="read", success=True)

    records = [
        json.loads(line)
        for line in (tmp_path / "events.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert [record["type"] for record in records] == [
        "run_started",
        "tool_finished",
    ]
    assert records[0]["run_id"] == "r1"
    assert records[1]["success"] is True


def test_event_log_rejects_events_outside_approved_vocabulary(tmp_path):
    event_log = EventLog(tmp_path / "events.jsonl")

    with pytest.raises(ValueError):
        event_log.append("made_up_event")


def test_event_payload_cannot_overwrite_event_type(tmp_path):
    event_log = EventLog(tmp_path / "events.jsonl")

    event_log.append("run_started", type="spoofed")

    record = json.loads(
        (tmp_path / "events.jsonl").read_text(encoding="utf-8").strip()
    )
    assert record["type"] == "run_started"


def test_redactor_handles_bare_secret_assignments_without_false_positive_examples():
    redacted = redact_sensitive(
        "API_KEY='ordinary-secret' TOKEN=token-value SECRET='secret-value' "
        "PASSWORD=pw-value PRIVATE_KEY='private-key-value'"
    )

    assert "ordinary-secret" not in redacted
    assert "token-value" not in redacted
    assert "secret-value" not in redacted
    assert "pw-value" not in redacted
    assert "private-key-value" not in redacted
    assert "sk-example" in redact_sensitive("literal sk-example documentation")


def test_redactor_handles_json_and_yaml_secret_assignments():
    redacted = redact_sensitive(
        '{"api_key": "json-secret-value", "PRIVATE_KEY": "json-private"}\n'
        "api_key: yaml-secret-value\nPRIVATE_KEY: yaml-private"
    )

    assert "json-secret-value" not in redacted
    assert "json-private" not in redacted
    assert "yaml-secret-value" not in redacted
    assert "yaml-private" not in redacted
    assert "api_key documentation" in redact_sensitive(
        "api_key documentation is ordinary text"
    )


def test_large_structured_and_hyphenated_secrets_are_sanitized(tmp_path):
    large = tmp_path / "large-config.txt"
    large.write_bytes(
        b"x" * (MAX_SCAN_BYTES + 128)
        + b'{"api-key": "large-json-secret", "private-key": "large-private"}'
    )

    sanitize_artifact_tree(tmp_path)

    assert not large.exists()
    assert "api-key: raw-secret-value" not in redact_sensitive(
        "api-key: raw-secret-value"
    )
    assert "private-key: raw-private-value" not in redact_sensitive(
        "private-key: raw-private-value"
    )
    assert "access-token: raw-access-value" not in redact_sensitive(
        "access-token: raw-access-value"
    )
    assert "api-key=[REDACTED]" in redact_sensitive(
        "api-key=raw-equals-secret"
    )


def test_event_observer_context_can_emit_full_lifecycle_vocabulary(tmp_path):
    event_log = EventLog(tmp_path / "events.jsonl")

    for event_type in EVENT_TYPES:
        event_log.emit(event_type)

    event_types = {
        json.loads(line)["type"]
        for line in (tmp_path / "events.jsonl").read_text(encoding="utf-8").splitlines()
    }
    assert event_types == set(EVENT_TYPES)


def test_metrics_accumulator_tracks_turns_tools_usage_and_wall_time():
    metrics = MetricsAccumulator()
    metrics.record_turn()
    metrics.record_tool_call()
    metrics.add_usage(UsageMetrics(input_tokens=3, output_tokens=4, requests=1))
    time.sleep(0.001)

    snapshot = metrics.finish()

    assert snapshot.turns == 1
    assert snapshot.tool_calls == 1
    assert snapshot.usage.input_tokens == 3
    assert snapshot.usage.output_tokens == 4
    assert snapshot.wall_time_seconds >= 0


def test_metrics_accumulator_turn_guard_fails_during_execution():
    metrics = MetricsAccumulator(max_turns=1)
    metrics.record_turn()

    with pytest.raises(RunLimitExceeded):
        metrics.record_turn()
