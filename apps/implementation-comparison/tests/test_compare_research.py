import json
import re
from pathlib import Path

import pytest

from impl_comparison.coding_llm import WorkspaceAwareLLM
from impl_comparison.protocol import ModelConfig
from impl_comparison.research_suite import research_tasks
from impl_comparison.scoring import as_points


def test_index_rejects_missing_or_mixed_areas():
    from impl_comparison.scoring import area_score, area_scores_from_records, research_index

    with pytest.raises(ValueError):
        research_index({"se": 0.4, "terminal": 0.5})

    with pytest.raises(ValueError):
        research_index({"se": 0.4, "terminal": 0.5, "qna": 0.6, "other": 0.1})

    with pytest.raises(ValueError):
        research_index({})

    with pytest.raises(ValueError):
        area_score([])

    with pytest.raises(ValueError):
        area_scores_from_records(
            {
                "t-se": {"area": "se", "task_score": 1.0},
                "t-term": {"area": "terminal", "task_score": 1.0},
                "t-qna": {"area": "qna", "task_score": 1.0},
                "t-other": {"area": "other", "task_score": 0.0},
            }
        )

    with pytest.raises(ValueError):
        area_scores_from_records({"t-missing": {"task_score": 1.0}})

    with pytest.raises(ValueError):
        area_scores_from_records({})


def test_cli_accepts_research_suite_and_rejects_unknown():
    from impl_comparison.compare import parse_args

    args = parse_args(["--suite", "research-30", "--attempts", "3", "--system", "dag-bpd"])
    assert args.suite == "research-30"
    assert args.attempts == 3
    assert args.system == "dag-bpd"

    defaults = parse_args([])
    assert defaults.suite == "fallback"
    assert defaults.attempts == 3
    assert defaults.system is None
    assert defaults.allow_fake is False

    fake_ok = parse_args(["--suite", "research-30", "--allow-fake"])
    assert fake_ok.allow_fake is True

    with pytest.raises(SystemExit):
        parse_args(["--suite", "not-a-suite"])

    with pytest.raises(SystemExit):
        parse_args(["--system", "unknown-system"])


def test_render_research_markdown_includes_index_and_disclaimer():
    from impl_comparison.compare import _render_research_markdown

    summary = {
        "dag-bpd": _synthetic_payload("dag-bpd", 0.2, 0.3, 0.4, 1.25, 0.01, 9),
        "dag-yonsei": _synthetic_payload("dag-yonsei", 0.5, 0.6, 0.7, 2.0, 0.02, 12),
        "general-agent-system": _synthetic_payload(
            "general-agent-system", 0.1, 0.2, 0.3, 0.5, 0.0, 6
        ),
    }
    markdown = _render_research_markdown(summary)
    assert "Index" in markdown
    assert "SE" in markdown
    assert "Terminal" in markdown
    assert "QnA" in markdown
    lowered = markdown.lower()
    assert "time" in lowered and "/task" in lowered
    assert "cost" in lowered and "/task" in lowered
    assert "token" in lowered
    assert "turn" in lowered
    assert "custom suite" in lowered
    assert "Artificial Analysis" in markdown
    assert "cannot be compared numerically" in lowered
    assert "leaderboard" in lowered
    assert "0–100" in markdown or "0-100" in markdown
    for system_id in summary:
        assert system_id in markdown
        assert "{:.1f}".format(as_points(summary[system_id]["index"])) in markdown


def test_one_system_one_task_per_area_has_index(tmp_path):
    from impl_comparison.compare import compare

    tasks = _one_task_per_area()
    summary = compare(
        tmp_path,
        attempts=1,
        suite="research-30",
        system="general-agent-system",
        tasks=tasks,
        max_turns=4,
        llm=WorkspaceAwareLLM(),
        model=ModelConfig(provider="injected", model="test-double"),
    )
    assert list(summary) == ["general-agent-system"]
    payload = summary["general-agent-system"]
    areas = payload["areas"]
    assert set(areas) == {"se", "terminal", "qna"}
    assert payload["index"] == pytest.approx(
        (areas["se"] + areas["terminal"] + areas["qna"]) / 3.0
    )

    records = payload["tasks"]
    assert set(records) == {task.task_id for task in tasks}
    for record in records.values():
        assert "attempts" in record
        assert len(record["attempts"]) == 1
        assert "task_score" in record
        assert record["area"] in {"se", "terminal", "qna"}
        assert isinstance(record["reason"], str)

    score_path = tmp_path / "general-agent-system" / "score.json"
    written = json.loads(score_path.read_text(encoding="utf-8"))
    assert written["index"] == pytest.approx(payload["index"])
    assert written["index_100"] == pytest.approx(as_points(payload["index"]))
    assert written["areas"] == areas
    metrics = written["metrics"]
    assert "time_per_task_seconds" in metrics
    assert "cost_per_task_usd" in metrics
    assert "turns_total" in metrics
    assert "tokens" in metrics
    assert "custom suite" in written["disclaimer"].lower()
    assert "Artificial Analysis" in written["disclaimer"]
    assert written["llm"] == "injected/test-double"
    assert "sk-" not in json.dumps(written)
    repo_comparison = (
        Path(__file__).resolve().parents[1] / "results" / "research-30" / "comparison.md"
    )
    assert tmp_path.resolve() != repo_comparison.parent.resolve()


