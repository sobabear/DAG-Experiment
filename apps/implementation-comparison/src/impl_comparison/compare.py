"""Run the three systems on fallback or research-30 and write Index-style scores."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Type

from . import research_suite
from .coding_llm import WorkspaceAwareLLM
from .llm_config import allow_fake_from_env, llm_from_env
from .protocol import ExecutionPolicy, ModelConfig, RunLimits, RunRequest, TaskSpec
from .runner import run_agent
from .scoring import area_scores_from_records, bench_score, index_score, research_index, task_score
from .suite import FALLBACK_TASKS
from .suite import SUITE_DISCLAIMER as FALLBACK_DISCLAIMER
from .suite import SUITE_ID as FALLBACK_SUITE_ID
from .suite import materialize_task as materialize_fallback
from .suite import verify_run as verify_fallback
from .systems.bpd import BpdDagSystem
from .systems.general import GeneralAgentSystem
from .systems.yonsei import YonseiDagSystem

SYSTEMS = {
    "dag-bpd": BpdDagSystem,
    "dag-yonsei": YonseiDagSystem,
    "general-agent-system": GeneralAgentSystem,
}

ATTEMPTS = 3
SUITES = ("fallback", "research-30")
DEFAULT_MAX_TURNS = 24
DEFAULT_MAX_TOOL_CALLS = 80


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="impl_comparison.compare")
    parser.add_argument("--suite", default="fallback", choices=SUITES)
    parser.add_argument("--attempts", type=int, default=ATTEMPTS)
    parser.add_argument("--system", default=None, choices=tuple(SYSTEMS))
    parser.add_argument(
        "--allow-fake",
        action="store_true",
        help="Permit the harness Fake LLM for research-30 (tests only)",
    )
    return parser.parse_args(argv)


def compare(
    results_dir: Path,
    attempts: int = ATTEMPTS,
    suite: str = "fallback",
    system: Optional[str] = None,
    tasks: Optional[Sequence[TaskSpec]] = None,
    max_turns: int = DEFAULT_MAX_TURNS,
    llm: Any = None,
    model: Optional[ModelConfig] = None,
    allow_fake: bool = False,
) -> Dict[str, Dict[str, object]]:
    if suite not in SUITES:
        raise ValueError("unknown suite: {}".format(suite))
    resolved_llm, resolved_model = _resolve_llm(suite, llm, model, allow_fake)
    results_dir = Path(results_dir)
    results_dir.mkdir(parents=True, exist_ok=True)
    selected = _selected_systems(system)
    task_list = list(tasks) if tasks is not None else _default_tasks(suite)
    summary: Dict[str, Dict[str, object]] = {}
    for system_id, cls in selected.items():
        summary[system_id] = evaluate_system(
            system_id,
            cls,
            results_dir / system_id,
            attempts,
            tasks=task_list,
            suite=suite,
            max_turns=max_turns,
            llm=resolved_llm,
            model=resolved_model,
            allow_fake=allow_fake,
        )
    renderer = _render_research_markdown if suite == "research-30" else _render_markdown
    (results_dir / "comparison.md").write_text(
        renderer(summary), encoding="utf-8"
    )
    return summary


def evaluate_system(
    system_id: str,
    cls: Type,
    out_dir: Path,
    attempts: int,
    tasks: Sequence[TaskSpec],
    suite: str = "fallback",
    max_turns: int = DEFAULT_MAX_TURNS,
    llm: Any = None,
    model: Optional[ModelConfig] = None,
    allow_fake: bool = False,
) -> Dict[str, object]:
    resolved_llm, resolved_model = _resolve_llm(suite, llm, model, allow_fake)
    out_dir.mkdir(parents=True, exist_ok=True)
    is_research = suite == "research-30"
    materialize = research_suite.materialize_task if is_research else materialize_fallback
    verifier = research_suite.verify_run if is_research else verify_fallback
    by_bench: Dict[str, List[float]] = defaultdict(list)
    task_records: Dict[str, Dict[str, object]] = {}
    total_time = 0.0
    total_turns = 0
    usage = {"input_tokens": 0, "output_tokens": 0, "cached_tokens": 0, "cost_usd": 0.0}
    for task in tasks:
        attempt_bits = []
        reasons: List[str] = []
        attempt_ids: List[str] = []
        for attempt in range(1, attempts + 1):
            attempt_id = str(attempt)
            source = out_dir / "workspace" / task.task_id / attempt_id
            if source.exists():
                raise FileExistsError(str(source))
            materialize(task, source)
            request = RunRequest(
                task=task,
                model=resolved_model,
                policy=ExecutionPolicy(
                    headless=True,
                    allow_writes=True,
                    allow_shell=True,
                    allow_destructive=True,
                    require_confirmation_for_writes=False,
                    workspace_root=str(source),
                ),
                limits=RunLimits(
                    max_turns=max_turns,
                    max_tool_calls=DEFAULT_MAX_TOOL_CALLS,
                    timeout_seconds=float(task.timeout),
                ),
                workspace=source,
                system_name=system_id,
                attempt=attempt_id,
            )
            result = run_agent(
                request,
                cls(resolved_llm),
                verifier,
                workspace_root=out_dir / "runs",
                run_id="{}-{}-{}".format(system_id, task.task_id, attempt_id),
            )
            bit = 1 if result.passed else 0
            attempt_bits.append(bit)
            attempt_ids.append(attempt_id)
            reasons.append(result.verifier_result.reason)
            total_time += result.wall_time
            total_turns += result.turns
            usage["input_tokens"] += result.usage.input_tokens
            usage["output_tokens"] += result.usage.output_tokens
            usage["cached_tokens"] += result.usage.cached_tokens
            usage["cost_usd"] += result.usage.cost_usd
        score = task_score(attempt_bits)
        record: Dict[str, object] = {
            "attempts": attempt_bits,
            "attempt_ids": attempt_ids,
            "task_score": score,
        }
        if is_research:
            record["area"] = task.area
            record["reason"] = _join_reasons(reasons)
        else:
            record["benchmark"] = task.benchmark
            by_bench[task.benchmark].append(score)
        task_records[task.task_id] = record
    llm_label = _llm_label(resolved_model)
    n_slots = max(1, len(list(tasks)) * attempts)
    if is_research:
        areas = area_scores_from_records(task_records)
        payload: Dict[str, object] = {
            "system_id": system_id,
            "llm": llm_label,
            "settings": (
                "identical ModelConfig across systems; research-30 suite; "
                "Index is correctness-only (time/cost/tokens/turns excluded)"
            ),
            "index": research_index(areas),
            "areas": areas,
            "tasks": task_records,
            "suite": research_suite.SUITE_ID,
            "disclaimer": research_suite.SUITE_DISCLAIMER,
            "methodology": (
                "Custom suite using the Coding Agent Index protocol: "
                "pass@1 mean of attempts; equal-weight se, terminal, and qna. "
                "This is a custom suite and cannot be compared numerically with the "
                "public Artificial Analysis leaderboard."
            ),
            "metrics": {
                "time_per_task_seconds": total_time / n_slots,
                "cost_per_task_usd": usage["cost_usd"] / n_slots,
                "turns_total": total_turns,
                "tokens": usage,
            },
        }
    else:
        benches = {
            name: bench_score(by_bench[name])
            for name in ("deepswe", "terminal_bench_v2", "swe_atlas_qna")
        }
        payload = {
            "system_id": system_id,
            "llm": llm_label,
            "settings": "deterministic WorkspaceAwareLLM; fallback suite",
            "index": index_score(benches),
            "benchmarks": benches,
            "tasks": task_records,
            "suite": FALLBACK_SUITE_ID,
            "disclaimer": FALLBACK_DISCLAIMER,
            "methodology": (
                "Coding Agent Index protocol: pass@1 mean of 3 attempts; "
                "equal-weight SE/Terminal/QnA analogs; same LLM across systems"
            ),
            "metrics": {
                "time_per_task_seconds": total_time / n_slots,
                "turns_total": total_turns,
                "tokens": usage,
            },
        }
    (out_dir / "score.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
    )
    (out_dir / "metrics.json").write_text(
        json.dumps(payload["metrics"], indent=2, sort_keys=True), encoding="utf-8"
    )
    (out_dir / "insights.md").write_text(
        _insights(system_id, payload, suite=suite), encoding="utf-8"
    )
    return payload


def _evaluate_system(
    system_id: str,
    cls: Type,
    out_dir: Path,
    attempts: int,
) -> Dict[str, object]:
    return evaluate_system(
        system_id,
        cls,
        out_dir,
        attempts,
        tasks=FALLBACK_TASKS,
        suite="fallback",
    )


def _resolve_llm(
    suite: str,
    llm: Any,
    model: Optional[ModelConfig],
    allow_fake: bool,
) -> Tuple[Any, ModelConfig]:
    if llm is not None:
        return llm, _model_for_llm(llm, model)
    if suite != "research-30":
        return WorkspaceAwareLLM(), ModelConfig(provider="fake", model="workspace-aware")
    if allow_fake or allow_fake_from_env():
        return WorkspaceAwareLLM(), ModelConfig(provider="fake", model="workspace-aware")
    resolved = llm_from_env()
    return resolved, resolved.config


def _model_for_llm(llm: Any, model: Optional[ModelConfig]) -> ModelConfig:
    if model is not None:
        return model
    config = getattr(llm, "config", None)
    if isinstance(config, ModelConfig):
        return config
    return ModelConfig(provider="injected", model=type(llm).__name__)


def _llm_label(model: ModelConfig) -> str:
    return "{}/{}".format(model.provider, model.model)


def _selected_systems(system: Optional[str]) -> Dict[str, Type]:
    if system is None:
        return dict(SYSTEMS)
    if system not in SYSTEMS:
        raise ValueError("unknown system: {}".format(system))
    return {system: SYSTEMS[system]}


def _default_tasks(suite: str) -> List[TaskSpec]:
    if suite == "research-30":
        return research_suite.research_tasks()
    return list(FALLBACK_TASKS)


def _join_reasons(reasons: Sequence[str]) -> str:
    joined = " | ".join(item for item in reasons if item)
    if joined:
        return joined
    if reasons:
        return reasons[-1]
    return ""


def _insights(
    system_id: str, payload: Dict[str, object], suite: str = "fallback"
) -> str:
    if suite == "research-30":
        areas = payload["areas"]  # type: ignore[index]
        lines = [
            "# {}\n".format(system_id),
            "- Index: {:.3f}".format(payload["index"]),  # type: ignore[arg-type]
            "- SE: {:.3f}".format(areas["se"]),
            "- Terminal: {:.3f}".format(areas["terminal"]),
            "- QnA: {:.3f}".format(areas["qna"]),
            "",
            research_suite.SUITE_DISCLAIMER,
            "",
        ]
        return "\n".join(lines) + "\n"
    benches = payload["benchmarks"]  # type: ignore[index]
    lines = [
        "# {}\n".format(system_id),
        "- Index: {:.3f}".format(payload["index"]),  # type: ignore[arg-type]
        "- DeepSWE analog (se-add): {:.3f}".format(benches["deepswe"]),
        "- Terminal analog: {:.3f}".format(benches["terminal_bench_v2"]),
        "- QnA analog: {:.3f}".format(benches["swe_atlas_qna"]),
        "",
        FALLBACK_DISCLAIMER,
        "",
    ]
    return "\n".join(lines) + "\n"


def _render_markdown(summary: Dict[str, Dict[str, object]]) -> str:
    lines = [
        "# Fallback suite comparison",
        "",
        FALLBACK_DISCLAIMER,
        "",
        "LLM is identical (`WorkspaceAwareLLM`). Architecture is the independent variable.",
        "",
        "| 시스템 | Index | DeepSWE analog | Terminal analog | QnA analog | Time/task (s) | Turns |",
        "|--------|-------|----------------|-----------------|------------|---------------|-------|",
    ]
    for system_id, payload in summary.items():
        benches = payload["benchmarks"]  # type: ignore[index]
        metrics = payload["metrics"]  # type: ignore[index]
        lines.append(
            "| {} | {:.3f} | {:.3f} | {:.3f} | {:.3f} | {:.3f} | {} |".format(
                system_id,
                payload["index"],
                benches["deepswe"],
                benches["terminal_bench_v2"],
                benches["swe_atlas_qna"],
                metrics["time_per_task_seconds"],
                metrics["turns_total"],
            )
        )
    lines.extend(
        [
            "",
            "## How to read this",
            "",
            "- SE analog rewards graphs that **force tests** after a first (wrong) patch.",
            "- Terminal and QnA are solvable by the shared model as long as the loop reads/runs tools.",
            "- Higher Index is better. Time/turns are not in the Index.",
            "",
        ]
    )
    return "\n".join(lines)


def _render_research_markdown(summary: Dict[str, Dict[str, object]]) -> str:
    lines = [
        "# Research-30 suite comparison",
        "",
        research_suite.SUITE_DISCLAIMER,
        "",
        "LLM is identical across systems. Architecture is the independent variable.",
        "Index is correctness-only: time, cost, tokens, and turns are reported "
        "separately and are not part of Index_system.",
        "",
        "| 시스템 | Index | SE | Terminal | QnA | Time/task (s) | Cost/task (USD) | Tokens (in/out/cache) | Turns |",
        "|--------|-------|----|----------|-----|---------------|-----------------|-----------------------|-------|",
    ]
    for system_id, payload in summary.items():
        areas = payload["areas"]  # type: ignore[index]
        metrics = payload["metrics"]  # type: ignore[index]
        tokens = metrics["tokens"]
        token_text = "{}/{}/{}".format(
            tokens.get("input_tokens", 0),
            tokens.get("output_tokens", 0),
            tokens.get("cached_tokens", 0),
        )
        lines.append(
            "| {} | {:.3f} | {:.3f} | {:.3f} | {:.3f} | {:.3f} | {:.4f} | {} | {} |".format(
                system_id,
                payload["index"],
                areas["se"],
                areas["terminal"],
                areas["qna"],
                metrics["time_per_task_seconds"],
                metrics["cost_per_task_usd"],
                token_text,
                metrics["turns_total"],
            )
        )
    lines.extend(
        [
            "",
            "## Disclaimer",
            "",
            research_suite.SUITE_DISCLAIMER,
            "",
            "This custom suite cannot be compared numerically with the public "
            "Artificial Analysis leaderboard.",
            "",
        ]
    )
    return "\n".join(lines) + "\n"


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = parse_args(argv)
    app_root = Path(__file__).resolve().parents[2]
    if args.suite == "research-30":
        results_dir = app_root / "results" / "research-30"
    else:
        results_dir = app_root / "results"
    compare(
        results_dir,
        attempts=args.attempts,
        suite=args.suite,
        system=args.system,
        allow_fake=args.allow_fake,
    )
    print("wrote", results_dir / "comparison.md")


if __name__ == "__main__":
    main()
