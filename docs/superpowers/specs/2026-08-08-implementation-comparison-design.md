# Implementation Comparison App — Design Spec

**Date:** 2026-08-08  
**Status:** Approved; methodology revised to Artificial Analysis–style Index  
**Repo:** `DAG-Experiment` (keep `dagcore` as the core library; sibling consumer app)

---

## 1. Goal

**Research question:** When does a **DAG-based agent system** show advantages over other agent systems, and what implementation insights follow?

| Axis | Setting |
|------|---------|
| Control | **Same LLM** for all systems under test |
| Systems built (3) | (1) BPD-paper DAG → `dag-bpd/` (2) Our DAG → `dag-yonsei/` (3) Claude Code–like multi-agent → `general-agent-system/` |
| Evaluation | [Artificial Analysis Coding Agent Benchmarks](https://artificialanalysis.ai/agents/coding-agents)–style: pass@1, 3 attempts/task, binary verifier; optional time/cost/tokens |
| Output | Per-system scores + strengths/weaknesses (what works well vs poorly; when DAG helps or hurts) |

**Discarded:** subjective 100-point rubric; notes-app / micro-mission lists as primary scoring. Always write **Artificial Analysis** in full (never “AA”).

The three directories are **agent systems we build and compare**, not three unrelated public datasets named like DeepSWE.

---

## 2. Decisions locked in brainstorming

| Decision | Choice |
|----------|--------|
| Relationship to dagcore | Consumer app in same repo; no required `EdgeGraph` dependency |
| Repo strategy | Stay in `DAG-Experiment`; do not relocate `src/dagcore` |
| Folder strategy | Top-level `apps/implementation-comparison/` |
| Methodology | Artificial Analysis Coding Agent Index–style scoring |
| Systems under test | `dag-bpd` (BPD paper), `dag-yonsei` (ours), `general-agent-system` (Claude Code–like multi-agent) |
| LLM | Fixed identical model across the three systems |
| Task outcome | Binary pass/fail via verifier |
| Naming | Full name “Artificial Analysis” only |

---

## 3. Layout

```text
apps/implementation-comparison/
├── README.md
├── implementation-comparison-plan.md
├── dag-bpd/
│   └── runs/<tool>/
├── dag-yonsei/
│   └── runs/<tool>/
├── general-agent-system/
│   └── runs/<tool>/
├── results/
├── src/impl_comparison/
└── tests/
```

| Path | Role |
|------|------|
| `implementation-comparison-plan.md` | Research goal, three systems, Artificial Analysis–style scoring |
| `dag-bpd/`, `dag-yonsei/`, `general-agent-system/` | Agent system implementations + `runs/<variant>/` |
| `results/` | Per-system scores, comparison table, insights |
| `src/impl_comparison/` | Optional aggregation harness |

---

## 4. Scoring (summary)

```text
task_score = mean(attempt_1, attempt_2, attempt_3)   # each in {0,1}
S_system   = mean(task_scores for that system)
```

Compare `S_dag-bpd`, `S_dag-yonsei`, `S_general-agent-system` under the **same LLM** and shared tasks. Record variant = `(system_id, llm, settings)`. Capture qualitative insights: strengths, failure modes, when DAG helps or hurts.

---

## 5. Boundaries

**In scope:** layout, research framing, Artificial Analysis–style methodology, three agent systems.  
**Out of scope (later):** full system implementations, shared task suite/verifiers, automated drivers, cost telemetry if unavailable.

---

## 6. Success criteria (current revision)

- [x] Three systems framed: BPD DAG, Yonsei DAG, Claude Code–like multi-agent
- [x] Same-LLM control + Artificial Analysis–style scoring documented
- [x] Research goal (when DAG helps; implementation insights) in README and plan
- [x] Old 5-dimension rubric removed from plan
