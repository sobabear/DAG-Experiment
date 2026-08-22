# Research-30 comparison

The real-LLM pilot has **not been executed in this tree**. This file is a
placeholder for live scores and qualitative findings. It is not a published
Index result.

## How to run the pilot

Configure **one identical LLM** for all three systems through the process
environment. Do not write credentials to files, `ModelConfig.extra`, logs, or
`score.json`. `OPENAI_API_KEY` is read by the OpenAI SDK from the process
environment.

```sh
export IMPL_COMPARISON_LLM_PROVIDER=openai-compatible
export IMPL_COMPARISON_LLM_MODEL=<model-id>
# optional:
export IMPL_COMPARISON_LLM_ENDPOINT=<openai-compatible-base-url>
export OPENAI_API_KEY=<secret>

cd apps/implementation-comparison
PYTHONPATH=src:../../../src python -m impl_comparison.compare --suite research-30
```

That command is the 30-task × 3-attempt × 3-system grid from **fresh
workspaces**. Missing `IMPL_COMPARISON_LLM_PROVIDER` or
`IMPL_COMPARISON_LLM_MODEL` raises `ValueError`. The research-30 CLI does not
fall back to a harness Fake LLM unless `--allow-fake` or
`IMPL_COMPARISON_ALLOW_FAKE=1` is set (tests only).

Copy `apps/implementation-comparison/.env.example` locally if useful; never
commit `.env`. The harness does **not** auto-load `.env`. Export variables
into the process (or `set -a; source .env`) before running.

## Disclaimer

This is a custom suite and cannot be compared numerically with the public
Artificial Analysis leaderboard.

Public DeepSWE, Terminal-Bench v2, and SWE-Atlas-QnA corpora are **not**
executed in this tree. `Index_system` copies the Coding Agent Index **formula**
(pass@1, three attempts, equal-weight Software Engineering / Terminal /
Repository QnA) onto this custom suite only.

`Index_system` is **correctness-only**. Time, cost, tokens, and turns are
recorded beside the score and are not part of Index.

## Scores

Awaiting real-LLM pilot. No numeric Index table is published from this tree.

## Qualitative findings

The four notes below will be filled from failure artifacts after the live
pilot. They are not conclusions.

### DAG advantage

Awaiting real-LLM pilot.

### DAG overhead

Awaiting real-LLM pilot.

### General-system flexibility

Awaiting real-LLM pilot.

### Task categories with no separation

Awaiting real-LLM pilot.
