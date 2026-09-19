---
name: superpaper-review
description: Use when a chapter draft exists and needs checking — reviews logic flow, citations, cross-chapter consistency, and style compliance, then outputs structured review notes with severity levels
---

# Review

## When to Use

- A chapter draft exists (`writings/<ch>/draft.md`) and needs review
- User says "review chapter N", "check my draft", "is the argument solid?", "check citations"
- After a round of drafting — completing the draft ↔ review loop
- Before finalizing a chapter (pre-submission check)

## Procedure

### 1. Identify the chapter

Ask (or infer from context): which chapter? (`writings/<ch>/`)

### 2. Read inputs

Read in this order:

1. `writings/<ch>/draft.md` — the draft to review
2. `writings/<ch>/outline.md` — intended argument structure (if it exists)
3. `meta/style/style-guide.md` — style expectations
4. All other `writings/*/draft.md` files — for cross-chapter consistency checks
5. Index of `references/literature/` — to verify citations exist in the project

### 3. Run the six checks

#### Check 1: Logic flow

- Does the argument hold from section to section? Is there a clear through-line?
- Are transitions between sections clear and logical?
- Does the evidence provided actually support the claims made?
- Are there unsupported logical leaps?
- Does the chapter structure match the argument outlined in outline.md?

#### Check 2: Citation check

- Are empirical claims backed by citations?
- Are there unfilled `[CITE]` markers remaining?
- Do cited citekeys in `[citekey]` format (e.g., `[bail2018]`) exist as directories in `references/literature/`?
- Are in-text citations written as `[citekey]` (square brackets)? Flag any citations written as `(citekey)` or `@citekey` as format errors.
- Are there citations that look fabricated or inconsistent with available literature?

#### Check 3: Cross-chapter consistency

- Read all other `writings/*/draft.md` files
- Does this chapter contradict claims made in other chapters?
- Are key terms and concepts defined consistently across chapters?
- Do any figures, statistics, or arguments conflict with other chapters?

#### Check 4: Style compliance

- Does the prose match `meta/style/style-guide.md`?
- Is sentence length consistent with the style samples?
- Is hedging language appropriate and consistent?
- Is citation format correct and consistent?

#### Check 5: Completeness

- Count remaining `[TODO]` markers — content not yet written
- Count remaining `[DATA]` markers — results not yet integrated
- Count remaining `[CITE]` markers — citations not yet resolved
- Are there sections that exist only as placeholder headers?

#### Check 6: Academic rigor

- Is hedging appropriate — are claims proportional to the evidence?
- Are there overreaching conclusions not supported by the data?
- Is the academic register maintained throughout?
- Are causal claims distinguished from correlational ones?

### 4. Write the review file

Create `writings/<ch>/reviews/YYYY-MM-DD-review.md` (use today's date).

Structure:

```markdown
# Review: <Chapter Name>
Date: YYYY-MM-DD

## Summary Assessment

[2–4 sentences: overall state of the draft — what is working, what needs the most attention]

## Issues by Severity

### Critical
Issues that undermine the argument or academic credibility — must fix before submission.

- **[Logic | Citation | Consistency | Style | Completeness | Rigor]** — [specific description]
  - Location: [section heading or approximate location in draft]
  - Suggestion: [concrete fix]

### Important
Issues that weaken the chapter but do not break it — should fix before finalization.

- **[type]** — [specific description]
  - Location: [section]
  - Suggestion: [concrete fix]

### Minor
Polish items — improve clarity or style but not urgent.

- **[type]** — [specific description]
  - Location: [section]
  - Suggestion: [concrete fix]

## Marker Summary
- [TODO] remaining: N
- [CITE] remaining: N
- [DATA] remaining: N

## Next Step
Run `draft` to address the Critical and Important issues above.
Focus first on: [top 1–2 items]
```

**Issue descriptions must be specific, not vague:**
- Bad: "The argument is unclear."
- Good: "Section 2.3 claims X causes Y but cites only correlational evidence (bail2018). Either hedge the claim ('is associated with') or add experimental evidence."

Line-level suggestions should quote the exact phrase in question where possible.

### 5. Report to the user

After writing the review file, tell the user:

> Review written to `writings/<ch>/reviews/YYYY-MM-DD-review.md`
>
> **Summary:** [2-sentence assessment]
>
> **Top issues:**
> 1. [Critical issue 1]
> 2. [Critical issue 2 or first Important issue]
>
> **Markers remaining:** [TODO]: N, [CITE]: N, [DATA]: N
>
> Run `draft` to revise — address Critical issues first.

## Inputs

- `writings/<ch>/draft.md` — the draft to review
- `writings/<ch>/outline.md` — intended argument (optional but useful)
- `meta/style/style-guide.md` — style expectations
- `writings/*/draft.md` — other chapter drafts for consistency check
- `references/literature/` index — to verify citekeys exist

## Outputs

- `writings/<ch>/reviews/YYYY-MM-DD-review.md` — structured review with:
  - Issues by severity (Critical / Important / Minor)
  - Specific line-level suggestions, not vague feedback
  - Summary assessment
  - Marker counts ([TODO], [CITE], [DATA])

## Notes

- Severity levels are not optional: every issue must be classified as Critical, Important, or Minor
- **Critical** = breaks the argument or academic credibility; **Important** = weakens but doesn't break; **Minor** = polish
- Suggestions must be specific and actionable — quote the problematic text where possible
- Cross-chapter consistency check requires reading other drafts; if no other drafts exist, note this
- After review, always suggest running `draft` to revise — this closes the draft ↔ review loop
- If `[CITE]` markers reference sources not in `references/literature/`, flag as Critical: the user may need to run `ingest` or `research` first
- Do not fabricate issues — only report what is genuinely present in the text
- Academic rigor check: hedging must be proportional to evidence strength; flag both over-hedging (weakens a well-supported claim) and under-hedging (overstates a weak finding)
- The review file is dated so the draft ↔ review history is preserved; do not overwrite previous reviews
