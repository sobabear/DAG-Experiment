import pytest

from impl_comparison.workspace import WorkspaceManager, WorkspacePathError


def test_workspace_manager_creates_fresh_isolated_attempts(tmp_path):
    manager = WorkspaceManager(tmp_path)

    first = manager.create_attempt("task-1", "attempt-1")
    (first / "output.txt").write_text("result", encoding="utf-8")
    second = manager.create_attempt("task-1", "attempt-2")

    assert first != second
    assert not (second / "output.txt").exists()
    assert manager.validate_artifact_path(second, "artifact.json") == (
        second / "artifact.json"
    )


def test_workspace_manager_rejects_artifact_escape(tmp_path):
    manager = WorkspaceManager(tmp_path)
    attempt = manager.create_attempt("task-1", "attempt-1")

    with pytest.raises(WorkspacePathError):
        manager.validate_artifact_path(attempt, "../outside.json")


def test_workspace_manager_only_validates_registered_attempt_roots(tmp_path):
    manager = WorkspaceManager(tmp_path)
    unregistered = tmp_path / "runs" / "task-1" / "unregistered"
    unregistered.mkdir(parents=True)

    with pytest.raises(WorkspacePathError):
        manager.validate_artifact_path(unregistered, "artifact.json")


def test_workspace_manager_rejects_source_inside_destination(tmp_path):
    manager = WorkspaceManager(tmp_path)
    attempt = manager.create_attempt("task-1", "attempt-1")
    source = attempt / "workspace"
    source.mkdir()

    with pytest.raises(WorkspacePathError):
        manager.create_workspace(attempt, source)


def test_workspace_manager_skips_destination_subtree_when_source_contains_root(
    tmp_path,
):
    source = tmp_path / "source"
    runner_root = source / "runner"
    source.mkdir()
    runner_root.mkdir()
    (source / "safe.txt").write_text("safe", encoding="utf-8")
    manager = WorkspaceManager(runner_root)
    attempt = manager.create_attempt("task-1", "attempt-1")

    workspace = manager.create_workspace(attempt, source)

    assert (workspace / "safe.txt").exists()
    assert not (workspace / "runner").exists()


def test_workspace_manager_skips_actual_attempt_when_source_is_runs_ancestor(
    tmp_path,
):
    manager = WorkspaceManager(tmp_path)
    attempt = manager.create_attempt("task-ancestor", "attempt-1")
    other = manager.runs_root / "other-task"
    other.mkdir()
    (other / "safe.txt").write_text("safe", encoding="utf-8")

    workspace = manager.create_workspace(attempt, manager.runs_root)

    assert (workspace / "other-task" / "safe.txt").exists()
    assert not (workspace / "task-ancestor" / "attempt-1").exists()
