"""Research 30-task suite: SE, Terminal, and Repository Q&A (10 each)."""

from __future__ import annotations

from pathlib import Path
from typing import List

from .protocol import TaskSpec, VerifierResult

SUITE_ID = "research-30"
SUITE_DISCLAIMER = (
    "This is a custom suite and cannot be compared numerically with the "
    "public Artificial Analysis leaderboard."
)

_AREA_BENCHMARK = {
    "se": "deepswe",
    "terminal": "terminal_bench_v2",
    "qna": "swe_atlas_qna",
}

_AREA_TIMEOUT = {
    "se": 90.0,
    "terminal": 120.0,
    "qna": 60.0,
}

_RESEARCH_TASK_DEFS = [
    (
        "se-01-multifile-bug",
        "se",
        "multifile_bug",
        (
            "A regression spans multiple modules: imports, shared helpers, and the "
            "failing entrypoint. Trace the failure across files, fix the root cause, "
            "and leave the workspace in a consistent state without breaking unrelated "
            "behavior."
        ),
        "Fix a bug that spans multiple source files.",
    ),
    (
        "se-02-api-migration",
        "se",
        "api_migration",
        (
            "A downstream client still calls a deprecated API surface. Migrate the "
            "codebase to the new interface, update call sites and adapters, and ensure "
            "existing behavior is preserved under the replacement contract."
        ),
        "Migrate callers from a deprecated API to its replacement.",
    ),
    (
        "se-03-schema-migration",
        "se",
        "schema_migration",
        (
            "The persisted data model changed: fields were renamed, types shifted, "
            "and one relation is now optional. Update models, serializers, and any "
            "migration helpers so reads and writes remain correct for old and new "
            "records."
        ),
        "Update code for a data model and schema change.",
    ),
    (
        "se-04-race-condition",
        "se",
        "race_condition",
        (
            "Intermittent failures appear under concurrent access. Identify the "
            "shared mutable state or ordering hazard, then apply a fix that makes "
            "the critical section safe without deadlocking normal requests."
        ),
        "Fix a concurrency race condition.",
    ),
    (
        "se-05-cache-invalidation",
        "se",
        "cache_invalidation",
        (
            "Stale values are served after writes because cache keys or invalidation "
            "hooks are incomplete. Correct the cache layer so updates propagate and "
            "reads reflect the latest authoritative state."
        ),
        "Fix incorrect cache invalidation after writes.",
    ),
    (
        "se-06-retry-timeout",
        "se",
        "retry_timeout",
        (
            "Outbound network calls fail unpredictably and sometimes hang. Implement "
            "or repair retry with backoff and explicit timeouts so transient errors "
            "recover and stuck requests do not block the service."
        ),
        "Implement reliable retry and timeout handling for network I/O.",
    ),
    (
        "se-07-auth-path-security",
        "se",
        "auth_path_security",
        (
            "A privileged action can be reached without the intended authorization "
            "check on one code path. Close the security gap so every entry route "
            "enforces the same policy before side effects occur."
        ),
        "Harden an authentication or authorization code path.",
    ),
    (
        "se-08-hidden-edge-case",
        "se",
        "hidden_edge_case",
        (
            "The happy path works, but boundary inputs trigger incorrect results. "
            "Find the unhandled edge case in the implementation and fix it while "
            "keeping the primary workflow unchanged."
        ),
        "Fix a non-obvious edge case in existing logic.",
    ),
    (
        "se-09-coupling-refactor",
        "se",
        "coupling_refactor",
        (
            "Two modules are tightly coupled through shared globals and circular "
            "imports. Refactor to reduce coupling, clarify boundaries, and keep "
            "external behavior stable for current callers."
        ),
        "Refactor tightly coupled modules without changing outward behavior.",
    ),
    (
        "se-10-performance-bottleneck",
        "se",
        "performance_bottleneck",
        (
            "A hot code path is unnecessarily slow due to redundant work or poor "
            "algorithmic choices. Locate the bottleneck and improve performance "
            "without altering the public result semantics."
        ),
        "Remove a measurable performance bottleneck.",
    ),
    (
        "terminal-01-broken-build",
        "terminal",
        "broken_build",
        (
            "The project build fails with errors in the workspace. Inspect build "
            "output, determine what broke, apply the minimal fixes, and confirm "
            "the build completes successfully."
        ),
        "Diagnose and repair a broken build.",
    ),
    (
        "terminal-02-log-config",
        "terminal",
        "log_config",
        (
            "Runtime logs show misconfiguration: wrong paths, levels, or missing "
            "handlers. Use the log evidence to correct configuration files and "
            "restart or rerun so logging behaves as intended."
        ),
        "Fix configuration using evidence from runtime logs.",
    ),
    (
        "terminal-03-file-transform",
        "terminal",
        "file_transform",
        (
            "Several files in the workspace need a consistent transformation applied "
            "via shell commands (rename, rewrite, or reformat). Perform the batch "
            "change and verify the transformed artifacts are present and well-formed."
        ),
        "Apply a multi-file transformation from the terminal.",
    ),
    (
        "terminal-04-test-triage",
        "terminal",
        "test_triage",
        (
            "The test suite reports multiple failures. Classify which failures share "
            "a common cause, fix the underlying issues, and rerun tests until the "
            "target subset passes."
        ),
        "Triage failing tests and fix the underlying problems.",
    ),
    (
        "terminal-05-timeout-restart",
        "terminal",
        "timeout_restart",
        (
            "A long-running process stalls and must be stopped safely, then restarted "
            "with corrected parameters. Handle the timeout, clean up partial state, "
            "and bring the service back to a healthy running state."
        ),
        "Recover from a timed-out process and restart it correctly.",
    ),
    (
        "terminal-06-checksum-artifact",
        "terminal",
        "checksum_artifact",
        (
            "Build artifacts were produced in the workspace. Compute the required "
            "checksum for the designated output and record the digest in the "
            "specified result file for downstream verification."
        ),
        "Compute and record a checksum for a build artifact.",
    ),
    (
        "terminal-07-env-diagnosis",
        "terminal",
        "env_diagnosis",
        (
            "A command fails because environment variables are missing or incorrect. "
            "Diagnose which variables are wrong, export or persist the proper "
            "values, and rerun the failing command successfully."
        ),
        "Diagnose and fix environment variable misconfiguration.",
    ),
    (
        "terminal-08-stream-large-file",
        "terminal",
        "stream_large_file",
        (
            "A large file must be processed without loading it entirely into memory. "
            "Use streaming shell or script techniques to produce the required "
            "aggregated output and write it to the designated location."
        ),
        "Process a large file using streaming techniques.",
    ),
    (
        "terminal-09-rollback-rerun",
        "terminal",
        "rollback_rerun",
        (
            "A partial deployment or migration left the workspace inconsistent. Roll "
            "back the failed changes, restore a known-good baseline, and rerun the "
            "procedure to completion."
        ),
        "Roll back a failed change and rerun the workflow.",
    ),
    (
        "terminal-10-parallel-checks",
        "terminal",
        "parallel_checks",
        (
            "Multiple independent checks must run in parallel and their results "
            "merged into a single summary report. Execute the checks concurrently, "
            "collect outcomes, and write the consolidated status file."
        ),
        "Run parallel checks and merge results into one report.",
    ),
    (
        "qna-01-call-graph",
        "qna",
        "call_graph",
        (
            "Trace the end-to-end call graph for the feature under study, from the "
            "public entrypoint through intermediate layers to side effects. Write "
            "answer.txt using the labeled key:value schema in ANSWER_FORMAT.md."
        ),
        "Describe the end-to-end call graph for a feature.",
    ),
    (
        "qna-02-config-impact",
        "qna",
        "config_impact",
        (
            "Explain how changing the named configuration setting affects runtime "
            "behavior across the repository. Write answer.txt using the labeled "
            "key:value schema in ANSWER_FORMAT.md."
        ),
        "Explain the impact of a configuration setting.",
    ),
    (
        "qna-03-root-cause",
        "qna",
        "root_cause",
        (
            "Given the observed failure symptoms in the workspace notes, determine "
            "the most likely root cause. Write answer.txt using the labeled "
            "key:value schema in ANSWER_FORMAT.md."
        ),
        "Identify the root cause of a reported failure.",
    ),
    (
        "qna-04-change-impact",
        "qna",
        "change_impact",
        (
            "A proposed code change touches a core module. Analyze which dependents "
            "are affected and what behaviors may break. Write answer.txt using the "
            "labeled key:value schema in ANSWER_FORMAT.md."
        ),
        "Analyze dependency and change-impact for a proposed edit.",
    ),
    (
        "qna-05-security-path",
        "qna",
        "security_path",
        (
            "Map the attack path an untrusted input could follow to reach a sensitive "
            "operation. Write answer.txt using the labeled key:value schema in "
            "ANSWER_FORMAT.md."
        ),
        "Trace a security-sensitive execution path.",
    ),
    (
        "qna-06-test-gap",
        "qna",
        "test_gap",
        (
            "Review the existing tests and implementation to find meaningful coverage "
            "gaps for the described scenario. Write answer.txt using the labeled "
            "key:value schema in ANSWER_FORMAT.md."
        ),
        "Identify test coverage gaps for a scenario.",
    ),
    (
        "qna-07-performance-location",
        "qna",
        "performance_location",
        (
            "Performance regressions are reported for a workflow. Using the codebase, "
            "pinpoint where time is likely spent and why. Write answer.txt using the "
            "labeled key:value schema in ANSWER_FORMAT.md."
        ),
        "Locate the likely performance bottleneck.",
    ),
    (
        "qna-08-state-flow",
        "qna",
        "state_flow",
        (
            "Explain how data or application state moves through the system for the "
            "given use case, including persistence and in-memory transitions. Write "
            "answer.txt using the labeled key:value schema in ANSWER_FORMAT.md."
        ),
        "Describe data or state flow for a use case.",
    ),
    (
        "qna-09-recovery-path",
        "qna",
        "recovery_path",
        (
            "After a described failure mode, determine how the system is expected to "
            "recover or what manual steps restore service. Write answer.txt using the "
            "labeled key:value schema in ANSWER_FORMAT.md."
        ),
        "Explain the failure recovery path.",
    ),
    (
        "qna-10-architecture-tradeoff",
        "qna",
        "architecture_tradeoff",
        (
            "Compare the two architectural approaches referenced in the repository "
            "docs for the stated concern. Write answer.txt using the labeled "
            "key:value schema in ANSWER_FORMAT.md."
        ),
        "Explain architecture trade-offs documented in the repo.",
    ),
]


