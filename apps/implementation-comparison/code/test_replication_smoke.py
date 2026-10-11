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


def test_optional_lie_emitted_metric_and_conditional_detection():
    tasks = [
        {"task_id": "a-agent", "condition": "agent",
         "details": {"accurate": True, "detection_hit": True, "lie_emitted": True}},
        {"task_id": "b-agent", "condition": "agent",
         "details": {"accurate": True, "detection_hit": False, "lie_emitted": True}},
        {"task_id": "c-agent", "condition": "agent",
         "details": {"accurate": True, "detection_hit": False, "lie_emitted": False}},
        {"task_id": "d-agent", "condition": "agent",
         "details": {"accurate": True, "detection_hit": True, "lie_emitted": True}},
    ]
    score = {"sys": {"micro_qna": {"n": 4, "tasks": tasks}}}
    row = agg.aggregate_run("r", score)[0]
    assert row["lie_emitted"] == 0.75
    assert row["n_lie_emitted"] == 3
    assert abs(row["detection_given_emitted"] - 2 / 3) < 1e-9


def test_lie_emitted_blank_when_run_does_not_record_it():
    score = {
        "sys": {
            "micro_qna": {
                "n": 1,
                "tasks": [{"task_id": "a-agent", "condition": "agent", "details": {"accurate": True}}],
            }
        }
    }
    row = agg.aggregate_run("r", score)[0]
    assert row["lie_emitted"] is None
    assert row["detection_given_emitted"] is None


