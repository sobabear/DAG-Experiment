# Coding Agent Systems Design

**Date:** 2026-08-08
**Status:** Approved design; implementation in progress

## 1. Goal

Build three runnable coding-agent systems for controlled comparison:

1. `dag-bpd`: a BPD-inspired signed layered DAG.
2. `dag-yonsei`: a Yonsei AgentDAG-inspired PFA and partial-rerun DAG.
3. `general-agent-system`: an independently designed bounded tool-loop agent.

All systems must use the same OpenAI-compatible model adapter, task contract,
tool semantics, workspace policy, verifier, budgets, and telemetry. The
architecture is the independent variable.

The implementation starts with deterministic fake-LLM smoke runs. Public
benchmark runners remain a later integration step.

## 2. Boundaries and responsible reuse

The existing `src/dagcore/` package remains unchanged. `dag-bpd` may use its
MIT-licensed `EdgeGraph` and retain the upstream MIT notice in documentation.
`dag-yonsei` is an independent implementation of the concepts observed in the
local `AgentDAG` checkout; it does not copy source files.

The `tanbiralam/claude-code` repository has no open-source license and states
that the archived source belongs to Anthropic. The general system therefore
uses only high-level observable behavior as inspiration. It does not copy
source, prompts, schemas, identifiers, comments, or internal algorithms.

No credential is stored in source code, configuration, transcripts, or run
artifacts. Provider configuration is supplied by environment variables.

## 3. Shared execution contract

The comparison app owns a provider-neutral contract:

```text
TaskSpec
  task_id, benchmark, prompt, workspace_snapshot, verifier, timeout

RunRequest
  task, workspace, model, policy, limits, attempt

RunResult
  status, final_text, verifier_result, transcript_path, event_path,
  turns, usage, wall_time
```

The model adapter normalizes text deltas, completed assistant messages, tool
calls, finish reasons, usage, and retryable errors. Provider-specific SDK
objects do not leave the adapter.

The common tool registry exposes:

- file listing and glob/search;
- bounded file reads;
- write and patch/edit operations;
- shell/test execution with timeout and output limits.

Every tool declares whether it is read-only, destructive, and concurrency-safe.
Read-only calls may run in bounded parallel batches. Mutating and destructive
calls run serially through the same workspace policy.

Each attempt gets a fresh workspace namespace. Events use one vocabulary across
systems: `run_started`, `turn_started`, `model_request`, `model_response`,
`tool_requested`, `permission_decision`, `tool_started`, `tool_finished`,
`child_started`, `child_finished`, and `run_finished`.

Synchronous systems run in a POSIX child process with best-effort process-group
cleanup. Descendants that detach into a new session are not contained, so
runtime metadata does not claim universal hard cancellation. Async cancellation
uses `asyncio.wait_for`, but coroutines can suppress cancellation; both
limitations are recorded explicitly in run metadata. Shell/test timeouts use
the same best-effort process-group boundary and have the same detached-
descendant limitation.

## 4. BPD system

The first runnable topology is `3+1+3`:

```text
proposal workers -> advisor -> final workers -> verifier
```

Configuration also supports paper-shaped `5+2+5` and flat peer review after the
core flow is tested.

Each node emits a structured message containing its role, stable identity,
round, parent references, text, tool calls, and patch/artifact references.
Relationships between a receiver and its supplied sender artifacts are scored
as `-1`, `0`, or `+1` and written to `dagcore.EdgeGraph`.

BPD backward propagation is used to identify a suspicious proposal, but agent
consensus never substitutes for objective correctness. The terminal signal is
the external verifier result for the selected patch. Repair is bounded to one
detection pass and one rerun, and agent work remains isolated until a verified
patch is selected.

## 5. Yonsei DAG system

The initial graph is:

```text
bootstrap
  -> repository_scan, test_scan, task_analysis
  -> plan_synthesis
  -> implementation
  -> run_tests, code_review
  -> repair_or_accept
  -> verify
```

Read-only inspection nodes may run concurrently. There is one write-capable
implementation stage to avoid shared-worktree conflicts.

Each node has a stable ID, role, declared input/output artifacts, retry limit,
timeout, and dependency policy. Node states are `IDLE`, `RUNNING`, `PASS`,
`FAIL`, and `AMBIGUOUS`. Evaluation records similarity `S`, confidence `C`,
critic deviation `D`, and ambiguity score `A`.

When a node is corrected, downstream impact is accumulated as
`R / (distance + 1)`. Only nodes above the configured threshold are reset and
rerun. Ambiguous nodes pause execution for an explicit HITL decision. State
snapshots and append-only events are saved after each node.

## 6. General agent system

The general system uses one bounded main model/tool loop. It supports
non-interactive prompt execution, an optional REPL, turn/time/token budgets,
session transcripts, and resume by session ID.

Read-only tools may be batched within a bounded concurrency limit. Writes and
destructive operations require policy checks and execute serially. Optional
child delegation is limited to one level and records parent/child identity,
separate transcript, cancellation, and result collection.

MCP, LSP, plugins, IDE bridges, voice, remote sessions, and OS-level sandboxing
are outside the MVP. Process-level policy is explicitly not a security
boundary.

## 7. Evaluation and testing

The verifier alone determines pass/fail. Run artifacts are stored under:

```text
runs/<variant>/<task-id>/<attempt-id>/
  events.jsonl
  transcript.jsonl
  metrics.json
  result.json
```

Tests first establish behavior for:

- common protocol normalization and tool policy;
- BPD edge scoring, propagation, detection, and repair isolation;
- Yonsei cycle validation, deterministic scheduling, PFA routing, impact
  selection, checkpointing, and HITL;
- general looping, permission denial, session resume, and child bounds;
- all three systems executing the same fake task contract.

The real provider adapter is tested separately and is never required for the
network-free smoke suite.
