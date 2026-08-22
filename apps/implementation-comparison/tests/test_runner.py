import json
import asyncio
import subprocess
import sys
import time

import pytest

from impl_comparison.events import EVENT_TYPES
from impl_comparison.protocol import (
    ExecutionPolicy,
    ModelConfig,
    RunLimits,
    RunRequest,
    TaskSpec,
    VerifierResult,
)
from impl_comparison.runner import run_agent
from impl_comparison.runner import SyncProcessUnavailable
from impl_comparison import runner as runner_module


def test_runner_uses_verifier_result_instead_of_system_self_claim(tmp_path):
    request = RunRequest(
        task=TaskSpec(task_id="task-1", prompt="do work"),
        model=ModelConfig(provider="fake", model="test"),
        policy=ExecutionPolicy(workspace_root=str(tmp_path)),
        workspace=tmp_path,
        limits=RunLimits(),
    )

    class SelfClaimingSystem:
        def run(self, request, context):
            assert context.workspace_root == request.workspace
            assert context.workspace_root != context.artifact_dir
            return {"passed": True, "message": "the model says it passed"}

    def verifier(request, system_result, artifact_dir):
        assert system_result["passed"] is True
        (artifact_dir / "answer.txt").write_text("checked", encoding="utf-8")
        return VerifierResult(passed=False, reason="independent check failed")

    result = run_agent(
        request,
        SelfClaimingSystem(),
        verifier,
        workspace_root=tmp_path,
        run_id="run-1",
    )

    assert result.passed is False
    assert result.verifier.reason == "independent check failed"
    assert result.artifact_dir.exists()
    assert result.metadata["timeout_enforcement"] == "sync_process"
    assert result.metadata["hard_cancel"] is False
    assert result.metadata["detached_descendants_uncontained"] is True
    assert result.metadata["process_group_cleanup"] == "best_effort"
    assert result.transcript_path.exists()
    assert (result.artifact_dir / "metrics.json").exists()
    assert (result.artifact_dir / "result.json").exists()
    events = [
        json.loads(line)
        for line in result.events_path.read_text(encoding="utf-8").splitlines()
    ]
    assert [event["type"] for event in events] == [
        "run_started",
        "run_finished",
    ]


def test_runner_marks_basic_turn_limit_without_trusting_system_claim(tmp_path):
    request = RunRequest(
        task=TaskSpec(task_id="task-2", prompt="do work"),
        model=ModelConfig(provider="fake", model="test"),
        policy=ExecutionPolicy(workspace_root=str(tmp_path)),
        workspace=tmp_path,
        limits=RunLimits(max_turns=1),
    )

    class OverLimitSystem:
        def run(self, request, context):
            context.metrics.record_turn()
            context.metrics.record_turn()
            return {"passed": True}

    result = run_agent(
        request,
        OverLimitSystem(),
        lambda request, output, artifact: VerifierResult(passed=True),
        workspace_root=tmp_path,
        run_id="run-2",
    )

    assert result.status == "limit_exceeded"
    assert result.passed is True


def test_runner_context_observer_can_emit_full_event_vocabulary(tmp_path):
    request = RunRequest(
        task=TaskSpec(task_id="task-3", prompt="emit events"),
        model=ModelConfig(provider="fake", model="test"),
        policy=ExecutionPolicy(workspace_root=str(tmp_path)),
        workspace=tmp_path,
    )

    class EventfulSystem:
        def run(self, request, context):
            for event_type in EVENT_TYPES:
                context.emit(event_type, source="system")
            return "done"

    result = run_agent(
        request,
        EventfulSystem(),
        lambda request, output, artifact: VerifierResult(passed=True),
        workspace_root=tmp_path,
        run_id="run-3",
    )
    event_types = {
        json.loads(line)["type"]
        for line in result.event_path.read_text(encoding="utf-8").splitlines()
    }

    assert set(EVENT_TYPES).issubset(event_types)


