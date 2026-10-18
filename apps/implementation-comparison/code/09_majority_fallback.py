#!/usr/bin/env python3
"""Which replica's workspace does each isolated three-replica arm promote on code tasks?

The string-majority arms promote the last replica whenever no proposal matches the
gold or lie string, which is the usual case for code tasks. This script checks that
mechanism on the raw runs, with no LLM call: it compares the final workspace of every
task with the three replica workspaces (exact text of the non-test Python files) and
reports

* ``final_last``: share of tasks whose final source equals replica 2's source,
* ``final_poisoned_only``: share whose final source equals only the poisoned replica's,
* accuracy when the final source is the poisoned replica's, and when it is not.

Usage:  python code/09_majority_fallback.py poison-budget-7
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
ARMS = ("general-majority-3", "flat-majority-3", "judge-only-3", "dag-bpd")
WORKERS = 3
LAST = WORKERS - 1
IGNORED_DIRS = {"__pycache__", ".pytest_cache"}


def _is_test_file(path: Path) -> bool:
    name = path.name
    return name.startswith("test_") or name.endswith("_test.py") or name == "conftest.py"


def source_text(folder: Path) -> str:
    """Exact text of the non-test Python files below ``folder``, keyed by relative path."""
    folder = Path(folder)
    parts: List[str] = []
    for path in sorted(folder.rglob("*.py")):
        relative = path.relative_to(folder)
        if any(p in IGNORED_DIRS or p.startswith(".") for p in relative.parts) or _is_test_file(path):
            continue
        parts.append("{}\n{}".format(relative.as_posix(), path.read_text(encoding="utf-8", errors="replace")))
    return "\n\x00\n".join(parts)


def matching_replicas(task_dir: Path) -> Optional[Tuple[int, ...]]:
    """Indices of the replicas whose source equals the promoted final workspace."""
    task_dir = Path(task_dir)
    final = task_dir / "workspace"
    workers = [task_dir / "workers" / str(i) for i in range(WORKERS)]
    if not final.is_dir() or not all(d.is_dir() for d in workers):
        return None
    final_text = source_text(final)
    return tuple(i for i, d in enumerate(workers) if source_text(d) == final_text)


def analyze_block(run_dir: Path, system: str, block: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for record in block.get("tasks", []):
        if record.get("status") == "timeout":
            continue
        task_dir = (
            Path(run_dir) / system / "code" / "runs" / "runs" / record["task_id"] / str(record.get("attempt", "1"))
        )
        matches = matching_replicas(task_dir)
        if matches is None:
            continue
        position = record.get("poison_worker")
        position = 0 if position is None else int(position)
        rows.append(
            {
                "task_id": record["task_id"],
                "poison_worker": position,
                "matches": matches,
                "final_last": LAST in matches,
                "final_poisoned_only": matches == (position,),
                "accurate": bool((record.get("details") or {}).get("accurate")),
            }
        )
    return rows


def _rate(k: int, n: int) -> float:
    return k / n if n else 0.0


def summarize(run_id: str, system: str, rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    n = len(rows)
    poisoned = [r for r in rows if r["final_poisoned_only"]]
    other = [r for r in rows if not r["final_poisoned_only"]]
    acc_poisoned = sum(1 for r in poisoned if r["accurate"])
    acc_other = sum(1 for r in other if r["accurate"])
    last_k = sum(1 for r in rows if r["final_last"])
    return {
        "run_id": run_id,
        "system": system,
        "n": n,
        "final_last_k": last_k,
        "final_last": _rate(last_k, n),
        "final_poisoned_only_k": len(poisoned),
        "final_poisoned_only": _rate(len(poisoned), n),
        "acc_poisoned_only_k": acc_poisoned,
        "acc_poisoned_only": _rate(acc_poisoned, len(poisoned)),
        "acc_other_k": acc_other,
        "n_other": len(other),
        "acc_other": _rate(acc_other, len(other)),
    }


def main(argv: Sequence[str] = ()) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run")
    args = parser.parse_args(list(argv) if argv else None)
    run_dir = ROOT / "results" / args.run
    score = json.loads((run_dir / "score.json").read_text(encoding="utf-8"))
    summaries: List[Dict[str, Any]] = []
    for system in ARMS:
        block = (score.get(system) or {}).get("code")
        if not block:
            continue
        summary = summarize(args.run, system, analyze_block(run_dir, system, block))
        summaries.append(summary)
        print(
            "{} n={} last={:.2f} poisoned_only={:.2f} acc|poisoned_only={:.2f} acc|other={:.2f}".format(
                system, summary["n"], summary["final_last"], summary["final_poisoned_only"],
                summary["acc_poisoned_only"], summary["acc_other"],
            )
        )
    if not summaries:
        print("no isolated code arms found in", args.run)
        return
    PROCESSED.mkdir(parents=True, exist_ok=True)
    path = PROCESSED / "fallback_{}.csv".format(args.run)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(summaries[0].keys()))
        writer.writeheader()
        writer.writerows(summaries)
    print("wrote", path)


if __name__ == "__main__":
    main(sys.argv[1:])
