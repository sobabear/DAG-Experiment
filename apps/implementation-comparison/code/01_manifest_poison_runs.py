#!/usr/bin/env python3
"""Index frozen poison run trees into data/processed/run_index.json."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
OUT_DIR = ROOT / "data" / "processed"
MANIFEST = ROOT / "data" / "raw" / "poison_runs" / "manifest.md"

DEFAULT_RUNS = (
    "poison-100",
    "poison-yonsei-improved",
    "poison-20",
    "poison-all",
    "poison",
    "poison-conditions",
)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    runs = []
    lines = [
        "# Poison run manifest",
        "",
        "| run_id | score.json | comparison.md | notes |",
        "|--------|------------|---------------|-------|",
    ]
    for run_id in DEFAULT_RUNS:
        run_dir = RESULTS / run_id
        score = run_dir / "score.json"
        comparison = run_dir / "comparison.md"
        if not score.is_file():
            continue
        entry = {
            "run_id": run_id,
            "path": str(run_dir.relative_to(ROOT)),
            "score_json": str(score.relative_to(ROOT)),
            "comparison_md": str(comparison.relative_to(ROOT))
            if comparison.is_file()
            else None,
        }
        runs.append(entry)
        lines.append(
            "| {} | `{}` | {} | frozen LLM artifacts |".format(
                run_id,
                entry["score_json"],
                "`{}`".format(entry["comparison_md"])
                if entry["comparison_md"]
                else "—",
            )
        )
    if len(runs) < 3:
        raise SystemExit("expected at least 3 runs with score.json, found {}".format(len(runs)))
    index_path = OUT_DIR / "run_index.json"
    index_path.write_text(json.dumps({"runs": runs}, indent=2) + "\n", encoding="utf-8")
    MANIFEST.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("wrote", index_path)
    print("wrote", MANIFEST)
    print("runs", len(runs))


if __name__ == "__main__":
    main()
