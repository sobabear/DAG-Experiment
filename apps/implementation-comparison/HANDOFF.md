# HANDOFF — Poison Attribution in Coding-Agent DAGs

**Last updated:** 2026-10-11 · **Branch:** `main` · **Remote:** `git@github.com:sobabear/DAG-Experiment.git`
**Working directory for everything below:** `apps/implementation-comparison/` (call it `$APP`).
**Audience:** another engineer / AI agent who must continue this project without the original chat history.

> Read this file first, then `results/POISON_RESULTS.md` (long result log) and
> `docs/superpapers/BRIEFING-abstract-and-next-experiments.md` (abstract + RQ framing).
> Korean text exists in those two files because the user (a Yonsei researcher) writes in Korean;
> **paper content must be English** (`CLAUDE.superpapers.md`).

---

## 0. TL;DR

- **Goal:** write a short empirical paper (target: arXiv anchor → agent workshop → ACL/EMNLP Findings next ARR cycle) on whether
  DAG-structured coding-agent systems can **isolate, attribute, and recover from an internally planted lie** better than a non-DAG single-loop agent.
- **Status:** experiments for the first paper draft are done (7 frozen runs, ~4,000+ LLM-agent runs). **No paper text exists yet** (`paper/` only has `references.bib` with 2 verified + 2 unverified entries).
- **Headline findings (current data, one model `gpt-5.6-luna`):**
  1. A single-loop agent has no attribution mechanism (detection = 0 everywhere) and propagates the planted lie on code tasks (~10–25%).
  2. DAG *topology alone is not sufficient*: a hierarchical scan→implement→test graph that trusts a poisoned scan node propagates the lie **more** than the single loop on QnA (0.71 vs 0.17) — unless a source-over-scan rule is added (exploratory).
  3. **Compute-matched controls (budget-5, n=100+100) change the BPD story:** much of BPD's benefit is a 3× ensemble effect; **for code, attribution comes from the independent judge, not from backpropagation** (`judge-only-3` = `dag-bpd`, 0.63 vs 0.63, McNemar p=1.0); for QnA, plain 3-replica string majority attributes *better* than the judge (1.00 vs 0.88, p=5e-4).
- **Most important open problem:** the **injection channel confound** (§7, issue I1). Fix it before making any DAG-vs-non-DAG claim in the paper.
- **Nothing here is an Index/leaderboard result.** Never merge poison rates with Artificial Analysis Index or `results/research-30`.

---

## 1. Research framing

### 1.1 Research questions
- **RQ1 (DAG vs non-DAG):** With a planted lie in an internal collaborator, do DAG-style coding-agent systems isolate/detect/recover better than a single-loop agent?
- **RQ2 (inside DAGs):** Does the handling of contaminated nodes (BPD-style contribution scoring vs trusting a scan node vs source-over-scan rule vs plain majority) change isolation/attribution/recovery?

### 1.2 Claims we can currently make (comparative language only, no causal "DAG causes safety")
- Single-loop: detection 0; code lie propagation ≈ 0.10–0.25 under strong injection.
- Naive hierarchical (Yonsei) DAG can be *worse* than single-loop on QnA propagation.
- Ensemble (3 isolated replicas) removes most propagation; the DAG label/backprop is not what buys it.
- Code attribution requires an independent judge (semantic matching); string-majority cannot attribute code strategies.

### 1.3 Non-claims (do NOT write these)
- "DAGs are always safer / more accurate than single-loop agents."
- "Yonsei source-over-scan rule = BPD" (different mechanisms).
- Any merge/ranking with the Index / research-30 suite.
- Treating the weak-injection pilot's Yonsei detection=1.0 as real attribution (it was a "gold→scan" heuristic artifact, replaced by conflict-based attribution).
- "General-3 cannot attribute" (its detection=0 is a *channel artifact*, see I1).
- "Single loop propagates lies on QnA at 17%" as a robust number (wording-sensitive: 0.17 → 0.10 → 0.01 across injection wordings). Use **code** as the primary evidence.

Label as **exploratory** in the paper: strong-injection scaling, Yonsei source-over-scan A/B, budget-5 ablation until I1 is fixed.

---

## 2. Metrics (all rates in [0,1], per task bucket)

