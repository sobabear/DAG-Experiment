"""Difficulty calibration for the research-30 suite.

Fake LLM calibration is a harness check only, not the research result.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from .protocol import TaskSpec
from .research_suite import apply_reference_fix, materialize_task, verify_task

SYSTEM_IDS = ("dag-bpd", "dag-yonsei", "general-agent-system")

AREA_TIMEOUT_MAX = {
    "se": 90.0,
    "terminal": 120.0,
    "qna": 60.0,
}

HARNESS_DISCLAIMER = (
    "Fake LLM calibration is a harness check only, not the research result. "
    "This is a custom suite and cannot be compared numerically with the public "
    "Artificial Analysis leaderboard."
)

_TEXT_SUFFIXES = {".py", ".md", ".json", ".txt", ".toml", ".cfg", ".ini"}


def validate_suite(
    tasks: Iterable[TaskSpec],
    workdir: Optional[Path] = None,
) -> List[str]:
    """Return issue strings for suite validity. Empty means the suite is valid."""
    task_list = list(tasks)
    issues: List[str] = []
    issues.extend(_unique_id_issues(task_list))
    for task in task_list:
        issues.extend(_timeout_issues(task))
        issues.extend(_prompt_text_issues(task))
    if workdir is not None:
        root = Path(workdir)
        root.mkdir(parents=True, exist_ok=True)
        for task in task_list:
            issues.extend(_materialized_issues(task, root / task.task_id))
    return issues


def classify_attempts(per_system_bits: Mapping[str, Sequence[int]]) -> str:
    """Tag a task as ceiling, floor, or ok from 3-attempt bits per system."""
    values = []
    for system_id in SYSTEM_IDS:
        if system_id not in per_system_bits:
            raise ValueError("missing system: {}".format(system_id))
        bits = [int(item) for item in per_system_bits[system_id]]
        if len(bits) != 3:
            raise ValueError("expected 3 attempts for {}".format(system_id))
        values.append(bits)
    if all(bits == [1, 1, 1] for bits in values):
        return "ceiling"
    if all(bits == [0, 0, 0] for bits in values):
        return "floor"
    return "ok"


def calibration_report(
    records: Sequence[Mapping[str, object]],
) -> Tuple[Dict[str, object], str]:
    """Build a per-task calibration dict and markdown. Ceiling/floor stay as controls."""
    tasks: Dict[str, Dict[str, object]] = {}
    excluded: List[Dict[str, str]] = []
    for record in records:
        task_id = str(record["task_id"])
        attempts = {
            system_id: [int(bit) for bit in record["attempts"][system_id]]  # type: ignore[index]
            for system_id in SYSTEM_IDS
        }
        bits: List[int] = []
        for system_id in SYSTEM_IDS:
            bits.extend(attempts[system_id])
        pass_count = sum(bits)
        fail_count = len(bits) - pass_count
        reasons = [str(item) for item in list(record.get("reasons") or []) if item]
        invalid = bool(record.get("invalid"))
        invalid_reason = str(record.get("invalid_reason") or "")
        tasks[task_id] = {
            "pass_count": pass_count,
            "fail_count": fail_count,
            "reasons": reasons,
            "tag": classify_attempts(attempts),
            "attempts": attempts,
            "invalid": invalid,
            "invalid_reason": invalid_reason,
        }
        if invalid:
            excluded.append(
                {
                    "task_id": task_id,
                    "reason": invalid_reason or "invalid task",
                }
            )
    report: Dict[str, object] = {
        "tasks": tasks,
        "excluded": excluded,
        "disclaimer": HARNESS_DISCLAIMER,
    }
    return report, _render_markdown(report)


def primary_task_ids(report: Mapping[str, object]) -> List[str]:
    """Primary comparison IDs: drop invalid tasks only. Ceiling/floor remain."""
    tasks = report.get("tasks") or {}
    ids: List[str] = []
    for task_id, row in tasks.items():  # type: ignore[union-attr]
        if isinstance(row, Mapping) and row.get("invalid"):
            continue
        ids.append(str(task_id))
    return ids


def _unique_id_issues(tasks: Sequence[TaskSpec]) -> List[str]:
    seen = set()
    issues = []
    for task in tasks:
        if task.task_id in seen:
            issues.append("duplicate task_id: {}".format(task.task_id))
        seen.add(task.task_id)
    if issues:
        issues.insert(0, "task_ids must be unique")
    return issues


def _timeout_issues(task: TaskSpec) -> List[str]:
    issues = []
    if task.timeout <= 0:
        issues.append("{}: timeout must be positive".format(task.task_id))
    maximum = AREA_TIMEOUT_MAX.get(task.area)
    if maximum is not None and task.timeout > maximum:
        issues.append(
            "{}: timeout {} exceeds {} bound for area {}".format(
                task.task_id, task.timeout, maximum, task.area
            )
        )
    return issues


def _prompt_text_issues(task: TaskSpec) -> List[str]:
    issues = []
    lowered = task.prompt.lower()
    if "apply_reference_fix" in lowered:
        issues.append(
            "{}: prompt contains apply_reference_fix".format(task.task_id)
        )
    if "hidden verifier" in lowered:
        issues.append("{}: prompt contains hidden verifier".format(task.task_id))
    return issues


def _materialized_issues(task: TaskSpec, dest: Path) -> List[str]:
    issues: List[str] = []
    dest.mkdir(parents=True, exist_ok=True)
    isolation = _isolation_issue(task, dest)
    if isolation:
        issues.append(isolation)
    issues.extend(_verifier_and_gold_issues(task, dest))
    return issues


def _isolation_issue(task: TaskSpec, dest: Path) -> Optional[str]:
    dest_a = dest / "iso-a"
    dest_b = dest / "iso-b"
    materialize_task(task, dest_a)
    materialize_task(task, dest_b)
    marker = dest_a / "isolation-marker.txt"
    marker.write_text("only-a", encoding="utf-8")
    if (dest_b / "isolation-marker.txt").is_file():
        return "{}: materializations are not isolated".format(task.task_id)
    target = _first_text_file(dest_a, skip={marker})
    if target is None:
        return "{}: materialized workspace is empty".format(task.task_id)
    original = target.read_text(encoding="utf-8", errors="replace")
    target.write_text(original + "\n# mutated\n", encoding="utf-8")
    other = dest_b / target.relative_to(dest_a)
    if other.is_file():
        copied = other.read_text(encoding="utf-8", errors="replace")
        if "# mutated" in copied:
            return "{}: materializations share state".format(task.task_id)
    return None


def _verifier_and_gold_issues(task: TaskSpec, dest: Path) -> List[str]:
    issues: List[str] = []
    broken_dir = dest / "broken"
    corrected_dir = dest / "corrected"
    materialize_task(task, broken_dir)
    broken = verify_task(task, broken_dir)
    materialize_task(task, corrected_dir)
    apply_reference_fix(task, corrected_dir)
    corrected = verify_task(task, corrected_dir)
    if broken.passed and corrected.passed:
        issues.append(
            "{}: verifier does not distinguish broken vs corrected "
            "(both pass)".format(task.task_id)
        )
    elif (not broken.passed) and (not corrected.passed):
        issues.append(
            "{}: verifier does not distinguish broken vs corrected "
            "(both fail)".format(task.task_id)
        )
    elif broken.passed:
        issues.append(
            "{}: broken fixture passed hidden verifier".format(task.task_id)
        )
    elif not corrected.passed:
        issues.append(
            "{}: corrected fixture failed hidden verifier ({})".format(
                task.task_id, corrected.reason
            )
        )
    gold_path = corrected_dir / "answer.txt"
    if gold_path.is_file():
        gold = gold_path.read_text(encoding="utf-8")
        if gold.strip() and task.prompt.strip() == gold.strip():
            issues.append(
                "{}: prompt equals gold answer.txt".format(task.task_id)
            )
        elif gold.strip() and gold.strip() in task.prompt:
            issues.append(
                "{}: prompt contains gold answer.txt body".format(task.task_id)
            )
    return issues


def _first_text_file(root: Path, skip: Optional[set] = None) -> Optional[Path]:
    ignored = skip or set()
    preferred: List[Path] = []
    others: List[Path] = []
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        if not path.is_file() or path in ignored:
            continue
        if path.suffix.lower() in _TEXT_SUFFIXES:
            preferred.append(path)
        else:
            others.append(path)
    if preferred:
        return preferred[0]
    if others:
        return others[0]
    return None


def _render_markdown(report: Mapping[str, object]) -> str:
    lines = [
        "# Research-30 calibration report",
        "",
        HARNESS_DISCLAIMER,
        "",
        "Do not publish Fake LLM scores as the study result. Real research uses "
        "an environment-configured LLM. Always write Artificial Analysis in full. "
        "This custom suite is not the public Artificial Analysis leaderboard.",
        "",
        "Ceiling and floor tasks are kept as controls in the suite and remain in "
        "the primary comparison unless they are also invalid.",
        "",
        "## Tasks",
        "",
        "| task_id | tag | pass_count | fail_count | reasons |",
        "|---------|-----|------------|------------|---------|",
    ]
    tasks = report.get("tasks") or {}
    for task_id, row in tasks.items():  # type: ignore[union-attr]
        reasons = row.get("reasons") or []
        reason_text = "; ".join(str(item) for item in reasons) or ""
        lines.append(
            "| {} | {} | {} | {} | {} |".format(
                task_id,
                row.get("tag"),
                row.get("pass_count"),
                row.get("fail_count"),
                reason_text.replace("|", "/"),
            )
        )
    lines.extend(["", "## Excluded from primary comparison", ""])
    excluded = list(report.get("excluded") or [])
    if not excluded:
        lines.append("None. Invalid tasks are excluded only after recording a reason.")
    else:
        for item in excluded:
            lines.append(
                "- `{}`: {}".format(item["task_id"], item["reason"])
            )
    lines.append("")
    return "\n".join(lines) + "\n"