def test_runner_enforces_async_timeout_before_long_sleep_finishes(tmp_path):
    request = RunRequest(
        task=TaskSpec(task_id="task-4", prompt="sleep", timeout=0.05),
        model=ModelConfig(provider="fake", model="test"),
        policy=ExecutionPolicy(workspace_root=str(tmp_path)),
        workspace=tmp_path,
        limits=RunLimits(timeout_seconds=0.05),
    )
    verifier_called = []

    class SlowAsyncSystem:
        async def run(self, request, context):
            await asyncio.sleep(1)
            return {"passed": True}

    def verifier(request, output, artifact_dir):
        verifier_called.append(output)
        return VerifierResult(passed=False, reason="timed out")

    started = time.monotonic()
    result = run_agent(
        request,
        SlowAsyncSystem(),
        verifier,
        workspace_root=tmp_path,
        run_id="run-4",
    )

    assert time.monotonic() - started < 0.5
    assert result.status == "timeout"
    assert result.metadata["timeout_enforcement"] == "async_cancelled"
    assert result.metadata["hard_cancel"] is False
    assert result.metadata["detached_descendants_uncontained"] is True
    assert result.metadata["process_group_cleanup"] == "not_applicable"
    assert result.metadata["cancellation_limitation"] == "async_cancel_can_be_suppressed"
    assert verifier_called
    assert (result.artifact_dir / "result.json").exists()


def test_runner_bounds_synchronous_system_without_claiming_hard_cancel(tmp_path):
    request = RunRequest(
        task=TaskSpec(task_id="task-sync-timeout", prompt="sleep", timeout=0.05),
        model=ModelConfig(provider="fake", model="test"),
        policy=ExecutionPolicy(workspace_root=str(tmp_path)),
        workspace=tmp_path,
        limits=RunLimits(timeout_seconds=0.05),
    )

    class SlowSyncSystem:
        def run(self, request, context):
            time.sleep(1)
            return "finished later"

    started = time.monotonic()
    result = run_agent(
        request,
        SlowSyncSystem(),
        lambda request, output, artifact: VerifierResult(passed=False),
        workspace_root=tmp_path,
        run_id="run-sync-timeout",
    )

    assert time.monotonic() - started < 0.5
    assert result.status == "timeout"
    assert result.metadata["timeout_enforcement"] == "sync_process"
    assert result.metadata["hard_cancel"] is False
    assert result.metadata["detached_descendants_uncontained"] is True
    assert result.metadata["process_group_cleanup"] == "best_effort"


def test_sync_timeout_cannot_write_late_events_or_artifacts(tmp_path):
    request = RunRequest(
        task=TaskSpec(task_id="task-sync-isolated", prompt="late write", timeout=0.05),
        model=ModelConfig(provider="fake", model="test"),
        policy=ExecutionPolicy(workspace_root=str(tmp_path)),
        workspace=tmp_path,
        limits=RunLimits(timeout_seconds=0.05),
    )

    class LateWriter:
        def run(self, request, context):
            time.sleep(0.2)
            context.emit("model_response", text="late sk-late-secret1234567890")
            (context.artifact_dir / "late.txt").write_text(
                "late sk-late-secret1234567890",
                encoding="utf-8",
            )
            return "late"

    started = time.monotonic()
    result = run_agent(
        request,
        LateWriter(),
        lambda request, output, artifact: VerifierResult(passed=False),
        workspace_root=tmp_path,
        run_id="run-sync-isolated",
    )
    time.sleep(0.35)

    events = [
        json.loads(line)
        for line in result.event_path.read_text(encoding="utf-8").splitlines()
    ]
    assert time.monotonic() - started < 0.5
    assert events[-1]["type"] == "run_finished"
    assert not (result.artifact_dir / "late.txt").exists()
    assert "late sk-late-secret1234567890" not in result.event_path.read_text(
        encoding="utf-8"
    )


