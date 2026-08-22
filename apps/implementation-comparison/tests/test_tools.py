from pathlib import Path
import shlex
import sys
import threading
import time

import pytest

from impl_comparison.policy import PolicyError
from impl_comparison.protocol import ExecutionPolicy, RunLimits
from impl_comparison.telemetry import MetricsAccumulator, RunLimitExceeded
from impl_comparison.tools import (
    EditTool,
    GlobTool,
    ListTool,
    ReadTool,
    ReplaceTool,
    SearchTool,
    ShellTool,
    ToolContext,
    ToolRegistry,
    WriteTool,
)


def test_registry_exposes_tool_metadata_and_safe_file_operations(tmp_path):
    registry = ToolRegistry(
        [
            GlobTool(),
            ReadTool(),
            WriteTool(),
            EditTool(),
            ShellTool(),
        ]
    )
    assert registry.names() == ["edit", "glob", "read", "shell", "write"]
    assert registry.get("read").read_only is True
    assert registry.get("write").destructive is False
    assert registry.get("shell").concurrency_safe is False

    context = ToolContext(
        workspace_root=tmp_path,
        policy=ExecutionPolicy(
            workspace_root=str(tmp_path), allow_writes=True, allow_shell=True
        ),
    )
    registry.execute("write", {"path": "note.txt", "content": "old"}, context)
    registry.execute(
        "edit",
        {"path": "note.txt", "old": "old", "new": "new"},
        context,
    )

    assert registry.execute("read", {"path": "note.txt"}, context)["content"] == "new"
    assert registry.execute("glob", {"pattern": "*.txt"}, context)["matches"] == [
        "note.txt"
    ]


def test_registry_denies_outside_paths_and_unapproved_shell(tmp_path):
    registry = ToolRegistry([ReadTool(), ShellTool()])
    context = ToolContext(
        workspace_root=tmp_path,
        policy=ExecutionPolicy(workspace_root=str(tmp_path)),
    )

    with pytest.raises(PolicyError):
        registry.execute("read", {"path": "../secret.txt"}, context)
    with pytest.raises(PolicyError):
        registry.execute("shell", {"command": "printf unsafe"}, context)


def test_shell_tool_enforces_output_limit(tmp_path):
    registry = ToolRegistry([ShellTool()])
    context = ToolContext(
        workspace_root=tmp_path,
        policy=ExecutionPolicy(
            workspace_root=str(tmp_path),
            allow_shell=True,
            allow_destructive=True,
        ),
        max_output_chars=4,
    )

    result = registry.execute("shell", {"command": "printf 123456"}, context)

    assert result["stdout"] == "1234"
    assert result["truncated"] is True


def test_list_and_replace_aliases_provide_the_basic_tool_variants(tmp_path):
    registry = ToolRegistry([ListTool(), ReplaceTool()])
    context = ToolContext(
        workspace_root=tmp_path,
        policy=ExecutionPolicy(
            workspace_root=str(tmp_path), allow_writes=True
        ),
    )
    (tmp_path / "x.txt").write_text("a", encoding="utf-8")

    assert registry.execute("list", {"path": "."}, context)["entries"] == ["x.txt"]
    registry.execute(
        "replace", {"path": "x.txt", "old": "a", "new": "b"}, context
    )
    assert (tmp_path / "x.txt").read_text(encoding="utf-8") == "b"


def test_ask_decision_uses_approval_callback_but_headless_ask_denies(tmp_path):
    approvals = []
    registry = ToolRegistry([WriteTool()])
    context = ToolContext(
        workspace_root=tmp_path,
        policy=ExecutionPolicy(workspace_root=str(tmp_path)),
        approval_callback=lambda name, arguments: approvals.append(name) or True,
    )

    registry.execute("write", {"path": "approved.txt", "content": "ok"}, context)

    assert approvals == ["write"]
    assert (tmp_path / "approved.txt").read_text(encoding="utf-8") == "ok"

    headless = ToolContext(
        workspace_root=tmp_path,
        policy=ExecutionPolicy(workspace_root=str(tmp_path), headless=True),
        approval_callback=lambda name, arguments: True,
    )
    with pytest.raises(PolicyError):
        registry.execute("write", {"path": "denied.txt", "content": "no"}, headless)


