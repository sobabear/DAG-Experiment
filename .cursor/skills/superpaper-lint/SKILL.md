---
name: superpaper-lint
description: Use when auditing the manuscript for quality issues — scans writings/*/draft.md for unfilled markers, cross-chapter contradictions, stale references, orphaned citations, and style drift, then produces a prioritized audit report
---

# Lint

## When to Use

- Periodic quality check on the manuscript (e.g., before a review meeting or submission push)
- User says "audit my paper", "check for issues", "run lint", "what's incomplete?"
- After a major drafting or revision session to catch regressions
- Before running `export` to ensure the manuscript is clean

## Procedure

SuperPaper does NOT fix issues. This skill reports them so the user can address each with the appropriate skill (`draft`, `review`, `ingest`, etc.).

### 1. Confirm project exists

Check that `writings/` exists in the current working directory. If not, stop:

> "No `writings/` directory found. Is this a superpaper project? Run `init` to set one up."

### 2. Scan for unfilled markers

Search only `writings/*/draft.md` files for unfilled placeholder markers. Do NOT scan `outline.md`, `status.md`, or `resources.md` — those files contain planning notes that are a normal part of the workflow, not manuscript issues.

**Outline files and status files have their own `[TODO]` markers that are part of normal planning — these are NOT manuscript issues and should not be flagged by lint.**

Marker types to scan for:
- `[TODO]` — planned content not yet written in the draft
- `[CITE]` — citation needed (two subtypes; see below)
- `[DATA]` — data reference or figure not yet inserted

#### [CITE] marker subtypes

The lint skill distinguishes between two kinds of `[CITE]` markers:

1. **Resolvable `[CITE: citekey]`** — contains a specific citekey (e.g., `[CITE: bail2018]`). Check whether `references/literature/<citekey>/` exists. If it does, the citation can be filled in. If it does not, flag as Critical: missing reference.

2. **Unresolvable `[CITE: description]`** — contains a descriptive note instead of a citekey (e.g., `[CITE: need a meta-analysis showing filter bubble effects are exaggerated]`). These cannot be automatically resolved — flag as Warning: unresolved placeholder citation. The user must find the source and replace the description with a citekey.

Report these under separate subcategories in the audit report.

For each marker found, record:
- File path (e.g., `writings/ch02-lit-review/draft.md`)
- Line number and surrounding context (one line before and after)

Count totals: N `[TODO]`, M `[CITE]` (M1 resolvable + M2 unresolvable), P `[DATA]`.

### 3. Check cross-chapter contradictions

Read all `writings/ch*/draft.md` files. Look for claims that directly conflict across chapters:

- Contradictory factual statements (e.g., "sample size is 500" in ch03 vs "sample size is 450" in ch04)
- Contradictory theoretical positions (e.g., "X causes Y" in ch02 vs "X does not cause Y" in ch05)
- Inconsistent terminology for the same concept

For each potential contradiction, record:
- The two conflicting passages with their locations
- A brief note on why they appear to conflict

If no contradictions are detected, report "No cross-chapter contradictions found."

### 4. Check stale references

For each chapter, read `writings/<ch>/resources.md` (if it exists) and extract the citekeys listed there.

Then check whether a corresponding directory exists in `references/literature/`. A citekey is **stale** if:
- It appears in `resources.md` but has no directory in `references/literature/`

For each stale reference, record:
- The citekey
- The chapter that references it (`writings/<ch>/resources.md`)

### 5. Check orphaned citations

Read all directories listed under `references/literature/`. A citation is **orphaned** if:
- Its citekey does not appear in any `writings/<ch>/resources.md` file
- Its citekey does not appear in any `writings/<ch>/draft.md` file

For each orphaned citation, record:
- The citekey (`references/literature/<citekey>/`)

Orphaned citations are not errors — they may be background reading — but they should be reviewed.

### 6. Check style drift

Read `meta/style/style-guide.md` (if it exists). Scan `writings/<ch>/draft.md` files for passages that deviate from the documented style. Common patterns to flag:

- Sentences significantly longer than the guide's recommended length
- Use of first person ("I think", "we believe") if the guide prohibits it
- Passive voice overuse if the guide favors active voice
- Inconsistent heading capitalization (Title Case vs. sentence case)
- Hedging phrases not in the approved list

If `meta/style/style-guide.md` does not exist, skip this check and note it in the report.

### 7. Produce audit report

Present a structured **Audit Report**:

```
## Audit Report

