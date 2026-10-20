#!/usr/bin/env python3
"""What code accuracy would each arm have under another promotion rule?

The string-majority arms promote the last replica when no proposal matches the gold
or lie string. This script keeps the three replicas' workspaces and rescores them,
with no LLM call, under four promotions:

* ``last``: always replica 2 (the fallback),
* ``random``: one replica, deterministic in the task id,
* ``uniform``: the mean of the three replicas (the expected accuracy of a uniform draw),
* ``ast``: a replica whose normalized source matches another replica, when exactly one
  replica differs; otherwise the last replica.

``actual`` is the accuracy the arm recorded. Usage:

    python code/11_selection_counterfactual.py poison-budget-7
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import sys
import zlib
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
SELECTION_SEED = 20261020
LAST = 2


def _load_semantic():
    spec = importlib.util.spec_from_file_location(
        "semantic_baselines_for_selection", ROOT / "code" / "08_semantic_baselines.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


_semantic = _load_semantic()


def ast_majority_index(signatures: Sequence[str]) -> Optional[int]:
    """Lowest index among the replicas that match, when exactly one differs."""
    dissenter = _semantic.odd_one_out(signatures)
    if dissenter is None:
        return None
    return min(index for index in range(len(signatures)) if index != dissenter)


def choose_index(rule: str, signatures: Sequence[str], task_id: str, seed: int = SELECTION_SEED) -> int:
    """Replica index promoted by ``rule``. ``ast`` falls back to the last replica."""
    if rule == "last":
        return LAST
    if rule == "ast":
        chosen = ast_majority_index(signatures)
        return LAST if chosen is None else chosen
    if rule == "random":
        digest = zlib.crc32("{}:{}".format(seed, task_id).encode("utf-8"))
        return digest % len(signatures)
    raise ValueError("unknown selection rule: {}".format(rule))


def summarize(
    run_id: str, system: str, rows: Sequence[Dict[str, Any]], seed: int = SELECTION_SEED
) -> Dict[str, Any]:
    n = len(rows)

    def rate(flags: Sequence[bool]) -> float:
        return sum(1 for flag in flags if flag) / n if n else 0.0

    last_hits = [bool(row["passes"][choose_index("last", row["signatures"], row["task_id"], seed)]) for row in rows]
    ast_hits = [bool(row["passes"][choose_index("ast", row["signatures"], row["task_id"], seed)]) for row in rows]
    random_hits = [bool(row["passes"][choose_index("random", row["signatures"], row["task_id"], seed)]) for row in rows]
    uniform = [sum(1 for ok in row["passes"] if ok) / len(row["passes"]) for row in rows]
    outliers = [row for row in rows if ast_majority_index(row["signatures"]) is not None]
    return {
        "run_id": run_id,
        "system": system,
        "n": n,
        "n_outlier": len(outliers),
        "acc_actual": rate([bool(row["actual"]) for row in rows]),
        "acc_last": rate(last_hits),
        "acc_ast": rate(ast_hits),
        "acc_random": rate(random_hits),
        "acc_uniform": sum(uniform) / n if n else 0.0,
    }


def _analyze_task(system: str, record: Dict[str, Any], run_dirs: Sequence[Path]) -> Optional[Dict[str, Any]]:
    dirs = _semantic._worker_dirs(run_dirs, system, record)
    if dirs is None:
        return None
    passes = [_semantic.replica_passes(folder) for folder in dirs]
    return {
        "task_id": record["task_id"],
        "poison_worker": int(record.get("poison_worker") or 0),
        "passes": passes,
        "signatures": [_semantic.source_signature(folder) for folder in dirs],
        "actual": bool((record.get("details") or {}).get("accurate")),
    }


def analyze_run(run_id: str) -> List[Dict[str, Any]]:
    score = json.loads((ROOT / "results" / run_id / "score.json").read_text(encoding="utf-8"))
    run_dirs = _semantic.source_run_dirs(run_id)
    summaries: List[Dict[str, Any]] = []
    for system in _semantic.ARMS:
        block = (score.get(system) or {}).get("code")
        if not block:
            continue
        records = [record for record in block.get("tasks", []) if record.get("status") != "timeout"]
        from concurrent.futures import ThreadPoolExecutor

        with ThreadPoolExecutor(max_workers=4) as pool:
            analyzed = list(pool.map(lambda record: _analyze_task(system, record, run_dirs), records))
        rows = [row for row in analyzed if row is not None]
        summaries.append(summarize(run_id, system, rows))
    return summaries


def main(argv: Sequence[str] = ()) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run")
    args = parser.parse_args(list(argv) if argv else None)
    summaries = analyze_run(args.run)
    if not summaries:
        print("no code arms in", args.run)
        return
    for row in summaries:
        print(
            "{system} n={n} outlier={n_outlier} actual={acc_actual:.2f} last={acc_last:.2f} "
            "uniform={acc_uniform:.2f} random={acc_random:.2f} ast={acc_ast:.2f}".format(**row)
        )
    PROCESSED.mkdir(parents=True, exist_ok=True)
    path = PROCESSED / "selection_{}.csv".format(args.run)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(summaries[0].keys()))
        writer.writeheader()
        writer.writerows(summaries)
    print("wrote", path)


if __name__ == "__main__":
    main(sys.argv[1:])
