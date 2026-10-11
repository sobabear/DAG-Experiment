#!/usr/bin/env python3
"""Re-run only the tasks that hit the harness wall-clock limit in a frozen run.

The harness aborts a task after ``task.timeout`` seconds (60 s) and records zero
tokens and ``accurate=False``. When this happens at a burst (API latency spike)
the failure is not a property of the system under test. This script re-runs
exactly those (arm, task) pairs with the identical configuration and writes the
result to ``results/<run>-retry/``. It also writes ``results/<run>-retried/``: the
frozen run with exactly those records replaced. The original run stays untouched,
so both versions can be reported.

Usage (needs the same LLM environment variables as the original run):
    python code/06_retry_infra_timeouts.py poison-budget-6 --profile system
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[1]
SUITE_DIRS = {"micro_qna": "micro-qna", "code": "code"}
METRIC_KEYS = ("accurate", "propagated", "detection_hit", "recovered")


def timeout_task_ids(summary: Dict[str, dict]) -> Dict[Tuple[str, str], List[str]]:
    """Map (arm, suite) -> task ids whose run ended with status ``timeout``."""
    selected: Dict[Tuple[str, str], List[str]] = {}
    for arm, suites in summary.items():
        for suite, payload in suites.items():
            ids = [
                record["task_id"]
                for record in payload.get("tasks", [])
                if record.get("status") == "timeout"
            ]
            if ids:
                selected[(arm, suite)] = ids
    return selected


def merge_retry(original: dict, rerun: dict) -> dict:
    """Return ``original`` with its timeout records replaced by the re-run records.

    Rates, counts and token totals are recomputed so the result passes the same
    consistency check as a directly produced ``score.json``. A task that times
    out again keeps its ``timeout`` record, so persistent failures stay visible.
    """
    merged = copy.deepcopy(original)
    replacements = {record["task_id"]: record for record in rerun.get("tasks", [])}
    replaced: List[str] = []
    records = []
    for record in merged["tasks"]:
        if record.get("status") == "timeout" and record["task_id"] in replacements:
            records.append(copy.deepcopy(replacements[record["task_id"]]))
            replaced.append(record["task_id"])
        else:
            records.append(record)
    merged["tasks"] = records
    slots = max(len(records), 1)
    counts = {
        key: sum(1 if (r.get("details") or {}).get(key) else 0 for r in records)
        for key in METRIC_KEYS
    }
    rates = {key: counts[key] / float(slots) for key in METRIC_KEYS}
    flags = [
        1 if (r.get("details") or {}).get("lie_emitted") else 0
        for r in records
        if "lie_emitted" in (r.get("details") or {})
    ]
    if flags:
        counts["lie_emitted"] = sum(flags)
        rates["lie_emitted"] = sum(flags) / float(len(flags))
    merged["counts"] = counts
    merged["rates"] = rates
    merged["n"] = len(records)
    tokens = merged["metrics"]["tokens"]
    for key, value in (rerun.get("metrics", {}).get("tokens") or {}).items():
        tokens[key] = tokens.get(key, 0) + value
    merged["metrics"]["cost_usd"] = tokens.get("cost_usd", 0.0)
    merged["metrics"]["cost_per_task_usd"] = tokens.get("cost_usd", 0.0) / float(slots)
    merged["retried_task_ids"] = replaced
    return merged


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", help="frozen run directory name under results/")
    parser.add_argument("--profile", default="system", choices=["aligned", "system"])
    parser.add_argument("--max-turns", type=int, default=20)
    parser.add_argument(
        "--merge-only",
        action="store_true",
        help="skip the LLM re-run and merge an existing results/<run>-retry/score.json",
    )
    args = parser.parse_args(argv)

    sys.path.insert(0, str(ROOT / "src"))
    from impl_comparison.poison import all_poison_tasks
    from impl_comparison.poison_code_tasks import all_code_poison_tasks
    from impl_comparison.poison_compare import (
        POISON_SYSTEMS,
        _resolve_llm,
        _tag_aligned_profile,
        evaluate_poison_system,
    )

    source = ROOT / "results" / args.run
    summary = json.loads((source / "score.json").read_text(encoding="utf-8"))
    pending = timeout_task_ids(summary)
    if not pending:
        print("no timeouts in {}".format(args.run))
        return
    out_dir = ROOT / "results" / "{}-retry".format(args.run)
    retry_summary: Dict[str, dict] = {}
    if args.merge_only:
        retry_summary = json.loads((out_dir / "score.json").read_text(encoding="utf-8"))
    else:
        llm, model = _resolve_llm(None, None, False)
        builders = {"micro_qna": all_poison_tasks, "code": all_code_poison_tasks}
        for (arm, suite), ids in sorted(pending.items()):
            tasks = _tag_aligned_profile(builders[suite](["agent"]), args.profile)
            wanted = [task for task in tasks if task.task_id in set(ids)]
            if len(wanted) != len(ids):
                raise SystemExit("could not rebuild all tasks for {} {}".format(arm, suite))
            retry_summary.setdefault(arm, {})[suite] = evaluate_poison_system(
                arm,
                POISON_SYSTEMS[arm],
                out_dir / arm / SUITE_DIRS[suite],
                1,
                wanted,
                llm,
                model,
                args.max_turns,
            )
        (out_dir / "score.json").write_text(
            json.dumps(retry_summary, indent=2, sort_keys=True), encoding="utf-8"
        )
        print("wrote {}".format(out_dir / "score.json"))

    from impl_comparison.poison_compare import render_poison_markdown

    merged_summary: Dict[str, dict] = {}
    for arm, suites in summary.items():
        merged_summary[arm] = {}
        for suite, block in suites.items():
            rerun = retry_summary.get(arm, {}).get(suite)
            merged_summary[arm][suite] = merge_retry(block, rerun) if rerun else block
    merged_dir = ROOT / "results" / "{}-retried".format(args.run)
    merged_dir.mkdir(parents=True, exist_ok=True)
    (merged_dir / "score.json").write_text(
        json.dumps(merged_summary, indent=2, sort_keys=True), encoding="utf-8"
    )
    (merged_dir / "comparison.md").write_text(
        render_poison_markdown(merged_summary), encoding="utf-8"
    )
    print("wrote {}".format(merged_dir / "score.json"))


if __name__ == "__main__":
    main()
