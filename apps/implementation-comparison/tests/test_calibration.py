from collections import Counter
from dataclasses import replace
from pathlib import Path

import pytest

from impl_comparison.calibration import (
    AREA_TIMEOUT_MAX,
    SYSTEM_IDS,
    calibration_report,
    classify_attempts,
    primary_task_ids,
    validate_suite,
)
from impl_comparison.protocol import TaskSpec
from impl_comparison.research_suite import (
    apply_reference_fix,
    materialize_task,
    research_tasks,
    verify_task,
)


def _one_task_per_area():
    selected = {}
    for task in research_tasks():
        if task.area not in selected:
            selected[task.area] = task
        if len(selected) == 3:
            break
    return [selected["se"], selected["terminal"], selected["qna"]]


def _bits(dag_bpd, dag_yonsei, general):
    return {
        "dag-bpd": list(dag_bpd),
        "dag-yonsei": list(dag_yonsei),
        "general-agent-system": list(general),
    }


def _record(task_id, attempts, reasons=None, invalid=False, invalid_reason=""):
    return {
        "task_id": task_id,
        "attempts": attempts,
        "reasons": list(reasons or []),
        "invalid": invalid,
        "invalid_reason": invalid_reason,
    }


def test_suite_has_unique_ids_thirty_tasks_ten_per_area():
    tasks = research_tasks()
    assert len(tasks) == 30
    assert len({task.task_id for task in tasks}) == 30
    assert Counter(task.area for task in tasks) == {"se": 10, "terminal": 10, "qna": 10}
    assert validate_suite(tasks) == []


def test_validate_suite_rejects_duplicate_ids():
    task = research_tasks()[0]
    issues = validate_suite([task, task])
    assert issues
    assert any("unique" in issue.lower() or "duplicate" in issue.lower() for issue in issues)


def test_timeouts_are_bounded():
    tasks = research_tasks()
    for task in tasks:
        assert task.timeout > 0, task.task_id
        assert task.timeout <= AREA_TIMEOUT_MAX[task.area], task.task_id
    assert validate_suite(tasks) == []


def test_validate_suite_rejects_unbounded_timeout():
    task = TaskSpec(
        task_id="se-too-slow",
        prompt="Fix the bug in the workspace.",
        area="se",
        timeout=91.0,
    )
    issues = validate_suite([task])
    assert issues
    assert any("timeout" in issue.lower() for issue in issues)


def test_fresh_materialization_isolation_one_per_area(tmp_path):
    tasks = _one_task_per_area()
    assert validate_suite(tasks, workdir=tmp_path / "validated") == []
    for task in tasks:
        dest_a = tmp_path / task.task_id / "a"
        dest_b = tmp_path / task.task_id / "b"
        out_a = materialize_task(task, dest_a)
        out_b = materialize_task(task, dest_b)
        assert Path(out_a).resolve() == dest_a.resolve()
        assert Path(out_b).resolve() == dest_b.resolve()
        marker = dest_a / "isolation-marker.txt"
        marker.write_text("only-a", encoding="utf-8")
        assert not (dest_b / "isolation-marker.txt").is_file()
        files = [path for path in dest_a.rglob("*") if path.is_file() and path != marker]
        assert files, task.task_id
        original = files[0].read_text(encoding="utf-8", errors="replace")
        files[0].write_text(original + "\n# mutated\n", encoding="utf-8")
        relative = files[0].relative_to(dest_a)
        other = dest_b / relative
        if other.is_file():
            assert "# mutated" not in other.read_text(encoding="utf-8", errors="replace")


def test_prompts_do_not_equal_gold_or_contain_reference_fix(tmp_path):
    tasks = research_tasks()
    for task in tasks:
        prompt = task.prompt
        lowered = prompt.lower()
        assert "apply_reference_fix" not in lowered, task.task_id
        assert "hidden verifier" not in lowered, task.task_id
        if task.area != "qna":
            continue
        workspace = materialize_task(task, tmp_path / task.task_id)
        apply_reference_fix(task, workspace)
        gold_path = workspace / "answer.txt"
        assert gold_path.is_file(), task.task_id
        gold = gold_path.read_text(encoding="utf-8")
        assert gold.strip()
        assert prompt.strip() != gold.strip(), task.task_id
        assert gold.strip() not in prompt, task.task_id
    assert validate_suite(tasks) == []
    sample = [task for task in tasks if task.area == "qna"][:1]
    assert validate_suite(sample, workdir=tmp_path / "qna-valid") == []


def test_validate_suite_rejects_prompt_equal_to_gold(tmp_path):
    task = next(item for item in research_tasks() if item.area == "qna")
    workspace = materialize_task(task, tmp_path / "gold-src")
    apply_reference_fix(task, workspace)
    gold = (workspace / "answer.txt").read_text(encoding="utf-8")
    leaky = replace(task, prompt=gold)
    issues = validate_suite([leaky], workdir=tmp_path / "leaky")
    assert issues
    assert any("answer" in issue.lower() or "gold" in issue.lower() for issue in issues)


def test_validate_suite_rejects_apply_reference_fix_in_prompt():
    task = TaskSpec(
        task_id="se-leaky-prompt",
        prompt="Please call apply_reference_fix on this workspace.",
        area="se",
        timeout=30.0,
    )
    issues = validate_suite([task])
    assert issues
    assert any("apply_reference_fix" in issue.lower() for issue in issues)


def test_hidden_verifier_sample_broken_fails_corrected_passes(tmp_path):
    tasks = _one_task_per_area()
    assert validate_suite(tasks, workdir=tmp_path / "verified") == []
    for task in tasks:
        broken = materialize_task(task, tmp_path / task.task_id / "broken")
        broken_result = verify_task(task, broken)
        assert broken_result.passed is False, (task.task_id, broken_result.reason)
        corrected = materialize_task(task, tmp_path / task.task_id / "corrected")
        apply_reference_fix(task, corrected)
        corrected_result = verify_task(task, corrected)
        assert corrected_result.passed is True, (task.task_id, corrected_result.reason)


