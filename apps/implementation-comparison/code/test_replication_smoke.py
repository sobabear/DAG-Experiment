"""Smoke tests for poison rate aggregation (no API calls)."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "code" / "02_aggregate_poison_rates.py"


def _load_agg():
    spec = importlib.util.spec_from_file_location("aggregate_poison_rates", MODULE_PATH)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


agg = _load_agg()


def test_aggregate_run_matches_published_rates():
    score = json.loads(
        (ROOT / "code" / "fixtures" / "mini_poison_score.json").read_text(encoding="utf-8")
    )
    rows = agg.aggregate_run("mini", score)
    qna = next(r for r in rows if r["task_set"] == "micro_qna")
    assert qna["n"] == 2
    assert qna["accurate"] == 1.0
    assert qna["detection_hit"] == 0.5
    assert (
        0.0
        <= qna["detection_hit_ci_low"]
        <= qna["detection_hit"]
        <= qna["detection_hit_ci_high"]
        <= 1.0
    )


def test_bootstrap_ci_bounds():
    lo, hi = agg.bootstrap_ci([1, 0, 1, 1], seed=20260909)
    assert 0.0 <= lo <= hi <= 1.0
