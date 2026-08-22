from impl_comparison.events import EventLog
from impl_comparison.protocol import (
    ExecutionPolicy,
    ModelConfig,
    RunLimits,
    RunRequest,
)
from impl_comparison.runner import RunnerContext, run_agent
from impl_comparison.suite import FALLBACK_TASKS, materialize_task, verify_run
from impl_comparison.systems.bpd import BpdDagSystem
from impl_comparison.systems.general import GeneralAgentSystem
from impl_comparison.systems.yonsei import YonseiDagSystem
from impl_comparison.coding_llm import WorkspaceAwareLLM
from impl_comparison.llm import FakeLLM
from impl_comparison.telemetry import MetricsAccumulator


def _orphan_tool_messages(messages):
    return [
        message
        for message in messages
        if message.get("role") == "tool" and not message.get("tool_call_id")
    ]


def _policy(workspace):
    return ExecutionPolicy(
        headless=True,
        allow_writes=True,
        allow_shell=True,
        allow_destructive=True,
        require_confirmation_for_writes=False,
        workspace_root=str(workspace),
    )


def _run(system, task, tmp_path, name):
    source = tmp_path / "src-{}".format(task.task_id)
    materialize_task(task, source)
    request = RunRequest(
        task=task,
        model=ModelConfig(provider="fake", model="workspace-aware"),
        policy=_policy(source),
        limits=RunLimits(max_turns=24, max_tool_calls=80, timeout_seconds=60.0),
        workspace=source,
        system_name=name,
        attempt="1",
    )
    return run_agent(
        request,
        system,
        verify_run,
        workspace_root=tmp_path / "runs-{}".format(name),
        run_id="{}-{}".format(name, task.task_id),
    )


def _task(task_id):
    return next(task for task in FALLBACK_TASKS if task.task_id == task_id)


def _in_process_run(system, task, tmp_path):
    workspace = tmp_path / "workspace"
    materialize_task(task, workspace)
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    request = RunRequest(
        task=task,
        model=ModelConfig(provider="fake", model="workspace-aware"),
        policy=_policy(workspace),
        limits=RunLimits(max_turns=3, max_tool_calls=8, timeout_seconds=15.0),
        workspace=workspace,
        system_name="in-process",
        attempt="1",
    )
    context = RunnerContext(
        artifact_dir=artifacts,
        transcript_path=artifacts / "transcript.jsonl",
        event_log=EventLog(artifacts / "events.jsonl"),
        metrics=MetricsAccumulator(),
        workspace_root=workspace,
    )
    return system.run(request, context), request, context


def test_general_agent_fails_se_without_forced_tests(tmp_path):
    result = _run(GeneralAgentSystem(WorkspaceAwareLLM()), _task("se-add"), tmp_path, "general")
    assert result.passed is False


def test_yonsei_dag_repairs_se_after_forced_tests(tmp_path):
    result = _run(YonseiDagSystem(WorkspaceAwareLLM()), _task("se-add"), tmp_path, "yonsei")
    assert result.passed is True


def test_bpd_dag_repairs_se_after_worker_tests(tmp_path):
    result = _run(BpdDagSystem(WorkspaceAwareLLM()), _task("se-add"), tmp_path, "bpd")
    assert result.passed is True


def test_all_systems_solve_qna(tmp_path):
    task = _task("qna-token")
    for name, system in (
        ("general", GeneralAgentSystem(WorkspaceAwareLLM())),
        ("yonsei", YonseiDagSystem(WorkspaceAwareLLM())),
        ("bpd", BpdDagSystem(WorkspaceAwareLLM())),
    ):
        assert _run(system, task, tmp_path / name, name).passed is True


def test_run_workspace_pytest_failed_passed_no_tests_and_se_add(tmp_path):
    from impl_comparison.systems.workspace_tests import run_workspace_pytest

    empty = tmp_path / "empty"
    empty.mkdir()
    assert run_workspace_pytest(empty) == "no tests"

    failing = tmp_path / "failing"
    failing.mkdir()
    (failing / "foo.py").write_text("def foo():\n    return 1\n", encoding="utf-8")
    (failing / "test_foo.py").write_text(
        "from foo import foo\n\n\ndef test_foo():\n    assert foo() == 2\n",
        encoding="utf-8",
    )
    failed = run_workspace_pytest(failing)
    assert "FAILED" in failed

    (failing / "foo.py").write_text("def foo():\n    return 2\n", encoding="utf-8")
    passed = run_workspace_pytest(failing)
    assert "FAILED" not in passed
    assert passed

    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "foo.py").write_text("def foo():\n    return 0\n", encoding="utf-8")
    (nested / "tests").mkdir()
    (nested / "tests" / "test_foo.py").write_text(
        "from foo import foo\n\n\ndef test_foo():\n    assert foo() == 1\n",
        encoding="utf-8",
    )
    nested_failed = run_workspace_pytest(nested)
    assert "FAILED" in nested_failed

    se_add = tmp_path / "se-add"
    se_add.mkdir()
    (se_add / "add.py").write_text(
        "def add(a, b):\n    return a - b\n", encoding="utf-8"
    )
    (se_add / "test_add.py").write_text(
        "from add import add\n\n\ndef test_add():\n    assert add(2, 3) == 5\n",
        encoding="utf-8",
    )
    se_failed = run_workspace_pytest(se_add)
    assert "FAILED" in se_failed


def test_yonsei_does_not_send_orphan_tool_messages(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "impl_comparison.systems.yonsei.run_workspace_pytest",
        lambda workspace: "FAILED AssertionError\n",
    )
    llm = FakeLLM([{"content": "done"}] * 4)
    _in_process_run(YonseiDagSystem(llm), _task("se-add"), tmp_path)
    assert llm.requests
    first = llm.requests[0].messages
    assert first
    leading = first[0]
    assert not (
        leading.get("role") == "tool" and not leading.get("tool_call_id")
    )
    for request in llm.requests:
        assert _orphan_tool_messages(request.messages) == []


def test_bpd_does_not_send_orphan_tool_messages(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "impl_comparison.systems.bpd.run_workspace_pytest",
        lambda workspace: "FAILED AssertionError\n",
    )
    llm = FakeLLM([{"content": "done"}] * 4)
    _in_process_run(BpdDagSystem(llm, workers=1), _task("se-add"), tmp_path)
    assert llm.requests
    for request in llm.requests:
        assert _orphan_tool_messages(request.messages) == []
