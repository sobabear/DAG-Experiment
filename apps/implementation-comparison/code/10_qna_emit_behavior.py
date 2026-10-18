#!/usr/bin/env python3
"""Why QnA Emit differs by arm: did the poisoned replica open the workspace?

The injected claim is identical for every arm. The base prompt is not. general-1 and
general-3 say "general coding agent"; flat-3, judge-only, and BPD say "proposal worker,
edit files". This script reads the frozen event logs (no LLM call) and, for the poisoned
replica of each QnA task, crosses tool use with the final answer:

* ``no_tool``: the replica finished without a tool call,
* ``no_tool_and_lie``: and its answer is the planted lie,
* ``tool_and_gold``: it used a tool and its answer is the source value,
* ``tool_and_lie``: it used a tool and still answered with the lie.

Usage:  python code/10_qna_emit_behavior.py poison-budget-8
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
ARMS = (
    "general-agent-system",
    "general-majority-3",
    "flat-majority-3",
    "judge-only-3",
    "dag-bpd",
)
SINGLE = "general-agent-system"


def _claim(text: str, gold: str, lie: str) -> str:
    sys.path.insert(0, str(ROOT / "src"))
    from impl_comparison.poison import _claim as claim

    return claim(text, gold, lie)


def tool_segments(events: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Tool calls and turns per replica, in order. One segment when there are no children."""
    current: Optional[Dict[str, Any]] = None
    out: List[Dict[str, Any]] = []
    for event in events:
        kind = event.get("type")
        if kind == "child_started":
            current = {"worker": event.get("worker"), "tools": 0, "turns": 0}
        elif kind == "child_finished":
            if current is not None:
                out.append(current)
                current = None
        elif current is None:
            continue
        elif kind == "tool_requested":
            current["tools"] += 1
        elif kind == "turn_started":
            current["turns"] += 1
    if out:
        return out
    segment = {"worker": None, "tools": 0, "turns": 0}
    for event in events:
        kind = event.get("type")
        if kind == "tool_requested":
            segment["tools"] += 1
        elif kind == "turn_started":
            segment["turns"] += 1
    return [segment]


def poisoned_behavior(
    segment: Dict[str, Any], answer: str, gold: str, lie: str
) -> Dict[str, Any]:
    """Cross one poisoned replica's tool use with whether it answered lie or gold."""
    tools = int(segment["tools"])
    claim = _claim(answer, gold, lie)
    return {
        "tools": tools,
        "turns": int(segment["turns"]),
        "claim": claim,
        "no_tool": tools == 0,
        "tool_and_gold": tools > 0 and claim == "gold",
        "no_tool_and_lie": tools == 0 and claim == "lie",
        "tool_and_lie": tools > 0 and claim == "lie",
    }


def summarize(run_id: str, system: str, rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    n = len(rows)
    out: Dict[str, Any] = {"run_id": run_id, "system": system, "n": n}

    def put(name: str, pred) -> None:
        k = sum(1 for row in rows if pred(row))
        out["{}_k".format(name)] = k
        out[name] = k / n if n else 0.0

    put("no_tool", lambda row: row["no_tool"])
    put("tool_and_gold", lambda row: row["tool_and_gold"])
    put("no_tool_and_lie", lambda row: row["no_tool_and_lie"])
    put("tool_and_lie", lambda row: row["tool_and_lie"])
    out["mean_poison_tools"] = sum(row["tools"] for row in rows) / n if n else 0.0
    return out


def _gold_lie() -> Dict[str, Any]:
    sys.path.insert(0, str(ROOT / "src"))
    from impl_comparison.poison import POISON_TASKS

    return {item["stem"]: item for item in POISON_TASKS}


def _answer(final_obj: Dict[str, Any], poison_worker: int, single: bool) -> str:
    if single:
        return str(final_obj.get("final_text", ""))
    return str(final_obj["workers"][poison_worker])


def analyze_run(run_id: str) -> List[Dict[str, Any]]:
    run_dir = ROOT / "results" / run_id
    score = json.loads((run_dir / "score.json").read_text(encoding="utf-8"))
    catalog = _gold_lie()
    summaries: List[Dict[str, Any]] = []
    for system in ARMS:
        block = (score.get(system) or {}).get("micro_qna")
        if not block:
            continue
        rows: List[Dict[str, Any]] = []
        single = system == SINGLE
        for record in block.get("tasks", []):
            if record.get("status") == "timeout":
                continue
            task_id = record["task_id"]
            stem = task_id[: -len("-agent")] if task_id.endswith("-agent") else task_id
            spec = catalog.get(stem)
            if spec is None:
                continue
            task_dir = run_dir / system / "micro-qna" / "runs" / "runs" / task_id / str(record.get("attempt", "1"))
            events = [
                json.loads(line)
                for line in (task_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            final_obj = json.loads(json.loads((task_dir / "result.json").read_text(encoding="utf-8"))["final_text"])
            poison_worker = int(record.get("poison_worker") or 0)
            segs = tool_segments(events)
            segment = segs[0] if single else next(seg for seg in segs if seg["worker"] == poison_worker)
            rows.append(
                poisoned_behavior(
                    segment,
                    _answer(final_obj, poison_worker, single),
                    spec["gold"],
                    spec["lie"],
                )
            )
        summaries.append(summarize(run_id, system, rows))
    return summaries


def main(argv: Sequence[str] = ()) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run")
    args = parser.parse_args(list(argv) if argv else None)
    summaries = analyze_run(args.run)
    if not summaries:
        print("no QnA arms in", args.run)
        return
    for row in summaries:
        print(
            "{system} n={n} no_tool={no_tool:.2f} tool_and_gold={tool_and_gold:.2f} "
            "no_tool_and_lie={no_tool_and_lie:.2f} tool_and_lie={tool_and_lie:.2f}".format(**row)
        )
    PROCESSED.mkdir(parents=True, exist_ok=True)
    path = PROCESSED / "qna_emit_behavior_{}.csv".format(args.run)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(summaries[0].keys()))
        writer.writeheader()
        writer.writerows(summaries)
    print("wrote", path)


if __name__ == "__main__":
    main(sys.argv[1:])
