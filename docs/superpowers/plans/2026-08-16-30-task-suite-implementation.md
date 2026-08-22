# 30-Task Evaluation Suite Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the three-task smoke suite with a calibrated 30-task custom suite that can distinguish the three agent architectures under the same LLM and verifier protocol.

**Architecture:** Keep task definitions data-driven. Each task has a stable ID, area, prompt, fixture builder, verifier, timeout, and expected artifact contract. A suite runner materializes a fresh workspace for every attempt, invokes the existing common runner, and aggregates 3-attempt binary results into area scores and `Index_system`. The public Artificial Analysis datasets are not downloaded or represented as local score data.

**Tech Stack:** Python 3.9, pytest, existing `impl_comparison` protocol/runner/tools, subprocesses with bounded timeouts, JSON/Markdown result files.

---

## File map

- Modify: `apps/implementation-comparison/src/impl_comparison/protocol.py` — add task area and verifier metadata without changing existing serialization compatibility.
- Create: `apps/implementation-comparison/src/impl_comparison/research_suite.py` — 30-task manifest, fixture materializers, and verifier dispatch.
- Create: `apps/implementation-comparison/src/impl_comparison/research_tasks/se/` — ten isolated SE fixture builders and verifiers.
- Create: `apps/implementation-comparison/src/impl_comparison/research_tasks/terminal/` — ten terminal fixture builders and verifiers.
- Create: `apps/implementation-comparison/src/impl_comparison/research_tasks/qna/` — ten repository fixture builders and answer verifiers.
- Create: `apps/implementation-comparison/tests/test_research_suite.py` — manifest, isolation, verifier, and hidden-condition tests.
- Modify: `apps/implementation-comparison/src/impl_comparison/compare.py` — select `research-30` suite and aggregate three areas.
- Modify: `apps/implementation-comparison/README.md` — document the executable 30-task command and custom-suite disclaimer.
- Modify: `apps/implementation-comparison/implementation-comparison-plan.md` — replace “target” wording when 30 tasks are executable.
- Create: `apps/implementation-comparison/results/research-30/comparison.md` — generated comparison report.

## Task 1: Add the typed 30-task manifest

**Files:**
- Test: `apps/implementation-comparison/tests/test_research_suite.py`
- Create: `apps/implementation-comparison/src/impl_comparison/research_suite.py`
- Modify: `apps/implementation-comparison/src/impl_comparison/protocol.py`

- [ ] **Step 1: Write failing manifest tests**

```python
def test_research_suite_has_exactly_thirty_unique_tasks():
    tasks = research_tasks()
    assert len(tasks) == 30
    assert len({task.task_id for task in tasks}) == 30
    assert Counter(task.area for task in tasks) == {
        "se": 10,
        "terminal": 10,
        "qna": 10,
    }
```

- [ ] **Step 2: Run the focused test and verify it fails because `research_tasks` is absent.**

Run from `apps/implementation-comparison/`:

```sh
python -m pytest tests/test_research_suite.py::test_research_suite_has_exactly_thirty_unique_tasks -q
```

Expected: collection failure with `ModuleNotFoundError` or missing `research_tasks`.

- [ ] **Step 3: Define the manifest IDs exactly**

Use these IDs:

```text
se-01-multifile-bug
se-02-api-migration
se-03-schema-migration
se-04-race-condition
se-05-cache-invalidation
se-06-retry-timeout
se-07-auth-path-security
se-08-hidden-edge-case
se-09-coupling-refactor
se-10-performance-bottleneck
terminal-01-broken-build
terminal-02-log-config
terminal-03-file-transform
terminal-04-test-triage
terminal-05-timeout-restart
terminal-06-checksum-artifact
terminal-07-env-diagnosis
terminal-08-stream-large-file
terminal-09-rollback-rerun
terminal-10-parallel-checks
qna-01-call-graph
qna-02-config-impact
qna-03-root-cause
qna-04-change-impact
qna-05-security-path
qna-06-test-gap
qna-07-performance-location
qna-08-state-flow
qna-09-recovery-path
qna-10-architecture-tradeoff
```

Add `area`, `prompt`, `timeout`, and `verifier_name` to the task contract. Keep existing `TaskSpec.from_dict()` behavior compatible with older tasks.

