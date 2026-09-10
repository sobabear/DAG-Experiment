# Literature notes — Poison attribution in coding-agent DAGs

**Status:** seed notes for paperization (full literature-search pass deferred to Writing).  
**Date:** 2026-09-09  
**Outlet bias:** ACL/EMNLP Findings, agent workshops, arXiv cs.MA / cs.AI.

## State of the field

- Multi-agent LLM systems are studied for collaboration resilience under faulty or corrupt agents, and for security under external adversarial inputs (malicious issues, skills, tools).
- Attribution / provenance work (e.g. VeriTrail-style tracing) largely targets text/QA pipelines rather than tool-using coding agents with hidden tests.
- Coding-agent security benchmarks emphasize **external** attacker channels, not an **internal** collaborator fed a planted lie during cooperative work.

## Methods and data typical in the area

- Debate / MMLU-style multi-agent evaluation for cascade defenses.
- Synthetic fault injection into agent graphs (topology resilience studies).
- Signed-DAG / contribution scoring (BPD) for corruption detection in multi-agent systems.
- Agent coding benchmarks with pass@k / Index-style correctness (orthogonal to attribution metrics).

## Papers this work positions against

| Theme | Anchor (verify before citing in camera-ready) | Positioning |
|-------|-----------------------------------------------|-------------|
| Contribution backpropagation | BPD (arXiv:2510.19420) | We port the *mechanism* to a tool-using coding harness with pytest ground truth, not a new algorithm paper. |
| Topology vs faulty agents | arXiv:2408.00989 | Motivates hierarchy vs flat comparison; our naive hierarchy *fails* under poisoned scan — topology alone insufficient. |
| Byzantine-robust multi-agent LLMs | arXiv:2605.09076 | Motivates independent judge vs self-report. |
| Provenance / tracing | VeriTrail arXiv:2505.21786 | Same “where did the wrong claim enter” question; different domain (not coding tools). |
| External coding-agent attacks | IssueTrojanBench / MalSkillBench / SkillJect (names from prior survey — re-verify) | External vs internal collaborator channel. |

## Recent target-venue-adjacent work

- Agent safety under pressure / normative drift appearing in ACL Findings tracks (re-check Anthology before citing).
- REALM-style LLM-agent workshops at ACL/EMNLP (venue fit for workshop track).

## Contribution claim (draft, non-causal)

Empirical evidence that in a tool-using coding-agent setting, a BPD-style attribution path is associated with higher detection/recovery under strong internal poison than a no-attribution single-loop agent, while a hierarchical pipeline that trusts a poisoned scan node can show higher lie propagation than the single-loop baseline — unless an explicit source-over-scan rule is added (exploratory defense).
