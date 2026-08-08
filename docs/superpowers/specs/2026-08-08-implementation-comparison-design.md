# Implementation Comparison App — Design Spec

**Date:** 2026-08-08  
**Status:** Approved; docs aligned to Artificial Analysis **Coding Agent** protocol (not LLM model Index)  
**Repo:** `DAG-Experiment` (keep `dagcore`; sibling app under `apps/`)

---

## 1. Goal

**Research question:** When does a **DAG-based agent system** show advantages over other agent systems, and what implementation insights follow?

| Axis | Setting |
|------|---------|
| Control | **Same LLM** for all systems |
| Systems (3) | `dag-bpd` (BPD paper) · `dag-yonsei` (ours) · `general-agent-system` (Claude Code–like) |
| Evaluation source | [Coding Agents](https://artificialanalysis.ai/agents/coding-agents) protocol only |
| Explicit non-goals | [Methodology](https://artificialanalysis.ai/methodology) Language Model Intelligence Index, TTFT, output tok/s as primary scores |
| Task suite (default) | Artificial Analysis Index components: DeepSWE · Terminal-Bench v2 · SWE-Atlas-QnA |
| Fallback suite | Custom SE / Terminal / Q&A categories with same scoring formula if public benches unavailable |
| Output | Per-system `Index_system` + per-benchmark breakdown + time/cost/tokens/turns + qualitative insights |

Always write **Artificial Analysis** in full. Do not claim “identical to Artificial Analysis leaderboard numbers” unless the same pinned public suite and runners are used.

---

## 2. Decisions

| Decision | Choice |
|----------|--------|
| dagcore | Unchanged sibling library |
| App path | `apps/implementation-comparison/` |
| What we compare | Three **systems we build**, not product brand names alone |
| What we borrow from Artificial Analysis | Coding Agent **scoring protocol** + default **three public benches** as shared suite |
| What we do not borrow | LLM model/endpoint methodology as agent primary metrics |
| Scoring | Binary verifier; pass@1 over 3 attempts; equal-weight Index over 3 benches |
| Naming | Full name “Artificial Analysis” only |

---

## 3. Layout

```text
apps/implementation-comparison/
├── README.md
├── implementation-comparison-plan.md
├── dag-bpd/runs/<variant>/
├── dag-yonsei/runs/<variant>/
├── general-agent-system/runs/<variant>/
├── tasks/                 # suite pin / runner notes
├── results/
├── src/impl_comparison/
└── tests/
```

---

## 4. Scoring (summary)

```text
task_score     = mean(attempt_1..3) ∈ [0,1]
S_bench        = mean(task_scores in bench)
Index_system   = mean(S_DeepSWE, S_Terminal-Bench_v2, S_SWE-Atlas-QnA)
```

Compare three systems’ Index and breakdowns under the same LLM and suite.

---

## 5. Boundaries

**In scope:** research framing, protocol documentation, folder layout, suite decision (default + fallback).  
**Out of scope (later):** implementing the three agents; wiring public bench runners; cost telemetry if unavailable.

---

## 6. Success criteria (doc revision)

- [x] Coding Agents vs LLM methodology distinction documented
- [x] Table: Artificial Analysis Index axes vs this experiment’s axes
- [x] Task suite default = public 3 benches; fallback = custom 3 categories
- [x] Index_system = equal-weight three benches; systems are rows under comparison
- [x] README and plan agree
