# HANDOFF — Poison Attribution in Coding-Agent DAGs

**Last updated:** 2026-10-20 (budget-7 is the paper's main run; budget-8 is the second model; offline AST and promotion analyses are in) · **Branch:** `main` · **Remote:** `git@github.com:sobabear/DAG-Experiment.git`
**Working directory for everything below:** `apps/implementation-comparison/` (call it `$APP`).
**Audience:** another engineer / AI agent who must continue this project without the original chat history.

> Read this file first, then `results/EXPERIMENT_SUMMARY.md` (English one-stop summary) and
> `paper/paper.tex` (the manuscript). `results/POISON_RESULTS.md` sections 1–11 and the Korean
> parts of the BRIEFING are the earlier log; they stop at budget-6. **Paper prose is English.**
> New markdown is English.

---

## 0. TL;DR

- **Goal:** write a short empirical paper (target: arXiv anchor → agent workshop → ACL/EMNLP Findings next ARR cycle) on whether
  DAG-structured coding-agent systems can **isolate, attribute, and recover from an internally planted lie** better than a non-DAG single-loop agent.
- **Status (2026-10-20):** the paper's main run is **`poison-budget-7`** (`gpt-5.6-luna`, poisoned replica index balanced, 180 s task limit, 0 timeouts). **`poison-budget-8`** repeats that design on `gpt-6-luna`. `poison-budget-6-retried` is the earlier replica-0-only run (appendix). Manuscript: `paper/paper.tex`, ACL review mode, 14 pages with references and appendix, content within 8 pages. Every prose number is a generated macro. Remaining `\todo{}`: AI-use disclosure / Responsible NLP checklist, and an anonymous repository plus a raw-run archive.
- **Headline findings (do not replace these with budget-5 or budget-6 numbers):**
  1. With the same claim in the system prompt, the single loop repeats the lie in every QnA run (acc 0.00). Three replicas remove that on QnA (acc 1.00).
  2. On code, string-majority accuracy depends on which replica is poisoned (flat-3: 0.88 / 0.91 / 0.36 for replica 0 / 1 / 2) because a failed string vote promotes the last replica. An AST-majority promotion on the saved workspaces reaches 0.98; a uniform draw stays at 0.79.
  3. Naming the source on code needs a comparison that reads the replicas. A judge-free normalized-source diff matches the judge (about 0.60 vs 0.63). Backprop adds nothing over judge-only (p = 0.48). On QnA, string majority beats the judge.
  4. `gpt-6-luna` reproduces the code pattern. Its QnA detection collapses to about 0.10–0.12 for the proposal-worker arms because those replicas open the file and answer with the source value. That is a prompt-by-model interaction, not "the model is safer."
- **Withdrawn:** "Yonsei propagates more than the single loop," "the single loop is robust," "general-3 cannot attribute" (budget-5 channel artifact), and "replication alone explains code isolation" (budget-6, replica 0 only).
- **Submission readiness:** not ready to post yet. See §13 (arXiv endorsement rules, ARR Jan-2027 deadline, remaining blockers).
- **Nothing here is an Index/leaderboard result.** Never merge poison rates with Artificial Analysis Index or `results/research-30`.

---

## 1. Research framing

### 1.1 Research questions
- **RQ1 (DAG vs non-DAG):** With a planted lie in an internal collaborator, do DAG-style coding-agent systems isolate/detect/recover better than a single-loop agent?
- **RQ2 (inside DAGs):** Does the handling of contaminated nodes (BPD-style contribution scoring vs trusting a scan node vs source-over-scan rule vs plain majority) change isolation/attribution/recovery?

### 1.2 Claims the paper makes (this suite only; two models, one family, one attempt)
- Same system-prompt claim: the single loop has no QnA isolation (acc 0.00, prop 1.00). Three replicas do (acc 1.00).
- On code, string majority is not position-robust. The cause is the last-replica fallback (`poison.aggregate_proposals`).
- A normalized-source diff both names the poisoned replica about as often as the judge and, used as a promotion rule, reaches judge-level code accuracy. A uniform draw does not.
- Backpropagation adds no measurable recovery over the judge.
- Attribution is capped by whether the poisoned replica emits the lie.

### 1.3 Non-claims (do NOT write these)
- "DAGs are always safer / more accurate than single-loop agents."
- "Yonsei source-over-scan rule = BPD" (different mechanisms; Yonsei is exploratory and was not rerun under budget-7).
- "Yonsei propagates more than the single loop" or "the single loop is robust." Both were channel artifacts.
- "General-3 cannot attribute." Budget-5 detection 0 was a user-message artifact.
- "Replication alone explains code isolation." True on QnA; on code it fails when the poisoned replica is the fallback.
- "Only an LLM judge can name the source or choose the workspace on code." The AST rule matches it on these small tasks. Do not extend that to repository-scale tasks.
- "gpt-6-luna is safer." Its QnA Emit drop is the proposal-worker prompt sending it to the file.
- "A random replica fixes majority code accuracy." Uniform accuracy stays near 0.80.
- Any merge/ranking with the Index / research-30 suite.
- The weak-injection pilot's Yonsei detection=1.0 (heuristic artifact).

Label as **exploratory**: Yonsei source-over-scan A/B. Budget-6 majority code accuracy (0.92–0.97) is the replica-0-only design, not the main result.

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

`injection_profile="aligned"` is budget-5 only (user message for general-1 and general-3). `injection_profile="system"` is `--arms budget-6` and is what budget-6, budget-7, and budget-8 use: the same `agent_worker_prompt` text in the poisoned node's system prompt for every arm. Poisoned index: default replica 0; `poison_position="balanced"` (seed `20261011`) assigns 0/1/2 in 34/33/33 tasks. `task_timeout=180` is budget-7 and budget-8; earlier runs use the task's own 60 s timeout.

Arm sets: `--arms default` (general, bpd, yonsei) · `budget-4` (general-1, general-3, flat-3, bpd; legacy wording; core n=20) · `budget-5` (+ `judge-only-3`; aligned wording) · `budget-6` (same five arms, system-prompt profile). There is no `budget-7` arm set: budget-7 and budget-8 are `arms="budget-6"` plus `poison_position="balanced"` and `task_timeout=180`.

Majority code promotion: `aggregate_proposals` returns the last replica when no proposal matches the gold or lie string. That is the position bug. `code/11_selection_counterfactual.py` rescores the saved workspaces under last / uniform / AST-majority rules.

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

### 5.2 budget-6 (DONE 2026-10-11 — the run that fixes issue I1)

- **Run:** 13:26–17:16 KST, `compare_poison(Path('results/poison-budget-6'), condition='agent', task_set='all', scale='all', arms='budget-6', max_turns=20)`, 5 arms × 200 = 1,000 runs. Raw tree (gitignored) in `results/poison-budget-6/`; `score.json` is tracked.
- **Harness timeouts:** in the first pass **11 dag-bpd code tasks hit the 60 s task limit** (status `timeout`, 0 tokens recorded, 16:26–16:41 KST); no other arm had any. `python code/06_retry_infra_timeouts.py poison-budget-6 --profile system` re-ran exactly those once (`results/poison-budget-6-retry/`) and wrote the merged run `results/poison-budget-6-retried/` (use `--merge-only` to rebuild the merge without LLM calls). **8 passed; 3 (strip-once, parity-000, default-000) timed out again and stay failures.** The original run is untouched (macro tag `BSix`); the merged one is the main result (tags `BSixR` and `Main`). Policy: one retry only, never retry until pass.
- **Results (merged, n=100 per cell):**

  | arm | QnA acc/prop/det | Code acc/prop/det | Code Emit / Det\|Emit |
  |---|---|---|---|
  | general-1 | 0.00 / 1.00 / 0 | 0.54 / 0.41 / 0 | 0.50 / 0 |
  | general-3 | 1.00 / 0 / 1.00 | 0.97 / 0.02 / 0.01 | 0.49 / 0.02 |
  | flat-3 | 1.00 / 0 / 0.99 | 0.92 / 0.08 / 0.01 | 0.56 / 0.02 |
  | judge-only-3 | 1.00 / 0 / 0.85 | 0.99 / 0.01 / 0.64 | 0.58 / 0.90 |
  | dag-bpd | 1.00 / 0 / 0.87 | 0.96 / 0.01 / 0.63 | 0.61 / 0.90 |

  McNemar: BPD vs judge-only recovery QnA 12 vs 10 (p=0.83), code 8 vs 9 (p=1.0); general-3 vs judge-only QnA recovery 15 vs 0 (p=6e-5).
- **Conclusions that now hold (one model, n=100+100):** (1) 3-replica isolation is strong; the single loop has none when the lie is in the system prompt. (2) budget-5's general-3 det=0 was a delivery artifact (det|Emit = 1.00 on QnA). (3) QnA attribution: plain majority > judge. (4) code attribution comes from the judge; backprop adds nothing. (5) The Yonsei-vs-single-loop propagation comparison is withdrawn (direction depends on channel).
- **Superseded as the main result** by budget-7 (§5.3). Keep this section as the channel-fix record. Majority code accuracy here (0.92–0.97) is replica 0 only.

### 5.3 budget-7 (paper main run, 2026-10-13) — `gpt-5.6-luna`

`compare_poison(..., arms='budget-6', max_turns=20, poison_position='balanced', task_timeout=180.0)` → `results/poison-budget-7/`. 1,000 runs, 0 timeouts. `score.json` is tracked; replica workspaces are gitignored but required by `code/08`, `09`, `10`, and `11`.

| arm | QnA acc/prop/det | Code acc/prop/det |
|---|---|---|
| general-1 | 0.00 / 1.00 / 0 | 0.59 / 0.40 / 0 |
| general-3 | 1.00 / 0 / 1.00 | 0.81 / 0.15 / 0.02 |
| flat-3 | 1.00 / 0 / 0.99 | 0.72 / 0.26 / 0.01 |
| judge-only-3 | 1.00 / 0 / 0.91 | 1.00 / 0 / 0.63 |
| dag-bpd | 1.00 / 0 / 0.94 | 0.99 / 0.01 / 0.67 |

Code accuracy by poisoned index (permutation p): flat-3 0.88 / 0.91 / **0.36** (p < 0.001); general-3 0.91 / 1.00 / **0.52** (p < 0.001); judge-only and BPD stay at 0.97–1.00 (p = 1). Judge vs BPD code recovery p = 0.48. QnA recovery: general-3 vs judge-only p = 0.004.

### 5.4 budget-8 (second model, 2026-10-16) — `gpt-6-luna`

Same call as budget-7 with `IMPL_COMPARISON_LLM_MODEL=gpt-6-luna` → `results/poison-budget-8/`. About 4 h 15 min, 0 timeouts. `llm.py` treats `gpt-6*` like `gpt-5.6` for chat-completions (`reasoning_effort=none` when tools are set; no `temperature`; `max_completion_tokens`). The project key at the time listed only `gpt-5.6-luna` and `gpt-6-luna`.

Code pattern replicates (flat-3 acc 0.70, and 0.30 when replica 2 is poisoned; judge-only 0.99, BPD 0.98; code detection 0.60 / 0.61; backprop p = 1.0). QnA detection does not: flat-3 / judge-only / BPD fall to 0.12 / 0.11 / 0.10 because Emit is 0.12 / 0.12 / 0.10, while general-3 stays at 0.95 (Emit 0.95). Det|Emit on those arms is still 0.92–1.00. `code/10_qna_emit_behavior.py`: on this model a proposal worker that calls a tool answers with the source value (flat-3 tool+gold 0.88); with no tool it states the lie (0.11). `gpt-5.6-luna` states the lie even after a tool call (flat-3 tool+lie 0.09, tool+gold 0.01).

One uncorrected lead, not a finding: judge-only code recovery by index on budget-8 is 0.65 / 0.42 / 0.73 (p = 0.037) across 20 recovery tests.

### 5.5 Offline analyses (no LLM calls)

| Script | Output | What it shows |
|---|---|---|
| `code/07_position_breakdown.py` | `position_*.csv`, `replication_*.csv` | Rates by poisoned index; paired McNemar across runs |
| `code/08_semantic_baselines.py` | `semantic_baselines_*.csv` | AST outlier and hidden-test oracle vs the arm's own detection. Copies workspaces under `/tmp` (macOS `/var/folders` makes pytest start in ~18 s) |
| `code/09_majority_fallback.py` | `fallback_*.csv` | Final code equals replica 2 in ~0.90 of majority tasks |
| `code/10_qna_emit_behavior.py` | `qna_emit_behavior_*.csv` | Tool use × lie/gold answer for the poisoned QnA replica |
| `code/11_selection_counterfactual.py` | `selection_*.csv` | Accuracy if another replica had been promoted |

Budget-7 flat-3 code accuracy under promotion rules: actual 0.72, always replica 2 = 0.78, uniform draw = 0.79, AST majority (else replica 2) = **0.98**. Judge-only recorded 1.00, AST on its replicas 0.97. Budget-8 flat-3: 0.70 / 0.77 / 0.79 / **0.98**. Random does not replace the judge; the diff does, on these tasks.

---

## 6. Repo map and replication pipeline

```
apps/implementation-comparison/
  HANDOFF.md                      <- this file
  CLAUDE.superpapers.md           <- project config for the superpapers research workflow (venue, style, rules)
  src/impl_comparison/            <- harness + poison suite (see §3, §4)
    poison_compare.py             <- CLI + compare_poison() runner, arm sets, smoke LLM
  tests/                          <- pytest (418 passed on 2026-10-20; run offline with FakeLLM)
  code/                           <- 01..05 regenerate tables/macros; 06 timeout retry; 07 position; 08 AST baseline; 09 fallback check; 10 QnA emit behavior; 11 promotion counterfactual
  data/raw/poison_runs/manifest.md        <- generated
  data/processed/                 <- rates_by_run.csv, paired_*.csv, position_*.csv, replication_*.csv, semantic_baselines_*.csv, fallback_*.csv, qna_emit_behavior_*.csv, selection_*.csv
  output/tables/                  <- generated booktabs .tex, including tab_main_compact, tab_position, tab_semantic, tab_selection, tab_emit, tab_second_compact
  results/EXPERIMENT_SUMMARY.md   <- English summary through budget-8 (force-added; results/** is otherwise ignored)
  results/POISON_RESULTS.md       <- long log. Sections 1–11 are the earlier Korean record through budget-6. Sections 12–14 (English) are current.
  results/poison*/score.json, comparison.md   <- committed frozen run summaries
  paper/paper.tex                 <- draft on budget-7 + budget-8 (ACL review mode)
  paper/acl.sty, acl_natbib.bst, acl_latex.tex  <- official ACL style files (github.com/acl-org/acl-style-files)
  paper/references.bib            <- 23 entries, all verified against the arXiv API on 2026-10-11 (published-venue versions not verified)
  output/macros/results.tex       <- generated LaTeX macros (RateMain..., Pval..., Tok...) so prose never hard-codes numbers
  docs/superpapers/               <- BRIEFING (abstract/RQ/roadmap), literature-notes, spec, plan
```
Repo root also has `docs/superpowers/specs/2026-08-30-poison-attribution-bpd-design.md` (original BPD design spec; `CLAUDE.superpapers.md` cites it) and a shared `src/dagcore` library (`EdgeGraph`).

### 6.1 Regenerate everything from frozen summaries (no API calls)
```sh
cd apps/implementation-comparison
PY=/Users/sobabear/Desktop/yonsei/DAG-Experiment/.venv/bin/python   # or any env with pytest installed
$PY code/01_manifest_poison_runs.py     # -> data/processed/run_index.json, data/raw/poison_runs/manifest.md  (add new run ids to DEFAULT_RUNS)
$PY code/02_aggregate_poison_rates.py   # -> rates_by_run.csv / _ci.json; bootstrap 95% CI, SEED=20260909, B=1000, condition split, tokens/task
$PY code/04_paired_tests.py poison-budget-7 poison-budget-8   # -> paired_<run>.csv
$PY code/07_position_breakdown.py poison-budget-7 --replicate-with poison-budget-6-retried
$PY code/07_position_breakdown.py poison-budget-8 --replicate-with poison-budget-7
$PY code/08_semantic_baselines.py poison-budget-7    # ~8 min; needs replica workspaces on disk
$PY code/09_majority_fallback.py poison-budget-7
$PY code/10_qna_emit_behavior.py poison-budget-7
$PY code/11_selection_counterfactual.py poison-budget-7   # ~4 min per run
$PY code/05_export_macros.py            # `Main` aliases poison-budget-7, else budget-6-retried, else budget-6, else budget-5
$PY code/03_export_paper_tables.py      # after 07-11, so position/semantic/selection tables exist
cd paper && latexmk -pdf paper.tex      # build the draft (build artifacts are gitignored)
```
`02` raises if an empirical rate disagrees with the `rates` published in `score.json` (consistency guard).
Seeds are now process-independent (`stable_seed` = crc32); previously `hash()` made CIs differ per run, so **CIs in committed tables differ slightly from any older numbers**.

### 6.2 Tests
```sh
PYTHONPATH=src:/Users/sobabear/Desktop/yonsei/DAG-Experiment/src $PY -m pytest tests code -q   # 418 passed on 2026-10-20 (~60 s)
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
| **I1** (resolved) | **Injection channel confound.** | Budget-5 mixed system prompt and user message. | **Resolved by budget-6** (`injection_profile="system"`, `lie_emitted`, `detection_given_emitted`). Budget-5 is a channel-sensitivity result only. |
| **I2** (resolved for this suite) | Substring majority cannot attribute code. | A missing semantic baseline would credit the judge for any comparison. | **Done:** `code/08` (AST outlier ≈ judge detection) and `code/11` (AST promotion ≈ judge accuracy, uniform draw does not). Not evidence for larger tasks. |
| **I3** (half done) | One model family, attempts=1. | Reviewer will ask for another family and for variance. | Budget-8 is `gpt-6-luna` (same family). A different family is optional unless the target is ACL main. Attempts ≥ 3 are not required for the current effect sizes. |
| **I4** | QnA tasks are short config values → ceiling effects (acc≈1.0 for all 3× arms); wording-sensitive propagation of single loop. | QnA cannot discriminate architectures well. | Make code the primary evidence; add harder multi-file SE tasks (backlog B7). |
| **I5** | Hand-built, synthetic tasks (single-file `worker.py`-style fixtures expanded from templates). | External validity. | Backlog B7. |
| **I6** | Yonsei arm compared with different injection point (scan node) and a post-hoc rule (exploratory). | Fairness; HARKing risk. | Keep as appendix/exploratory; label clearly. |
| **I7** | `document` condition has no effect (prop≈0) — the policy-in-NOTES.md poison is ignored by this model. | Can't claim document-poison results. | Treat as negative control or redesign (separate RQ). |
| **I8** | Raw transcript trees (~190 MB) are not in git. | Qualitative audit/reproduction of raw runs impossible from a clone. | Archive to Zenodo/HF/GitHub release and cite DOI; keep `score.json` in git (done). |
| **I9** | `results/POISON_RESULTS.md` section order is 7, 9, 10, 8; `CLAUDE.superpapers.md` cites a spec under `docs/superpowers/` (repo root) while newer docs live in `docs/superpapers/`. | Navigation confusion. | Reorder/renumber; add cross-links. |
| **I10** (resolved for now) | `references.bib` now has 23 entries, all checked against the arXiv API on 2026-10-11 (title/authors/year/category). Published-venue versions (e.g. ICLR/ACL/NeurIPS) were **not** verified, so entries are cited as arXiv preprints. | Never fabricate citations. | At camera-ready, replace with venue versions after verifying them; add 5–10 more references closer to the target venue (ACL/EMNLP Findings 2024–2026 on agent safety/coding agents). Note: BibTeX treats a lowercase word after a hyphen as a *von* part ("Jen-tse Huang" printed as "tse Huang") — write such names as `Huang, Jen-tse`. |
| **I11** (resolved) | Poison position fixed at replica 0. | Hid the majority fallback failure. | **Resolved by budget-7/8** (`poison_position="balanced"`, seed 20261011). Judge-arm position cells are n≈33; one uncorrected budget-8 judge-only code test is p=0.037 and is labeled a lead. |

---

## 8. Backlog (prioritized, with acceptance criteria)

**P0 — needed before any DAG-vs-non-DAG claim**
- **B1. Fix channel confound (I1). [DONE — see §5.2.]** Add `injection_profile="system"` handling in `general.py` and `majority3.py` (TDD: mirror `test_aligned_profile_*` in `tests/test_poison.py`), add arm option (e.g. `--arms budget-6` or a flag), rerun general-1/general-3 (and ideally all 5 arms for a single coherent run, ≈3.5 h). Acceptance: all arms receive byte-identical injection text in the same channel; report lie-compliance of the poisoned replica per arm; add a table + McNemar rows; update `POISON_RESULTS.md` §11 and BRIEFING.
- **B2. Update Abstract/RQ2 text** — DONE for the paper (abstract rewritten for budget-6); keep wording "associated with", not causal.

**P1 — makes the paper defensible**
- **B3. Cost–recovery paragraph/figure** from logged tokens (no new API calls): recovery vs input tokens per task for the 5 arms (script `code/06_cost_recovery.py` (code/05 is the macro exporter) + `output/tables|figures/`).
- **B4. Qualitative BPD-miss analysis**: sample 10–20 `dag-bpd` agent failures (det=0) from `results/poison-budget-5/dag-bpd/*/runs/*/` transcripts (local only), code failure modes (judge mislabels, poisoned worker declines the lie, summarizers copy a single proposal, etc.). Put taxonomy in `docs/superpapers/` and a short paper paragraph.
- **B5. Second model. [DONE as budget-8, `gpt-6-luna`, same family.]** Code conclusions replicate. QnA attribution does not, and `code/10` explains it. A model from another family is optional for the current claim scope, recommended for ACL main.
- **B6. Variance:** attempts≥3. Not required for the current effect sizes (code accuracy gaps are tens of points and budget-8 replicates them). Do it only if a reviewer asks.

**P2 — strengthens external validity (can be future work)**
- **B7. Harder tasks:** multi-file SE tasks with hidden tests; or adapt a public benchmark slice.
- **B8. Runner robustness:** write per-arm `score.json` incrementally (checkpoint/resume) so a crash doesn't lose hours; optional parallel workers with rate-limit handling.
- **B9. Yonsei fair-defense compare** under matched budget (source-over-scan vs BPD vs flat-3) — exploratory appendix.

- **B10. Randomize poison position (I11). [DONE — budget-7 and budget-8.]**
- **B11. Judge-free semantic baseline (I2). [DONE — `code/08` and `code/11`.]** The promotion counterfactual is the result that lets the paper say a diff can choose the workspace, not only name the source.

**Writing track**
- **W1. `paper/paper.tex`. [DRAFT DONE on budget-7 + budget-8.]** Remaining `\todo{}`: AI-use disclosure / Responsible NLP checklist, anonymous repository and raw-run archive. Content fits in 8 pages; the PDF is 14 pages with references and appendix. Never hard-code numbers.
- **W2. Literature review. [PARTLY DONE: 23 arXiv-verified refs; extend with venue-adjacent 2024–2026 ACL/EMNLP/Findings papers.]** 15–30 web-verified references (use `docs/superpapers/literature-notes.md` as seed; bias to ACL/EMNLP/agent workshops, last 3–5 years); fill `paper/references.bib`; fix the 2 unverified entries.
- **W3. Venue/ARR check. [DONE — see §13.]**
- **W4. Final audit:** skill `superpapers-paper-review` before submission.

---

## 9. Conventions and rules (must follow)

1. **Never commit `.env` or secrets.** `.env` is gitignored. `.cursor/` is also not tracked.
2. **Do not commit/push unless the user explicitly asks.** (This handoff was committed on explicit request.)
3. **Never put analysis into `results/research-30/comparison.md`** (only glossary/cost notes). Never merge poison metrics with the Index / research-30.
4. **Never hard-code numbers in the paper**; tables via `\input{}` from `output/tables/` and prose numbers via macros from `output/macros/results.tex`, regenerated by `code/01` through `code/11`.
5. **TDD:** write a failing pytest first for any change in `src/`; keep `pytest tests code` green (418 passed on 2026-10-20).
6. **No fabricated citations;** verify each via web.
7. **Label exploratory findings** (strong-injection scaling, Yonsei rule A/B) in paper text.
8a. **Disclose AI assistance.** ACL policy requires disclosing generative-AI use for writing/coding in the Responsible NLP checklist and Acknowledgments; this project used AI coding/writing assistants, so the authors must disclose it and verify every claim themselves.
8. Code-review subagents (if used): prefer Composer / Cursor Auto models.
9. Gitignore: `results/**` ignored except `POISON_RESULTS.md`, `EXPERIMENT_SUMMARY.md` (force-added), `research-30/comparison.md`, and `results/poison*/{score.json,comparison.md}`. Transcript trees and `run.log` remain ignored. `code/08` and `code/11` need those local workspaces.
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

- `03c2046` Position-balanced budget-7, second-model budget-8, and the paper rewrite. The selection-rule analysis (`code/11`) and this handoff update are the following commit.
- `6a5a283` Budget-6 same-channel run, timeout retry, first paper draft.
- `649bcf5` Add compute-matched poison arms so BPD is not credited for 3× rollouts alone.
- `73891ec` WIP (user commit)
- `e27b49a` Expand poison suite for paperization: strong injection, n=100, yonsei fix, tables.
- `864f962`, `65c65d9`, `faf700d`, `b5f6704`, `2c78607`: earlier BPD v2 / code-fixture / pytest-grading work.

---

## 12. Quick start checklist for the next agent

1. `git pull`; create/activate a Python env (`pyproject.toml`); run `pytest tests code -q` → 418 passed on 2026-10-20.
2. Read §0 and `results/EXPERIMENT_SUMMARY.md`. Do not treat budget-6 or the Korean sections of `POISON_RESULTS.md` as the main result.
3. Remaining work is writing and submission, not another LLM run, unless the user aims at ACL main (then one model from a different family). See §13.
4. Keep this file updated when a run or a claim changes.

---

## 13. Submission plan: arXiv and ACL Rolling Review (verified 2026-10-11)

**Facts checked on the web today (cite the sources when re-checking):**
- **arXiv endorsement (since 2026-01-21):** an institutional email alone no longer suffices for new submitters. Path 1 needs *both* an institutional academic/research email *and* an existing accepted arXiv paper in the same endorsement domain; otherwise Path 2: **personal endorsement from an established arXiv author in that domain** (arXiv staff cannot endorse). Request via the endorsement link shown after starting a submission; do not mass-email. Sources: blog.arxiv.org/2026/01/21/attention-authors-updated-endorsement-policy/, info.arxiv.org/help/endorsement.html. arXiv CS also stopped accepting *review/position* papers unless already peer reviewed (Oct 2025) — this paper is an empirical paper, so it is not affected.
- **ARR/ACL timeline:** the ARR **October 2026 cycle deadline is 2026-10-12** (not feasible); next is the **January 2027 cycle, submission deadline 2027-01-04**, which feeds **ACL 2027** (Kyoto, Aug 2027; commitment date TBD). Source: aclrollingreview.org/dates, 2027.aclweb.org/calls/main/.
- **ARR requirements that can desk-reject you:** official ACL template unmodified; **long paper ≤ 8 pages / short ≤ 4 pages** of content (limitations, ethics, references, appendices extra); a **Limitations section is required**; Responsible NLP checklist must be complete; **generative-AI use must be disclosed** (checklist + Acknowledgments); anonymized supplementary material (no Dropbox/Drive links; use Anonymous GitHub). Source: aclrollingreview.org/cfp.
- **New sustainable-reviewing policy (from Oct 2026):** every submission must name one **qualified designated service contributor** (reviewer/chair-level; max 2 submissions each; must register within 48 h after the deadline); submissions without one go into a **lottery** and may not be reviewed. **All authors need complete OpenReview profiles incl. ORCID.** Caps: 20 submissions/author, 5 as first author per cycle. Source: aclrollingreview.org/cfp and the ACL sustainable reviewing policy PDF. *Action for the user:* find a co-author or colleague who qualifies as a reviewer, or accept the lottery risk.
- **Preprints during review:** since 2024-02-15 ACL has **no anonymity period**; non-anonymous arXiv preprints are allowed while under review (choose "no non-anonymous preprint" only if you want the award/priority incentive). So posting to arXiv first does not block ARR.

**Recommended path:** (1) disclosure, checklist, anonymous repo, and raw-run archive → (2) arXiv preprint (cs.AI primary; cs.MA or cs.SE cross-list; needs an endorser) → (3) ARR **January 2027** (deadline 2027-01-04) with a designated service contributor → (4) an agent workshop if the main-conference bar is the goal and a third model family is not run.

**Readiness (2026-10-20):** budget-7, budget-8, position randomization, the judge-free diff, and the promotion counterfactual are in the paper. Still open: (1) the two `\todo` blocks (AI-use disclosure / Responsible NLP checklist; anonymous repository and raw-run archive); (2) author list, OpenReview, ORCID, and a designated service contributor; (3) an arXiv endorser. A model from another family is optional for this claim scope and recommended only for ACL main. Do not start another luna-family run for its own sake.