def _one_task_per_area():
    selected = {}
    for task in research_tasks():
        if task.area not in selected:
            selected[task.area] = task
        if len(selected) == 3:
            break
    return [selected["se"], selected["terminal"], selected["qna"]]


def _synthetic_payload(system_id, se, terminal, qna, time_s, cost, turns):
    return {
        "system_id": system_id,
        "index": (se + terminal + qna) / 3.0,
        "areas": {"se": se, "terminal": terminal, "qna": qna},
        "metrics": {
            "time_per_task_seconds": time_s,
            "cost_per_task_usd": cost,
            "turns_total": turns,
            "tokens": {
                "input_tokens": 100,
                "output_tokens": 20,
                "cached_tokens": 0,
            },
        },
    }


def test_research_run_contract_has_verifier_transcript_events_metrics_attempt(
    tmp_path,
):
    from impl_comparison.compare import compare

    tasks = _one_task_per_area()
    summary = compare(
        tmp_path,
        attempts=1,
        suite="research-30",
        system="general-agent-system",
        tasks=tasks,
        max_turns=4,
        llm=WorkspaceAwareLLM(),
        model=ModelConfig(provider="injected", model="test-double"),
    )
    payload = summary["general-agent-system"]
    areas = payload["areas"]
    assert payload["index"] == pytest.approx(
        (areas["se"] + areas["terminal"] + areas["qna"]) / 3.0
    )
    metrics = payload["metrics"]
    for key in ("time_per_task_seconds", "cost_per_task_usd", "tokens", "turns_total"):
        assert key in metrics
        assert key not in areas

    for task in tasks:
        attempt_id = "1"
        run_dir = (
            tmp_path
            / "general-agent-system"
            / "runs"
            / "runs"
            / task.task_id
            / attempt_id
        )
        transcript = run_dir / "transcript.jsonl"
        events = run_dir / "events.jsonl"
        metrics_path = run_dir / "metrics.json"
        result_path = run_dir / "result.json"
        assert transcript.is_file(), task.task_id
        assert events.is_file(), task.task_id
        assert metrics_path.is_file(), task.task_id
        assert result_path.is_file(), task.task_id
        result = json.loads(result_path.read_text(encoding="utf-8"))
        assert "verifier_result" in result
        assert "passed" in result["verifier_result"]
        assert result["transcript_path"]
        assert result["event_path"]
        assert Path(result["transcript_path"]).is_file()
        assert Path(result["event_path"]).is_file()
        assert attempt_id in result["run_id"]
        record = payload["tasks"][task.task_id]
        assert record["attempt_ids"] == [attempt_id]


def test_research_30_without_env_raises_and_does_not_write_repo_scores(
    monkeypatch, tmp_path
):
    monkeypatch.delenv("IMPL_COMPARISON_LLM_PROVIDER", raising=False)
    monkeypatch.delenv("IMPL_COMPARISON_LLM_MODEL", raising=False)
    monkeypatch.delenv("IMPL_COMPARISON_LLM_ENDPOINT", raising=False)
    monkeypatch.delenv("IMPL_COMPARISON_ALLOW_FAKE", raising=False)

    from impl_comparison.compare import compare, main, parse_args

    args = parse_args(["--suite", "research-30"])
    assert args.suite == "research-30"
    assert args.allow_fake is False

    repo_comparison = (
        Path(__file__).resolve().parents[1] / "results" / "research-30" / "comparison.md"
    )
    before = (
        repo_comparison.read_text(encoding="utf-8") if repo_comparison.is_file() else None
    )

    with pytest.raises(ValueError) as excinfo:
        compare(tmp_path, attempts=1, suite="research-30", system="dag-bpd")
    message = str(excinfo.value)
    assert "IMPL_COMPARISON_LLM_PROVIDER" in message
    assert "IMPL_COMPARISON_LLM_MODEL" in message
    assert not (tmp_path / "comparison.md").exists()
    assert not (tmp_path / "dag-bpd" / "score.json").exists()

    with pytest.raises(ValueError) as excinfo:
        main(["--suite", "research-30", "--attempts", "1", "--system", "dag-bpd"])
    main_message = str(excinfo.value)
    assert "IMPL_COMPARISON_LLM_PROVIDER" in main_message
    assert "IMPL_COMPARISON_LLM_MODEL" in main_message

    after = (
        repo_comparison.read_text(encoding="utf-8") if repo_comparison.is_file() else None
    )
    assert after == before
    if after:
        lowered = after.lower()
        assert "workspaceawarellm" not in lowered
        assert "workspace-aware" not in lowered
        assert "fake/workspace-aware" not in lowered


