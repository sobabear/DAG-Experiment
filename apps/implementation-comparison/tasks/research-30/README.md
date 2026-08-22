# Research-30 custom suite

This directory documents the **custom 30-task** comparison suite used by the implementation-comparison app. It is **not** the public DeepSWE, Terminal-Bench v2, or SWE-Atlas-QnA corpora.

Always write **Artificial Analysis** in full. Scores from this suite **cannot** be compared numerically with the public Artificial Analysis leaderboard.

## Layout

| Area | Count | Analog (protocol only) | Timeout bound |
|------|-------|------------------------|---------------|
| Software Engineering (`se`) | 10 | DeepSWE | ≤ 90s |
| Terminal / agentic workflow (`terminal`) | 10 | Terminal-Bench v2 | ≤ 120s |
| Repository Q&A (`qna`) | 10 | SWE-Atlas-QnA | ≤ 60s |

Task definitions, fixtures, and hidden verifiers live in `src/impl_comparison/research_suite.py` and `src/impl_comparison/research_tasks/`. Each attempt materializes a **fresh** workspace; agents never see another attempt's files or transcripts.

## Hidden verifiers

Every task has a binary hidden verifier:

- The starting (broken) fixture **fails**.
- The intended repair (`apply_reference_fix`, tests only) **passes**.
- Prompts do **not** include `apply_reference_fix`, the words `hidden verifier`, or gold `answer.txt` bodies.

Agents are scored on the workspace after the run, not on claimed success text.

## Scoring (Index protocol)

Copied from the Artificial Analysis Coding Agent Index **formula**, not from the public task set:

1. Each task is binary pass/fail per attempt.
2. **Three** independent attempts per task; `task_score = mean(attempt bits)` (pass@1).
3. Area score = equal mean of that area's 10 task scores.
4. `Index = mean(S_SE, S_Terminal, S_QnA)`.

The three systems under comparison are **dag-bpd**, **dag-yonsei**, and **general-agent-system**. They share the same task prompts, snapshots, tool schema, timeouts, token budget, and LLM.

## Calibration controls

- **Ceiling**: all three systems pass all three attempts. Kept in the suite as a control.
- **Floor**: all three systems fail all three attempts. Kept in the suite as a control.
- **Invalid**: for example a verifier that does not distinguish broken vs corrected, or a prompt that equals the gold answer. Invalid tasks stay in the suite but are **excluded from the primary comparison** only after the exclusion and reason are recorded.

## Fake LLM vs real research

The deterministic Fake `WorkspaceAwareLLM` is **CI / harness only**. It cannot solve these 30 tasks by design. Fake LLM calibration is a **harness check only, not the research result**. Do not write Fake LLM scores into `results/research-30/comparison.md` as the study result.

Real research runs use an **environment-configured LLM**. Set
`IMPL_COMPARISON_LLM_PROVIDER`, `IMPL_COMPARISON_LLM_MODEL`, optional
`IMPL_COMPARISON_LLM_ENDPOINT`, and `OPENAI_API_KEY` in the process
environment, then run `python -m impl_comparison.compare --suite research-30`.
**Do not put secrets in files** in this repository: no API keys in task
fixtures, READMEs, or committed configs. Copy
`apps/implementation-comparison/.env.example` locally if needed (empty
placeholders only); never commit `.env`. The harness does **not** auto-load
`.env`. Export variables into the process (or `set -a; source .env`) before
running.