- [ ] **Step 4: Run the focused manifest test and verify it passes.**

- [ ] **Step 5: Run `python -m pytest tests/test_protocol.py tests/test_research_suite.py -q` and verify all protocol and manifest tests pass.**

## Task 2: Implement the ten Software Engineering fixtures

**Files:**
- Test: `apps/implementation-comparison/tests/test_research_suite.py`
- Create: `apps/implementation-comparison/src/impl_comparison/research_tasks/se/__init__.py`
- Create: `apps/implementation-comparison/src/impl_comparison/research_tasks/se/tasks.py`

- [ ] **Step 1: Add red tests that materialize every `se-*` task into a new temporary directory and assert the fixture contains at least three source/test/config files.**

- [ ] **Step 2: Add one verifier test per task using a deliberately broken fixture. Each verifier must return `passed=False`; it must not inspect the agent’s claimed text.**

- [ ] **Step 3: Implement the fixtures and verifiers with these hidden conditions:**

| ID | Hidden verifier condition |
|---|---|
| `se-01` | Service and CLI both use the corrected parser behavior; regression test passes |
| `se-02` | New interface is implemented and all two legacy callers use it |
| `se-03` | Migration is idempotent and preserves existing records |
| `se-04` | 100 concurrent increments produce exactly 100 without a race |
| `se-05` | Updating a source invalidates both key and derived cache entries |
| `se-06` | Retry stops on success, caps attempts, and respects timeout |
| `se-07` | Traversal and unauthorized role access are rejected |
| `se-08` | Empty, Unicode, negative, and maximum-size inputs satisfy hidden cases |
| `se-09` | Public behavior stays unchanged while duplicate logic is removed |
| `se-10` | Large input completes under the fixture’s bounded operation budget |

- [ ] **Step 4: Run all SE verifier tests and verify 10 broken-fixture failures are detected and 10 corrected-fixture tests pass.**

- [ ] **Step 5: Run the existing harness tests to confirm the new fixtures do not alter common runner behavior.**

## Task 3: Implement the ten Terminal / Agentic Workflow fixtures

**Files:**
- Test: `apps/implementation-comparison/tests/test_research_suite.py`
- Create: `apps/implementation-comparison/src/impl_comparison/research_tasks/terminal/__init__.py`
- Create: `apps/implementation-comparison/src/impl_comparison/research_tasks/terminal/tasks.py`

- [ ] **Step 1: Add tests asserting each terminal task has a command-oriented prompt and a bounded timeout of at most 120 seconds.**

- [ ] **Step 2: Add failing verifier tests for missing or invalid artifacts.**

- [ ] **Step 3: Implement fixture and verifier pairs with these hidden conditions:**

| ID | Hidden verifier condition |
|---|---|
| `terminal-01` | Build succeeds and generated artifact contains the required version |
| `terminal-02` | Only the matching error pattern is changed; unrelated config remains unchanged |
| `terminal-03` | All input files are transformed and manifest counts match |
| `terminal-04` | Only the requested failing-test group is fixed; unrelated failures remain visible |
| `terminal-05` | Timeout is handled and a restart marker records the second attempt |
| `terminal-06` | `answer.txt` matches the hidden SHA-256 digest exactly |
| `terminal-07` | Missing variable is diagnosed without writing a secret value |
| `terminal-08` | Peak-memory marker stays below the fixture limit while output is complete |
| `terminal-09` | Failed mutation is rolled back before the successful rerun |
| `terminal-10` | Three independent check results are present and aggregate status is correct |

- [ ] **Step 4: Test timeout, output-limit, and rollback verifiers against malicious or incomplete artifacts.**

- [ ] **Step 5: Run the terminal task tests and verify all pass.**

## Task 4: Implement the ten Repository Q&A fixtures

**Files:**
- Test: `apps/implementation-comparison/tests/test_research_suite.py`
- Create: `apps/implementation-comparison/src/impl_comparison/research_tasks/qna/__init__.py`
- Create: `apps/implementation-comparison/src/impl_comparison/research_tasks/qna/tasks.py`

- [ ] **Step 1: Add tests requiring every Q&A fixture to contain at least five linked source files and a deterministic answer schema.**

