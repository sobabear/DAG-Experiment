# Poison Paperization Gap-Closing — Implementation Plan

> **For agentic workers:** Execute task-by-task. Prefer inline execution for the replication pipeline (shared files). Ask before launching the 1800-run LLM ablation.

**Goal:** Regenerable paper tables from frozen poison runs (Phase A), then full `none`/`document`/`agent` ablation (Phase B, B1).

**Architecture:** Raw LLM artifacts under `results/poison*` → `code/0x_*.py` → `data/processed/` → `output/tables/*.tex`. Ablation writes `results/poison-conditions/` then reuses the same aggregators.

**Tech stack:** Python 3, stdlib + existing pytest, bootstrap CIs with `SEED=20260909`.

**Spec:** `docs/superpapers/specs/2026-09-09-poison-paperization-gaps-design.md`  
**Config:** `CLAUDE.superpapers.md`

**Phase exclusions / deferrals:**
- **Literature:** one bibliography-prep task only (gap notes already in design spec §1.1 of 2026-08-30); full 15–30 ref curation deferred until Writing starts — recorded as Task L1 placeholder commitment below with concrete outputs.
- **Writing / Submission:** scaffold only after Phase B tables exist (Tasks W1–S1 listed; do not start until user says write the paper).

---

## Task L1: Seed literature notes and bib stub

- **Phase:** Literature  
- **Inputs:** `docs/superpowers/specs/2026-08-30-poison-attribution-bpd-design.md` §1.1; `CLAUDE.superpapers.md` outlets  
- **Outputs:** `docs/superpapers/literature-notes.md` (state of field + positioning bullets); `paper/references.bib` stub with BPD + resilience arXiv entries marked pending DOI verify  
- **Script:** manual write in this task (no collection script)  
- **Verification:** both files non-empty; each bib entry has a URL or `[unverified]` tag  
- **Skills involved:** `academic-baseline`, `literature-search` (gap-check mode only — full mode later), `citation-management`  
- **Commit message:** `docs(poison): seed literature notes and bib stub for paperization`  
- **Depends on:** none  

---

## Task C1: Manifest frozen poison runs

- **Phase:** Collection  
- **Inputs:** `results/poison-100/`, `results/poison-yonsei-improved/`, `results/poison-20/`, `results/poison-all/`, `results/poison/`  
- **Outputs:** `data/raw/poison_runs/manifest.md`, `data/processed/run_index.json`  
- **Script:** `code/01_manifest_poison_runs.py`  
- **Verification:** `python code/01_manifest_poison_runs.py` exits 0; `run_index.json` lists ≥3 runs with `score_json` paths that exist  
- **Skills involved:** `academic-baseline`, `replication-driven-research`, `data-collection`  
- **Commit message:** `feat(poison): manifest frozen poison run trees`  
- **Depends on:** none  

---

## Task P1: Aggregate rates with bootstrap CIs

- **Phase:** Preparation + Exploratory  
- **Inputs:** `data/processed/run_index.json`, each run `score.json` (system → micro_qna/code → tasks[].details)  
- **Outputs:** `data/processed/rates_by_run.csv`, `data/processed/rates_by_run_ci.json`  
- **Script:** `code/02_aggregate_poison_rates.py` (`SEED=20260909`, B=1000 bootstrap over tasks)  
- **Verification:** CSV has columns `run_id,system,task_set,n,accurate,propagated,detection_hit,recovered` plus `*_ci_low,*_ci_high`; rates for poison-100/dag-bpd/micro_qna match score.json within 1e-9  
- **Skills involved:** `academic-baseline`, `replication-driven-research`, `statistical-modeling`  
- **Commit message:** `feat(poison): aggregate poison rates with bootstrap CIs`  
- **Depends on:** C1  

---

## Task M1: Export main paper tables (TeX)

- **Phase:** Main Analysis  
- **Inputs:** `data/processed/rates_by_run.csv`, `rates_by_run_ci.json`  
- **Outputs:**  
  - `output/tables/tab_main_agent.tex` (poison-100)  
  - `output/tables/tab_yonsei_ab.tex` (exploratory caption)  
  - `output/tables/tab_weak_vs_strong.tex` (exploratory)  