def test_classify_attempts_ceiling_floor_and_ok():
    assert (
        classify_attempts(_bits([1, 1, 1], [1, 1, 1], [1, 1, 1])) == "ceiling"
    )
    assert (
        classify_attempts(_bits([0, 0, 0], [0, 0, 0], [0, 0, 0])) == "floor"
    )
    assert classify_attempts(_bits([1, 0, 1], [0, 0, 0], [1, 1, 1])) == "ok"
    assert classify_attempts(_bits([1, 1, 0], [1, 1, 1], [1, 1, 1])) == "ok"


def test_invalid_verifier_excluded_from_primary_ceiling_kept():
    records = [
        _record(
            "t-ceiling",
            _bits([1, 1, 1], [1, 1, 1], [1, 1, 1]),
        ),
        _record(
            "t-floor",
            _bits([0, 0, 0], [0, 0, 0], [0, 0, 0]),
            reasons=["hidden verifier failed"],
        ),
        _record(
            "t-ok",
            _bits([1, 0, 0], [0, 1, 0], [0, 0, 1]),
            reasons=["partial"],
        ),
        _record(
            "t-invalid",
            _bits([1, 1, 1], [1, 1, 1], [1, 1, 1]),
            reasons=["verifier does not distinguish broken vs corrected"],
            invalid=True,
            invalid_reason="verifier does not distinguish broken vs corrected",
        ),
    ]
    report, markdown = calibration_report(records)
    ids = primary_task_ids(report)
    assert "t-invalid" not in ids
    assert "t-ceiling" in ids
    assert "t-floor" in ids
    assert "t-ok" in ids
    excluded = report["excluded"]
    assert any(item["task_id"] == "t-invalid" for item in excluded)
    invalid_row = next(item for item in excluded if item["task_id"] == "t-invalid")
    assert "distinguish" in invalid_row["reason"].lower()
    assert report["tasks"]["t-ceiling"]["tag"] == "ceiling"
    assert report["tasks"]["t-floor"]["tag"] == "floor"
    assert report["tasks"]["t-ok"]["tag"] == "ok"
    assert report["tasks"]["t-ceiling"]["pass_count"] == 9
    assert report["tasks"]["t-ceiling"]["fail_count"] == 0
    assert report["tasks"]["t-floor"]["pass_count"] == 0
    assert report["tasks"]["t-floor"]["fail_count"] == 9
    assert "t-invalid" in markdown
    assert "t-ceiling" in markdown


def test_report_markdown_contains_harness_disclaimer_and_artificial_analysis():
    records = [
        _record("t-ok", _bits([1, 0, 1], [0, 1, 0], [1, 1, 0]), reasons=["timeout"]),
    ]
    report, markdown = calibration_report(records)
    lowered = markdown.lower()
    assert "harness check" in lowered
    assert "not the research result" in lowered
    assert "artificial analysis" in lowered
    assert "Artificial Analysis" in markdown
    assert "custom suite" in lowered
    assert "leaderboard" in lowered
    assert "fake llm" in lowered or "fake" in lowered
    assert report["tasks"]["t-ok"]["pass_count"] == 5
    assert report["tasks"]["t-ok"]["fail_count"] == 4
    assert report["tasks"]["t-ok"]["attempts"]["dag-bpd"] == [1, 0, 1]
    assert any("timeout" in reason.lower() for reason in report["tasks"]["t-ok"]["reasons"])


def test_harness_check_classifies_synthetic_bits_not_full_fake_run():
    """Step 5: Fake LLM calibration is a harness check only.

    Do not run the 30-task x 3-system x 3-attempt Fake LLM grid in pytest,
    and do not write Fake LLM scores into results/research-30/comparison.md.
    """
    tag = classify_attempts(_bits([0, 0, 1], [0, 0, 0], [0, 1, 0]))
    assert tag == "ok"
    report, markdown = calibration_report(
        [_record("harness-synthetic", _bits([0, 0, 0], [0, 0, 0], [0, 0, 0]))]
    )
    assert report["tasks"]["harness-synthetic"]["tag"] == "floor"
    assert "harness check" in markdown.lower()
    assert "not the research result" in markdown.lower()
    published = (
        Path(__file__).resolve().parents[1] / "results" / "research-30" / "comparison.md"
    )
    if published.is_file():
        text = published.read_text(encoding="utf-8")
        lowered = text.lower()
        banned = ("workspaceawarellm", "workspace-aware", "fake/workspace-aware")
        assert not any(token in lowered for token in banned)


def test_research_30_readme_documents_suite_and_harness_policy():
    readme = (
        Path(__file__).resolve().parents[1] / "tasks" / "research-30" / "README.md"
    )
    assert readme.is_file()
    text = readme.read_text(encoding="utf-8")
    lowered = text.lower()
    assert "30" in text
    assert "hidden" in lowered and "verifier" in lowered
    assert "3" in text or "three" in lowered
    assert "index" in lowered
    assert "Artificial Analysis" in text
    assert "harness" in lowered
    assert "fake" in lowered
    assert "env" in lowered
    assert "secret" in lowered
    _assert_harness_does_not_autoload_env(text)
    for system_id in SYSTEM_IDS:
        assert system_id in text


def _assert_harness_does_not_autoload_env(text):
    lowered = text.lower()
    assert "auto-load" in lowered or "autoload" in lowered
    assert ".env" in text
    assert "does not auto-load" in lowered or "does **not** auto-load" in lowered
    assert "source .env" in lowered or "set -a" in lowered