def test_tool_context_rejects_policy_workspace_root_mismatch(tmp_path):
    with pytest.raises(PolicyError):
        ToolContext(
            workspace_root=tmp_path / "caller",
            policy=ExecutionPolicy(workspace_root=str(tmp_path / "configured")),
        )


def test_read_is_bounded_and_search_supports_regex(tmp_path):
    (tmp_path / "large.txt").write_text("needle\n" + "x" * 100, encoding="utf-8")
    registry = ToolRegistry([ReadTool(), SearchTool()])
    context = ToolContext(
        workspace_root=tmp_path,
        policy=ExecutionPolicy(workspace_root=str(tmp_path)),
        max_output_chars=8,
    )

    read_result = registry.execute("read", {"path": "large.txt"}, context)
    search_result = registry.execute(
        "search", {"pattern": r"needle", "path": "large.txt"}, context
    )

    assert len(read_result["content"]) == 8
    assert search_result["matches"][0]["line"] == 1


def test_shell_rejects_workspace_escape_and_reports_timeout(tmp_path):
    registry = ToolRegistry([ShellTool()])
    context = ToolContext(
        workspace_root=tmp_path,
        policy=ExecutionPolicy(
            workspace_root=str(tmp_path),
            allow_shell=True,
            allow_destructive=True,
        ),
        limits=RunLimits(timeout_seconds=0.01),
    )

    with pytest.raises(PolicyError):
        registry.execute("shell", {"command": "cd .. && pwd"}, context)
    result = registry.execute("shell", {"command": "sleep 1"}, context)

    assert result["timed_out"] is True
    assert result["error"]["code"] == "timeout"


def test_shell_truncation_terminates_process_group_during_execution(tmp_path):
    marker = tmp_path / "child-finished.txt"
    child_script = (
        "import pathlib,time; time.sleep(0.5); "
        "pathlib.Path({!r}).write_text('finished')"
    ).format(str(marker))
    parent_script = (
        "import subprocess,sys,time; "
        "subprocess.Popen([sys.executable, '-c', {child!r}]); "
        "sys.stdout.write('x' * 1000000); sys.stdout.flush(); time.sleep(10)"
    ).format(child=child_script)
    command = "{} -c {}".format(sys.executable, shlex.quote(parent_script))
    registry = ToolRegistry([ShellTool()])
    context = ToolContext(
        workspace_root=tmp_path,
        policy=ExecutionPolicy(
            workspace_root=str(tmp_path),
            allow_shell=True,
            allow_destructive=True,
        ),
        limits=RunLimits(timeout_seconds=2),
        max_output_chars=32,
    )

    result = registry.execute("shell", {"command": command}, context)

    assert result["truncated"] is True
    assert len(result["output"]) <= 32
    assert result["error"]["code"] == "output_limit"
    assert not marker.exists()


def test_glob_list_search_bound_matches_and_reject_nonpositive_limits(tmp_path):
    for index in range(4):
        (tmp_path / "file{}.txt".format(index)).write_text(
            "needle", encoding="utf-8"
        )
    registry = ToolRegistry([GlobTool(), ListTool(), SearchTool()])
    context = ToolContext(
        workspace_root=tmp_path,
        policy=ExecutionPolicy(workspace_root=str(tmp_path)),
        max_output_chars=32,
    )

    glob_result = registry.execute(
        "glob", {"pattern": "*.txt", "max_matches": 2}, context
    )
    list_result = registry.execute(
        "list", {"path": ".", "max_matches": 2}, context
    )
    search_result = registry.execute(
        "search",
        {"path": "file0.txt", "pattern": "needle", "max_matches": 1},
        context,
    )

    assert len(glob_result["matches"]) == 2
    assert glob_result["truncated"] is True
    assert len(list_result["entries"]) == 2
    assert list_result["truncated"] is True
    assert search_result["truncated"] is False
    for name, arguments in (
        ("glob", {"pattern": "*", "max_matches": 0}),
        ("list", {"path": ".", "max_matches": 0}),
        ("search", {"path": "file0.txt", "pattern": "x", "max_matches": 0}),
        ("glob", {"pattern": "*", "max_matches": 1001}),
        ("list", {"path": ".", "max_matches": 1001}),
        ("search", {"path": "file0.txt", "pattern": "x", "max_matches": 1001}),
    ):
        with pytest.raises(ValueError):
            registry.execute(name, arguments, context)
    with pytest.raises(ValueError):
        ToolContext(
            workspace_root=tmp_path,
            policy=ExecutionPolicy(workspace_root=str(tmp_path)),
            max_output_chars=0,
        )