**Scanned:** [timestamp or "all writings/ chapters"]
**Chapters found:** [list of ch* directories scanned]

---

### Summary

| Category              | Count |
|-----------------------|-------|
| [TODO] markers        | N     |
| [CITE] resolvable     | M1    |
| [CITE] unresolvable   | M2    |
| [DATA] markers        | P     |
| Contradictions        | Q     |
| Stale references      | R     |
| Orphaned citations    | S     |
| Style drift passages  | T     |

---

### Critical — Must fix before export

**Cross-chapter contradictions** (Q found)
- [ch02 draft.md:45] "X causes Y ..."
  vs [ch05 draft.md:12] "X does not affect Y ..."
  → Likely conflict: opposing causal claims about X

**Stale references** (R found)
- `bail2018` — cited in writings/ch02-lit-review/resources.md but missing from references/literature/
- ...

---

### Warning — Should address before submission

**Unfilled [TODO] markers** (N found)
- writings/ch01-intro/draft.md:23 — [TODO: add motivation paragraph]
- writings/ch03-methods/draft.md:67 — [TODO: describe sampling procedure]
- ...

**Unfilled [CITE] markers** (M found)
- writings/ch02-lit-review/draft.md:14 — "According to [CITE], deliberation..."
- ...

**Unfilled [DATA] markers** (P found)
- writings/ch04-results/draft.md:88 — "As shown in [DATA: figure 4.1]..."
- ...

---

### Info — Review when convenient

**Orphaned citations** (S found)
- references/literature/chen2019/ — not referenced in any chapter
- ...

**Style drift** (T passages found)
- writings/ch03-methods/draft.md:102 — sentence length exceeds guide maximum (~45 words)
- writings/ch02-lit-review/draft.md:57 — passive construction flagged
- ...
```

Severity levels:
- **Critical**: Cross-chapter contradictions, stale references (citations in resources.md that can't be resolved) — these affect factual integrity
- **Warning**: Unfilled `[TODO]`, `[CITE]`, `[DATA]` markers — content is incomplete
- **Info**: Orphaned citations, style drift — worth reviewing but not blocking

### 8. Recommend next steps

After the report, suggest appropriate skills:

- Contradictions → `superpaper-review` on the affected chapters
- Stale references → `superpaper-ingest` to add missing literature
- Unfilled markers → `superpaper-draft` on the affected sections
- Orphaned citations → review manually; add to a chapter or remove
- Style drift → `superpaper-review` with style focus

## Inputs

- `writings/*/draft.md` files only — scanned for markers, contradictions, style drift (outline.md, status.md, resources.md are excluded)
- All `writings/ch*/resources.md` files — scanned for citekeys (stale reference check)
- All `references/literature/` directories — compared against resources.md (stale + orphan checks)
- `meta/style/style-guide.md` — used for style drift check (skipped if absent)

## Outputs

- **Audit report** with summary counts and severity-classified issue list
- File locations (path + line number) for every issue found
- Recommended next skill for each category of issue

## Notes

- This skill does NOT fix issues — it reports them for the user to address
- If `writings/` is empty or has no draft.md files with content, report that and stop
- Contradiction detection is heuristic — flag suspected contradictions, not certainties; the user confirms
- Style drift detection is approximate — flag obvious deviations, not every stylistic choice
- Run lint periodically, not just before submission; catching contradictions early saves significant revision effort
- After fixing issues, re-run lint to confirm the report is clean before export
- Severity levels follow the pattern: Critical (factual integrity), Warning (completeness), Info (polish)
