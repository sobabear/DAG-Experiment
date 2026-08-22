"""Shared run lifecycle; verification is always independent of model claims."""

from dataclasses import dataclass, replace
import asyncio
import inspect
import json
import multiprocessing
import os
import pickle
from pathlib import Path
import queue
import signal
import time
from typing import Any, Callable, Optional, Protocol, Union
import uuid

from .events import EventLog
from .protocol import RunRequest, RunResult, VerifierResult
from .security import redact_sensitive, sanitize_artifact_tree
from .protocol import UsageMetrics
from .telemetry import MetricsAccumulator
from .workspace import WorkspaceManager


@dataclass
class RunnerContext:
    artifact_dir: Path
    transcript_path: Path
    event_log: EventLog
    metrics: MetricsAccumulator
    workspace_root: Path

    @property
    def events(self) -> EventLog:
        return self.event_log

    def emit(self, event_type: str, **payload: Any) -> None:
        self.event_log.append(event_type, **payload)


class AgentSystem(Protocol):
    def run(self, request: RunRequest, context: RunnerContext) -> Any:
        ...


Verifier = Callable[[RunRequest, Any, Path], VerifierResult]


class SyncProcessTimeout(TimeoutError):
    """A synchronous child process exceeded its deadline."""


class SyncProcessUnavailable(RuntimeError):
    """The platform cannot provide safe synchronous process isolation."""


