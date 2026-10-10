#!/usr/bin/env python3
"""Paired exact McNemar tests + Wilson intervals between arms of one run.

Reads the frozen score.json of a run, pairs tasks by task_id across arms, and
writes data/processed/paired_<run_id>.csv.
"""

from __future__ import annotations

import csv
import json
import math
import sys
from itertools import combinations
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
METRICS = ("accurate", "propagated", "detection_hit", "recovered")
TASK_SETS = ("micro_qna", "code")
Z = 1.959963984540054


def wilson_interval(successes: int, n: int, z: float = Z) -> Tuple[float, float]:
    if n <= 0:
        return 0.0, 0.0
    p = successes / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return max(0.0, center - half), min(1.0, center + half)


def mcnemar_exact(a_only: int, b_only: int) -> float:
    """Two-sided exact binomial test on discordant pairs."""
    n = a_only + b_only
    if n == 0:
        return 1.0
    k = min(a_only, b_only)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / (2**n)
    return min(1.0, 2 * tail)


def _flag(task: Dict[str, Any], metric: str) -> int:
    return 1 if (task.get("details") or {}).get(metric) else 0


def paired_comparison(
    tasks_a: Sequence[Dict[str, Any]], tasks_b: Sequence[Dict[str, Any]], metric: str
) -> Dict[str, Any]:
    by_b = {t["task_id"]: t for t in tasks_b}
    both = a_only = b_only = neither = 0
    for task in tasks_a:
        other = by_b.get(task["task_id"])
        if other is None:
            continue
        fa, fb = _flag(task, metric), _flag(other, metric)
        if fa and fb:
            both += 1
        elif fa:
            a_only += 1
        elif fb:
            b_only += 1
        else:
            neither += 1
    return {
        "n": both + a_only + b_only + neither,
        "both": both,
        "a_only": a_only,
        "b_only": b_only,
        "neither": neither,
        "p_value": mcnemar_exact(a_only, b_only),
    }


def compare_run(run_id: str, score: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for task_set in TASK_SETS:
        blocks = {
            system: entry[task_set]["tasks"]
            for system, entry in score.items()
            if isinstance(entry, dict)
            and isinstance(entry.get(task_set), dict)
            and "tasks" in entry[task_set]
        }
        for sys_a, sys_b in combinations(blocks, 2):
            for metric in METRICS:
                result = paired_comparison(blocks[sys_a], blocks[sys_b], metric)
                rate_a = sum(_flag(t, metric) for t in blocks[sys_a])
                rate_b = sum(_flag(t, metric) for t in blocks[sys_b])
                lo_a, hi_a = wilson_interval(rate_a, len(blocks[sys_a]))
                lo_b, hi_b = wilson_interval(rate_b, len(blocks[sys_b]))
                rows.append(
                    {
                        "run_id": run_id,
                        "task_set": task_set,
                        "metric": metric,
                        "arm_a": sys_a,
                        "arm_b": sys_b,
                        "rate_a": rate_a / max(1, len(blocks[sys_a])),
                        "wilson_a_low": lo_a,
                        "wilson_a_high": hi_a,
                        "rate_b": rate_b / max(1, len(blocks[sys_b])),
                        "wilson_b_low": lo_b,
                        "wilson_b_high": hi_b,
                        **result,
                    }
                )
    return rows


def main(argv: Sequence[str] = ()) -> None:
    run_ids = list(argv) or ["poison-budget-5"]
    index = json.loads((PROCESSED / "run_index.json").read_text(encoding="utf-8"))
    entries = {e["run_id"]: e for e in index["runs"]}
    for run_id in run_ids:
        if run_id not in entries:
            raise SystemExit("run {} not in run_index.json".format(run_id))
        score = json.loads((ROOT / entries[run_id]["score_json"]).read_text(encoding="utf-8"))
        rows = compare_run(run_id, score)
        out = PROCESSED / "paired_{}.csv".format(run_id)
        with out.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        print("wrote", out, "rows", len(rows))


if __name__ == "__main__":
    main(sys.argv[1:])
