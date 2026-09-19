---
name: superpaper-analysis
description: Use when formal confirmatory analysis is needed — generates a rigorous analysis spec with model specifications, robustness checks, and a ready-to-copy prompt for a coding agent
---

# Analysis

## When to Use

- Hypotheses are formed and the user is ready for formal, confirmatory analysis
- User says "I need to run my main analysis", "set up the regression", "specify the model"
- Moving from exploratory data analysis to hypothesis testing
- Analysis plan exists and needs to be translated into a coding spec

## Procedure

SuperPaper does NOT run code itself. This skill generates a formal analysis spec and a ready-to-copy prompt for a coding agent (Claude Code, Codex, or Cursor). The coding agent does the actual analysis.

## Step 0: STOP AND ASK

Before generating any output, you MUST confirm the following. If the answers are already clear from the user's triggering message, verify with a single confirmation question. If any are unclear, ASK BEFORE PROCEEDING. Do not embed these as "clarifying questions" in the output document — ask them conversationally first.

**Mandatory confirmations:**
- Unit of analysis (user-wave, user, post, etc.)
- Operationalization of key variables (how is the DV measured? IV?)
- Available control variables
- Panel structure (number of waves, gaps between waves)

Before asking the user for dataset description, check `references/results/` for existing data-explore specs to avoid redundant questioning.

Only proceed to the next steps once these are confirmed.

### 1. Gather inputs

Ask the user for:

1. **Hypotheses** — the specific claims to test (H1, H2, …)
2. **Data description** — dataset location, format, key variables (or reference the `data-explore` results if available)
3. **Analysis plan** — preferred method (OLS, logistic regression, panel fixed effects, DiD, SEM, etc.)
4. **Chapter mapping** — which chapter sections will use these results

If the user has already provided context, skip the questions and proceed.

### 2. Generate formal analysis spec

Produce a structured **Analysis Spec** covering:

#### Hypotheses
Restate each hypothesis clearly:
- H1: [outcome variable] is [higher/lower/correlated with] [predictor variable] after controlling for [controls]
- H2: …

#### Model Specifications
For each hypothesis, specify:
- **Outcome variable** — name, measurement, expected range
- **Key predictor(s)** — name, measurement, expected direction
- **Controls** — list all control variables with justification
- **Method** — statistical method (e.g., OLS with robust SEs, panel FE with clustered SEs, logistic regression)
- **Unit of analysis** — observation level (individual, country-year, firm, etc.)
- **Sample** — any filtering criteria (year range, geographic scope, eligibility rules)
- **Estimation notes** — weights, clustering level, fixed effects structure

#### Robustness Checks
Specify alternative specifications to test sensitivity of main findings:
- Alternative model (e.g., logit instead of OLS; random effects instead of fixed effects)
- Alternative sample (e.g., drop outliers, restrict to subgroup, extend time window)
- Alternative measurement of key variable (e.g., logged, standardized, lagged)
- Placebo tests (if applicable)
- Sensitivity analysis for missing data (e.g., imputation vs. listwise deletion)

#### Expected Results Format
- Main results table: coefficients, standard errors, p-values, N, R² (or equivalent fit statistics)
- Robustness table: same layout, alternative specifications in columns
- Key figures: coefficient plot, marginal effects plot, or interaction plot (as applicable)

#### Chapter Mapping
State which chapter sections each result feeds:
- Main results table → [Chapter N, Section N.N: e.g., "Ch4 §4.3 Main Findings"]
- Figure X → [Chapter N, Section N.N]
- Robustness table → [Chapter N, Section N.N: e.g., "Ch4 §4.5 Robustness"]

### 3. Generate ready-to-copy prompt

Present this block for the user to copy to their coding agent:

```
Project: [repo path or description]
Task: Formal confirmatory analysis
Input data: [location, format, key variables]
Hypotheses: [list from spec above]
Model: [method, outcome, predictors, controls, sample]
Robustness checks:
- [alternative specification 1]
- [alternative specification 2]
- [sensitivity analysis]
Expected output:
- Main results table to references/results/<key>/results-main.csv
- Robustness table to references/results/<key>/results-robustness.csv
- Figures to references/results/<key>/figures/
- Analysis log / session info to references/results/<key>/session-info.txt
Chapter mapping:
- Main results → [chapter section]
- Robustness → [chapter section]
Notes:
- Save the exact code used to references/results/<key>/analysis-code.[R/py]
- Do not modify source data; work on a copy if transformations are needed
- Use [R/Python — specify] for all analysis
- Include session/environment info for reproducibility
```

Fill in the bracketed fields from the spec. Use the same `<key>` slug as the corresponding `data-explore` run if one exists.

### 4. Capture spec for reproducibility

Tell the user:

> Save this spec as `references/results/<key>/spec.md` — it records exactly what was asked of the coding agent. This is your reproducibility record: if results change, compare against this spec to trace the cause.

### 5. Set expectations and hand off

After presenting the spec and prompt, tell the user:

> Drop results files in `references/results/<key>/` and run `ingest` once the coding agent is done. SuperPaper will link results to the chapter sections listed in the spec and update the project's memory.

## Inputs

- Hypotheses or research questions to test
- Data description (or reference to `data-explore` results)
- Analysis plan (preferred method, controls, sample definition)
- Chapter mapping: which sections will cite these results

## Outputs

- **Formal Analysis Spec** with: model specifications (variables, controls, methods), robustness checks (alternative specifications, sensitivity analysis), expected results format, chapter section mapping
- **Ready-to-copy prompt** for a coding agent (Claude Code, Codex, Cursor) with full context
- Reminder to save `references/results/<key>/spec.md` for reproducibility

## Notes

- SuperPaper does NOT run code or interpret raw output — that is the coding agent's job
- The `spec.md` in `references/results/<key>/` captures exactly what was asked; it is the reproducibility anchor for this analysis
- Robustness checks are not optional: always specify at least two alternative specifications
- The chapter mapping in the spec helps `draft` and `review` skills link results to prose automatically
- After the coding agent returns results, run `ingest` to organize them and update chapter status
- If the analysis plan changes after the spec is written, save a new version of `spec.md` with a date suffix (e.g., `spec-2024-04-10.md`) rather than overwriting
