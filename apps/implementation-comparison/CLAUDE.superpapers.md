# Poison Attribution in Coding-Agent DAGs

## Research Context

- **Field:** multi-agent LLM systems / coding-agent safety / attribution & resilience
- **Research question:** When an internal collaborating agent is fed a planted lie, can a DAG-structured coding-agent system isolate, detect, and recover from it — and does a general single-loop agent have any equivalent attribution mechanism?
- **Type:** mixed — primary architecture comparison (BPD vs hierarchical vs single-loop) intended as confirmatory per `docs/superpowers/specs/2026-08-30-poison-attribution-bpd-design.md`; injection-strength and yonsei source-over-scan defense results are exploratory and must be labeled as such (no HARKing)
- **Identification strategy:** controlled experimental comparison on a fixed task suite (micro-QnA string-match + code-verifiable hidden pytest); not DiD/RD/IV — use correlational/comparative language for architecture associations; do not claim causal “effect of DAG topology” without an explicit identification argument
- **Paper language:** en
- **Code language:** Python
- **Significance convention:** descriptive rates with bootstrap CIs preferred; no NHST-first framing (this is an ML systems empirical study, not an econ/psych significance ladder)
- **Citation style:** author-year (default); switch to numeric only if the target venue requires it via `journal-guidelines`

## Target Outlets

- **Primary target journal:** ACL Findings / EMNLP Findings (next open ARR cycle) — short empirical systems paper on internal collaborator poison + attribution in tool-using coding agents
- **Backup journals:** (1) collocated agent / multi-agent / LLM-agent workshop at ACL·EMNLP·ICLR·NeurIPS (e.g. REALM-style agent workshops — confirm open CFP before submitting); (2) arXiv cs.AI / cs.MA / cs.SE preprint as standing archival anchor
- **Tier strategy:** realistic-to-safety (between workshop-first and Findings): ship arXiv + workshop for feedback, then expand ablations into Findings/short; do not aim ICML/NeurIPS/ICLR main until multi-model + harder SE tasks + cost–safety Pareto exist

## Reproducibility Defaults

- **Seed:** document and fix seeds in any stochastic aggregation/bootstrap scripts; LLM API runs are inherently non-deterministic — record model id, prompt versions, `max_turns`, task catalog hashes, and raw `results/poison*/` artifacts
- **Results source of truth:** `apps/implementation-comparison/results/POISON_RESULTS.md` and per-run `comparison.md`; never merge poison rates into Artificial Analysis Index / `research-30`
- **Lockfile:** repo `.venv` / `pyproject.toml` under `DAG-Experiment` and `apps/implementation-comparison`

## Instructions for Claude Code

- Use the `superpapers` plugin skills for all research tasks in this project.
- Invoke `academic-baseline` first in every research session and keep it active as the standing policy layer.
- Enforce `replication-driven-research` as a guardrail for every analysis step.
- When executing a plan, treat each task's `Skills involved` field as mandatory routing, not a suggestion.
- For any journal-facing work (target outlet, author instructions, template adaptation, formatting, blinding, checklist, cover letter, submission portal), invoke `journal-guidelines` in the current session.
- Respect the paper language setting above for all user-facing paper content (sections, tables notes, figure captions).
- Use the code language preference above for all new scripts; when multiple languages are allowed, prefer the one already used in the project.
- Plugin internals, scripts, and code comments remain in English regardless of paper language.
- Never fabricate citations — verify every reference via web.
- When looking up literature for any purpose (gap verification, citation, literature review), bias toward the user's target journals and closely related outlets in the same field tier.
- Prioritize recent publications (last 3-5 years) from target journals.
- Never hardcode results in `paper/paper.tex` — always use `\input{}` from `output/`.
- Citations default to author–year style; switch to numeric only with an explicit journal requirement documented via `journal-guidelines`.
- Keep poison metrics (accuracy, propagation, detection, recovery) separate from Index/cost leaderboard narratives.
- Label exploratory findings (strong-injection scaling, yonsei source-over-scan A/B) explicitly in paper text.
- Prefer comparative language (“associated with higher recovery”) over causal “DAG causes safety” unless a dedicated identification section is added and approved.

## Gap-Closing Priorities (standing research backlog)

1. Multi-model replication (at least one additional model family beyond `gpt-5.6-luna`)
2. Condition ablation: `none` / `document` / `agent` on the same 100+100 suite
3. Cost–safety Pareto (tokens/USD vs recovery) for BPD vs baselines
4. Fair defense compare: source-over-scan rule vs BPD under matched prompt/token budget
5. Harder code tasks (multi-file SE) and qualitative audit of BPD detection misses
6. Replication scripts that regenerate all paper tables from `results/` JSON with fixed bootstrap seed

## Skill Routing by Phase

Before executing any plan task, consult this table and invoke every listed skill for the task's phase. This table supplements the plan's `Skills involved` field — use the union of both. `academic-baseline` and `replication-driven-research` are mandatory on every task in every phase and are not repeated below.

| Phase | Mandatory skills to invoke |
|---|---|
| Literature | `literature-search`, `citation-management` |
| Collection | `data-collection` |
| Preparation | — (mandatory baseline skills only) |
| Exploratory Analysis | `statistical-modeling`, `tables-and-figures` |
| Main Analysis | `statistical-modeling`, `tables-and-figures` |
| Robustness | `robustness-checks`, `tables-and-figures` |
| Writing | `paper-writing` (main session only, never subagent), `tables-and-figures` (table/figure fixes surfaced while writing), `compile-latex` |
| Review | `paper-review` (standalone audit via `/superpapers:paper-review`; also runs as the blocking Submission-phase audit) |
| Submission | `journal-selection` (if outlet not fixed), then `journal-guidelines`, `compile-latex`, `paper-review` (audit-and-remediate until "go") |
