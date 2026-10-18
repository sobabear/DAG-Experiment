#!/usr/bin/env python3
"""Position analysis and cross-run replication for poison runs.

1. ``position_<run>.csv``: rates by which replica (0, 1, 2) carried the lie, with
   Wilson intervals and a permutation test of whether the outcome depends on the
   position (chi-square statistic, 10,000 seeded label permutations).
2. ``replication_<runA>_vs_<runB>.csv``: the same arm on the same task ids in two
   runs, with exact McNemar tests on discordant tasks. This is a run-to-run
   stability check; it does not separate model sampling noise from a changed
   setting, so read it together with what differs between the two runs.

Usage:
    python code/07_position_breakdown.py poison-budget-7 --replicate-with poison-budget-6-retried
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import random
import sys
import zlib
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
METRICS = ("accurate", "propagated", "detection_hit", "recovered")
TASK_SETS = ("micro_qna", "code")
PERMUTATIONS = 10000


def _load_paired():
    spec = importlib.util.spec_from_file_location(
        "paired_tests_for_position", ROOT / "code" / "04_paired_tests.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


_paired = _load_paired()


def stable_seed(*parts: Any) -> int:
    return zlib.crc32("|".join(str(p) for p in parts).encode("utf-8"))


def _flag(task: Dict[str, Any], metric: str) -> int:
    return 1 if (task.get("details") or {}).get(metric) else 0


def _chi_square(sizes: Sequence[int], successes: Sequence[int]) -> float:
    total, hits = sum(sizes), sum(successes)
    if total == 0 or hits in (0, total):
        return 0.0
    stat = 0.0
    for n_g, k_g in zip(sizes, successes):
        expected_hit = n_g * hits / total
        expected_miss = n_g * (total - hits) / total
        stat += (k_g - expected_hit) ** 2 / expected_hit
        stat += ((n_g - k_g) - expected_miss) ** 2 / expected_miss
    return stat


def permutation_pvalue(
    pairs: Sequence[Tuple[int, int]], seed: int, permutations: int = PERMUTATIONS
) -> float:
    """Permutation p-value for dependence of a binary outcome on a group label.

    ``pairs`` holds (group, outcome). The statistic is chi-square over the groups;
    outcomes are shuffled across fixed group sizes. Returns 1.0 when the outcome
    does not vary at all.
    """
    groups = sorted({g for g, _ in pairs})
    outcomes = [o for _, o in pairs]
    if len(set(outcomes)) < 2 or len(groups) < 2:
        return 1.0
    sizes = [sum(1 for g, _ in pairs if g == group) for group in groups]
    labels: List[int] = []
    for index, size in enumerate(sizes):
        labels.extend([index] * size)

    def statistic(values: Sequence[int]) -> float:
        hits = [0] * len(groups)
        for label, value in zip(labels, values):
            hits[label] += value
        return _chi_square(sizes, hits)

    ordered = [o for _, o in sorted(pairs, key=lambda item: item[0])]
    observed = statistic(ordered)
    rng = random.Random(seed)
    shuffled = list(ordered)
    at_least = 0
    for _ in range(permutations):
        rng.shuffle(shuffled)
        if statistic(shuffled) >= observed - 1e-12:
            at_least += 1
    return (at_least + 1) / (permutations + 1)


def position_rows(run_id: str, score: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for system, entry in score.items():
        if not isinstance(entry, dict):
            continue
        for task_set in TASK_SETS:
            block = entry.get(task_set)
            if not isinstance(block, dict):
                continue
            tasks = [
                t for t in block.get("tasks", []) if t.get("poison_worker") is not None
            ]
            if not tasks:
                continue
            p_values = {
                metric: permutation_pvalue(
                    [(int(t["poison_worker"]), _flag(t, metric)) for t in tasks],
                    seed=stable_seed(run_id, system, task_set, metric),
                )
                for metric in METRICS
            }
            for position in sorted({int(t["poison_worker"]) for t in tasks}):
                group = [t for t in tasks if int(t["poison_worker"]) == position]
                row: Dict[str, Any] = {
                    "run_id": run_id,
                    "system": system,
                    "task_set": task_set,
                    "position": position,
                    "n": len(group),
                }
                for metric in METRICS:
                    k = sum(_flag(t, metric) for t in group)
                    lo, hi = _paired.wilson_interval(k, len(group))
                    row["{}_k".format(metric)] = k
                    row[metric] = k / len(group)
                    row["{}_ci_low".format(metric)] = lo
                    row["{}_ci_high".format(metric)] = hi
                    row["perm_p_{}".format(metric)] = p_values[metric]
                rows.append(row)
    return rows


def replication_rows(
    run_a: str, run_b: str, score_a: Dict[str, Any], score_b: Dict[str, Any]
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for system in score_a:
        if system not in score_b:
            continue
        for task_set in TASK_SETS:
            block_a = (score_a[system] or {}).get(task_set)
            block_b = (score_b[system] or {}).get(task_set)
            if not isinstance(block_a, dict) or not isinstance(block_b, dict):
                continue
            tasks_a, tasks_b = block_a.get("tasks", []), block_b.get("tasks", [])
            for metric in METRICS:
                result = _paired.paired_comparison(tasks_a, tasks_b, metric)
                rows.append(
                    {
                        "run_a": run_a,
                        "run_b": run_b,
                        "system": system,
                        "task_set": task_set,
                        "metric": metric,
                        "rate_a": sum(_flag(t, metric) for t in tasks_a) / max(1, len(tasks_a)),
                        "rate_b": sum(_flag(t, metric) for t in tasks_b) / max(1, len(tasks_b)),
                        **result,
                    }
                )
    return rows


def _write_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    PROCESSED.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print("wrote", path, "rows", len(rows))


def _load_score(run_id: str) -> Dict[str, Any]:
    return json.loads((ROOT / "results" / run_id / "score.json").read_text(encoding="utf-8"))


def main(argv: Sequence[str] = ()) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run")
    parser.add_argument("--replicate-with", default=None)
    args = parser.parse_args(list(argv) if argv else None)
    score = _load_score(args.run)
    rows = position_rows(args.run, score)
    if rows:
        _write_csv(PROCESSED / "position_{}.csv".format(args.run), rows)
    else:
        print("no poison_worker recorded in {}; nothing to write".format(args.run))
    if args.replicate_with:
        other = _load_score(args.replicate_with)
        rep = replication_rows(args.run, args.replicate_with, score, other)
        _write_csv(
            PROCESSED / "replication_{}_vs_{}.csv".format(args.run, args.replicate_with), rep
        )


if __name__ == "__main__":
    main(sys.argv[1:])