def research_tasks() -> List[TaskSpec]:
    tasks: List[TaskSpec] = []
    for task_id, area, verifier_name, prompt, description in _RESEARCH_TASK_DEFS:
        tasks.append(
            TaskSpec(
                task_id=task_id,
                prompt=prompt,
                description=description,
                area=area,
                benchmark=_AREA_BENCHMARK[area],
                verifier_name=verifier_name,
                timeout=_AREA_TIMEOUT[area],
            )
        )
    return tasks


def materialize_task(task: TaskSpec, dest: Path) -> Path:
    """Write the BROKEN starting workspace the agent will see. Fresh dest every call."""
    if task.area == "se":
        from .research_tasks.se.tasks import materialize_se_task

        return materialize_se_task(task, dest)
    if task.area == "terminal":
        from .research_tasks.terminal.tasks import materialize_terminal_task

        return materialize_terminal_task(task, dest)
    if task.area == "qna":
        from .research_tasks.qna.tasks import materialize_qna_task

        return materialize_qna_task(task, dest)
    raise NotImplementedError(
        "materialize_task is not implemented for area {}".format(task.area)
    )


def verify_run(request, system_result, artifact_dir) -> VerifierResult:
    """Ignore model claims; score the workspace only."""
    del system_result, artifact_dir
    return verify_task(request.task, request.workspace)