def run_agent(
    request: RunRequest,
    system: AgentSystem,
    verifier: Verifier,
    workspace_root: Union[str, Path],
    run_id: Optional[str] = None,
) -> RunResult:
    actual_run_id = run_id or uuid.uuid4().hex
    manager = WorkspaceManager(workspace_root)
    artifact_dir = manager.create_attempt(
        request.task.task_id, request.attempt or request.attempt_id or actual_run_id
    )
    try:
        system_workspace = manager.create_workspace(artifact_dir, request.workspace)
    except Exception:
        manager.discard_attempt(artifact_dir)
        raise
    effective_request = replace(
        request,
        workspace=system_workspace,
        policy=replace(request.policy, workspace_root=str(system_workspace)),
    )
    events_path = artifact_dir / "events.jsonl"
    transcript_path = artifact_dir / "transcript.jsonl"
    event_log = EventLog(events_path)
    metrics = MetricsAccumulator(
        max_turns=request.limits.max_turns,
        max_tool_calls=request.limits.max_tool_calls,
    )
    context = RunnerContext(
        artifact_dir=artifact_dir,
        transcript_path=transcript_path,
        event_log=event_log,
        metrics=metrics,
        workspace_root=system_workspace,
    )
    event_log.append(
        "run_started",
        run_id=actual_run_id,
        task_id=request.task.task_id,
        system_name=request.system_name,
    )

    started = time.monotonic()
    system_result: Any
    system_error = False
    execution_timeout = False
    sync_execution_timeout = False
    system_is_async = inspect.iscoroutinefunction(getattr(system, "run", None))
    try:
        system_result, child_metrics, child_error = _invoke_system(
            system,
            effective_request,
            context,
            min(
                effective_request.limits.timeout_seconds,
                effective_request.task.timeout,
            ),
        )
        if child_metrics is not None:
            metrics.merge_child(
                child_metrics["turns"],
                child_metrics["tool_calls"],
                UsageMetrics.from_dict(child_metrics["usage"]),
            )
        system_error = child_error
    except asyncio.TimeoutError:
        execution_timeout = True
        system_error = True
        system_result = {"error": "system execution timed out"}
    except SyncProcessTimeout:
        execution_timeout = True
        sync_execution_timeout = True
        system_error = True
        system_result = {"error": "synchronous process exceeded its deadline"}
    except SyncProcessUnavailable:
        manager.discard_attempt(artifact_dir)
        raise
    except Exception as exc:
        system_error = True
        system_result = {"error": "{}: {}".format(type(exc).__name__, exc)}

    metrics_snapshot = metrics.finish()
    system_output = redact_sensitive(_stringify_output(system_result))
    with transcript_path.open("a", encoding="utf-8") as transcript:
        transcript.write(
            json.dumps(
                {"type": "system_result", "text": system_output},
                sort_keys=True,
            )
            + "\n"
        )

    try:
        verifier_result = verifier(effective_request, system_result, artifact_dir)
    except Exception as exc:
        verifier_result = VerifierResult(
            passed=False,
            reason=redact_sensitive("verifier error: {}".format(exc)),
        )
    verifier_result = replace(
        verifier_result,
        reason=redact_sensitive(verifier_result.reason),
        details=redact_sensitive(verifier_result.details),
    )
    sanitize_artifact_tree(artifact_dir)
    total_elapsed = time.monotonic() - started
    limit_exceeded = (
        metrics_snapshot.turns > effective_request.limits.max_turns
        or metrics_snapshot.tool_calls > effective_request.limits.max_tool_calls
    )
    timeout_exceeded = metrics_snapshot.wall_time_seconds > min(
        effective_request.limits.timeout_seconds, effective_request.task.timeout
    )
    if limit_exceeded:
        status = "limit_exceeded"
    elif execution_timeout or timeout_exceeded:
        status = "timeout"
    elif system_error or not verifier_result.passed:
        status = "failed"
    else:
        status = "passed"
    event_log.append(
        "run_finished",
        run_id=actual_run_id,
        status=status,
        passed=verifier_result.passed,
        turns=metrics_snapshot.turns,
        tool_calls=metrics_snapshot.tool_calls,
    )
    result = RunResult(
        run_id=actual_run_id,
        status=status,
        final_text=system_output,
        transcript_path=transcript_path,
        event_path=events_path,
        verifier_result=verifier_result,
        turns=metrics_snapshot.turns,
        tool_calls=metrics_snapshot.tool_calls,
        usage=metrics_snapshot.usage,
        wall_time=metrics_snapshot.wall_time_seconds,
        artifact_dir=artifact_dir,
        metadata={
            "timeout_enforcement": (
                "async_cancelled"
                if execution_timeout and not sync_execution_timeout
                else "async_wait_for"
                if system_is_async
                else "sync_process"
            ),
            "hard_cancel": False,
            "detached_descendants_uncontained": True,
            "process_group_cleanup": (
                "not_applicable" if system_is_async else "best_effort"
            ),
            "cancellation_limitation": (
                "async_cancel_can_be_suppressed"
                if system_is_async
                else "process_group_does_not_contain_detached_descendants"
            ),
            "total_runner_wall_time": total_elapsed,
        },
    )
    (artifact_dir / "metrics.json").write_text(
        json.dumps(
            {
                "turns": metrics_snapshot.turns,
                "tool_calls": metrics_snapshot.tool_calls,
                "wall_time_seconds": metrics_snapshot.wall_time_seconds,
                "usage": metrics_snapshot.usage.to_dict(),
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    (artifact_dir / "result.json").write_text(
        json.dumps(result.to_dict(), sort_keys=True),
        encoding="utf-8",
    )
    return result


def _invoke_system(system, request, context, timeout):
    """Run async systems cancellably and sync systems in a forked process."""
    if inspect.iscoroutinefunction(getattr(system, "run", None)):
        result = system.run(request, context)
        return asyncio.run(asyncio.wait_for(result, timeout=timeout)), None, False
    return _invoke_sync_process(system, request, context, timeout)


def _invoke_sync_process(system, request, context, timeout):
    methods = multiprocessing.get_all_start_methods()
    if "fork" not in methods:
        raise SyncProcessUnavailable(
            "synchronous systems require POSIX multiprocessing fork isolation"
        )
    process_context = multiprocessing.get_context("fork")
    result_queue = process_context.Queue()
    child_context = {
        "artifact_dir": str(context.artifact_dir),
        "transcript_path": str(context.transcript_path),
        "workspace_root": str(context.workspace_root),
    }
    process = process_context.Process(
        target=_sync_process_entry,
        args=(system, request, child_context, result_queue),
    )
    try:
        process.start()
    except Exception as exc:
        result_queue.close()
        raise SyncProcessUnavailable(
            "could not start isolated synchronous process: {}".format(exc)
        ) from exc
    process.join(timeout)
    if process.is_alive():
        _terminate_child_process(process)
        result_queue.close()
        raise SyncProcessTimeout()
    try:
        payload = pickle.loads(result_queue.get(timeout=1.0))
    except (
        queue.Empty,
        EOFError,
        pickle.PickleError,
        TypeError,
        ValueError,
    ) as exc:
        payload = {
            "result": {
                "error": "synchronous child returned no readable result: {}".format(
                    exc
                )
            },
            "metrics": {"turns": 0, "tool_calls": 0, "usage": UsageMetrics().to_dict()},
            "system_error": True,
        }
    finally:
        result_queue.close()
    return payload["result"], payload["metrics"], bool(payload.get("system_error"))


def _sync_process_entry(system, request, context_data, result_queue):
    if hasattr(os, "setsid"):
        os.setsid()
    child_metrics = MetricsAccumulator(
        max_turns=request.limits.max_turns,
        max_tool_calls=request.limits.max_tool_calls,
    )
    child_context = RunnerContext(
        artifact_dir=Path(context_data["artifact_dir"]),
        transcript_path=Path(context_data["transcript_path"]),
        event_log=EventLog(Path(context_data["artifact_dir"]) / "events.jsonl"),
        metrics=child_metrics,
        workspace_root=Path(context_data["workspace_root"]),
    )
    try:
        result = system.run(request, child_context)
        if inspect.isawaitable(result):
            raise TypeError("synchronous system returned an awaitable")
        error = None
    except BaseException as exc:
        result = {
            "error": "{}: {}".format(type(exc).__name__, exc),
        }
        error = exc
    snapshot = child_metrics.finish()
    metrics = {
        "turns": snapshot.turns,
        "tool_calls": snapshot.tool_calls,
        "usage": snapshot.usage.to_dict(),
    }
    payload = {"result": result, "metrics": metrics}
    if error is not None:
        payload["system_error"] = True
    try:
        result_queue.put(pickle.dumps(payload))
    except Exception:
        result_queue.put(
            pickle.dumps(
                {
                    "result": {"error": "synchronous system result was unpicklable"},
                    "metrics": metrics,
                    "system_error": True,
                }
            )
        )


def _terminate_child_process(process):
    process_group_available = True
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except (OSError, AttributeError):
        process_group_available = False
        process.terminate()
    process.join(0.2)
    if process_group_available:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except (OSError, AttributeError):
            pass
    elif process.is_alive():
        process.kill()
    process.join()


def _stringify_output(value: Any) -> str:
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, sort_keys=True, default=str)
    except (TypeError, ValueError):
        return str(value)