- **Script:** `code/03_export_paper_tables.py`  
- **Verification:** three `.tex` files non-empty; contain `booktabs`/`tabular`; no hardcoded path to Index; `python code/03_export_paper_tables.py` idempotent  
- **Skills involved:** `academic-baseline`, `replication-driven-research`, `tables-and-figures`  
- **Commit message:** `feat(poison): export regenerable poison paper tables`  
- **Depends on:** P1  

---

## Task M2: Replication smoke test

- **Phase:** Main Analysis  
- **Inputs:** fixture mini `score.json` under `code/fixtures/mini_poison_score.json`  
- **Outputs:** `code/test_replication_smoke.py` passing  
- **Script:** `code/test_replication_smoke.py` (pytest)  
- **Verification:** `cd apps/implementation-comparison && PYTHONPATH=src:code python -m pytest code/test_replication_smoke.py -q` exits 0  
- **Skills involved:** `academic-baseline`, `replication-driven-research`  
- **Commit message:** `test(poison): smoke test for rate aggregation pipeline`  
- **Depends on:** P1, M1  

---

## Task R1: Launch condition ablation B1 (LLM)

- **Phase:** Robustness (path ablation)  
- **Inputs:** improved `YonseiDagSystem`, env LLM config, task catalogs n=100+100  
- **Outputs:** `results/poison-conditions/{comparison.md,score.json,...}`  
- **Script:** inline driver calling `compare_poison(..., condition='all', task_set='all', max_turns=20)` → `results/poison-conditions`  
- **Verification:** `score.json` present; each of 3 systems has micro_qna and code with `n=300` (100×3 conditions) or documented equivalent; comparison.md has three condition slices or flat rates with condition in task ids  
- **Skills involved:** `academic-baseline`, `replication-driven-research`, `data-collection`  
- **Commit message:** `data(poison): add none/document/agent condition ablation runs`  
- **Depends on:** M2  
- **Gate:** print estimated cost/time; user already approved B1 — proceed unless API key missing  

---

## Task R2: Export condition ablation table

- **Phase:** Robustness  
- **Inputs:** `results/poison-conditions/score.json`  
- **Outputs:** `output/tables/tab_condition_ablation.tex`; update `data/processed/*` via re-run of 01–03 with new run registered  
- **Script:** re-run `01`→`03` after adding poison-conditions to manifest defaults  
- **Verification:** TeX file exists; includes none/document/agent rows  
- **Skills involved:** `academic-baseline`, `tables-and-figures`, `statistical-modeling`  
- **Commit message:** `feat(poison): export condition ablation table`  
- **Depends on:** R1  

---

## Task R3: Update POISON_RESULTS.md with Phase B

- **Phase:** Robustness  
- **Inputs:** `tab_condition_ablation.tex` / score.json  
- **Outputs:** updated `results/POISON_RESULTS.md` Phase E section  
- **Script:** edit markdown  
- **Verification:** file mentions poison-conditions and none/document/agent  
- **Skills involved:** `academic-baseline`, `replication-driven-research`  
- **Commit message:** `docs(poison): document condition ablation results`  
- **Depends on:** R2  

---

## Task W1–S1 (deferred — do not execute in this session unless asked)

- **W1 Writing:** draft `paper/paper.tex` with `\input{../output/tables/...}`; Conceptual Framework + Discussion required. Skills: `paper-writing`, `compile-latex`, `academic-baseline`.  
- **S1 Submission:** `journal-guidelines` + `paper-review` audit-and-remediate until go.  

---

## Execution order

L1 → C1 → P1 → M1 → M2  ⇒ **Phase A complete**  
→ R1 → R2 → R3  ⇒ **Phase B complete**  
→ (later) W1 → S1

## Self-review

- Spec Phase A/B mapped: yes  
- Literature present (L1); full review deferred with reason  
- Writing/Submission deferred with explicit tasks  
- No placeholders in executable tasks  
- B1 ablation gated by prior user approval (option 1)