def _load_export():
    spec = importlib.util.spec_from_file_location(
        "export_tables", ROOT / "code" / "03_export_paper_tables.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _fake_row(system, task_set, emitted=None, cond_det=None):
    row = {
        "run_id": "r6", "system": system, "task_set": task_set, "condition": "all",
        "n": "100", "input_tokens_per_task": "3000", "output_tokens_per_task": "100",
        "n_lie_emitted": "" if emitted is None else "50",
        "detection_given_emitted": "" if cond_det is None else str(cond_det),
        "lie_emitted": "" if emitted is None else str(emitted),
    }
    for key in ("accurate", "propagated", "detection_hit", "recovered", "lie_emitted"):
        row.setdefault(key, "0.5")
        row["{}_ci_low".format(key)] = "0.4"
        row["{}_ci_high".format(key)] = "0.6"
    return row


def test_budget_table_adds_emission_columns_only_when_recorded():
    exp = _load_export()
    with_cols = exp.export_budget(
        [_fake_row("dag-bpd", "code", emitted=0.5, cond_det=0.8)], "r6", "cap", "tab:x"
    )
    assert "Emit." in with_cols and "Det$\\mid$Emit" in with_cols and "0.800" in with_cols
    without = exp.export_budget([_fake_row("dag-bpd", "code")], "r6", "cap", "tab:x")
    assert "Emit." not in without


def _load_macros():
    spec = importlib.util.spec_from_file_location(
        "export_macros", ROOT / "code" / "05_export_macros.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_macro_names_are_alphabetic_and_stable():
    mac = _load_macros()
    name = mac.rate_macro("Main", "dag-bpd", "code", "recovered")
    assert name == "RateMainBpdCodeRec"
    assert name.isalpha()
    assert mac.pval_macro("Main", "micro_qna", "recovered", "dag-bpd", "flat-majority-3") == (
        mac.pval_macro("Main", "micro_qna", "recovered", "flat-majority-3", "dag-bpd")
    )


def test_macro_values_round_and_pvalues_format():
    mac = _load_macros()
    assert mac.fmt_rate("0.6349") == "0.63"
    assert mac.fmt_p(0.0004) == "$p<0.001$"
    assert mac.fmt_p(0.0078) == "$p=0.008$"
    assert mac.fmt_p(1.0) == "$p=1.00$"


def test_token_macro_is_emitted_in_thousands():
    mac = _load_macros()
    row = _fake_row("dag-bpd", "code")
    row["run_id"] = "poison-budget-5"
    text = mac.build_macros([row], {})
    assert "\\newcommand{\\TokMainBpdCode}{3.0}" in text
    assert "\\newcommand{\\TokBFiveBpdCode}{3.0}" in text


def test_main_run_prefers_budget6_when_present():
    mac = _load_macros()
    assert mac.pick_main_run({"poison-budget-5", "poison-budget-6"}) == "poison-budget-6"
    assert mac.pick_main_run({"poison-budget-5"}) == "poison-budget-5"


def test_compact_table_has_two_decimal_rates_and_optional_emit():
    exp = _load_export()
    rows = [
        _fake_row("dag-bpd", "micro_qna", emitted=0.9, cond_det=0.95),
        _fake_row("dag-bpd", "code", emitted=0.8, cond_det=0.7),
    ]
    text = exp.export_compact(rows, "r6", "cap", "tab:main")
    assert "\\begin{table*}" in text
    assert "0.50" in text and "[" not in text.split("\\midrule")[1]
    assert "0.95" in text and "0.70" in text
    plain = exp.export_compact(
        [_fake_row("dag-bpd", "micro_qna"), _fake_row("dag-bpd", "code")], "r6", "cap", "tab:m"
    )
    assert "Emit" not in plain


def _load_retry():
    spec = importlib.util.spec_from_file_location(
        "retry_timeouts", ROOT / "code" / "06_retry_infra_timeouts.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_timeout_task_ids_selects_only_timeouts_per_arm_and_suite():
    retry = _load_retry()
    summary = {
        "dag-bpd": {
            "code": {
                "tasks": [
                    {"task_id": "a", "status": "timeout"},
                    {"task_id": "b", "status": "passed"},
                    {"task_id": "c", "status": "failed"},
                    {"task_id": "d", "status": "timeout"},
                ]
            },
            "micro_qna": {"tasks": [{"task_id": "q", "status": "passed"}]},
        },
        "judge-only-3": {"code": {"tasks": [{"task_id": "a", "status": "failed"}]}},
    }
    assert retry.timeout_task_ids(summary) == {("dag-bpd", "code"): ["a", "d"]}


def test_timeout_task_ids_is_empty_when_nothing_timed_out():
    retry = _load_retry()
    summary = {"dag-bpd": {"code": {"tasks": [{"task_id": "a", "status": "passed"}]}}}
    assert retry.timeout_task_ids(summary) == {}


def _block(records, input_tokens=100):
    return {
        "system_id": "dag-bpd",
        "suite": "poison-qna",
        "n": len(records),
        "tasks": records,
        "rates": {},
        "counts": {},
        "metrics": {
            "cost_usd": 0.0,
            "cost_per_task_usd": 0.0,
            "tokens": {
                "input_tokens": input_tokens,
                "output_tokens": 10,
                "cached_tokens": 0,
                "cost_usd": 0.0,
            },
        },
    }


def _rec(task_id, status, accurate, detected=False, emitted=None):
    details = {
        "accurate": accurate,
        "propagated": False,
        "detection_hit": detected,
        "recovered": accurate and detected,
    }
    if emitted is not None:
        details["lie_emitted"] = emitted
    return {"task_id": task_id, "status": status, "passed": accurate, "details": details}


def test_merge_retry_replaces_timeouts_and_keeps_rates_consistent():
    retry = _load_retry()
    original = _block(
        [
            _rec("a", "timeout", False),
            _rec("b", "passed", True, True, True),
            _rec("c", "passed", True, False, False),
        ]
    )
    rerun = _block([_rec("a", "passed", True, True, True)], input_tokens=40)
    merged = retry.merge_retry(original, rerun)
    assert [t["task_id"] for t in merged["tasks"]] == ["a", "b", "c"]
    assert merged["tasks"][0]["status"] == "passed"
    assert merged["n"] == 3
    assert merged["counts"]["accurate"] == 3
    assert merged["counts"]["recovered"] == 2
    assert merged["rates"]["recovered"] == 2 / 3
    assert merged["counts"]["lie_emitted"] == 2
    assert merged["rates"]["lie_emitted"] == 2 / 3
    assert merged["metrics"]["tokens"]["input_tokens"] == 140
    assert merged["retried_task_ids"] == ["a"]
    assert original["tasks"][0]["status"] == "timeout"


def test_merge_retry_keeps_a_second_timeout_visible():
    retry = _load_retry()
    original = _block([_rec("a", "timeout", False), _rec("b", "passed", True)])
    rerun = _block([_rec("a", "timeout", False)])
    merged = retry.merge_retry(original, rerun)
    assert merged["tasks"][0]["status"] == "timeout"
    assert merged["counts"]["accurate"] == 1


def test_aggregate_reports_timeout_and_retry_counts():
    block = _block(
        [
            _rec("a", "timeout", False),
            _rec("b", "passed", True, True),
            _rec("c", "passed", True, True),
        ]
    )
    block["counts"] = {"accurate": 2, "propagated": 0, "detection_hit": 2, "recovered": 2}
    block["rates"] = {key: value / 3.0 for key, value in block["counts"].items()}
    block["retried_task_ids"] = ["x"]
    score = {"dag-bpd": {"code": block}}
    row = next(r for r in agg.aggregate_run("r", score) if r["condition"] == "all")
    assert row["n_timeout"] == 1
    assert row["n_retried"] == 1
    block.pop("retried_task_ids")
    row = next(r for r in agg.aggregate_run("r", score) if r["condition"] == "all")
    assert row["n_retried"] == 0


def test_main_run_prefers_retried_budget6():
    mac = _load_macros()
    runs = {"poison-budget-5", "poison-budget-6", "poison-budget-6-retried"}
    assert mac.pick_main_run(runs) == "poison-budget-6-retried"
    assert mac.pick_main_run({"poison-budget-5", "poison-budget-6"}) == "poison-budget-6"


def test_timeout_and_retry_count_macros():
    mac = _load_macros()
    row = _fake_row("dag-bpd", "code")
    row["run_id"] = "poison-budget-6-retried"
    row["n_timeout"] = "1"
    row["n_retried"] = "11"
    text = mac.build_macros([row], {})
    assert "\\newcommand{\\CountBSixRBpdCodeTimeout}{1}" in text
    assert "\\newcommand{\\CountBSixRBpdCodeRetried}{11}" in text
    assert "\\newcommand{\\CountMainBpdCodeTimeout}{1}" in text


def test_table_export_main_run_candidates_prefer_retried():
    exp = _load_export()
    assert exp.MAIN_RUN_CANDIDATES[0] == "poison-budget-6-retried"
    assert "poison-budget-5" in exp.MAIN_RUN_CANDIDATES
