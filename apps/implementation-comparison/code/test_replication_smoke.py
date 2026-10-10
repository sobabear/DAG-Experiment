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


def test_bootstrap_seed_is_stable_across_processes():
    import subprocess

    snippet = (
        "import importlib.util,sys;"
        "spec=importlib.util.spec_from_file_location('a','{}');"
        "m=importlib.util.module_from_spec(spec);sys.modules['a']=m;"
        "spec.loader.exec_module(m);"
        "print(m.stable_seed('r','s','code','agent','recovered'))"
    ).format(MODULE_PATH)
    outs = {
        subprocess.run(
            [sys.executable, "-c", snippet],
            capture_output=True,
            text=True,
            env={"PYTHONHASHSEED": str(seed), "PATH": ""},
            check=True,
        ).stdout.strip()
        for seed in (1, 2, 3)
    }
    assert len(outs) == 1


def test_aggregate_run_reports_tokens_per_task():
    score = {
        "sys": {
            "micro_qna": {
                "n": 2,
                "rates": {"accurate": 1.0, "propagated": 0.0, "detection_hit": 0.0, "recovered": 0.0},
                "metrics": {"tokens": {"input_tokens": 100, "output_tokens": 20}},
                "tasks": [
                    {"task_id": "a-agent", "condition": "agent", "details": {"accurate": True}},
                    {"task_id": "b-agent", "condition": "agent", "details": {"accurate": True}},
                ],
            }
        }
    }
    row = agg.aggregate_run("r", score)[0]
    assert row["input_tokens_per_task"] == 50.0
    assert row["output_tokens_per_task"] == 10.0


def _load_paired():
    spec = importlib.util.spec_from_file_location(
        "paired_tests", ROOT / "code" / "04_paired_tests.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_mcnemar_exact_matches_known_values():
    paired = _load_paired()
    assert paired.mcnemar_exact(0, 0) == 1.0
    assert abs(paired.mcnemar_exact(10, 0) - 2 * 0.5**10) < 1e-12
    assert abs(paired.mcnemar_exact(3, 3) - 1.0) < 1e-12


def test_wilson_interval_contains_rate_and_handles_extremes():
    paired = _load_paired()
    lo, hi = paired.wilson_interval(20, 20)
    assert 0.8 < lo < 1.0 and hi == 1.0
    lo, hi = paired.wilson_interval(0, 20)
    assert lo == 0.0 and 0.0 < hi < 0.2
    assert paired.wilson_interval(0, 0) == (0.0, 0.0)


def test_paired_comparison_counts_discordant_pairs():
    paired = _load_paired()
    a = [{"task_id": str(i), "details": {"recovered": v}} for i, v in enumerate([1, 1, 0, 0, 1])]
    b = [{"task_id": str(i), "details": {"recovered": v}} for i, v in enumerate([1, 0, 0, 1, 1])]
    result = paired.paired_comparison(a, b, "recovered")
    assert result["a_only"] == 1 and result["b_only"] == 1 and result["both"] == 2
    assert result["n"] == 5