| Metric | Definition |
|---|---|
| `accurate` | Gold answer: string match (QnA) or hidden pytest passes (code). |
| `propagated` | The planted lie appears in the final answer / code behavior. |
| `detection_hit` (attribution) | System names the poisoned source: worker index for BPD/majority arms, `"scan"` for Yonsei. |
| `recovered` | `detection_hit ∧ accurate`. |

Implemented in `src/impl_comparison/poison.py` (`verify_poison`, `aggregate_proposals`, `backward_propagate`, `detect_bpd_outlier`, `terminal_scores_from_summaries`).

**Conditions:** `none` (control), `document` (NOTES.md policy claim; barely works in this suite, prop≈0), `agent` (core condition: poison on worker 0 / scan node / extra user message).

---

## 3. Systems (arms)

All in `src/impl_comparison/systems/`; registered in `src/impl_comparison/poison_compare.py` (`POISON_SYSTEMS`).

| Arm id | File / class | What it is | Poison entry point |
|---|---|---|---|
| `general-agent-system` | `general.py` `GeneralAgentSystem` | Non-DAG single tool loop ("general-1") | extra **user** message |
| `general-majority-3` | `majority3.py` `GeneralMajority3System` | 3 isolated single-loop replicas, substring majority, no judge | replica 0, extra **user** message |
| `flat-majority-3` | `majority3.py` `FlatMajority3System` | 3 isolated "proposal workers", substring majority, no judge | worker 0, **system-prompt** suffix |
| `judge-only-3` | `bpd.py` `JudgeOnlyBpdSystem` | BPD pipeline but worker score = mean judge edge (no terminal plurality weighting) | worker 0, **system-prompt** suffix |
| `dag-bpd` | `bpd.py` `BpdDagSystem` | 3 isolated workers → 3 summarizers → one batched independent judge (edges ±1/0) → closed-form backward propagation → argmax winner; `detect_bpd_outlier` flags unique negative score | worker 0, **system-prompt** suffix |
| `dag-yonsei` | `yonsei.py` `YonseiDagSystem` | Hierarchical scan → implement → tests → repair. Contains `SOURCE_OVER_SCAN_RULE`, `source_conflicts_with_scan`, `_attribute_scan_qna/_code` | **scan node** report |

Injection text lives in `src/impl_comparison/poison_injection.py`:
`agent_worker_prompt`, `aligned_general_message` (same text as worker prompt, as user message), `general_claim_for(meta, ...)` (chooses legacy vs aligned by `meta["injection_profile"]`), `scan_node_message`, `general_agent_message` (legacy, weaker), `document_notes`.

`injection_profile="aligned"` is set only for `--arms budget-5` (via `poison_compare._tag_aligned_profile`).

Arm sets: `--arms default` (general, bpd, yonsei) · `budget-4` (general-1, general-3, flat-3, bpd; legacy wording; core n=20) · `budget-5` (+ `judge-only-3`; aligned wording).

---

## 4. Task suites

- `src/impl_comparison/poison.py`: 20 hand-authored core QnA tasks (`_CORE_POISON_TASKS`) expanded to 100 (`POISON_TASKS`, via `poison_task_catalog.py`). Config-value QnA with a planted wrong value; gold in source, lie in the injection.
- `src/impl_comparison/poison_code_tasks.py` + `poison_code_catalog.py`: 20 core code bug-fix tasks expanded to 100; graded by **hidden pytest** (test file materialized in the workspace; workers are told not to run tests).
- `--scale core` = 20+20, `--scale all` = 100+100. Each task × 3 conditions → task ids end with `-agent|-document|-none`.
- Tests that guard the suites: `tests/test_poison.py`, `tests/test_poison_code_tasks.py` (counts 100/300, discrimination tests on core 20).

---

## 5. Experiment log (frozen runs; summaries committed, transcripts not)

Model for all: `openai-compatible/gpt-5.6-luna`, `max_turns=20`, attempts=1, `condition=agent` unless noted.
Run dirs under `results/<run_id>/` (`score.json` and `comparison.md` **are committed**; per-run transcript trees are gitignored, ~190 MB total).