def test_sync_timeout_kills_descendant_process_group(tmp_path):
    request = RunRequest(
        task=TaskSpec(task_id="task-sync-descendant", prompt="child", timeout=0.05),
        model=ModelConfig(provider="fake", model="test"),
        policy=ExecutionPolicy(workspace_root=str(tmp_path)),
        workspace=tmp_path,
        limits=RunLimits(timeout_seconds=0.05),
    )
    late_file = tmp_path / "descendant-late.txt"
    events_path = tmp_path / "descendant-late-events.jsonl"
    descendant_code = (
        "import pathlib,signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); "
        "time.sleep(0.2); "
        "pathlib.Path({!r}).write_text('late', encoding='utf-8'); "
        "pathlib.Path({!r}).open('a').write('\\n{{\"type\":\"model_response\"}}')"
    ).format(str(late_file), str(events_path))

    class DescendantSpawner:
        def run(self, request, context):
            subprocess.Popen([sys.executable, "-c", descendant_code])
            time.sleep(1)
            return "late"

    result = run_agent(
        request,
        DescendantSpawner(),
        lambda request, output, artifact: VerifierResult(passed=False),
        workspace_root=tmp_path,
        run_id="run-sync-descendant",
    )
    time.sleep(0.35)

    assert result.status == "timeout"
    assert not late_file.exists()
    assert not events_path.exists()


def test_unsupported_sync_process_discards_attempt(tmp_path, monkeypatch):
    monkeypatch.setattr(
        runner_module.multiprocessing,
        "get_all_start_methods",
        lambda: ["spawn"],
    )
    request = RunRequest(
        task=TaskSpec(task_id="task-no-fork", prompt="fail"),
        model=ModelConfig(provider="fake", model="test"),
        policy=ExecutionPolicy(workspace_root=str(tmp_path)),
        workspace=tmp_path,
    )

    with pytest.raises(SyncProcessUnavailable):
        run_agent(
            request,
            type("System", (), {"run": lambda self, request, context: "ok"})(),
            lambda request, output, artifact: VerifierResult(passed=True),
            workspace_root=tmp_path,
            run_id="run-no-fork",
        )

    assert not (tmp_path / "runs" / "task-no-fork").exists()


def test_missing_sync_child_payload_forces_failed_status(tmp_path, monkeypatch):
    monkeypatch.setattr(
        runner_module,
        "_sync_process_entry",
        lambda system, request, context, result_queue: None,
    )
    request = RunRequest(
        task=TaskSpec(task_id="task-no-payload", prompt="fail"),
        model=ModelConfig(provider="fake", model="test"),
        policy=ExecutionPolicy(workspace_root=str(tmp_path)),
        workspace=tmp_path,
    )

    result = run_agent(
        request,
        type("System", (), {"run": lambda self, request, context: "ok"})(),
        lambda request, output, artifact: VerifierResult(passed=True),
        workspace_root=tmp_path,
        run_id="run-no-payload",
    )

    assert result.status == "failed"
    assert result.passed is True


