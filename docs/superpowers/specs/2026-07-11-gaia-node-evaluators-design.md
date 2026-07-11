# GAIA DAG Node Evaluators — Design Spec

**Date:** 2026-07-11  
**Status:** Approved for planning (pending user review of this file)  
**Repo:** Convert `DAG-Experiment` from BPD `dagcore` core into this GAIA study.

---

## 1. Research question

When an LLM pipeline is a **DAG**, a node **evaluator** scores each step’s text. Different evaluators estimate **confidence (C)** and **deviation (D)** differently.

**Question:** On the *same* worker outputs, which of five evaluators best aligns **deviation / PASS** with **GAIA exact-match** on the final answer?

**Design rule:** Run the worker **once** per task, persist traces, then swap only the evaluator. Never regenerate workers when comparing methods.

---

## 2. Decisions locked in brainstorming

| Decision | Choice |
|----------|--------|
| Repo strategy | Convert this repo; move existing `src/dagcore` → `legacy/dagcore` |
| Package layout | Role-separated package `src/gaia_dag/` (not monolithic scripts, not BPD EdgeGraph) |
| Worker LLM | OpenAI `gpt-4o-mini` |
| Multi-judge | OpenAI + Anthropic + Gemini (mean over available keys) |
| Embeddings (S, DSS) | OpenAI `text-embedding-3-small` |
| Ranking τ | D ≥ 0.3 = “high D”; DSS ≥ 0.3 = HIGH-RISK log |

---

## 3. Architecture

### 3.1 Package layout

```
project/
├── README.md
├── .env.example
├── pyproject.toml
├── legacy/dagcore/          # former BPD matrix core (reference only)
├── src/gaia_dag/
│   ├── models.py            # Node, Graph, EvaluationResult
│   ├── graphs/
│   │   └── gaia_pipeline.py # Plan → Solve → Answer builder
│   ├── orchestrator.py      # topo sort + execute
│   ├── worker.py            # generate output_data only
│   ├── llm/                 # OpenAI / Anthropic / Gemini clients
│   ├── scoring/
│   │   └── gaia_em.py       # normalize + exact match
│   ├── benchmarks/
│   │   └── gaia_loader.py   # HF GAIA + --demo synthetic
│   ├── routing.py           # fixed ambiguity → PASS/FAIL/AMBIGUOUS
│   └── evaluators/
│       ├── base.py
│       ├── baseline.py
│       ├── logprobs_confidence.py
│       ├── multi_judge.py
│       ├── dss.py
│       └── context_ensemble.py
├── scripts/
│   ├── run_gaia_worker.py   # Phase A
│   └── run_gaia_eval.py     # Phase B
├── tests/
└── results/gaia/
    ├── worker_traces/
    └── eval_results.json
```

### 3.2 Core types

**Node**

| Field | Meaning |
|-------|---------|
| `node_id` | Stable id (`Plan`, `Solve`, `Answer`) |
| `task_description` | Prompt / instructions |
| `depends_on` | Parent node ids |
| `input_data` | Resolved parent outputs (+ optional eval metadata) |
| `output_data` | Primary worker text (immutable in Phase B) |
| `status` | `PASS` / `FAIL` / `AMBIGUOUS` |
| `C`, `D`, `S`, `DSS` | Evaluator signals in [0, 1] where defined |
| `eval_meta` | Method-specific extras (judge scores, probe tokens, etc.) |

**Graph:** dict of nodes + dependency edges; topological execution order.

**EvaluationResult:** method name, per-node scores, Answer predicted string, EM bool, status.

### 3.3 APIs

- `run_worker(node) -> node` — generate `output_data` (and optionally a secondary sample for traces); no scoring.
- `evaluate(node) -> node` — attach C/D/S/DSS/status; **must not** overwrite primary `output_data`.
- Orchestrator: topo-sort → inject parent `output_data` into `input_data` → call worker **or** evaluate.

### 3.4 Phases

```
Phase A: load tasks → build DAG → worker once → save trace (+ secondaries)
Phase B: load traces → rebuild graph (outputs fixed) → evaluate × 5 → aggregate
```

---

## 4. GAIA pipeline

### 4.1 Dataset

- **Real:** Hugging Face `gaia-benchmark/GAIA`, **validation** split, **Level 2 and 3**. Requires accepting dataset terms + `HF_TOKEN`.
- **Demo:** `--demo` synthetic arithmetic / string tasks so smoke tests need no HF.
- **Attachments:** if a task has a file, extract text (PDF/txt) and append to the Plan prompt.

### 4.2 Task DAG

```
Plan → Solve → Answer
```

| Node | Responsibility |
|------|----------------|
| Plan | Restate question (+ attachment text); outline steps; **no** final answer |
| Solve | Execute the plan using upstream plan text; draft reasoning + draft answer |
| Answer | Emit a **short** final answer only (EM-friendly). Prefer `Final answer: …`; bare numbers when gold has no units |

### 4.3 Trace schema (minimum)

```json
{
  "task_id": "…",
  "level": 2,
  "question": "…",
  "gold_answer": "…",
  "worker_model": "gpt-4o-mini",
  "nodes": {
    "Plan": {
      "task_description": "…",
      "output_data": "…",
      "depends_on": []
    },
    "Solve": {
      "task_description": "…",
      "output_data": "…",
      "depends_on": ["Plan"]
    },
    "Answer": {
      "task_description": "…",
      "output_data": "…",
      "depends_on": ["Solve"]
    }
  },
  "secondaries": { "Plan": "…", "Solve": "…", "Answer": "…" }
}
```