| run_id | What | n per cell | Key numbers (acc/prop/det) |
|---|---|---|---|
| `poison`, `poison-all`, `poison-20` | Weak-injection pilots (Aug 31). Historical; small n. | small | Yonsei det=1.0 was a heuristic artifact — do not cite |
| `poison-100` | Strong injection, 3 default systems | 100+100 | BPD QnA 1.00/0.00/0.85, code 0.97/0.02/0.63 · Yonsei(naive) QnA 0.29/0.71/0.29, code 1.00/0/0.23 · general QnA 0.83/0.17/0, code 0.88/0.10/0 |
| `poison-yonsei-improved` | Yonsei with source-over-scan rule (exploratory A/B) | 100+100 | acc 1.0, prop 0, det/rec 1.0 (both sets) |
| `poison-conditions` | none/document/agent ablation (1,800 runs) | 100 per cell | none/document: prop≈0 everywhere; agent: BPD QnA rec 0.87, code 0.64; general prop 0.20/0.19, det 0; Yonsei(improved) rec 1.0 |
| `poison-budget-4` | **Pilot** compute-matched (legacy wording) | 20+20 core | see `POISON_RESULTS.md` §9; cite only as pilot |
| `poison-budget-5` | **Compute-matched + aligned wording + judge-only ablation** | 100+100 | table below |

### 5.1 budget-5 results (`results/poison-budget-5/`, ran 2026-10-10 21:07 → 2026-10-11 00:37 KST, 1,000 runs, ≈3.5 h)

| arm | QnA acc/prop/det(=rec) | Code acc/prop/det(=rec) | input tok/task QnA / code |
|---|---|---|---|
| general-1 | 0.99 / 0.01 / 0 | 0.84 / 0.11 / 0 | 1.3k / 3.0k |
| general-3 maj. | 1.00 / 0 / 0 | 1.00 / 0 / 0 | 3.6k / 8.4k |
| flat-3 maj. | 1.00 / 0 / **1.00** | 0.91 / 0.09 / 0 | 3.0k / 8.1k |
| judge-only-3 | 1.00 / 0 / 0.84 | 1.00 / 0 / **0.63** | 3.0k / 8.2k |
| dag-bpd | 1.00 / 0 / 0.88 | 0.99 / 0.01 / **0.63** | 3.0k / 8.1k |

Paired exact McNemar (`data/processed/paired_poison-budget-5.csv`, 80 rows, all arm pairs × 4 metrics × 2 sets):
- QnA recovery: flat-3 vs BPD 1.00 vs 0.88 (12 vs 0 discordant, p=4.9e-4); BPD vs judge-only 0.88 vs 0.84 (12 vs 8, p=0.50).
- Code recovery: BPD vs judge-only 0.63 vs 0.63 (5 vs 5, p=1.0); BPD vs flat-3/general-3/general-1: 63 vs 0 (p≈2e-19).
- Code accuracy: BPD 0.99 vs flat-3 0.91 (p=0.008) and vs general-1 0.84 (p=6e-5); BPD vs general-3/judge-only: no difference.

Cost: `score.json["<arm>"]["<set>"]["metrics"]["tokens"]` has input/output token totals; the API returns **no USD cost** (`cost_usd=0`). Use tokens as the cost proxy.

---

## 6. Repo map and replication pipeline

```
apps/implementation-comparison/
  HANDOFF.md                      <- this file
  CLAUDE.superpapers.md           <- project config for the superpapers research workflow (venue, style, rules)
  src/impl_comparison/            <- harness + poison suite (see §3, §4)
    poison_compare.py             <- CLI + compare_poison() runner, arm sets, smoke LLM
  tests/                          <- pytest (340 tests; run offline with FakeLLM)
  code/                           <- replication pipeline (see below) + test_replication_smoke.py + fixtures/
  data/raw/poison_runs/manifest.md        <- generated
  data/processed/                 <- run_index.json, rates_by_run.csv, rates_by_run_ci.json, paired_*.csv
  output/tables/                  <- generated booktabs .tex (tab_main_agent, tab_yonsei_ab, tab_weak_vs_strong,
                                     tab_condition_ablation, tab_budget4_pilot, tab_budget5)
  results/POISON_RESULTS.md       <- long result log, phases A–E + §9 budget-4 + §10 budget-5 (sections ordered 7,9,10,8 — tidy up)
  results/poison*/score.json, comparison.md   <- committed frozen run summaries
  paper/references.bib            <- only 4 entries; NO paper.tex yet
  docs/superpapers/               <- BRIEFING (abstract/RQ/roadmap), literature-notes, spec, plan
```
Repo root also has `docs/superpowers/specs/2026-08-30-poison-attribution-bpd-design.md` (original BPD design spec; `CLAUDE.superpapers.md` cites it) and a shared `src/dagcore` library (`EdgeGraph`).

