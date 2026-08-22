from pathlib import Path

from impl_comparison.protocol import TaskSpec, VerifierResult
from impl_comparison.suite import FALLBACK_TASKS, materialize_task, verify_task


def test_fallback_suite_has_one_task_per_index_component():
    benches = {task.benchmark for task in FALLBACK_TASKS}
    assert benches == {"deepswe", "terminal_bench_v2", "swe_atlas_qna"}
    assert len(FALLBACK_TASKS) == 3


def test_se_verifier_fails_on_buggy_add(tmp_path):
    task = _task("se-add")
    workspace = materialize_task(task, tmp_path)
    result = verify_task(task, workspace)
    assert result.passed is False


def test_se_verifier_passes_after_fix(tmp_path):
    task = _task("se-add")
    workspace = materialize_task(task, tmp_path)
    (workspace / "add.py").write_text(
        "def add(a, b):\n    return a + b\n", encoding="utf-8"
    )
    assert verify_task(task, workspace).passed is True


def test_qna_verifier_checks_answer_file(tmp_path):
    task = _task("qna-token")
    workspace = materialize_task(task, tmp_path)
    assert verify_task(task, workspace).passed is False
    (workspace / "answer.txt").write_text("ALPHA-42\n", encoding="utf-8")
    assert verify_task(task, workspace).passed is True


def test_terminal_verifier_checks_hash(tmp_path):
    task = _task("terminal-hash")
    workspace = materialize_task(task, tmp_path)
    import hashlib

    expected = hashlib.sha256((workspace / "data.txt").read_bytes()).hexdigest()
    (workspace / "answer.txt").write_text(expected + "\n", encoding="utf-8")
    assert verify_task(task, workspace).passed is True


def _task(task_id: str) -> TaskSpec:
    return next(task for task in FALLBACK_TASKS if task.task_id == task_id)
