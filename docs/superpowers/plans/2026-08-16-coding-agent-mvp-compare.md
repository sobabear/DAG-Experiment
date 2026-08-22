# Coding Agent MVP Compare — Implementation Plan

> **For agentic workers:** Execute task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Run the three agent systems on a shared fallback suite and report which architecture scores better under the Artificial Analysis Coding Agent protocol.

**Architecture:** Reuse the existing `impl_comparison` harness in this worktree. Public DeepSWE / Terminal-Bench v2 / SWE-Atlas-QnA runners are out of scope. Use plan §3.2: three tiny tasks mapped to SE / Terminal / Q&A, same deterministic FakeLLM, pass@1 with 3 attempts, equal-weight Index.

**Tech Stack:** Python 3.9, pytest, existing `impl_comparison` runner/tools.

**Honesty constraint:** Results are **not** Artificial Analysis leaderboard numbers. `results/` must say so.

---

### Task 1: Scoring

**Files:**
- Test: `apps/implementation-comparison/tests/test_scoring.py`
- Create: `apps/implementation-comparison/src/impl_comparison/scoring.py`

- [ ] Failing tests for task_score / bench_score / index
- [ ] Implement scoring
- [ ] Tests pass

### Task 2: Fallback suite

**Files:**
- Test: `apps/implementation-comparison/tests/test_suite.py`
- Create: `apps/implementation-comparison/src/impl_comparison/suite.py`
- Create: `apps/implementation-comparison/tasks/fallback/`

- [ ] Failing tests for fixtures + verifiers
- [ ] Implement suite
- [ ] Tests pass

### Task 3: Three systems + same FakeLLM

**Files:**
- Test: `apps/implementation-comparison/tests/test_systems.py`
- Create: `apps/implementation-comparison/src/impl_comparison/coding_llm.py`
- Create: `apps/implementation-comparison/src/impl_comparison/loop.py`
- Create: `apps/implementation-comparison/dag-bpd/agent.py`
- Create: `apps/implementation-comparison/dag-yonsei/agent.py`
- Create: `apps/implementation-comparison/general-agent-system/agent.py`

- [ ] Failing tests that the three systems are runnable through `run_agent`
- [ ] Implement systems
- [ ] Tests pass

### Task 4: Comparison run

**Files:**
- Create: `apps/implementation-comparison/src/impl_comparison/compare.py`
- Create: `apps/implementation-comparison/results/comparison.md`

- [ ] Run all systems × suite × 3 attempts
- [ ] Write score.json + comparison.md with fallback disclaimer