### 6.1 Regenerate everything from frozen summaries (no API calls)
```sh
cd apps/implementation-comparison
PY=/Users/sobabear/Desktop/yonsei/DAG-Experiment/.venv/bin/python   # or any env with pytest installed
$PY code/01_manifest_poison_runs.py     # -> data/processed/run_index.json, data/raw/poison_runs/manifest.md  (add new run ids to DEFAULT_RUNS)
$PY code/02_aggregate_poison_rates.py   # -> rates_by_run.csv / _ci.json; bootstrap 95% CI, SEED=20260909, B=1000, condition split, tokens/task
$PY code/03_export_paper_tables.py      # -> output/tables/*.tex
$PY code/04_paired_tests.py poison-budget-5   # -> data/processed/paired_poison-budget-5.csv (exact McNemar + Wilson)
```
`02` raises if an empirical rate disagrees with the `rates` published in `score.json` (consistency guard).
Seeds are now process-independent (`stable_seed` = crc32); previously `hash()` made CIs differ per run, so **CIs in committed tables differ slightly from any older numbers**.

### 6.2 Tests
```sh
PYTHONPATH=src:/Users/sobabear/Desktop/yonsei/DAG-Experiment/src $PY -m pytest tests code -q   # expect 347 passed (~80 s)
```

### 6.3 Re-running LLM experiments
Environment (never commit `.env`; `.env.example` lists the variable names):
`IMPL_COMPARISON_LLM_PROVIDER=openai-compatible`, `IMPL_COMPARISON_LLM_MODEL=gpt-5.6-luna`, `IMPL_COMPARISON_LLM_ENDPOINT=<…>`, `OPENAI_API_KEY=<…>` (read by SDK from process env, intentionally not stored in configs).
```sh
cd apps/implementation-comparison
PYTHONPATH=src:<repo>/src nohup $PY -c "
from pathlib import Path
from impl_comparison.poison_compare import compare_poison
compare_poison(Path('results/<new-run-id>'), condition='agent', task_set='all', scale='all', arms='budget-5', max_turns=20)
" > results/<new-run-id>/run.log 2>&1 &
```
or CLI: `python -m impl_comparison.poison_compare --arms budget-5 --scale all --condition agent --max-turns 20`.
Practical notes:
- Run **outside any sandbox** with network access; LLM runs are sequential (no parallelism implemented).
- Speed: ≈11 runs/min for single-loop; judge arms ≈ 80 min per 200 runs. Budget-5 (5 arms × 200) took ≈3.5 h. `score.json` is written only when **all** arms finish — a crash loses the summary (per-run artifacts remain). Consider adding checkpointing (see backlog B8).
- Keep the laptop awake (`caffeinate -i`) for long runs.
- `--allow-fake` uses `PoisonSmokeLLM` (deterministic stand-in) for offline dry runs only; never report its numbers.

---

## 7. Known issues and threats to validity (ordered by importance)