def test_runner_uses_isolated_snapshot_workspace_and_redacts_artifacts(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "safe.py").write_text("print('safe')", encoding="utf-8")
    (source / "config.py").write_text(
        "API_KEY = 'sk-config-secret12345'\n"
        "PRIVATE_KEY = 'private-source-secret'\n"
        "VALUE = 1\n",
        encoding="utf-8",
    )
    (source / ".env").write_text("OPENAI_API_KEY=do-not-copy", encoding="utf-8")
    (source / "credentials.json").write_text("sk-live-secret", encoding="utf-8")
    (source / ".git").mkdir()
    (source / ".git" / "config").write_text("git", encoding="utf-8")
    (source / ".venv").mkdir()
    runner_root = tmp_path / "runner"
    runner_root.mkdir()
    request = RunRequest(
        task=TaskSpec(task_id="task-secret", prompt="copy"),
        model=ModelConfig(provider="fake", model="test"),
        policy=ExecutionPolicy(workspace_root=str(source)),
        workspace=source,
    )
    observed = {}

    class SnapshotSystem:
        def run(self, effective_request, context):
            observed["workspace"] = effective_request.workspace
            observed["policy_root"] = effective_request.policy.workspace_root
            observed["artifact_dir"] = context.artifact_dir
            context.emit(
                "model_response",
                text=(
                    "sk-abc12345678901234567 sk-ant-abc12345678901234567 "
                    "AIza12345678901234567890 hf_token12345678901234567 "
                    "Authorization: Bearer bearer-event-secret"
                ),
                env="MY_API_KEY=event-secret",
            )
            return {
                "text": (
                    "sk-abc12345678901234567 sk-ant-abc12345678901234567 "
                    "AIza12345678901234567890 hf_token12345678901234567 "
                    "Authorization: Bearer bearer-system-secret"
                ),
                "env": "MY_API_KEY=system-secret",
            }

    def verifier(effective_request, output, artifact_dir):
        observed["workspace"] = effective_request.workspace
        observed["policy_root"] = effective_request.policy.workspace_root
        assert effective_request.workspace == observed["workspace"]
        raise RuntimeError(
            "verifier MY_API_KEY=verifier-secret sk-verify12345678901234567 "
            "Authorization: Bearer bearer-verifier-secret"
        )

    result = run_agent(
        request,
        SnapshotSystem(),
        verifier,
        workspace_root=runner_root,
        run_id="run-secret",
    )

    fresh_workspace = observed["workspace"]
    assert fresh_workspace != source
    assert fresh_workspace.parent == result.artifact_dir
    assert observed["policy_root"] == str(fresh_workspace)
    assert (fresh_workspace / "safe.py").exists()
    assert "sk-config-secret12345" not in (
        fresh_workspace / "config.py"
    ).read_text(encoding="utf-8")
    assert "private-source-secret" not in (
        fresh_workspace / "config.py"
    ).read_text(encoding="utf-8")
    assert not (fresh_workspace / ".env").exists()
    assert not (fresh_workspace / "credentials.json").exists()
    assert not (fresh_workspace / ".git").exists()
    artifact_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in result.artifact_dir.glob("*.json*")
    )
    for secret in (
        "do-not-copy",
        "sk-abc12345678901234567",
        "sk-ant-abc12345678901234567",
        "AIza12345678901234567890",
        "hf_token12345678901234567",
        "event-secret",
        "system-secret",
        "verifier-secret",
        "bearer-event-secret",
        "bearer-system-secret",
        "bearer-verifier-secret",
        "sk-config-secret12345",
        "private-source-secret",
    ):
        assert secret not in artifact_text


def test_runner_uses_empty_workspace_when_source_equals_runner_root(tmp_path):
    (tmp_path / "source-file.txt").write_text("source", encoding="utf-8")
    request = RunRequest(
        task=TaskSpec(task_id="task-root", prompt="avoid recursion"),
        model=ModelConfig(provider="fake", model="test"),
        policy=ExecutionPolicy(workspace_root=str(tmp_path)),
        workspace=tmp_path,
    )
    observed = {}

    class RootSystem:
        def run(self, effective_request, context):
            (context.workspace_root / "child-seen.txt").write_text(
                effective_request.workspace.name,
                encoding="utf-8",
            )
            return "done"

    result = run_agent(
        request,
        RootSystem(),
        lambda request, output, artifact: VerifierResult(passed=True),
        workspace_root=tmp_path,
        run_id="run-root",
    )

    workspace = result.artifact_dir / "workspace"
    assert (workspace / "child-seen.txt").read_text(encoding="utf-8") == "workspace"
    assert not (workspace / "source-file.txt").exists()


