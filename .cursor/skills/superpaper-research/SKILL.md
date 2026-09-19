---
name: superpaper-research
description: Use when a literature gap has been identified and a search strategy is needed — generates search keywords, database recommendations, and ready-to-copy prompts for Deep Research agents
---

# Research

## When to use

- A research direction or gap has been identified (typically after `brainstorm`)
- User needs a systematic search strategy for literature
- User wants to delegate literature discovery to Gemini Deep Research or GPT Deep Research
- User prefers to search databases manually and needs a structured keyword kit

**CRITICAL: This skill does NOT do research itself.** It generates search strategy and prompts. Actual literature discovery is delegated to Deep Research agents or done manually by the user.

## Procedure

### Step 1 — Clarify the search target

If not already clear, ask:

- What is the specific research question or gap you are searching around?
- What field and subfield?
- Do you have any anchor papers or authors already? (These help seed the search.)
- Are you looking for theoretical foundations, empirical studies, or both?
- Language preference: do you need Chinese-language literature (CNKI, CSSCI)?

### Step 2 — Generate both paths

By default, generate both Path A and Path B in one response. Present both paths simultaneously — the user may want to delegate some searches (Path A) while doing others manually (Path B). Do not require the user to choose first.

- **Path A: Delegated Deep Research** — ready-to-copy prompt for Gemini or GPT Deep Research. Faster, broader synthesis, good first pass.
- **Path B: Manual Search Kit** — keywords and database recommendations the user searches themselves. More control, better for niche topics.

### Step 3A — Path A: Delegated Deep Research

Generate a ready-to-copy prompt the user can paste directly into Gemini Deep Research or GPT Deep Research:

```
Topic: [specific research question]
Field: [user's field and subfield]
Find: peer-reviewed journal articles, highly cited
For each paper return:
- Authors, year, journal
- Citation count
- Abstract
- Main argument/finding
- Why it's relevant to [specific research question]
- Citekey suggestion (author+year format)

Prioritize: [specific journals or authors if known]
Keywords (EN): [list of English search terms]
Keywords (ZH): [list of Chinese search terms]
```

Tell the user: "Paste this into Gemini Deep Research or GPT Deep Research. When you have results, run `ingest` to process them into the project."

### Step 3B — Path B: Manual Search Kit

Generate a structured search kit:

```
Suggested keywords:
  English: [terms with Boolean combinations, e.g., "political polarization" AND "social media" NOT "echo chamber"]
  Chinese: [terms, e.g., 政治极化、社交媒体、舆论分化]

Suggested databases:
  CSSCI — Chinese Social Sciences Citation Index (Chinese journals)
  Web of Science — peer-reviewed international journals
  JSTOR — humanities and social sciences archive
  Google Scholar — broad discovery, check citations
  CNKI — Chinese National Knowledge Infrastructure (Chinese theses, journals)

Suggested authors to check: [names active in this area]
Suggested journals: [top journals for this topic and field]

Filter criteria:
  peer-reviewed only
  citation count > 50 for international journals, > 10 for Chinese journals (sociology defaults — adjust for your field)
  publication year: [suggest range based on topic]
```

**Warning:** Only suggest authors you are confident exist in this field. If you're not sure who the active researchers are, leave this field with a note like '[consult advisor for key authors in this subfield]' rather than guessing. Do NOT fabricate author names.

Tell the user: "When you have results, run `ingest` to process them into the project."

## Inputs

- Research question or gap description
- Field and subfield
- Any existing anchor papers or authors
- Language requirements (English only, or Chinese + English)

Optional (if project exists):
- `meta/memory.md` — prior direction decisions and existing references
- `references/literature/` — existing literature to avoid re-searching

## Outputs

**Path A:** Ready-to-copy Deep Research prompt for Gemini or GPT Deep Research, including:
- Structured topic description
- Per-paper return format with citation count and citekey suggestion
- Keywords in English and Chinese

**Path B:** Manual search kit including:
- Boolean keyword combinations in English
- Chinese keyword list
- Recommended databases: CSSCI, Web of Science, JSTOR, Google Scholar, CNKI
- Suggested authors and journals
- Peer-reviewed and citation count filters

Both paths end at: "When you have results, run `ingest` to process them into the project."

## Notes

- Never fabricate citations or pretend to search databases. This skill generates prompts and strategies only.
- Citekey format is author+year, e.g., `bail2018`, `zhang2021` — consistent with Zotero BetterBibTeX convention used across the project.
- For Chinese social science topics, CSSCI and CNKI are essential — do not omit them.
- If the user already has some papers, ask for them before generating keywords — anchor papers dramatically improve keyword quality.
- After this skill, the next step is always `ingest` once the user has literature results.
- Path A (Gemini/GPT Deep Research) is recommended for initial broad sweeps. Path B is better for specialized or niche searches where automated tools underperform.
