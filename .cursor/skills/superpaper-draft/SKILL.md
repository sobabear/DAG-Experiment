---
name: superpaper-draft
description: Use when a chapter outline is ready and it's time to write or update prose — produces draft.md with [TODO]/[CITE]/[DATA] markers for missing content
---

# Draft

## When to Use

- Chapter outline exists and it is time to write prose
- User says "write the draft", "draft section X", "continue drafting chapter N"
- Existing draft needs expansion or new sections filled in
- After `outline` is complete and references are ingested

## Procedure

## Step 0: STOP AND ASK

Before generating any output, you MUST confirm the following. If the answers are already clear from the user's triggering message, verify with a single confirmation question. If any are unclear, ASK BEFORE PROCEEDING. Do not embed these as "clarifying questions" in the output document — ask them conversationally first.

**Mandatory confirmations:**
- Target scope: single section or full chapter?
- If single section: which section specifically?
- Has the user made manual edits to draft.md since last run? (If yes, read them first to preserve)

Only proceed to the next steps once these are confirmed.

### 1. Identify the chapter

Ask (or infer from context): which chapter? (`writings/<ch>/`)

Ask: work on a **single section** or the **full chapter**? If a single section, ask which one.

### 2. Read all inputs

Read in this order:

1. `writings/<ch>/outline.md` — argument chain, section structure, evidence map
2. `writings/<ch>/resources.md` — references relevant to this chapter (by citekey)
3. `meta/style/style-guide.md` — writing style extracted from the user's sample paragraphs/chapters
4. For each citekey in resources.md: `references/literature/<citekey>/summary.md`
5. For each results key referenced in outline or resources: `references/results/<key>/summary.md`
6. `writings/<ch>/draft.md` — existing draft (if it exists — **read it before writing anything**)

### 3. Check for an existing draft

If `writings/<ch>/draft.md` exists:

- Read the full file before making any changes
- Identify sections already written by a human (contains non-placeholder prose)
- **Never overwrite human edits without asking**
- If a section appears to have substantive human content, ask: "Section X already has content. Do you want me to revise it, expand it, or leave it unchanged?"
- Only fill in sections that are empty, contain only `[TODO]`, or were explicitly flagged for revision

### 4. Draft the requested content

For each section in scope:

- Write prose following the argument structure in outline.md
- Follow `meta/style/style-guide.md` strictly — match tone, sentence length, hedging style, and citation format from the user's own samples
- Use references from resources.md; insert inline citations by citekey using square brackets: `[bail2018]`
- **Write in-text citations as `[citekey]` (square brackets, not parentheses).** Example: 'Exposure to opposing views increases polarization [bail2018].'
- Integrate data and figures from results summaries where appropriate

#### Marker conventions

Use these markers where content cannot be completed yet:

- `[TODO]` — content that needs to be written but the required information is not available
- `[CITE]` — a claim that needs a citation but the source is unclear; add a note: `[CITE: describe the claim]`
- `[DATA]` — a figure, table, or statistic that needs to be pulled from results; add a note: `[DATA: describe what is needed, e.g., "regression coefficient for X"]`

**Never fabricate citations, statistics, or results.** Use markers instead.

#### Structural completeness

The draft must be structurally complete:

- Every section from outline.md must appear in draft.md
- Sections not yet drafted get a placeholder header with `[TODO]`:
  ```
  ## 2.3 Hypotheses

  [TODO: Draft hypotheses section — see outline.md §2.3 for argument structure]
  ```
- A reader should be able to see the full architecture of the chapter even if some sections are placeholders

#### Writing style

- **Shorter is better** — academic writing should be concise; cut filler phrases
- Match the style extracted in `meta/style/style-guide.md`:
  - Sentence structure and length patterns from the user's samples
  - Hedging conventions (e.g., "suggests", "appears to", "is consistent with")
  - Paragraph structure (topic sentence → evidence → interpretation)
  - Citation style (in-text format, author–year vs. numbered, etc.)
- Do not use first person unless the style guide permits it
- Prefer active voice unless the sample style uses passive

### 5. Write draft.md

Write the updated `writings/<ch>/draft.md`:

- If no existing draft: create the full file with all sections from outline.md
- If existing draft: merge new content, preserving all human-written sections
- Add a header comment showing what was updated and when:
  ```
  <!-- Last drafted: YYYY-MM-DD | Sections updated: [list] -->
  ```

### 6. Update status.md

Update `writings/<ch>/status.md` with the current section states:

```markdown
# <Chapter> Status

## Sections
- <section>: [DRAFTED] — first pass complete
- <section>: [DRAFTING] — partial, needs [TODO] items resolved
- <section>: [OUTLINED] — placeholder only, not yet drafted
- <section>: [HUMAN-EDITED] — contains human content, preserved

## Open Markers
- [TODO] count: N
- [CITE] count: N
- [DATA] count: N

## Last Updated
YYYY-MM-DD by draft
```

### 7. Suggest next steps

After drafting, tell the user:

> Draft updated. Next: run `review` to check logic flow, citations, and style compliance.
>
> Remaining markers:
> - [TODO]: N items need content
> - [CITE]: N items need citations — check references/literature/ for candidates
> - [DATA]: N items need results — check references/results/ or run analysis first

## Inputs

- `writings/<ch>/outline.md` — argument chain and section structure
- `writings/<ch>/resources.md` — citekeys relevant to this chapter
- `meta/style/style-guide.md` — extracted style from user's sample writings
- `references/literature/<citekey>/summary.md` — one per citekey in resources.md
- `references/results/<key>/summary.md` — one per results key referenced
- `writings/<ch>/draft.md` — existing draft (if any); **always read before writing**

## Outputs

- Updated `writings/<ch>/draft.md` — structurally complete draft with [TODO]/[CITE]/[DATA] markers
- Updated `writings/<ch>/status.md` — section states and marker counts

## Notes

- **Never overwrite human edits without asking** — always read the existing draft first
- Structural completeness is required: every section in outline.md must appear in draft.md, even as a placeholder
- Shorter is better — trim filler; academic writing should be dense and precise
- Never fabricate citations or data — use [CITE] and [DATA] markers instead
- The `[DATA]` marker signals that a result from `references/results/` is needed; if the result does not exist yet, the marker tells the user to run analysis first
- Style must match `meta/style/style-guide.md` — this is extracted from the user's own writing samples, not generic academic English
- If `meta/style/style-guide.md` does not exist, remind the user to run `setup-style` with sample paragraphs/chapters before drafting
- After resolving `[CITE]` markers, run `review` to verify citation consistency with `references/literature/`