- Path: `results/gaia/worker_traces/{task_id}.json`
- Resume-safe: skip if file already exists
- Phase B never calls the worker for the primary answer

### 4.4 Routing (fixed across all methods)

Missing signals default to neutral `0.5`.

```
ambiguity = 0.5 * D + 0.3 * (1 - C) + 0.2 * (1 - S)
status =
  PASS       if ambiguity < 0.3
  AMBIGUOUS  if 0.3 ≤ ambiguity < 0.5
  FAIL       if ambiguity ≥ 0.5
```

DSS ≥ 0.3 → log HIGH-RISK; does **not** change Baseline D semantics for ranking tables.

### 4.5 GAIA EM

Normalize case, articles, punctuation; prefer bare numbers when gold has no units. Extract predicted answer from Answer `output_data` (strip `Final answer:` prefix when present).

---

## 5. Five evaluators

Ablation rule: change one axis at a time where possible. Context-aware ensemble is the combined proposal.

| Method | What changes | C | D | S / DSS |
|--------|--------------|---|---|---------|
| **Baseline** | Control | Self-report JSON confidence (fallback 0.5) | Single OpenAI critic; **no** parent context | S = cosine(primary, secondary) |
| **Logprobs C** | C only | YES/NO probe; `C = P(YES)/(P(YES)+P(NO))` | Same as Baseline | Same S |
| **Multi-judge D** | D only | Same as Baseline | Mean of OpenAI + Anthropic + Gemini; **node task+output only** | Same S |
| **DSS** | Add DSS | Same as Baseline | Same as Baseline (D tables ≈ Baseline by design) | Perturb prompt once; `DSS = 1 - cosine(orig, pert)`; HIGH-RISK if ≥ 0.3 |
| **Context ensemble** | Combined | Logprobs C | Multi-judge **with** parent task snippets + parent outputs (+ optional upstream DSS warning) | + DSS |

**Out of canonical set** (unless asked): Quiz-based D (QAG), G-Eval-only D, concordance-only index.

**Judge key policy:** If a provider key is missing, skip that judge and average the rest; warn in logs. OpenAI is required for worker, Baseline critic, logprobs, and embeddings.

---

## 6. Metrics & success

### Worker (evaluator-independent)

- GAIA EM% on Answer after normalization.

### Evaluator (Answer node, frozen traces)

| Metric | Meaning |
|--------|---------|
| wrong → high D % | EM wrong and D ≥ 0.3 — higher better |
| correct → low D % | EM correct and D < 0.3 — higher better |
| PASS on wrong % | EM wrong but PASS — lower better |
| FAIL on correct % | EM correct but FAIL — lower better |
| mean D | Average Answer deviation |
| eval_score | Fixed aggregate (below) |

```
eval_score = wrong_high_d×40 + correct_low_d×30
           + (1 - pass_on_wrong)×20 + (1 - fail_on_correct)×10
```

Rates are fractions in [0, 1]. Document these weights in README; keep fixed across runs.

### Reproduction success

1. Smoke (`--demo`) → pilot (`--max-tasks 20`) → optional full L2+L3.
2. All five methods scored on the **same** traces.
3. Report worker EM% and method ranking in `results/gaia/eval_results.json`.
4. **Ceiling caveat:** if almost all answers are EM-correct, wrong→high-D cannot separate methods — state this; prefer Level 3 / larger N.
5. Note DSS ≈ Baseline on D; highlight Context-aware ensemble vs Multi-judge (context on vs off).

---

## 7. Configuration & error handling

### Required environment

| Variable | Purpose |
|----------|---------|
| `OPENAI_API_KEY` | Worker, Baseline critic, logprobs, embeddings, one judge |
| `ANTHROPIC_API_KEY` | Multi-judge / context ensemble |
| `GOOGLE_API_KEY` | Gemini judge (or documented Gemini env alias) |
| `HF_TOKEN` | Real GAIA load (not required for `--demo`) |

Ship `.env.example`; load via `python-dotenv`. Never commit `.env`.

### Errors

- API calls: retry with exponential backoff; cap retries.
- Per-task failure: record error, continue the run.
- Never overwrite an existing worker trace.
- Eval phase must refuse to regenerate primary `output_data`.

---

## 8. Testing strategy

- Unit: topo sort, EM normalization, routing thresholds, trace load/rebuild.
- Integration: `--demo` worker + eval for 2–5 tasks with mocked or live LLM (CI prefers mocks).
- Manual ladder: demo smoke → pilot 20 → full when pilot OK.

---

## 9. Implementation order

1. Models + orchestrator (topo execute).
2. GAIA loader (`--demo` first) + 3-node graph builder.
3. Worker-only runner + trace I/O.
4. GAIA EM scorer.
5. Baseline `evaluate()`.
6. Eval runner (load traces → five method slots).
7. Logprobs C → Multi-judge → DSS → Context-aware ensemble.
8. Aggregation + ranking report.
9. Pilot 20 tasks; only then full L2+L3.

---

## 10. Non-goals

- Reusing BPD `EdgeGraph` as the execution engine.
- Adding QAG / G-Eval / concordance-only to the canonical five.
- Regenerating workers between evaluator methods.
- Building a full multi-agent MAS beyond the 3-node GAIA DAG.
