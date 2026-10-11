#!/usr/bin/env python3
"""Aggregate poison score.json trees into rates + bootstrap CIs."""

from __future__ import annotations

import csv
import json
import random
import zlib
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
SEED = 20260909
BOOTSTRAP_B = 1000
METRIC_KEYS = ("accurate", "propagated", "detection_hit", "recovered")
OPTIONAL_METRICS = ("lie_emitted",)
TASK_SETS = ("micro_qna", "code")


def stable_seed(*parts: str) -> int:
    """Process-independent seed (built-in hash() is salted per process)."""
    key = "|".join(str(p) for p in parts).encode("utf-8")
    return SEED + (zlib.crc32(key) % 10_000)


def task_flags(tasks: Sequence[Dict[str, Any]]) -> Dict[str, List[int]]:
    flags = {key: [] for key in METRIC_KEYS}
    for item in tasks:
        details = item.get("details") or {}
        for key in METRIC_KEYS:
            flags[key].append(1 if details.get(key) else 0)
    return flags


def mean(values: Sequence[int]) -> float:
    if not values:
        return 0.0
    return sum(values) / float(len(values))


def bootstrap_ci(
    values: Sequence[int], *, seed: int, b: int = BOOTSTRAP_B
) -> Tuple[float, float]:
    if not values:
        return 0.0, 0.0
    rng = random.Random(seed)
    n = len(values)
    samples = []
    for _ in range(b):
        draw = [values[rng.randrange(n)] for _ in range(n)]
        samples.append(mean(draw))
    samples.sort()
    lo = samples[int(0.025 * (b - 1))]
    hi = samples[int(0.975 * (b - 1))]
    return lo, hi


def iter_blocks(score: Dict[str, Any]) -> Iterable[Tuple[str, str, Dict[str, Any]]]:
    for system_id, entry in score.items():
        if not isinstance(entry, dict):
            continue
        for task_set in TASK_SETS:
            block = entry.get(task_set)
            if isinstance(block, dict) and "tasks" in block:
                yield system_id, task_set, block


def _condition_from_task(task: Dict[str, Any]) -> str:
    if task.get("condition"):
        return str(task["condition"])
    task_id = str(task.get("task_id", ""))
    for cond in ("agent", "document", "none"):
        if task_id.endswith("-" + cond):
            return cond
    return "unknown"


def _add_optional_metrics(
    row: Dict[str, Any],
    run_id: str,
    system_id: str,
    task_set: str,
    cond_key: str,
    tasks: Sequence[Dict[str, Any]],
) -> None:
    """Metrics recorded only by newer runs; left blank (None) when absent."""
    recorded = [t for t in tasks if "lie_emitted" in (t.get("details") or {})]
    if not recorded:
        for key in OPTIONAL_METRICS:
            row[key] = None
            row["{}_ci_low".format(key)] = None
            row["{}_ci_high".format(key)] = None
        row["n_lie_emitted"] = None
        row["detection_given_emitted"] = None
        return
    flags = [1 if (t["details"] or {}).get("lie_emitted") else 0 for t in recorded]
    lo, hi = bootstrap_ci(
        flags, seed=stable_seed(run_id, system_id, task_set, cond_key, "lie_emitted")
    )
    row["lie_emitted"] = mean(flags)
    row["lie_emitted_ci_low"] = lo
    row["lie_emitted_ci_high"] = hi
    emitted = [t for t in recorded if (t["details"] or {}).get("lie_emitted")]
    row["n_lie_emitted"] = len(emitted)
    if emitted:
        row["detection_given_emitted"] = mean(
            [1 if (t["details"] or {}).get("detection_hit") else 0 for t in emitted]
        )
    else:
        row["detection_given_emitted"] = None


def aggregate_run(
    run_id: str, score: Dict[str, Any], *, split_condition: bool = True
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for system_id, task_set, block in iter_blocks(score):
        tasks = block.get("tasks") or []
        groups: Dict[str, List[Dict[str, Any]]] = {"__all__": list(tasks)}
        if split_condition:
            for task in tasks:
                cond = _condition_from_task(task)
                groups.setdefault(cond, []).append(task)
        published = block.get("rates") or {}
        for cond_key, group_tasks in groups.items():
            if cond_key != "__all__" and len(group_tasks) == len(tasks):
                # Single-condition run: skip duplicate condition slice matching __all__.
                if len(groups) == 2:
                    continue
            flags = task_flags(group_tasks)
            row: Dict[str, Any] = {
                "run_id": run_id,
                "system": system_id,
                "task_set": task_set,
                "condition": "all" if cond_key == "__all__" else cond_key,
                "n": len(group_tasks),
                "input_tokens_per_task": None,
                "output_tokens_per_task": None,
                "n_timeout": sum(1 for t in group_tasks if t.get("status") == "timeout"),
                "n_retried": len(block.get("retried_task_ids") or []),
            }
            if cond_key == "__all__" and group_tasks:
                tokens = (block.get("metrics") or {}).get("tokens") or {}
                if "input_tokens" in tokens:
                    row["input_tokens_per_task"] = tokens["input_tokens"] / len(group_tasks)
                    row["output_tokens_per_task"] = (
                        tokens.get("output_tokens", 0) / len(group_tasks)
                    )
            for key in METRIC_KEYS:
                values = flags[key]
                emp = mean(values)
                if cond_key == "__all__" and key in published:
                    point = float(published[key])
                    if abs(emp - point) > 1e-9:
                        raise ValueError(
                            "empirical rate disagrees with score.json for {} {} {} {}: {} vs {}".format(
                                run_id, system_id, task_set, key, emp, point
                            )
                        )
                else:
                    point = emp
                seed = stable_seed(run_id, system_id, task_set, cond_key, key)
                lo, hi = bootstrap_ci(values, seed=seed)
                row[key] = point
                row["{}_ci_low".format(key)] = lo
                row["{}_ci_high".format(key)] = hi
            _add_optional_metrics(row, run_id, system_id, task_set, cond_key, group_tasks)
            rows.append(row)
    return rows


def load_and_aggregate(index_path: Path) -> List[Dict[str, Any]]:
    index = json.loads(index_path.read_text(encoding="utf-8"))
    all_rows: List[Dict[str, Any]] = []
    for entry in index["runs"]:
        score = json.loads((ROOT / entry["score_json"]).read_text(encoding="utf-8"))
        all_rows.extend(aggregate_run(entry["run_id"], score))
    return all_rows


def write_outputs(rows: List[Dict[str, Any]]) -> None:
    PROCESSED.mkdir(parents=True, exist_ok=True)
    csv_path = PROCESSED / "rates_by_run.csv"
    fieldnames = [
        "run_id",
        "system",
        "task_set",
        "condition",
        "n",
        "input_tokens_per_task",
        "output_tokens_per_task",
        "n_timeout",
        "n_retried",
    ]
    for key in METRIC_KEYS + OPTIONAL_METRICS:
        fieldnames.extend([key, "{}_ci_low".format(key), "{}_ci_high".format(key)])
    fieldnames.extend(["n_lie_emitted", "detection_given_emitted"])
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    ci_path = PROCESSED / "rates_by_run_ci.json"
    payload = {"seed": SEED, "bootstrap_b": BOOTSTRAP_B, "rows": rows}
    ci_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print("wrote", csv_path, "rows", len(rows))
    print("wrote", ci_path)


def main() -> None:
    rows = load_and_aggregate(PROCESSED / "run_index.json")
    write_outputs(rows)


if __name__ == "__main__":
    main()