def test_execute_many_preserves_order_and_serializes_mutations(tmp_path):
    active = 0
    maximum = 0
    lock = threading.Lock()

    class TrackingWrite:
        name = "tracking-write"
        read_only = False
        destructive = False
        concurrency_safe = False

        def run(self, arguments, context):
            nonlocal active, maximum
            with lock:
                active += 1
                maximum = max(maximum, active)
            time.sleep(0.01)
            with lock:
                active -= 1
            return {"value": arguments["value"]}

    registry = ToolRegistry([TrackingWrite()])
    context = ToolContext(
        workspace_root=tmp_path,
        policy=ExecutionPolicy(
            workspace_root=str(tmp_path), allow_writes=True
        ),
    )

    results = registry.execute_many(
        [
            ("tracking-write", {"value": 1}),
            ("tracking-write", {"value": 2}),
            ("tracking-write", {"value": 3}),
        ],
        context,
        max_workers=3,
    )

    assert [result["value"] for result in results] == [1, 2, 3]
    assert maximum == 1


def test_registry_records_tool_calls_and_enforces_budget(tmp_path):
    (tmp_path / "a.txt").write_text("a", encoding="utf-8")
    metrics = MetricsAccumulator(max_tool_calls=2)
    registry = ToolRegistry([ReadTool()])
    context = ToolContext(
        workspace_root=tmp_path,
        policy=ExecutionPolicy(workspace_root=str(tmp_path)),
        metrics=metrics,
    )

    registry.execute("read", {"path": "a.txt"}, context)
    registry.execute("read", {"path": "a.txt"}, context)

    assert metrics.tool_calls == 2
    with pytest.raises(RunLimitExceeded):
        registry.execute("read", {"path": "a.txt"}, context)


def test_execute_many_records_each_call_and_enforces_budget(tmp_path):
    (tmp_path / "a.txt").write_text("a", encoding="utf-8")
    metrics = MetricsAccumulator(max_tool_calls=1)
    registry = ToolRegistry([ReadTool()])
    context = ToolContext(
        workspace_root=tmp_path,
        policy=ExecutionPolicy(workspace_root=str(tmp_path)),
        metrics=metrics,
    )

    with pytest.raises(RunLimitExceeded):
        registry.execute_many(
            [
                ("read", {"path": "a.txt"}),
                ("read", {"path": "a.txt"}),
            ],
            context,
        )
    assert metrics.tool_calls == 2


def test_execute_many_counts_bounded_parallel_reads_safely(tmp_path):
    metrics = MetricsAccumulator(max_tool_calls=4)

    class ReadProbe:
        name = "read-probe"
        read_only = True
        destructive = False
        concurrency_safe = True

        def run(self, arguments, context):
            time.sleep(0.005)
            return {"value": arguments["value"]}

    registry = ToolRegistry([ReadProbe()])
    context = ToolContext(
        workspace_root=tmp_path,
        policy=ExecutionPolicy(workspace_root=str(tmp_path)),
        metrics=metrics,
    )

    results = registry.execute_many(
        [("read-probe", {"value": value}) for value in range(4)],
        context,
        max_workers=4,
    )

    assert [result["value"] for result in results] == [0, 1, 2, 3]
    assert metrics.tool_calls == 4
