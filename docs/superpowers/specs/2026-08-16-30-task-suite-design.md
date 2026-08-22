# 30-Task Coding Agent Evaluation Suite — Design Spec

**Date:** 2026-08-16  
**Status:** Approved design; pending implementation  
**Repository:** `DAG-Experiment/.worktrees/coding-agent-systems`

## 1. Goal

Expand the current three-task smoke suite into a 30-task research suite so the comparison measures architectural differences rather than a trivial success ceiling.

The research question remains:

> When does a DAG-based agent system outperform a general multi-agent system, and what are the associated strengths, costs, and failure modes?

The three systems remain:

1. `dag-bpd` — BPD-paper-inspired DAG
2. `dag-yonsei` — Yonsei-designed DAG
3. `general-agent-system` — bounded general multi-agent loop

## 2. Evaluation structure

The suite contains three equally weighted areas with ten tasks each:

```text
Software Engineering       10 tasks
Terminal / Agentic Workflow 10 tasks
Repository Q&A              10 tasks
                              ---
                              30 tasks
```

Each task is run three times from a fresh workspace:

```text
task_score = mean(attempt_1, attempt_2, attempt_3)
area_score = mean(task_scores in area)
Index_system = mean(SE, Terminal, Repository Q&A)
```

Every attempt is binary pass/fail according to an independent verifier. The verifier and hidden tests are not included in the agent prompt.

This is a custom suite modeled on the evaluation categories and scoring protocol of Artificial Analysis Coding Agent Benchmarks. It is not the public DeepSWE, Terminal-Bench v2, or SWE-Atlas-QnA dataset, so its scores must not be presented as public leaderboard scores.

## 3. Task categories

### 3.1 Software Engineering

Tasks should require code changes across multiple files and hidden regression checks:

1. Multi-file bug fix with regression prevention
2. API interface change and caller migration
3. Data model or schema migration
4. Concurrency race-condition fix
5. Cache invalidation and consistency
6. Network retry, timeout, and partial-failure handling
7. Authentication, authorization, and path-security fix
8. Hidden edge-case behavior
9. High-coupling module refactor
10. Performance bottleneck measurement and improvement

### 3.2 Terminal / Agentic Workflow

Tasks should require sequential or conditional tool use:

1. Diagnose and repair a broken build
2. Extract a log pattern and update configuration
3. Transform multiple files and validate the artifact
4. Classify failing tests and fix the selected group
5. Handle process timeout and restart
6. Produce and verify a checksum artifact
7. Diagnose missing or invalid environment configuration
8. Process a large file without loading it entirely
9. Roll back a failed step and rerun safely
10. Run independent checks in parallel and aggregate results

### 3.3 Repository Q&A

Tasks should require reading multiple files and citing evidence:

1. Trace an end-to-end call graph
2. Explain configuration impact on runtime behavior
3. Identify a bug’s root cause and exact fix location
4. Map dependencies and change impact
5. Identify a security weakness and attack path
6. Identify meaningful test-coverage gaps
7. Locate a performance bottleneck and propose measurement
8. Explain data flow and state transitions
9. Describe a failure and recovery path
10. Explain architectural trade-offs and propose a bounded improvement

Q&A verifiers should check required facts, file references, and format. They should reject fabricated APIs, unsupported claims, and answers without repository evidence.

## 4. Fairness controls

- Fix the LLM, model settings, tool schema, timeout, and token budget across systems.
- Use the same prompt and initial workspace snapshot for every system.
- Create a new workspace for every attempt.
- Do not expose hidden tests, verifier implementation, expected answer, or previous transcripts.
- Keep task order and system order fixed for the first comparison; randomization can be added in a later replication.
- Use the real LLM for research results. The deterministic Fake LLM is permitted only for harness and CI smoke tests.
- Separate correctness score from time, cost, token, and turn metrics.
- Record failure reasons and artifacts for qualitative analysis, but never convert them into subjective points.

## 5. Expected discriminating power

- DAG systems should have an opportunity to benefit on tasks requiring dependency tracking, forced verification, partial reruns, recovery, and multi-stage review.
- The general system should have an opportunity to benefit on exploratory Q&A, irregular terminal workflows, and tasks where fixed graph structure adds overhead.
- A task is invalid if it can be solved by a single hard-coded response or if its verifier does not distinguish the required behavior.
- A pilot should reject or revise tasks with all three systems passing all three attempts or all three systems failing all three attempts, unless that ceiling/floor result is an intentional control.

## 6. Acceptance criteria

- 30 task specifications exist: 10 per area.
- Every task has an independent verifier and a hidden expected condition.
- Every task can be materialized into a clean workspace.
- The runner records three independent attempts per task.
- Results include area scores, `Index_system`, time, cost, tokens, turns, and failure artifacts.
- Results explicitly state that this is a custom suite and cannot be compared numerically with the public Artificial Analysis leaderboard.

