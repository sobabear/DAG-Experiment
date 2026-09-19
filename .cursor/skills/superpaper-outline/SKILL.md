---
name: superpaper-outline
description: Use when starting or rethinking a chapter — builds an argument-chain outline grounded in available evidence, with claim/evidence/source structure and [TODO] markers for gaps
---

# Outline

## When to Use

- Starting a new chapter and need to map the argument before writing
- Rethinking an existing chapter's structure
- User says "outline chapter N", "structure this chapter", "plan the argument for chapter N"
- References have been ingested and the user is ready to plan how to use them

## Procedure

### 1. Gather inputs

If chapter topic and slot are already clear from the user's triggering message (e.g., "outline chapter 2 — my literature review"), skip asking them to restate what they just said and proceed directly to loading resources.

Otherwise, ask the user for:

1. **Chapter topic** — the specific question or argument this chapter addresses
2. **Chapter slot** — which chapter number / folder (e.g., `writings/ch02-theory/`)

If `writings/<ch>/resources.md` exists, read it for the list of available references. If not, ask the user to list the citekeys they expect to use.

### 2. Load available evidence

For each citekey listed in `writings/<ch>/resources.md`:

1. Check if `references/literature/<citekey>/summary.md` exists
2. If yes: read the summary — note the main argument, key findings, and relevance
3. If no: note the gap — this reference is listed but not yet summarized

Do not fabricate reference content. Only work with what is in the `summary.md` files.

### 3. Map argument chain and evidence

Before writing the outline, construct an internal argument map:

- **Main thesis**: What is the central claim this chapter will make?
- **Supporting arguments**: What 3–5 sub-claims build toward the thesis?
- **Evidence inventory**: Which references support which sub-claims? Be specific.
- **Logic chain**: How does sub-claim 1 lead to sub-claim 2 lead to … lead to the thesis?
- **Gaps**: Which sub-claims lack supporting evidence?

This is your evidence map — it drives the outline structure. Only outline sections you can support.

### 4. Write writings/<ch>/outline.md

Create `writings/<ch>/outline.md` with the following structure:

```markdown
# Chapter [N]: [Title]

## Main Argument / Thesis
[One clear sentence stating what this chapter argues]

## Argument Chain
[How the sections connect: Section 1 establishes X, which enables Section 2 to argue Y, which together support the thesis Z]

---

## Section 1: [Title]

**Claim:** [What this section argues — one sentence]

**Evidence:**
- `[citekey]`: [specific finding or argument that supports the claim]
- `[citekey]`: [specific finding or argument]

**Logic to Section 2:** [How this section's conclusion sets up the next section]

**Transition note:** [Draft transition sentence or idea]

---

## Section 2: [Title]

**Claim:** [What this section argues]

**Evidence:**
- `[citekey]`: [specific finding]
- `[citekey]`: [specific finding]

**Logic to Section 3:** [Connection to next section]

**Transition note:** [Draft transition]

---

[Continue for each section...]

---

## Evidence Gaps

[TODO: need more literature on X — claim in Section N lacks support]
[TODO: need more literature on Y — Section N argument is thin]

## Open Questions
- [Any unresolved tensions or ambiguities the draft will need to address]
```

Fill in bracketed placeholders from the actual evidence loaded in Step 2.

### 5. Mark insufficient sections

For any section where evidence is thin or missing:

- Mark the section with `[TODO: need more literature on X]`
- Add the gap to the **Evidence Gaps** section at the bottom
- Do NOT invent claims that aren't supported — leave the section skeleton with TODO markers
- Suggest running `research` if a gap is significant

### 6. Update writings/<ch>/status.md

Update `writings/<ch>/status.md` to mark the chapter as `[OUTLINED]` and list the sections now planned:

```markdown
# <Chapter Name> Status

## Sections
- <section 1>: [OUTLINED] — ready to draft
- <section 2>: [OUTLINED] — ready to draft
- <section N>: [TODO: need more literature] — gap identified, resolve before drafting

## Blockers
[Any gaps from Evidence Gaps section that block drafting]

## Last Updated
YYYY-MM-DD by outline
```

### 7. Confirm and suggest next steps

After writing the outline, tell the user:

> `writings/<ch>/outline.md` is ready. The argument chain is:
> [one-line summary of the logic chain]
>
> [N] sections have [TODO] markers for missing evidence — consider running `research` for: [list gaps].
>
> When you're ready to write, run `draft` — it will use this outline and `meta/style/style-guide.md`.

## Inputs

- Chapter topic and chapter folder (e.g., `writings/ch02-theory/`)
- `writings/<ch>/resources.md` — list of available references by citekey
- `references/literature/<citekey>/summary.md` — one file per reference (read as needed)
- `meta/style/style-guide.md` — optional, not used in outlining but good to be aware of

## Outputs

- `writings/<ch>/outline.md` containing:
  - Main argument / thesis for this chapter (one clear sentence)
  - Argument chain narrative (how sections connect)
  - Section-by-section breakdown: claim → evidence → source citekey → logic link → transition note
  - Evidence map (which citekeys support which claims)
  - [TODO] markers for sections with insufficient evidence
  - Evidence Gaps section listing what additional literature is needed

## Notes

- **Ground every section in available evidence** — do not outline sections you cannot support. It is better to have a shorter outline with strong evidence than a long outline with invented support.
- **[TODO] markers are first-class citizens** — a `[TODO: need more literature on X]` is honest and useful; a fabricated claim is not
- The argument chain is the most important part of the outline: if sections don't connect logically, the chapter will not hold together even with good evidence
- Transition notes between sections are seeds for the actual transition sentences in the draft — they save significant time in `draft`
- If `resources.md` is empty or missing, prompt the user to run `ingest` or `research` before outlining — a section-less outline is rarely worth writing
- The `draft` skill reads `outline.md` directly — keep section headers consistent with the structure expected by `draft`
- Step 6 (Update status.md) is a required numbered step — do not skip it