def test_runner_sanitizes_binary_snapshots_and_post_run_artifacts(tmp_path):
    source = tmp_path / "source-binary"
    source.mkdir()
    (source / "ordinary.py").write_text(
        'VALUE = 1\nEXAMPLE = "sk-example"\n',
        encoding="utf-8",
    )
    (source / "binary.dat").write_bytes(
        b"\x00sk-binary-source-secret12345\xff"
    )
    (source / "large-ordinary.bin").write_bytes(b"x" * (2 * 1024 * 1024))
    (source / "large-secret.bin").write_bytes(
        b"x" * (2 * 1024 * 1024)
        + b"sk-large-secret12345678901234567"
    )
    request = RunRequest(
        task=TaskSpec(task_id="task-binary", prompt="sanitize"),
        model=ModelConfig(provider="fake", model="test"),
        policy=ExecutionPolicy(workspace_root=str(source)),
        workspace=source,
    )

    class ArtifactWriter:
        def run(self, effective_request, context):
            (context.artifact_dir / "post.txt").write_text(
                "Authorization: Bearer post-artifact-secret123\n",
                encoding="utf-8",
            )
            (context.artifact_dir / "post.bin").write_bytes(
                b"\xffhf_post-binary-secret12345"
            )
            (effective_request.workspace / "agent.py").write_text(
                "TOKEN = 'sk-agent-secret12345'\n",
                encoding="utf-8",
            )
            return "ordinary result"

    def verifier(effective_request, output, artifact_dir):
        (artifact_dir / "verifier.txt").write_text(
            "Authorization: Bearer verifier-secret123\n",
            encoding="utf-8",
        )
        return VerifierResult(passed=True)

    result = run_agent(
        request,
        ArtifactWriter(),
        verifier,
        workspace_root=tmp_path / "runner-binary",
        run_id="run-binary",
    )

    assert (result.artifact_dir / "workspace" / "ordinary.py").exists()
    assert "sk-example" in (
        result.artifact_dir / "workspace" / "ordinary.py"
    ).read_text(encoding="utf-8")
    assert (
        result.artifact_dir / "workspace" / "large-ordinary.bin"
    ).stat().st_size == 2 * 1024 * 1024
    persisted = b"\n".join(
        path.read_bytes()
        for path in result.artifact_dir.rglob("*")
        if path.is_file()
    )
    for secret in (
        b"sk-binary-source-secret12345",
        b"post-artifact-secret123",
        b"hf_post-binary-secret12345",
        b"sk-agent-secret12345",
        b"verifier-secret123",
        b"sk-large-secret12345678901234567",
    ):
        assert secret not in persisted


def test_runner_cleans_orphan_attempt_when_workspace_setup_fails(tmp_path):
    runner_root = tmp_path / "runner-orphan"
    request = RunRequest(
        task=TaskSpec(task_id="task-orphan", prompt="fail setup"),
        model=ModelConfig(provider="fake", model="test"),
        policy=ExecutionPolicy(workspace_root=str(tmp_path / "missing")),
        workspace=tmp_path / "missing",
    )

    class NeverRun:
        def run(self, request, context):
            raise AssertionError("system should not run")

    with pytest.raises(Exception):
        run_agent(
            request,
            NeverRun(),
            lambda request, output, artifact: VerifierResult(passed=False),
            workspace_root=runner_root,
            run_id="run-orphan",
        )

    assert not (runner_root / "runs" / "task-orphan").exists()


def test_agent_wall_time_excludes_verifier_time(tmp_path):
    request = RunRequest(
        task=TaskSpec(task_id="task-wall", prompt="measure"),
        model=ModelConfig(provider="fake", model="test"),
        policy=ExecutionPolicy(workspace_root=str(tmp_path)),
        workspace=tmp_path,
    )

    def verifier(request, output, artifact_dir):
        time.sleep(0.05)
        return VerifierResult(passed=True)

    class FastSystem:
        def run(self, request, context):
            return "agent"

    result = run_agent(
        request,
        FastSystem(),
        verifier,
        workspace_root=tmp_path,
        run_id="run-wall",
    )

    assert result.wall_time < 0.04