- [ ] **Step 2: Add failing answer tests for missing facts, fabricated paths, and unsupported claims.**

- [ ] **Step 3: Implement answer verifiers with required facts and evidence paths:**

| ID | Required answer evidence |
|---|---|
| `qna-01` | Caller, intermediate function, and sink with file paths |
| `qna-02` | Configuration key, parser, consumer, and behavior change |
| `qna-03` | Root cause, triggering input, and exact fix location |
| `qna-04` | Direct dependency, transitive dependency, and affected test |
| `qna-05` | Attack input, vulnerable boundary, and mitigation |
| `qna-06` | Missing branch, observable behavior, and proposed test |
| `qna-07` | Hot path, measurement command, and expected metric |
| `qna-08` | State names, valid transition, and persistence point |
| `qna-09` | Failure boundary, retry/rollback path, and terminal state |
| `qna-10` | Two explicit trade-offs and one bounded recommendation |

- [ ] **Step 4: Reject answers that cite nonexistent files, omit required facts, or contain unsupported API names.**

- [ ] **Step 5: Run all Q&A verifier tests and verify corrected answer fixtures pass.**

## Task 5: Add suite execution and scoring integration

**Files:**
- Test: `apps/implementation-comparison/tests/test_compare_research.py`
- Modify: `apps/implementation-comparison/src/impl_comparison/compare.py`
- Modify: `apps/implementation-comparison/src/impl_comparison/scoring.py`

- [ ] **Step 1: Write a test that runs one selected system over one task per area and asserts the result contains area scores and a three-area Index.**

- [ ] **Step 2: Write a test that rejects mixed suites or missing area results before calculating the Index.**

- [ ] **Step 3: Add `--suite research-30`, `--attempts 3`, and `--system <id>` command options.**

- [ ] **Step 4: Aggregate exactly 30 task records into `results/research-30/<system>/score.json`, with `attempts`, `task_score`, `area`, and verifier reason for every task.**

- [ ] **Step 5: Generate `results/research-30/comparison.md` with one row per system, three area columns, Index, time/task, cost/task, token counts, turns, and the custom-suite disclaimer.**

- [ ] **Step 6: Run the integration test and verify the Index is the equal-weight mean of the three area scores.**

## Task 6: Calibrate difficulty before real comparison

**Files:**
- Test: `apps/implementation-comparison/tests/test_calibration.py`
- Create: `apps/implementation-comparison/src/impl_comparison/calibration.py`
- Create: `apps/implementation-comparison/tasks/research-30/README.md`

- [ ] **Step 1: Add tests for task validity: unique IDs, fresh materialization, hidden verifier, bounded timeout, and no prompt text equal to the expected answer.**

- [ ] **Step 2: Implement a calibration report containing per-task pass counts, fail counts, and failure reasons for all three systems.**

- [ ] **Step 3: Mark a task `ceiling` when all systems pass all three attempts and `floor` when all fail all three attempts.**

- [ ] **Step 4: Keep ceiling/floor controls in the suite but exclude invalid tasks from the primary comparison only after recording the exclusion and reason in the report.**

- [ ] **Step 5: Run calibration with the deterministic Fake LLM only as a harness check; do not publish it as the research result.**

## Task 7: Run the real-LLM pilot and document results

**Files:**
- Modify: `apps/implementation-comparison/README.md`
- Modify: `apps/implementation-comparison/implementation-comparison-plan.md`
- Create: `apps/implementation-comparison/results/research-30/comparison.md`

- [ ] **Step 1:** Configure one identical real LLM and settings for all three systems through environment variables; do not write credentials to files.

- [ ] **Step 2:** Run all 30 tasks × 3 attempts × 3 systems from fresh workspaces.

- [ ] **Step 3:** Verify every result has a verifier outcome, transcript, event log, metrics, and attempt ID.

- [ ] **Step 4:** Compute area scores and `Index_system`; keep time, cost, tokens, and turns outside the correctness score.

- [ ] **Step 5:** Write qualitative findings from failure artifacts: DAG advantage, DAG overhead, general-system flexibility, and task categories with no separation.

- [ ] **Step 6:** Run the full test suite and `git diff --check`; report public-benchmark limitations explicitly.

