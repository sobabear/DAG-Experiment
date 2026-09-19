---
name: superpaper-brainstorm
description: Use when exploring research topics, directions, or pivots — early-stage ideation or mid-project course correction around a research question
---

# Brainstorm

## When to use

- User is exploring potential research topics and has not settled on one yet
- User wants to pivot from their current direction mid-project
- User has a broad area of interest but needs to narrow it to a specific research question
- User is unsure whether a direction is feasible or novel enough

This skill is about RESEARCH TOPICS — it is not for brainstorming software features or writing structure. For those, see other tools.

## Procedure

This skill is conversational. Do not generate a list of ideas immediately. Ask first, listen, then help narrow.

### Step 1 — Understand interests and context

If the user has already stated their research area in the triggering message (e.g., "I want to explore X"), treat that as the answer to step 1 and proceed directly to step 2 (data/methods/feasibility questions). Don't waste a turn asking them to restate what they already said.

Otherwise, ask the user (one or two questions at a time, not a wall of questions):

- What broad field or subfield are you working in?
- What topics or puzzles have you found most interesting recently?
- Do you have a sense of the field gaps you want to address, or are you still exploring?
- What kind of contribution are you aiming for — theoretical, empirical, or both?

### Step 2 — Probe for constraints

Before generating directions, understand feasibility constraints:

- **Data availability**: Is relevant data accessible? Public datasets, original surveys, administrative data?
- **Methods mastery**: What quantitative or qualitative methods are you comfortable with, or willing to learn?
- **Advisor alignment**: Does your advisor have a preferred direction or known expertise?
- **Timeline**: Dissertation or journal article? How much time do you have?

### Step 3 — Generate candidate research directions

Based on the conversation, produce 3–5 research directions. For each:

```
Direction: [one-sentence statement of the research question]
Theoretical contribution: [what gap in the literature it fills]
Empirical tractability: [how feasible it is to actually do]
Novelty: [why it's not already done / what's new]
Data/method sketch: [quick note on what you'd need]
Feasibility: HIGH / MEDIUM / LOW — [brief reason]
```

### Step 4 — Narrow together

Ask the user which directions resonate. Discuss trade-offs. Help them land on 1–2 directions worth pursuing.

### Step 5 — Offer a Deep Research delegation prompt (optional)

If the user wants to explore the literature around a promising direction before committing, offer to generate a ready-to-copy prompt for a Deep Research agent (Gemini Deep Research or GPT Deep Research):

```
Topic: [refined research question]
Field: [user's field]
Find: peer-reviewed journal articles, highly cited
For each paper return:
- Authors, year, journal
- Citation count
- Abstract
- Main argument/finding
- Why it's relevant to [the specific direction]
- Citekey suggestion (author+year format)

Prioritize: [key journals or authors if known]
Keywords (EN): [list]
Keywords (ZH): [list]
```

Tell the user: "Paste this into Gemini Deep Research or GPT Deep Research. When you have results, run `ingest` to bring them into the project."

## Inputs

- User's stated interests (gathered conversationally)
- Field context (discipline, subfield)
- Constraints: data access, methods, advisor, timeline

Optional (if project already exists):
- `meta/memory.md` — check for any previous direction decisions
- `meta/progress.md` — check how far along the project is

## Outputs

- 3–5 candidate research directions with feasibility assessment
- Narrowed recommendation (1–2 directions)
- Optional: ready-to-copy Deep Research prompt for literature exploration

## Notes

- Do not rush to generate directions. The conversational exploration step is where value is created.
- Feasibility matters as much as novelty. A brilliant direction that requires inaccessible data is not viable.
- If `meta/memory.md` exists, read it first — the user may have made prior direction decisions that should not be ignored.
- After brainstorming, the natural next step is `research` (to find literature on the chosen direction) or `ingest` (if the user already has papers).
- If the user is mid-project and considering a pivot, acknowledge the cost of pivoting before generating alternatives.
- **Never fabricate citations or paper titles during brainstorming.** If you reference a paper or author, only do so if you're confident it exists. Use general phrasing like "some research suggests..." or "similar to work on X" instead of naming papers unless you're sure.
