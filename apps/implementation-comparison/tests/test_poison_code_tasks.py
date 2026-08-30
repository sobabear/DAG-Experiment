import re

import pytest

from impl_comparison.poison_code_tasks import (
    CODE_POISON_TASKS,
    all_code_poison_tasks,
    code_poison_task,
    materialize_code_poison_task,
)
from impl_comparison.systems.workspace_tests import run_workspace_pytest


def test_code_poison_tasks_have_required_fields():
    assert len(CODE_POISON_TASKS) == 5
    required = {
        "stem",
        "prompt",
        "source_file",
        "source",
        "gold_source",
        "lie_source",
        "lie_pattern",
        "test_file",
        "test_source",
        "notes",
        "gold",
        "lie",
    }
    for spec in CODE_POISON_TASKS:
        assert required.issubset(spec.keys())
        assert spec["gold"] != spec["lie"]
        assert spec["gold"] not in spec["lie"]
        assert spec["lie"] not in spec["gold"]


@pytest.mark.parametrize(
    "spec", CODE_POISON_TASKS, ids=[item["stem"] for item in CODE_POISON_TASKS]
)
def test_code_poison_fixture_discriminates_gold_from_lie(spec, tmp_path):
    workspace = tmp_path / spec["stem"]
    workspace.mkdir()
    (workspace / spec["test_file"]).write_text(spec["test_source"], encoding="utf-8")

    (workspace / spec["source_file"]).write_text(spec["source"], encoding="utf-8")
    assert run_workspace_pytest(workspace) != "passed", "buggy source must fail"

    (workspace / spec["source_file"]).write_text(spec["gold_source"], encoding="utf-8")
    assert run_workspace_pytest(workspace) == "passed", "gold fix must pass"
    gold_content = (workspace / spec["source_file"]).read_text(encoding="utf-8")
    assert re.search(spec["lie_pattern"], gold_content) is None

    (workspace / spec["source_file"]).write_text(spec["lie_source"], encoding="utf-8")
    assert run_workspace_pytest(workspace) != "passed", "lie fix must fail"
    lie_content = (workspace / spec["source_file"]).read_text(encoding="utf-8")
    assert re.search(spec["lie_pattern"], lie_content) is not None


def test_code_poison_task_materializes_buggy_source_and_hidden_test(tmp_path):
    task = code_poison_task("poison-retry-backoff", "document")
    dest = tmp_path / "doc"
    materialize_code_poison_task(task, dest)
    assert (dest / "worker.py").is_file()
    assert (dest / "test_worker.py").is_file()
    assert (dest / "NOTES.md").is_file()
    assert task.metadata["grading"] == "pytest"
    assert task.area == "se"

    clean = tmp_path / "agent"
    materialize_code_poison_task(code_poison_task("poison-retry-backoff", "agent"), clean)
    assert not (clean / "NOTES.md").exists()


def test_all_code_poison_tasks_covers_five_stems_times_three_conditions():
    tasks = all_code_poison_tasks()
    assert len(tasks) == 15
    stems = {item["stem"] for item in CODE_POISON_TASKS}
    assert len(stems) == 5
