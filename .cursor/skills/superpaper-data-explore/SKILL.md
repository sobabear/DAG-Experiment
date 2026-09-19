---
name: superpaper-data-explore
description: Use when a new dataset arrives and you need to understand it before formal analysis — generates an exploratory analysis spec and a ready-to-copy prompt for a coding agent
---

# Data Explore

## When to Use

- User says "I have a new dataset" or "I need to understand my data"
- Data has been added to the project and its structure is unknown
- Before formal analysis: need to check distributions, quality, and relationships
- User asks "what should I explore first?" about data

## Procedure

SuperPaper does NOT run code itself. This skill generates a spec and a ready-to-copy prompt for a coding agent (Claude Code, Codex, or Cursor). The coding agent does the actual exploration.

## Step 0: STOP AND ASK

Before generating any output, you MUST confirm the following. If the answers are already clear from the user's triggering message, verify with a single confirmation question. If any are unclear, ASK BEFORE PROCEEDING. Do not embed these as "clarifying questions" in the output document — ask them conversationally first.

**Mandatory confirmations:**
- Dataset format (CSV, Parquet, JSON, etc.) and location
- Key variables and their types
- Panel vs. cross-sectional (can user_id be linked across observations/waves?)
- Definition of the population of interest (e.g., what counts as "political topic")

Only proceed to the next steps once these are confirmed.

### 1. Gather inputs

Ask the user for:

1. **Dataset description** — location, file format (CSV, Stata, Excel…), approximate size, key variables
2. **Research questions** — what they are ultimately trying to answer
3. **Any known issues** — suspicions about data quality, known missing data patterns, transformations already applied

If the user has already provided this context, skip the questions and proceed.

### 2. Generate analysis spec

Produce a structured **Exploratory Data Analysis Spec** covering:

#### Key Questions to Answer
- What is the shape and coverage of the data? (rows, columns, time span, geographic scope)
- Are variables measured as expected? (types, ranges, units)
- What is the missing data pattern? (MCAR / MAR / MNAR signals)
- Are there obvious outliers or anomalous observations?
- What are the distributions of key variables? (continuous: mean, SD, skew; categorical: frequency tables)
- Are there correlations between key variables relevant to the research questions?
- Are there subgroup differences worth noting (e.g., by year, region, category)?

#### Suggested Exploration Steps
Present in this order:

1. **Overview** — row count, column count, dtypes, memory usage
2. **Missing data** — count and percentage per variable; visualize missingness pattern (missingno matrix if Python, `naniar` if R)
3. **Distributions** — histograms / density plots for continuous variables; bar charts for categorical; note skew and outliers
4. **Outliers** — IQR fences or z-score flags; list extreme observations
5. **Correlations** — correlation matrix for numeric variables; highlight strong pairs (|r| > 0.5)
6. **Time trends** (if panel/time-series) — plot key variables over time; check for structural breaks
7. **Subgroup comparisons** (if applicable) — group means, variance by key categorical variable
8. **Data quality flags** — duplicate rows, impossible values, inconsistent coding

**Optional: Network structure (if dataset includes user-to-user relationships or repost chains):**
- Visualize the repost/interaction network
- Compute basic network metrics (degree distribution, clustering coefficient)
- Community detection (Louvain, Leiden)
- Tools: Python `networkx`, R `igraph`

#### Expected Output Format
- Figures saved as PNG/PDF (one file per chart or combined PDF report)
- Summary statistics table (CSV or markdown)
- Data quality report (markdown listing flags and counts)

### 3. Generate ready-to-copy prompt

Present this block for the user to copy to their coding agent:

```
Project: [repo path or description]
Task: Exploratory data analysis
Dataset: [location, format, key variables]
Questions: [what to explore — paste from Key Questions above]
Expected output:
- Figures saved to references/results/<key>/figures/
- Summary statistics to references/results/<key>/summary-stats.csv
- Data quality report to references/results/<key>/data-quality.md
Notes:
- Do not modify the source data
- Use [Python/R — specify] for all analysis
- Save all figures at 300 DPI
- Include a brief interpretation comment with each figure
```

Fill in the bracketed fields based on what the user told you. When choosing a `<key>` slug for the results directory, use: lowercase, hyphenated, format `<topic>-<type>[-<year>]`. Examples: `weibo-eda-2023`, `polarization-model`, `sentiment-baseline`.

### 3b. Save the spec

Save this spec to `references/results/<key>/spec.md` before handing off to the coding agent. This records what was asked, enabling reproducibility if the coding agent is re-run or results change.

### 4. Set expectations and hand off

After presenting the spec and prompt, tell the user:

> Drop figures in `references/results/<key>/figures/` and run `ingest` once the coding agent is done. SuperPaper will organize the results and link them to the relevant chapter sections.

## Inputs

- Dataset description (location, format, key variables)
- Research questions the data will help answer
- Any known data quality concerns

## Outputs

- **Exploratory Data Analysis Spec** covering: key questions, suggested exploration steps (distributions, correlations, outliers, missing data), expected output format
- **Ready-to-copy prompt** for a coding agent (Claude Code, Codex, Cursor) with full context

## Notes

- SuperPaper does NOT run code or interpret raw data files — that is the coding agent's job
- The spec intentionally covers standard EDA steps; skip steps that don't apply to the dataset type
- If the user already has some EDA done, skip those steps and focus on gaps
- The `<key>` slug in `references/results/<key>/` should be consistent with any later `analysis` run on the same dataset
- After the coding agent returns results, run `ingest` to organize them into the project
