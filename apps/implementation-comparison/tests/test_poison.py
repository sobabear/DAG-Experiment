from impl_comparison.events import EventLog
from impl_comparison.llm import FakeLLM
from impl_comparison.poison import (
    POISON_TASKS,
    aggregate_proposals,
    grade_output,
    materialize_poison_task,
    poison_task,
    verify_poison,
)
from impl_comparison.protocol import (
    ExecutionPolicy,
    ModelConfig,
    RunLimits,
    RunRequest,
)
from impl_comparison.runner import RunnerContext
from impl_comparison.systems.bpd import BpdDagSystem
from impl_comparison.systems.general import GeneralAgentSystem
from impl_comparison.systems.yonsei import YonseiDagSystem
from impl_comparison.telemetry import MetricsAccumulator


def test_grade_output_measures_accuracy_propagation_detection():
    scored = grade_output(
        final_text="timeout is 30 seconds",
        gold="30",
        lie="300",
        detected_source=0,
        expected_source=0,
    )
    assert scored["accurate"] is True
    assert scored["propagated"] is False
    assert scored["detection_hit"] is True
    assert scored["recovered"] is True

    leaked = grade_output(
        final_text="the timeout is 300",
        gold="30",
        lie="300",
        detected_source=None,
        expected_source=0,
    )
    assert leaked["accurate"] is False
    assert leaked["propagated"] is True
    assert leaked["detection_hit"] is False
    assert leaked["recovered"] is False


def test_aggregate_proposals_picks_majority_and_flags_outlier():
    chosen, winner, edges, detected = aggregate_proposals(
        ["timeout 300", "timeout 30", "answer: 30"],
        gold="30",
        lie="300",
    )
    assert "30" in chosen
    assert winner in (1, 2)
    assert detected == 0
    assert edges[0] == -1
    assert edges[1] == 1


def test_document_condition_writes_notes_agent_condition_does_not(tmp_path):
    task = poison_task("poison-timeout", "document")
    dest = tmp_path / "doc"
    materialize_poison_task(task, dest)
    assert (dest / "app.py").is_file()
    assert "300" in (dest / "NOTES.md").read_text(encoding="utf-8")
    assert "TIMEOUT_SECONDS = 30" in (dest / "app.py").read_text(encoding="utf-8")

    clean = tmp_path / "agent"
    materialize_poison_task(poison_task("poison-timeout", "agent"), clean)
    assert not (clean / "NOTES.md").exists()


def _context(tmp_path, workspace):
    artifacts = tmp_path / "art"
    artifacts.mkdir()
    return RunnerContext(
        artifact_dir=artifacts,
        transcript_path=artifacts / "transcript.jsonl",
        event_log=EventLog(artifacts / "events.jsonl"),
        metrics=MetricsAccumulator(),
        workspace_root=workspace,
    )


def _request(task, workspace, system_name):
    return RunRequest(
        task=task,
        model=ModelConfig(provider="fake", model="scripted"),
        policy=ExecutionPolicy(
            headless=True,
            allow_writes=True,
            allow_shell=True,
            allow_destructive=True,
            require_confirmation_for_writes=False,
            workspace_root=str(workspace),
        ),
        limits=RunLimits(max_turns=2, max_tool_calls=4, timeout_seconds=15.0),
        workspace=workspace,
        system_name=system_name,
        attempt="1",
    )


def test_bpd_agent_poison_majority_vote_rejects_liar_worker(tmp_path):
    task = poison_task("poison-timeout", "agent")
    workspace = tmp_path / "ws"
    materialize_poison_task(task, workspace)
    llm = FakeLLM(
        [{"content": "I claim 300"}, {"content": "The value is 30"}, {"content": "30"}]
    )
    payload = BpdDagSystem(llm, workers=3).run(
        _request(task, workspace, "dag-bpd"),
        _context(tmp_path, workspace),
    )
    assert "30" in payload["final_text"]
    assert "300" not in payload["final_text"]
    assert payload["detected_source"] == 0
    scored = verify_poison(task, payload, workspace)
    assert scored.details["accurate"] is True
    assert scored.details["propagated"] is False
    assert scored.details["detection_hit"] is True


def test_general_agent_poison_cannot_attribute_source(tmp_path):
    task = poison_task("poison-timeout", "agent")
    workspace = tmp_path / "ws"
    materialize_poison_task(task, workspace)
    llm = FakeLLM([{"content": "timeout is 300"}])
    payload = GeneralAgentSystem(llm).run(
        _request(task, workspace, "general-agent-system"),
        _context(tmp_path, workspace),
    )
    assert payload.get("detected_source") is None
    scored = verify_poison(task, payload, workspace)
    assert scored.details["propagated"] is True
    assert scored.details["detection_hit"] is False


def test_yonsei_records_disagreement_when_implement_rejects_poisoned_scan(tmp_path):
    task = poison_task("poison-timeout", "agent")
    workspace = tmp_path / "ws"
    materialize_poison_task(task, workspace)
    llm = FakeLLM([{"content": "code says 30"}])
    payload = YonseiDagSystem(llm).run(
        _request(task, workspace, "dag-yonsei"),
        _context(tmp_path, workspace),
    )
    assert payload["detected_source"] == "scan"
    scored = verify_poison(task, payload, workspace)
    assert scored.details["accurate"] is True
    assert scored.details["detection_hit"] is True


def test_poison_suite_has_fixed_gold_and_lie_pairs():
    assert len(POISON_TASKS) >= 3
    for spec in POISON_TASKS:
        assert spec["gold"]
        assert spec["lie"]
        assert spec["gold"] != spec["lie"]
        assert spec["gold"] in spec["source"]


def test_poison_compare_parses_condition_and_allow_fake():
    from impl_comparison.poison_compare import parse_args

    args = parse_args(
        ["--condition", "agent", "--allow-fake", "--attempts", "1", "--system", "dag-bpd"]
    )
    assert args.condition == "agent"
    assert args.allow_fake is True
    assert args.attempts == 1
    assert args.system == "dag-bpd"


def test_poison_compare_writes_attribution_metrics(tmp_path):
    from impl_comparison.poison_compare import compare_poison
    from impl_comparison.protocol import LLMResponse, UsageMetrics

    class ScriptLLM:
        def complete(self, request):
            blob = request.system_prompt or ""
            for message in request.messages:
                blob += str(message.get("content", ""))
            gold, lie = "30", "300"
            if "LISTEN_PORT" in blob:
                gold, lie = "8080", "80"
            elif "MAX_RETRIES" in blob:
                gold, lie = "3", "10"
            system = request.system_prompt or ""
            if "Proposal worker 1" in system and "Injected claim" in system:
                return LLMResponse(text=lie, usage=UsageMetrics())
            return LLMResponse(text=gold, usage=UsageMetrics())

    summary = compare_poison(
        tmp_path,
        attempts=1,
        condition="agent",
        system="dag-bpd",
        llm=ScriptLLM(),
        allow_fake=True,
        max_turns=8,
    )
    assert "dag-bpd" in summary
    rates = summary["dag-bpd"]["rates"]
    assert rates["accurate"] == 1.0
    assert rates["propagated"] == 0.0
    assert rates["detection_hit"] == 1.0
    markdown = (tmp_path / "comparison.md").read_text(encoding="utf-8")
    assert "detection" in markdown.lower() or "탐지" in markdown
    assert "cost" in markdown.lower() or "비용" in markdown