def test_committed_research_30_comparison_file():
    path = (
        Path(__file__).resolve().parents[1] / "results" / "research-30" / "comparison.md"
    )
    assert path.is_file()
    text = path.read_text(encoding="utf-8")
    lowered = text.lower()
    assert "Artificial Analysis" in text
    assert "custom suite" in lowered
    assert "cannot be compared numerically" in lowered
    assert re.search(r"\bAA\b", text) is None
    banned = ("workspaceawarellm", "workspace-aware", "fake/workspace-aware")
    assert not any(token in lowered for token in banned)
    if "not been executed" in lowered:
        for heading in (
            "DAG advantage",
            "DAG overhead",
            "general-system flexibility",
            "task categories with no separation",
        ):
            assert heading.lower() in lowered
        assert "awaiting real-llm pilot" in lowered
        _assert_harness_does_not_autoload_env(text)
        for system_id in ("dag-bpd", "dag-yonsei", "general-agent-system"):
            assert not re.search(
                r"\|\s*" + re.escape(system_id) + r"\s*\|\s*[-+]?\d", text
            )
        return
    for system_id in ("dag-bpd", "dag-yonsei", "general-agent-system"):
        assert re.search(
            r"\|\s*" + re.escape(system_id) + r"\s*\|\s*[-+]?\d", text
        )
    assert "0–100" in text or "0-100" in text or "100 × pass@1" in text


def test_readme_documents_research_30_command_and_env_vars():
    readme = Path(__file__).resolve().parents[1] / "README.md"
    text = readme.read_text(encoding="utf-8")
    assert "--suite research-30" in text
    assert "IMPL_COMPARISON_LLM_PROVIDER" in text
    assert "IMPL_COMPARISON_LLM_MODEL" in text
    assert "IMPL_COMPARISON_LLM_ENDPOINT" in text
    assert "OPENAI_API_KEY" in text
    assert "now executable" in text.lower()
    assert "correctness-only" in text.lower() or "correctness only" in text.lower()
    _assert_harness_does_not_autoload_env(text)
    assert ".[dev,openai]" in text


def test_resolve_llm_uses_env_stub_when_allow_fake_is_false(monkeypatch):
    from impl_comparison.compare import _resolve_llm

    stub = _StubEnvLLM()
    monkeypatch.setenv("IMPL_COMPARISON_LLM_PROVIDER", "openai-compatible")
    monkeypatch.setenv("IMPL_COMPARISON_LLM_MODEL", "stub-model")
    monkeypatch.delenv("IMPL_COMPARISON_ALLOW_FAKE", raising=False)
    monkeypatch.setattr(
        "impl_comparison.compare.llm_from_env",
        lambda: stub,
    )

    llm, model = _resolve_llm(
        "research-30", llm=None, model=None, allow_fake=False
    )
    assert llm is stub
    assert not isinstance(llm, WorkspaceAwareLLM)
    assert model.provider == "openai-compatible"
    assert model.model == "stub-model"


def test_resolve_llm_allow_fake_flag_ignores_provider_env(monkeypatch):
    from impl_comparison.compare import _resolve_llm

    monkeypatch.setenv("IMPL_COMPARISON_LLM_PROVIDER", "openai-compatible")
    monkeypatch.setenv("IMPL_COMPARISON_LLM_MODEL", "stub-model")
    monkeypatch.delenv("IMPL_COMPARISON_ALLOW_FAKE", raising=False)

    def boom():
        raise AssertionError("llm_from_env must not construct a live client")

    monkeypatch.setattr("impl_comparison.compare.llm_from_env", boom)

    llm, model = _resolve_llm(
        "research-30", llm=None, model=None, allow_fake=True
    )
    assert isinstance(llm, WorkspaceAwareLLM)
    assert model.provider == "fake"
    assert model.model == "workspace-aware"


def test_resolve_llm_allow_fake_env_ignores_provider_env(monkeypatch):
    from impl_comparison.compare import _resolve_llm

    monkeypatch.setenv("IMPL_COMPARISON_LLM_PROVIDER", "openai-compatible")
    monkeypatch.setenv("IMPL_COMPARISON_LLM_MODEL", "stub-model")
    monkeypatch.setenv("IMPL_COMPARISON_ALLOW_FAKE", "1")

    def boom():
        raise AssertionError("llm_from_env must not construct a live client")

    monkeypatch.setattr("impl_comparison.compare.llm_from_env", boom)

    llm, model = _resolve_llm(
        "research-30", llm=None, model=None, allow_fake=False
    )
    assert isinstance(llm, WorkspaceAwareLLM)
    assert model.provider == "fake"
    assert model.model == "workspace-aware"


def _assert_harness_does_not_autoload_env(text):
    lowered = text.lower()
    assert "auto-load" in lowered or "autoload" in lowered
    assert ".env" in text
    assert "does not auto-load" in lowered or "does **not** auto-load" in lowered
    assert "source .env" in lowered or "set -a" in lowered


class _StubEnvLLM:
    def __init__(self):
        self.config = ModelConfig(provider="openai-compatible", model="stub-model")