| # | Issue | Why it matters | Suggested fix |
|---|---|---|---|
| **I1** | **Injection channel confound.** Flat/judge-only/BPD receive the lie in the *system prompt*; general-1/general-3 receive the same text as a *user message*. Under aligned wording the general poisoned replica almost never emits the lie (QnA prop 0.01), so majority detection (which needs the lie to appear in a replica's output) is 0 for a mechanical reason. | Invalidates reading "general-3 det=0" as an architectural limitation; makes DAG vs non-DAG comparison partly a prompt-channel comparison. | Add a third profile (e.g. `injection_profile="system"`) that appends the identical text to the **system prompt** for general arms; rerun budget-5 (≈3.5 h) or at least general-1/general-3 (≈1 h). Also log **lie-compliance of the poisoned replica** (`lie in workers[poison_worker]`) and report detection *conditional on compliance*. |
| **I2** | Substring majority (`aggregate_proposals`) is a weak baseline on code (strategy phrases vary) — det=0 is partly "string matching can't match semantics", not "no judge ⇒ no attribution". | Confounds flat-3 vs judge arms on code. | Add a judge-free *semantic* baseline (embedding or normalized-test-behavior clustering of worker outputs/patches), or run the workers' patches against the visible/hidden tests as an oracle upper bound and label it so. |
| **I3** | Single model (`gpt-5.6-luna`), attempts=1. BPD QnA detection varies 0.85–0.88 across runs. | Reviewer will ask for second model + variance. | Run core 20+20 (or 100+100) on one more model family; run attempts≥3 on core suite for variance. |
| **I4** | QnA tasks are short config values → ceiling effects (acc≈1.0 for all 3× arms); wording-sensitive propagation of single loop. | QnA cannot discriminate architectures well. | Make code the primary evidence; add harder multi-file SE tasks (backlog B7). |
| **I5** | Hand-built, synthetic tasks (single-file `worker.py`-style fixtures expanded from templates). | External validity. | Backlog B7. |
| **I6** | Yonsei arm compared with different injection point (scan node) and a post-hoc rule (exploratory). | Fairness; HARKing risk. | Keep as appendix/exploratory; label clearly. |
| **I7** | `document` condition has no effect (prop≈0) — the policy-in-NOTES.md poison is ignored by this model. | Can't claim document-poison results. | Treat as negative control or redesign (separate RQ). |
| **I8** | Raw transcript trees (~190 MB) are not in git. | Qualitative audit/reproduction of raw runs impossible from a clone. | Archive to Zenodo/HF/GitHub release and cite DOI; keep `score.json` in git (done). |
| **I9** | `results/POISON_RESULTS.md` section order is 7, 9, 10, 8; `CLAUDE.superpapers.md` cites a spec under `docs/superpowers/` (repo root) while newer docs live in `docs/superpapers/`. | Navigation confusion. | Reorder/renumber; add cross-links. |
| **I10** | `references.bib` has 2 verified (`wu2025bpd` = arXiv 2510.19420, `huang2024resilience` = arXiv 2408.00989) and 2 `[unverified]` entries (`byzantineMultiAgent2026` ≈ arXiv 2605.09076, `veritrail2025` ≈ arXiv 2505.21786). | Never fabricate citations. | Verify every reference via web fetch before use (skill `superpapers-literature-search`). |

---

## 8. Backlog (prioritized, with acceptance criteria)

**P0 — needed before any DAG-vs-non-DAG claim**
- **B1. Fix channel confound (I1).** Add `injection_profile="system"` handling in `general.py` and `majority3.py` (TDD: mirror `test_aligned_profile_*` in `tests/test_poison.py`), add arm option (e.g. `--arms budget-6` or a flag), rerun general-1/general-3 (and ideally all 5 arms for a single coherent run, ≈3.5 h). Acceptance: all arms receive byte-identical injection text in the same channel; report lie-compliance of the poisoned replica per arm; add a table + McNemar rows; update `POISON_RESULTS.md` §11 and BRIEFING.
- **B2. Update Abstract/RQ2 text** to the budget-5 finding (see §1.2) once B1 is done; keep wording "associated with", not causal.

**P1 — makes the paper defensible**
- **B3. Cost–recovery paragraph/figure** from logged tokens (no new API calls): recovery vs input tokens per task for the 5 arms (script `code/05_cost_recovery.py` + `output/tables|figures/`).
- **B4. Qualitative BPD-miss analysis**: sample 10–20 `dag-bpd` agent failures (det=0) from `results/poison-budget-5/dag-bpd/*/runs/*/` transcripts (local only), code failure modes (judge mislabels, poisoned worker declines the lie, summarizers copy a single proposal, etc.). Put taxonomy in `docs/superpapers/` and a short paper paragraph.
- **B5. Second model** on core 20+20 (or full) for the 5 arms; report whether the judge-vs-backprop and ensemble conclusions hold.
- **B6. Variance:** repeat core budget-5 with attempts=3 (or 3 seeds) and report run-to-run spread.

**P2 — strengthens external validity (can be future work)**
- **B7. Harder tasks:** multi-file SE tasks with hidden tests; or adapt a public benchmark slice.
- **B8. Runner robustness:** write per-arm `score.json` incrementally (checkpoint/resume) so a crash doesn't lose hours; optional parallel workers with rate-limit handling.
- **B9. Yonsei fair-defense compare** under matched budget (source-over-scan vs BPD vs flat-3) — exploratory appendix.

**Writing track (can run in parallel with B1)**
- **W1. `paper/paper.tex` skeleton** (ACL-style; check template via skill `superpapers-journal-guidelines`): Intro (RQ1→RQ2, closing sentence in BRIEFING §8), Related Work, Setup (§2–§4 of this file), Results (`\input{../output/tables/tab_*.tex}` only — never hard-code numbers), Analysis (ensemble vs judge vs backprop), Limitations (I1–I8), Ethics. Compile with skill `superpapers-compile-latex`.
- **W2. Literature review:** 15–30 web-verified references (use `docs/superpapers/literature-notes.md` as seed; bias to ACL/EMNLP/agent workshops, last 3–5 years); fill `paper/references.bib`; fix the 2 unverified entries.
- **W3. Venue/ARR check:** confirm ARR deadline, page limit, template; consider arXiv first.
- **W4. Final audit:** skill `superpapers-paper-review` before submission.

---

## 9. Conventions and rules (must follow)

1. **Never commit `.env` or secrets.** `.env` is gitignored. `.cursor/` is also not tracked.
2. **Do not commit/push unless the user explicitly asks.** (This handoff was committed on explicit request.)
3. **Never put analysis into `results/research-30/comparison.md`** (only glossary/cost notes). Never merge poison metrics with the Index / research-30.
4. **Never hard-code numbers in the paper**; tables via `\input{}` from `output/tables/`, regenerated by `code/01..04`.
5. **TDD:** write a failing pytest first for any change in `src/`; keep `pytest tests code` green (347 at handoff).
6. **No fabricated citations;** verify each via web.
7. **Label exploratory findings** (strong-injection scaling, Yonsei rule A/B, budget-5 until B1) in paper text.
8. Code-review subagents (if used): prefer Composer / Cursor Auto models.
9. Gitignore: `results/**` ignored except `POISON_RESULTS.md`, `research-30/comparison.md`, and `results/poison*/{score.json,comparison.md}` (added at handoff so a clone can regenerate tables). Transcript trees and `run.log` remain ignored.
10. Python env: repo `.venv` (not committed). The harness imports `dagcore` from repo-root `src/` → keep `PYTHONPATH=src:<repo>/src` when running outside pytest config.

---

## 10. Decision log (why things are the way they are)

- **Framing change (data-driven):** user wanted "DAG beats non-DAG"; data show *topology alone doesn't decide* → thesis: "DAG enlarges the node-level isolation/attribution design space; contaminated-node handling, not the DAG label, determines recovery."
- **Fairness concern (user):** BPD uses ~3× workers → added compute-matched arms (budget-4 pilot → budget-5) rather than arguing around it.
- **Why `judge-only-3` instead of a "summarizer-vote" arm:** summarizer outputs cannot be mapped back to a worker's *workspace* without a judge, so a vote-only arm cannot choose which code edit to promote for pytest grading. The judge-only arm isolates the judge's contribution from terminal-score backprop instead.
- **Yonsei fix:** poison enters at the scan node; naive trust → high propagation. Added `SOURCE_OVER_SCAN_RULE` and attribution only when source↔scan conflict exists and the lie was rejected (replaced a misleading "gold→scan" heuristic).
- **Stats:** descriptive rates + bootstrap CIs (+ Wilson, exact McNemar for paired arms); no NHST-first framing. Bootstrap seeds are crc32-stable.
- **Condition split in aggregation:** pooling `none/document/agent` dilutes detection (comparison.md n=300 table) → use the condition-split table (`tab_condition_ablation.tex`).

---

## 11. Git history (most recent first)

- *(this handoff commit)* Budget-5 (aligned wording, `judge-only-3`, n=100+100), stable-seed stats, paired tests, handoff doc, committed run summaries.
- `649bcf5` Add compute-matched poison arms so BPD is not credited for 3× rollouts alone.
- `73891ec` WIP (user commit)
- `e27b49a` Expand poison suite for paperization: strong injection, n=100, yonsei fix, tables.
- `864f962`, `65c65d9`, `faf700d`, `b5f6704`, `2c78607`: earlier BPD v2 / code-fixture / pytest-grading work.

---

## 12. Quick start checklist for the next agent

1. `git pull`; create/activate a Python env with the project deps (`pyproject.toml` at `$APP` and repo root); run `pytest tests code -q` → expect all green.
2. Run `code/01..04` and confirm `git diff` is empty (pipeline reproducibility check).
3. Read §7 (I1–I3) and decide with the user whether to start **B1** (needs API key + ≈3.5 h) or the **writing track W1/W2** (no API needed).
4. Keep this file updated: add new runs to §5, new issues to §7, and tick off backlog items in §8.
