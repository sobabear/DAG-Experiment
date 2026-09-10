# Poison Paperization — Gap-Closing Design (Replication → Condition Ablation)

**Date:** 2026-09-09  
**Status:** Pending user review  
**Paper folder:** `apps/implementation-comparison`  
**Config:** `CLAUDE.superpapers.md`  
**Prior design:** `docs/superpowers/specs/2026-08-30-poison-attribution-bpd-design.md` (repo root)  
**Results narrative:** `results/POISON_RESULTS.md`

## 1. Goal

Close the two highest-priority gaps for a realistic-to-safety submission (arXiv → agent workshop → ACL/EMNLP Findings), in this order:

1. **Replication pipeline** — every number that will appear in the paper is regenerated from raw run artifacts by a fixed-seed script (`\input{}` ready).
2. **Condition ablation** — run `none` / `document` / `agent` on the same 100+100 suite so poison-path claims are not agent-only.

Out of scope for this design (later backlog): multi-model replication, cost–safety Pareto plots beyond token totals already logged, multi-file SE expansion, fair token-matched BPD vs source-rule bake-off.

## 2. Research framing (paper)

**Confirmatory (from prior approved design):** Under strong agent-condition injection, BPD-style attribution is associated with higher detection/recovery than a no-attribution single-loop agent on controlled QnA and code-verifiable tasks.

**Exploratory (must be labeled):** Injection-strength dependence; yonsei source-over-scan A/B.

**Causal language ban:** Do not write “DAG topology causes safety.” Comparative language only, unless a later identification section is approved.

## 3. Phase A — Replication scripts

### 3.1 Data (raw)

Treat existing LLM run trees as immutable raw data:

| Run id | Path | Role |
|--------|------|------|
| poison-100 | `results/poison-100/` | Main agent-condition, 3 systems × 100+100 |
| poison-yonsei-improved | `results/poison-yonsei-improved/` | Exploratory yonsei defense A/B |
| poison-20 | `results/poison-20/` | Weak-injection contrast (exploratory) |
| (new) poison-conditions | `results/poison-conditions/` | Phase B output |

Raw inputs: per-attempt `result.json` (`verifier_result.details`: accurate / propagated / detection_hit / recovered), `score.json`, `metrics.json` / usage fields when present.

Copy or symlink manifests into `data/raw/poison_runs/manifest.md` listing paths, model id, date, condition, n.

### 3.2 Code

Under `code/` (Python):

| Script | Input | Output |
|--------|-------|--------|
| `01_manifest_poison_runs.py` | `results/poison*` | `data/raw/poison_runs/manifest.md` + `data/processed/run_index.json` |
| `02_aggregate_poison_rates.py` | run trees + `score.json` | `data/processed/rates_by_run.csv`, bootstrap CIs (`SEED=20260909`) |
| `03_export_paper_tables.py` | processed rates | `output/tables/tab_main_agent.tex`, `tab_yonsei_ab.tex`, `tab_weak_vs_strong.tex` |
| `04_export_comparison_md.py` | same | optional check that regenerated rates match `comparison.md` within tol |

Verification: `pytest` or a `code/test_replication_smoke.py` that aggregates a tiny fixture tree and checks column presence + CI bounds in [0,1].

### 3.3 Expected tables (Phase A only)

- **Table 1:** poison-100 agent — system × (QnA/Code) × {acc, prop, det, rec} + bootstrap 95% CI  
- **Table 2:** yonsei A/B (exploratory note in caption)  
- **Table 3:** weak (poison-20) vs strong (poison-100) BPD detection (exploratory)

No hardcoded digits in `paper/paper.tex`.

## 4. Phase B — Condition ablation

### 4.1 Design

- **Systems:** `dag-bpd`, `dag-yonsei` (improved source-over-scan code path — document version used), `general-agent-system`
- **Conditions:** `none`, `document`, `agent`
- **Tasks:** full 100 micro-QnA + 100 code (same catalogs as poison-100)
- **Model:** `gpt-5.6-luna` (same as poison-100) unless user changes `CLAUDE.superpapers.md`
- **max_turns:** 20  
- **Attempts:** 1 (match poison-100); note limitation in paper  
- **Output dir:** `results/poison-conditions/`

Scale: 3 systems × 3 conditions × 200 tasks = **1800 runs** (~3× poison-100 wall time). Cost/time mitigation options (choose at plan execute time if user prefers):

- **B1 full (preferred for Findings):** 1800 runs  
- **B2 stratified subsample:** 20 core QnA + 20 core code × 3 × 3 = 360 runs, then claim limited to core stems (weaker)

Default in this design: **B1 full**, with explicit go/no-go before launch.

### 4.2 Hypotheses (pre-registered here; Phase B is confirmatory for path ablation)

H1: Under `none`, propagation ≈ 0 and detection undefined/off for all systems.  
H2: Under `document`, propagation rises vs `none`, with system ranking not assumed a priori.  
H3: Under `agent`, BPD recovery > general recovery on QnA (replicating poison-100).  
H4: Document-condition propagation is not interchangeable with agent-condition propagation (paths differ).

### 4.3 Analysis

Extend `02_aggregate_poison_rates.py` to emit `tab_condition_ablation.tex`: condition × system × task-set rates + CIs.  
Primary contrast: agent vs none (isolation of injection); secondary: document vs agent (path).

## 5. Approaches considered

| Approach | Pros | Cons |
|----------|------|------|
| A. Tables only from existing `comparison.md` hand-copy | Fast | Violates replication discipline |
| **B. Scripted aggregate → TeX, then full condition ablation (recommended)** | Paper-ready, auditable | Ablation expensive |
| C. Ablation on n=20 core only first | Cheap | Weaker Findings claim |

**Recommendation:** B (with B1 ablation after tables exist). User approved priority order 2→1; B1 vs B2 decided at execute go/no-go.

## 6. Robustness (minimal, YAGNI)

- Bootstrap CIs (seed fixed)  
- Weak vs strong injection contrast already collected  
- Condition ablation (Phase B)  
Defer: multi-model, multi-file SE, token-matched defense bake-off

## 7. Submission target (from CLAUDE.superpapers.md)

realistic-to-safety: arXiv anchor → agent workshop → ACL/EMNLP Findings next ARR cycle.

## 8. Success criteria

- [ ] `code/03_export_paper_tables.py` regenerates Table 1–3 bit-stable given frozen raw trees + seed  
- [ ] Smoke test passes without API calls  
- [ ] `results/poison-conditions/comparison.md` exists (or B2 subsample explicitly documented)  
- [ ] `POISON_RESULTS.md` updated with Phase B rates and exploratory labels preserved  
- [ ] Spec conflicts with Index narrative: none (poison stays separate)

## 9. Non-goals

- Rewriting BPD algorithm  
- Merging with research-30 Index  
- Claiming yonsei source-rule equals BPD mechanistically
