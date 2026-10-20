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


def test_table_export_main_run_candidates_prefer_position_balanced_run():
    exp = _load_export()
    assert exp.MAIN_RUN_CANDIDATES[0] == "poison-budget-7"
    assert exp.MAIN_RUN_CANDIDATES[1] == "poison-budget-6-retried"
    assert "poison-budget-5" in exp.MAIN_RUN_CANDIDATES


def test_main_run_prefers_position_balanced_budget7_over_second_model_run():
    mac = _load_macros()
    runs = {"poison-budget-6-retried", "poison-budget-7", "poison-budget-8"}
    assert mac.pick_main_run(runs) == "poison-budget-7"
    assert mac.pick_main_run({"poison-budget-8"}) is None
    assert mac.RUN_TAGS["poison-budget-8"] == "BEight"


# ---- position breakdown and cross-run replication (07) ---------------------------


def _load_position():
    spec = importlib.util.spec_from_file_location(
        "position_breakdown", ROOT / "code" / "07_position_breakdown.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _pos_task(task_id, position, accurate, detected):
    return {
        "task_id": task_id,
        "status": "passed",
        "poison_worker": position,
        "details": {
            "accurate": accurate,
            "propagated": not accurate,
            "detection_hit": detected,
            "recovered": accurate and detected,
        },
    }


def _pos_score(flags):
    tasks = [
        _pos_task("t{}".format(i), pos, acc, det)
        for i, (pos, acc, det) in enumerate(flags)
    ]
    return {"dag-bpd": {"code": {"tasks": tasks}}}


def test_position_rows_group_by_poisoned_replica():
    pos = _load_position()
    score = _pos_score(
        [(0, True, True), (0, True, True), (1, True, False), (1, True, True), (2, False, False), (2, True, False)]
    )
    rows = pos.position_rows("r", score)
    by_pos = {r["position"]: r for r in rows}
    assert sorted(by_pos) == [0, 1, 2]
    assert by_pos[0]["n"] == 2
    assert by_pos[0]["recovered_k"] == 2
    assert by_pos[0]["recovered"] == 1.0
    assert by_pos[1]["recovered"] == 0.5
    assert by_pos[2]["detection_hit"] == 0.0
    assert by_pos[2]["accurate"] == 0.5
    assert 0.0 <= by_pos[1]["recovered_ci_low"] <= 0.5 <= by_pos[1]["recovered_ci_high"] <= 1.0


def test_position_rows_skip_tasks_without_a_recorded_position():
    pos = _load_position()
    score = _pos_score([(0, True, True), (1, True, True)])
    score["dag-bpd"]["code"]["tasks"].append(
        {"task_id": "legacy", "status": "passed", "details": {"accurate": True}}
    )
    rows = pos.position_rows("r", score)
    assert sum(r["n"] for r in rows) == 2


def test_permutation_pvalue_is_one_without_variation_and_small_when_separated():
    pos = _load_position()
    flat = [(0, 1)] * 5 + [(1, 1)] * 5 + [(2, 1)] * 5
    assert pos.permutation_pvalue(flat, seed=1) == 1.0
    separated = [(0, 1)] * 20 + [(1, 0)] * 20 + [(2, 1)] * 20
    assert pos.permutation_pvalue(separated, seed=1) < 0.01


def test_permutation_pvalue_is_deterministic():
    pos = _load_position()
    data = [(0, 1), (0, 0), (1, 1), (1, 1), (2, 0), (2, 1), (0, 1), (2, 0)]
    assert pos.permutation_pvalue(data, seed=3) == pos.permutation_pvalue(data, seed=3)


def test_position_rows_carry_the_same_test_p_value_for_every_position():
    pos = _load_position()
    score = _pos_score([(0, True, True)] * 12 + [(1, True, False)] * 12 + [(2, True, True)] * 12)
    rows = pos.position_rows("r", score)
    p_values = {r["perm_p_recovered"] for r in rows}
    assert len(p_values) == 1
    assert next(iter(p_values)) < 0.01


def test_cross_run_replication_counts_discordant_tasks():
    pos = _load_position()
    run_a = {"dag-bpd": {"code": {"tasks": [
        _pos_task("a", 0, True, True), _pos_task("b", 0, True, False), _pos_task("c", 0, True, True)
    ]}}}
    run_b = {"dag-bpd": {"code": {"tasks": [
        _pos_task("a", 1, True, True), _pos_task("b", 1, True, True), _pos_task("c", 1, True, False)
    ]}}}
    rows = pos.replication_rows("A", "B", run_a, run_b)
    rec = next(r for r in rows if r["metric"] == "recovered")
    assert rec["system"] == "dag-bpd"
    assert rec["task_set"] == "code"
    assert rec["a_only"] == 1 and rec["b_only"] == 1
    assert rec["rate_a"] == 2 / 3 and rec["rate_b"] == 2 / 3
    assert rec["p_value"] == 1.0


def _pos_csv_row(system="dag-bpd", task_set="code", position="0", recovered="0.80", p="0.250"):
    row = {
        "run_id": "poison-budget-7",
        "system": system,
        "task_set": task_set,
        "position": position,
        "n": "34",
    }
    for metric in ("accurate", "propagated", "detection_hit", "recovered"):
        row[metric] = recovered if metric in ("detection_hit", "recovered") else "1.00"
        row["perm_p_{}".format(metric)] = p
    return row


def test_position_macros_have_alphabetic_names_and_values():
    mac = _load_macros()
    rows = [
        _pos_csv_row(position="0", recovered="0.80"),
        _pos_csv_row(position="1", recovered="0.60"),
        _pos_csv_row(position="2", recovered="0.70"),
    ]
    text = mac.build_macros([], {}, position={"poison-budget-7": rows})
    assert "\\newcommand{\\RatePosBSevenBpdCodeRecZero}{0.80}" in text
    assert "\\newcommand{\\RatePosBSevenBpdCodeRecOne}{0.60}" in text
    assert "\\newcommand{\\RatePosBSevenBpdCodeRecTwo}{0.70}" in text
    assert "\\newcommand{\\PvalPosBSevenBpdCodeRec}{$p=0.250$}" in text
    assert text.count("\\newcommand{\\PvalPosBSevenBpdCodeRec}") == 1


def test_position_table_lists_each_position_and_the_test():
    exp = _load_export()
    rows = [
        _pos_csv_row(position="0", recovered="0.80"),
        _pos_csv_row(position="1", recovered="0.60"),
        _pos_csv_row(position="2", recovered="0.70"),
    ]
    text = exp.export_position(rows, "poison-budget-7", "Cap.", "tab:pos")
    assert "Acc@0" in text and "Rec@2" in text
    assert "Det@0" not in text
    assert "dag-bpd" in text
    assert "0.80" in text and "0.60" in text and "0.70" in text
    assert "0.250" in text
    assert "\\label{tab:pos}" in text
    assert exp.export_position([], "poison-budget-7", "Cap.", "tab:pos") is None


def test_replication_table_shows_rates_discordance_and_p():
    exp = _load_export()
    rows = [
        {
            "run_a": "A", "run_b": "B", "system": "dag-bpd", "task_set": "code",
            "metric": "recovered", "rate_a": "0.63", "rate_b": "0.60",
            "a_only": "8", "b_only": "5", "p_value": "0.58",
        },
        {
            "run_a": "A", "run_b": "B", "system": "dag-bpd", "task_set": "code",
            "metric": "accurate", "rate_a": "0.96", "rate_b": "0.99",
            "a_only": "0", "b_only": "3", "p_value": "0.25",
        },
    ]
    text = exp.export_replication(rows, "A", "B", "Cap.", "tab:rep")
    assert "0.63" in text and "0.60" in text
    assert "8/5" in text
    assert "0.58" in text
    assert exp.export_replication([], "A", "B", "Cap.", "tab:rep") is None


# ---- judge-free semantic baselines (08) -------------------------------------------


def _load_semantic():
    spec = importlib.util.spec_from_file_location(
        "semantic_baselines", ROOT / "code" / "08_semantic_baselines.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _write_worker(root, index, source, passes=True):
    folder = root / "workers" / str(index)
    folder.mkdir(parents=True)
    (folder / "worker.py").write_text(source, encoding="utf-8")
    expected = "2" if passes else "3"
    (folder / "test_worker.py").write_text(
        "from worker import f\n\n\ndef test_f():\n    assert f(1) == {}\n".format(expected),
        encoding="utf-8",
    )
    return folder


def test_source_signature_ignores_comments_whitespace_and_docstrings(tmp_path):
    sem = _load_semantic()
    a = _write_worker(tmp_path / "a", 0, "def f(x):\n    return x + 1\n")
    b = _write_worker(
        tmp_path / "b", 0, "# note\ndef f(x):\n    '''doc'''\n    return   x+1\n"
    )
    c = _write_worker(tmp_path / "c", 0, "def f(x):\n    return x + 2\n")
    assert sem.source_signature(a) == sem.source_signature(b)
    assert sem.source_signature(a) != sem.source_signature(c)


def test_source_signature_excludes_test_files(tmp_path):
    sem = _load_semantic()
    a = _write_worker(tmp_path / "a", 0, "def f(x):\n    return x + 1\n", passes=True)
    b = _write_worker(tmp_path / "b", 0, "def f(x):\n    return x + 1\n", passes=False)
    assert sem.source_signature(a) == sem.source_signature(b)


def test_odd_one_out_needs_exactly_one_dissenter():
    sem = _load_semantic()
    assert sem.odd_one_out(["x", "x", "y"]) == 2
    assert sem.odd_one_out(["y", "x", "x"]) == 0
    assert sem.odd_one_out(["x", "x", "x"]) is None
    assert sem.odd_one_out(["x", "y", "z"]) is None


def test_failing_replica_index_needs_exactly_one_failure():
    sem = _load_semantic()
    assert sem.failing_replica([True, False, True]) == 1
    assert sem.failing_replica([True, True, True]) is None
    assert sem.failing_replica([False, False, True]) is None


def test_replica_passes_runs_tests_on_a_copy(tmp_path):
    sem = _load_semantic()
    good = _write_worker(tmp_path / "g", 0, "def f(x):\n    return x + 1\n", passes=True)
    bad = _write_worker(tmp_path / "b", 0, "def f(x):\n    return x + 1\n", passes=False)
    assert sem.replica_passes(good) is True
    assert sem.replica_passes(bad) is False
    assert not (good / ".pytest_cache").exists()


def test_analyze_block_counts_detections_per_baseline(tmp_path):
    sem = _load_semantic()
    run_dir = tmp_path / "run"
    arm_runs = run_dir / "flat-majority-3" / "code" / "runs" / "runs"
    # task t1: replica 0 poisoned and broken, others fine -> both baselines hit
    t1 = arm_runs / "t1" / "1"
    _write_worker(t1, 0, "def f(x):\n    return x + 5\n", passes=False)
    _write_worker(t1, 1, "def f(x):\n    return x + 1\n", passes=True)
    _write_worker(t1, 2, "def f(x):\n    return x + 1\n", passes=True)
    # task t2: all replicas equal and correct -> nothing to detect
    t2 = arm_runs / "t2" / "1"
    for i in range(3):
        _write_worker(t2, i, "def f(x):\n    return x + 1\n", passes=True)
    block = {
        "tasks": [
            {"task_id": "t1", "attempt": "1", "details": {"detection_hit": True}},
            {"task_id": "t2", "attempt": "1", "details": {"detection_hit": False}},
        ]
    }
    rows = sem.analyze_block(run_dir, "flat-majority-3", block)
    by_id = {r["task_id"]: r for r in rows}
    assert by_id["t1"]["ast_outlier"] == 0 and by_id["t1"]["ast_hit"] is True
    assert by_id["t1"]["oracle_outlier"] == 0 and by_id["t1"]["oracle_hit"] is True
    assert by_id["t1"]["method_hit"] is True
    assert by_id["t2"]["ast_outlier"] is None and by_id["t2"]["ast_hit"] is False
    assert by_id["t2"]["poisoned_replica_fails"] is False
    summary = sem.summarize("r", "flat-majority-3", rows)
    assert summary["n"] == 2
    assert summary["ast_hit_k"] == 1
    assert summary["oracle_hit_k"] == 1
    assert summary["method_hit_k"] == 1
    assert summary["poisoned_fails_k"] == 1


def test_analyze_block_uses_recorded_poison_position(tmp_path):
    sem = _load_semantic()
    run_dir = tmp_path / "run"
    t1 = run_dir / "judge-only-3" / "code" / "runs" / "runs" / "t1" / "1"
    _write_worker(t1, 0, "def f(x):\n    return x + 1\n", passes=True)
    _write_worker(t1, 1, "def f(x):\n    return x + 1\n", passes=True)
    _write_worker(t1, 2, "def f(x):\n    return x + 9\n", passes=False)
    block = {
        "tasks": [
            {"task_id": "t1", "attempt": "1", "poison_worker": 2, "details": {"detection_hit": True}}
        ]
    }
    row = sem.analyze_block(run_dir, "judge-only-3", block)[0]
    assert row["ast_outlier"] == 2 and row["ast_hit"] is True
    assert row["poison_worker"] == 2


def test_analyze_block_reports_wrong_ast_flags(tmp_path):
    sem = _load_semantic()
    run_dir = tmp_path / "run"
    arm_runs = run_dir / "flat-majority-3" / "code" / "runs" / "runs"
    # replica 2 is the structural odd one out, but the poisoned replica is 0
    t1 = arm_runs / "t1" / "1"
    _write_worker(t1, 0, "def f(x):\n    return x + 1\n", passes=True)
    _write_worker(t1, 1, "def f(x):\n    return x + 1\n", passes=True)
    _write_worker(t1, 2, "def f(x):\n    return x + 7\n", passes=False)
    block = {"tasks": [{"task_id": "t1", "attempt": "1", "details": {"detection_hit": False}}]}
    rows = sem.analyze_block(run_dir, "flat-majority-3", block)
    assert rows[0]["ast_outlier"] == 2
    assert rows[0]["ast_hit"] is False and rows[0]["ast_wrong"] is True
    summary = sem.summarize("r", "flat-majority-3", rows)
    assert summary["ast_flag_k"] == 1
    assert summary["ast_wrong_k"] == 1
    assert summary["ast_hit_k"] == 0


def test_analyze_block_falls_back_to_retry_directory(tmp_path):
    sem = _load_semantic()
    run_dir = tmp_path / "run"
    retry_dir = tmp_path / "run-retry"
    t1 = retry_dir / "dag-bpd" / "code" / "runs" / "runs" / "t1" / "1"
    _write_worker(t1, 0, "def f(x):\n    return x + 9\n", passes=False)
    _write_worker(t1, 1, "def f(x):\n    return x + 1\n", passes=True)
    _write_worker(t1, 2, "def f(x):\n    return x + 1\n", passes=True)
    block = {"tasks": [{"task_id": "t1", "attempt": "1", "details": {"detection_hit": True}}]}
    assert sem.analyze_block(run_dir, "dag-bpd", block) == []
    rows = sem.analyze_block(run_dir, "dag-bpd", block, fallback_dirs=[retry_dir])
    assert len(rows) == 1 and rows[0]["ast_hit"] is True


def test_source_run_dirs_for_retried_run_include_retry_directory():
    sem = _load_semantic()
    dirs = sem.source_run_dirs("poison-budget-6-retried")
    names = [d.name for d in dirs]
    assert names == ["poison-budget-6-retry", "poison-budget-6"]
    assert [d.name for d in sem.source_run_dirs("poison-budget-7")] == ["poison-budget-7"]


def _semantic_csv_row(system="flat-majority-3", **overrides):
    row = {
        "run_id": "poison-budget-6-retried",
        "system": system,
        "n": "100",
        "n_skipped": "3",
        "ast_hit": "0.67", "ast_hit_k": "67", "ast_hit_ci_low": "0.57", "ast_hit_ci_high": "0.75",
        "ast_wrong": "0.05", "ast_wrong_k": "5", "ast_wrong_ci_low": "0.02", "ast_wrong_ci_high": "0.11",
        "oracle_hit": "0.64", "oracle_hit_k": "64", "oracle_hit_ci_low": "0.54", "oracle_hit_ci_high": "0.73",
        "method_hit": "0.01", "method_hit_k": "1", "method_hit_ci_low": "0.00", "method_hit_ci_high": "0.05",
        "poisoned_fails": "0.64", "poisoned_fails_k": "64",
        "poisoned_fails_ci_low": "0.54", "poisoned_fails_ci_high": "0.73",
        "ast_flag_k": "72",
    }
    row.update(overrides)
    return row


def test_semantic_macros_are_alphabetic_and_carry_both_run_and_main_tags():
    mac = _load_macros()
    row = {"run_id": "poison-budget-6-retried", "system": "flat-majority-3", "task_set": "code",
           "condition": "all"}
    text = mac.build_macros([row], {}, semantic={"poison-budget-6-retried": [_semantic_csv_row()]})
    assert "\\newcommand{\\RateSemBSixRFlatThreeCodeAst}{0.67}" in text
    assert "\\newcommand{\\RateSemMainFlatThreeCodeAst}{0.67}" in text
    assert "\\newcommand{\\RateSemBSixRFlatThreeCodeAstWrong}{0.05}" in text
    assert "\\newcommand{\\RateSemBSixRFlatThreeCodeOracle}{0.64}" in text
    assert "\\newcommand{\\RateSemBSixRFlatThreeCodeMethod}{0.01}" in text
    assert "\\newcommand{\\CountSemBSixRFlatThreeCodeN}{100}" in text


def test_semantic_table_lists_arms_with_ast_oracle_and_method_rates():
    exp = _load_export()
    rows = [
        _semantic_csv_row("flat-majority-3"),
        _semantic_csv_row("dag-bpd", ast_hit="0.69", method_hit="0.63"),
    ]
    text = exp.export_semantic(rows, "poison-budget-6-retried", "Cap.", "tab:sem")
    assert "0.67" in text and "0.69" in text and "0.64" in text and "0.63" in text
    assert "\\label{tab:sem}" in text
    assert exp.export_semantic([], "poison-budget-6-retried", "Cap.", "tab:sem") is None
    assert exp.export_semantic(rows, "other-run", "Cap.", "tab:sem") is None


def test_semantic_summary_reports_mcnemar_of_arm_detection_vs_ast():
    sem = _load_semantic()
    rows = []
    for i in range(10):
        rows.append({
            "task_id": "t{}".format(i), "poison_worker": 0,
            "ast_outlier": 0 if i < 8 else None, "ast_hit": i < 8, "ast_wrong": False,
            "oracle_outlier": None, "oracle_hit": False,
            "method_hit": i < 2 or i >= 8, "poisoned_replica_fails": False,
        })
    summary = sem.summarize("r", "judge-only-3", rows)
    # method hits: i in {0,1,8,9}; ast hits: i in 0..7 -> both {0,1}; ast-only 6; method-only 2
    assert summary["method_and_ast_k"] == 2
    assert summary["ast_only_k"] == 6 and summary["method_only_k"] == 2
    assert abs(summary["p_method_vs_ast"] - 0.2890625) < 1e-9


def test_semantic_macros_include_mcnemar_p():
    mac = _load_macros()
    row = {"run_id": "poison-budget-6-retried", "system": "judge-only-3", "task_set": "code",
           "condition": "all"}
    sem_row = _semantic_csv_row("judge-only-3", p_method_vs_ast="0.7266")
    text = mac.build_macros([row], {}, semantic={"poison-budget-6-retried": [sem_row]})
    assert "\\newcommand{\\PvalSemBSixRJudgeOnlyCodeMethodVsAst}{$p=0.727$}" in text


# ---- majority fallback mechanism (09) ---------------------------------------------


def _load_fallback():
    spec = importlib.util.spec_from_file_location(
        "majority_fallback", ROOT / "code" / "09_majority_fallback.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _fallback_task(root, final_source, sources):
    task = root / "t1" / "1"
    (task / "workspace").mkdir(parents=True)
    (task / "workspace" / "worker.py").write_text(final_source, encoding="utf-8")
    (task / "workspace" / "test_worker.py").write_text("# tests differ\n", encoding="utf-8")
    for index, source in enumerate(sources):
        folder = task / "workers" / str(index)
        folder.mkdir(parents=True)
        (folder / "worker.py").write_text(source, encoding="utf-8")
    return task


def test_matching_replicas_compares_exact_non_test_source(tmp_path):
    fb = _load_fallback()
    task = _fallback_task(tmp_path, "x = 1\n", ["x = 0\n", "x = 1\n", "x = 1\n"])
    assert fb.matching_replicas(task) == (1, 2)
    task2 = _fallback_task(tmp_path / "b", "x = 2\n", ["x = 0\n", "x = 1\n", "x = 3\n"])
    assert fb.matching_replicas(task2) == ()
    assert fb.matching_replicas(tmp_path / "missing") is None


def test_fallback_rows_and_summary_split_accuracy_by_final_replica(tmp_path):
    fb = _load_fallback()
    run = tmp_path / "run"
    arm_root = run / "flat-majority-3" / "code" / "runs" / "runs"
    # poisoned replica 2 is promoted and wrong
    t1 = arm_root / "t1" / "1"
    (t1 / "workspace").mkdir(parents=True)
    (t1 / "workspace" / "worker.py").write_text("bad\n", encoding="utf-8")
    for i, src in enumerate(["good\n", "good\n", "bad\n"]):
        (t1 / "workers" / str(i)).mkdir(parents=True)
        (t1 / "workers" / str(i) / "worker.py").write_text(src, encoding="utf-8")
    # poisoned replica 0, last replica promoted and right
    t2 = arm_root / "t2" / "1"
    (t2 / "workspace").mkdir(parents=True)
    (t2 / "workspace" / "worker.py").write_text("good\n", encoding="utf-8")
    for i, src in enumerate(["bad\n", "good\n", "good\n"]):
        (t2 / "workers" / str(i)).mkdir(parents=True)
        (t2 / "workers" / str(i) / "worker.py").write_text(src, encoding="utf-8")
    block = {
        "tasks": [
            {"task_id": "t1", "attempt": "1", "poison_worker": 2, "details": {"accurate": False}},
            {"task_id": "t2", "attempt": "1", "poison_worker": 0, "details": {"accurate": True}},
            {"task_id": "t3", "attempt": "1", "status": "timeout", "details": {}},
        ]
    }
    rows = fb.analyze_block(run, "flat-majority-3", block)
    assert [r["task_id"] for r in rows] == ["t1", "t2"]
    summary = fb.summarize("r", "flat-majority-3", rows)
    assert summary["n"] == 2
    assert summary["final_last_k"] == 2
    assert summary["final_poisoned_only_k"] == 1
    assert summary["acc_poisoned_only"] == 0.0
    assert summary["acc_other"] == 1.0
    assert summary["n_other"] == 1


def test_fallback_macros_have_alphabetic_names():
    mac = _load_macros()
    row = {
        "run_id": "poison-budget-7", "system": "flat-majority-3", "n": "100",
        "final_last_k": "90", "final_last": "0.90",
        "final_poisoned_only_k": "40", "final_poisoned_only": "0.40",
        "acc_poisoned_only_k": "12", "acc_poisoned_only": "0.30",
        "acc_other_k": "60", "n_other": "60", "acc_other": "1.00",
    }
    text = mac.build_macros([], {}, fallback={"poison-budget-7": [row]})
    assert "\\newcommand{\\RateFbBSevenFlatThreeCodeLast}{0.90}" in text
    assert "\\newcommand{\\RateFbBSevenFlatThreeCodePoisonedOnly}{0.40}" in text
    assert "\\newcommand{\\RateFbBSevenFlatThreeCodeAccPoisonedOnly}{0.30}" in text
    assert "\\newcommand{\\RateFbBSevenFlatThreeCodeAccOther}{1.00}" in text
    assert "\\newcommand{\\CountFbBSevenFlatThreeCodePoisonedOnly}{40}" in text


def test_fallback_table_has_two_model_blocks():
    exp = _load_export()
    row_a = {"system": "flat-majority-3", "final_last": "0.90", "final_poisoned_only": "0.40",
             "acc_poisoned_only": "0.30", "acc_other": "1.00"}
    row_b = dict(row_a, final_last="0.92", acc_poisoned_only="0.19")
    text = exp.export_fallback([row_a], [row_b], "Cap.", "tab:fb")
    assert "0.90" in text and "0.92" in text and "0.19" in text
    assert "\\label{tab:fb}" in text
    assert exp.export_fallback([], [], "Cap.", "tab:fb") is None


def test_position_table_prints_tiny_p_values_as_a_bound():
    exp = _load_export()
    rows = [_pos_csv_row(position=str(k), p="0.0001") for k in (0, 1, 2)]
    text = exp.export_position(rows, "poison-budget-7", "Cap.", "tab:pos")
    assert "$<$0.001" in text
    assert "0.000" not in text


# ---- QnA emit behavior (10) ---------------------------------------------------


def _load_emit_behavior():
    spec = importlib.util.spec_from_file_location(
        "qna_emit_behavior", ROOT / "code" / "10_qna_emit_behavior.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_tool_segments_split_children_and_fall_back_to_one_stream():
    beh = _load_emit_behavior()
    events = [
        {"type": "child_started", "worker": 0},
        {"type": "turn_started"},
        {"type": "tool_requested", "name": "search"},
        {"type": "child_finished", "worker": 0},
        {"type": "child_started", "worker": 1},
        {"type": "turn_started"},
        {"type": "child_finished", "worker": 1},
    ]
    segs = beh.tool_segments(events)
    assert [(s["worker"], s["tools"], s["turns"]) for s in segs] == [(0, 1, 1), (1, 0, 1)]
    single = beh.tool_segments(
        [{"type": "turn_started"}, {"type": "tool_requested", "name": "read"}]
    )
    assert single == [{"worker": None, "tools": 1, "turns": 1}]


def test_poisoned_behavior_crosses_tool_use_with_the_answer():
    beh = _load_emit_behavior()
    opened = beh.poisoned_behavior({"tools": 2, "turns": 3}, "30", "30", "300")
    assert opened["tool_and_gold"] is True and opened["no_tool_and_lie"] is False
    obeyed = beh.poisoned_behavior({"tools": 0, "turns": 1}, "300", "30", "300")
    assert obeyed["no_tool"] is True and obeyed["no_tool_and_lie"] is True
    assert obeyed["claim"] == "lie"


def test_emit_behavior_summary_counts_the_cross_cells():
    beh = _load_emit_behavior()
    rows = [
        {"no_tool": False, "tool_and_gold": True, "no_tool_and_lie": False, "tool_and_lie": False, "tools": 2},
        {"no_tool": True, "tool_and_gold": False, "no_tool_and_lie": True, "tool_and_lie": False, "tools": 0},
    ]
    summary = beh.summarize("poison-budget-8", "flat-majority-3", rows)
    assert summary["n"] == 2
    assert summary["no_tool"] == 0.5
    assert summary["tool_and_gold"] == 0.5
    assert summary["no_tool_and_lie_k"] == 1


def test_emit_behavior_macros_have_alphabetic_names():
    mac = _load_macros()
    row = {
        "run_id": "poison-budget-8", "system": "flat-majority-3", "n": "100",
        "no_tool": "0.11", "tool_and_gold": "0.88", "no_tool_and_lie": "0.11",
        "tool_and_lie": "0.01",
    }
    text = mac.build_macros([], {}, emit={"poison-budget-8": [row]})
    assert "\\newcommand{\\RateBehBEightFlatThreeQnaNoTool}{0.11}" in text
    assert "\\newcommand{\\RateBehBEightFlatThreeQnaToolGold}{0.88}" in text
    assert "\\newcommand{\\RateBehBEightFlatThreeQnaNoToolLie}{0.11}" in text


# ---- counterfactual workspace selection (11) ----------------------------------


def _load_selection():
    spec = importlib.util.spec_from_file_location(
        "selection_counterfactual", ROOT / "code" / "11_selection_counterfactual.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_ast_majority_picks_a_matching_replica_and_skips_the_dissenter():
    sel = _load_selection()
    assert sel.ast_majority_index(["a", "a", "b"]) == 0
    assert sel.ast_majority_index(["b", "a", "a"]) == 1
    assert sel.ast_majority_index(["a", "a", "a"]) is None
    assert sel.ast_majority_index(["a", "b", "c"]) is None


def test_choose_index_falls_back_to_last_replica_without_an_outlier():
    sel = _load_selection()
    assert sel.choose_index("last", ["a", "b", "a"], "t") == 2
    assert sel.choose_index("ast", ["a", "a", "b"], "t") == 0
    assert sel.choose_index("ast", ["a", "b", "c"], "t") == 2
    first = sel.choose_index("random", ["a", "a", "a"], "task-1")
    again = sel.choose_index("random", ["a", "a", "a"], "task-1")
    other = sel.choose_index("random", ["a", "a", "a"], "task-2")
    assert first == again and first in (0, 1, 2)
    assert other in (0, 1, 2)


def test_selection_summary_scores_the_promoted_replica():
    sel = _load_selection()
    rows = [
        {"passes": [True, True, False], "signatures": ["a", "a", "b"], "actual": False, "poison_worker": 2, "task_id": "t1"},
        {"passes": [False, True, True], "signatures": ["a", "a", "a"], "actual": True, "poison_worker": 0, "task_id": "t2"},
    ]
    summary = sel.summarize("poison-budget-7", "flat-majority-3", rows, seed=1)
    assert summary["n"] == 2
    assert summary["n_outlier"] == 1
    assert summary["acc_last"] == 0.5
    assert summary["acc_ast"] == 1.0
    assert summary["acc_uniform"] == (2 / 3 + 2 / 3) / 2
    assert summary["acc_actual"] == 0.5


def test_selection_macros_have_alphabetic_names():
    mac = _load_macros()
    row = {
        "run_id": "poison-budget-7", "system": "flat-majority-3",
        "acc_actual": "0.72", "acc_last": "0.70", "acc_uniform": "0.80",
        "acc_ast": "0.97", "acc_random": "0.81",
    }
    rate_row = {"run_id": "poison-budget-7", "system": "flat-majority-3", "task_set": "code", "condition": "all"}
    text = mac.build_macros([rate_row], {}, selection={"poison-budget-7": [row]})
    assert "\\newcommand{\\RateSelMainFlatThreeCodeAst}{0.97}" in text
    assert "\\newcommand{\\RateSelBSevenFlatThreeCodeLast}{0.70}" in text
    assert "\\newcommand{\\RateSelBSevenFlatThreeCodeUniform}{0.80}" in text


def test_selection_table_lists_actual_last_uniform_and_ast():
    exp = _load_export()
    row = {
        "system": "flat-majority-3", "acc_actual": "0.72", "acc_last": "0.70",
        "acc_uniform": "0.80", "acc_ast": "0.97",
    }
    text = exp.export_selection([row], [dict(row, acc_ast="0.95")], "Cap.", "tab:sel")
    assert "0.97" in text and "0.95" in text and "0.80" in text
    assert "general-1" not in text
    assert exp.export_selection([], [], "Cap.", "tab:sel") is None