def verify_task(task: TaskSpec, workspace: Path) -> VerifierResult:
    """Independent of any agent claim/final_text. Inspect workspace only."""
    if task.area == "se":
        from .research_tasks.se.tasks import verify_se_task

        return verify_se_task(task, workspace)
    if task.area == "terminal":
        from .research_tasks.terminal.tasks import verify_terminal_task

        return verify_terminal_task(task, workspace)
    if task.area == "qna":
        from .research_tasks.qna.tasks import verify_qna_task

        return verify_qna_task(task, workspace)
    raise NotImplementedError(
        "verify_task is not implemented for area {}".format(task.area)
    )


def apply_reference_fix(task: TaskSpec, workspace: Path) -> None:
    """Test-only helper that applies the intended repair. Agents never call this."""
    if task.area == "se":
        from .research_tasks.se.tasks import apply_se_reference_fix

        apply_se_reference_fix(task, workspace)
        return
    if task.area == "terminal":
        from .research_tasks.terminal.tasks import apply_terminal_reference_fix

        apply_terminal_reference_fix(task, workspace)
        return
    if task.area == "qna":
        from .research_tasks.qna.tasks import apply_qna_reference_fix

        apply_qna_reference_fix(task, workspace)
        return
    raise NotImplementedError(
        "apply_reference_fix is not implemented for area {}".format(task.area)
    )
