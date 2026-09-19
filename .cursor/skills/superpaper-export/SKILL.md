---
name: superpaper-export
description: Use when preparing the final submission document — merges all chapter drafts in order, formats citations, assembles front matter, and generates output in the requested format (markdown, LaTeX prompt, or Word prompt)
---

# Export

## When to Use

- User says "export my paper", "prepare for submission", "generate the final document", "compile all chapters"
- Manuscript is ready (or near-ready) for submission or advisor review
- A single merged document is needed from the individual chapter drafts

## Procedure

### 0. Ask export mode

Before doing anything else, ask the user:

> "Is this export for **advisor review** (include all chapters with placeholders for missing ones) or for **submission** (only include chapters with substantive content)?"

- **Review mode**: include all chapters; insert `[Chapter N: <title> — draft pending]` for empty chapters
- **Submission mode**: skip chapters with no substantive draft content; only include chapters with actual prose

### 1. Pre-export check: warn about remaining markers

Before merging anything, scan all `writings/ch*/draft.md` files for unfilled markers:

- `[TODO]` — unwritten content
- `[CITE]` — unfilled citations
- `[DATA]` — missing data or figures

If any are found, present a warning:

```
⚠️  Pre-export warnings found:
  - 3 [TODO] markers
  - 5 [CITE] markers
  - 2 [DATA] markers

These will appear in the exported document. Run `lint` for the full list.
Proceed with export anyway? (yes/no)
```

Wait for the user to confirm before proceeding. They may want to resolve issues first using `draft` or `review`.

### 2. Determine chapter sources

Check for git-tagged final versions first:

1. Run `git tag -l "final-ch*"` to list any chapter-level final tags
2. If a tag like `final-ch02` exists, use that tagged version of `writings/ch02-*/draft.md` instead of HEAD
3. If no tags exist, use HEAD versions of all draft.md files

Report which source is used for each chapter:

```
Chapter sources:
  ch01-intro:        HEAD (no final tag)
  ch02-lit-review:   git:final-ch02
  ch03-methods:      HEAD (no final tag)
```

### 3. Collect chapters in order

List all `writings/ch*/` directories and sort them alphanumerically:
`ch01`, `ch02`, `ch03`, ... (zero-padded, so natural sort is correct order).

For each chapter directory in order:
1. Check if `writings/<ch>/draft.md` exists
2. Check if `writings/<ch>/draft.md` has non-trivial content (more than just a header placeholder — at least one paragraph of prose)
3. If empty or placeholder-only: insert `[Chapter N: <title> — draft pending]` marker in the merged document with a note that the chapter exists but has no draft content yet
4. If substantial content: include it

### 4. Assemble front matter

Gather the following, in order:

1. **Title page** — pull from project settings in `CLAUDE.md`:
   - Paper title, author name, university, department, date
   - If any field is missing, insert a `[TODO: field name]` placeholder

2. **Abstract** — look for it in this order:
   - `writings/ch00-abstract/draft.md` (if exists)
   - `meta/abstract.md` (if exists)
   - If neither exists, insert `[TODO: abstract]`

3. **Table of contents** — auto-generate from the heading structure of all chapter drafts:
   - H1 → chapter entry
   - H2 → section entry (indented)
   - H3 → sub-section entry (further indented)

### 5. Handle citation formatting

Read the configured citation style from `CLAUDE.md` (e.g., `Citation style: GB/T 7714` or `APA`).

For each citekey found in the chapter text in `[citekey]` format (e.g., `[bail2018]`):

1. Look up `references/literature/<citekey>/summary.md` or `references/literature/<citekey>/notes.md`
2. Extract author, year, title, journal/publisher information
3. Format according to the configured style

**GB/T 7714** (default for Chinese academic submissions):
```
[序号] 作者. 题名[文献类型标志]. 刊名, 年份, 卷(期): 起止页码.
Example: [1] 张三, 李四. 网络舆论与政治极化[J]. 政治学研究, 2021, (3): 45-60.
```

**APA**:
```
Author, A. A., & Author, B. B. (Year). Title of article. Journal Name, volume(issue), pages.
```

If a citekey has no corresponding entry in `references/literature/`, flag it:
```
⚠️  Unresolved citekey: bail2018 — no entry in references/literature/
```

Generate a **References / Bibliography section** at the end of the merged document.

### 6. Merge into single document

Combine in this order:

1. Title page
2. Abstract
3. Table of contents
4. Chapter 1 content
5. Chapter 2 content
6. ...
7. Final chapter content
8. References / Bibliography

Between chapters, insert a horizontal rule (`---`) and ensure headings are renumbered consistently if the chapter files use local numbering.

### 7. Output options

Ask the user which output format they need (or check `CLAUDE.md` for a default):

#### Option A: Single merged markdown file

Create `export/` directory if it doesn't exist: `mkdir -p export/`

Write the merged document to `export/manuscript-<date>.md`.

This is the simplest output — useful for review, version control, and further editing.

#### Option B: LaTeX conversion prompt

Generate a ready-to-copy prompt for converting the merged markdown to LaTeX:

```
Task: Convert the attached markdown manuscript to LaTeX.

Requirements:
- Document class: [article / ctexart for Chinese / book — specify based on university requirements]
- Citation style: GB/T 7714 (use natbib or biblatex with the appropriate style file)
- Preserve all headings, footnotes, and figure references
- Generate a .bib file from the references section
- Use the structure: \title, \author, \date, \maketitle, \tableofcontents, then chapters

Input: [path to export/manuscript-<date>.md]
Output: manuscript.tex + references.bib

University formatting requirements:
[paste any specific requirements from CLAUDE.md here]
```

#### Option C: Word conversion prompt

Generate a ready-to-copy prompt for converting the merged markdown to a Word (.docx) file:

```
Task: Convert the attached markdown manuscript to a Word document (.docx).

Requirements:
- Apply university thesis formatting: [margins, font, line spacing from CLAUDE.md if specified]
- Format citations per GB/T 7714 (or the configured style)
- Generate a bibliography at the end
- Preserve heading levels as Word heading styles (Heading 1, Heading 2, Heading 3)
- Table of contents using Word's built-in TOC feature

Input: [path to export/manuscript-<date>.md]
Output: manuscript.docx

University formatting requirements:
[paste any specific requirements from CLAUDE.md here]
```

### 8. Confirm output and next steps

Report what was produced:

```
Export complete.

Output: export/manuscript-2024-04-10.md
Chapters merged: ch01, ch02, ch03, ch04, ch05 (5 chapters)
Citations formatted: 23 references (GB/T 7714)
Warnings: 3 unresolved [CITE] markers retained in document

Next steps:
- Review the merged document for formatting issues
- Use the LaTeX or Word prompt (Option B/C) if you need a formatted submission file
- Tag final chapter versions: git tag final-ch02 (once you're satisfied)
```

## Inputs

- All `writings/ch*/draft.md` files — merged in chapter order
- `CLAUDE.md` — project settings (title, author, citation style, university requirements)
- `references/literature/<citekey>/` — used to format citations and build bibliography
- `meta/abstract.md` or `writings/ch00-abstract/draft.md` — abstract content
- Git tags (`final-ch*`) — if present, use tagged versions instead of HEAD

## Outputs

- `export/manuscript-<date>.md` — single merged markdown document
- **LaTeX conversion prompt** (Option B) — ready-to-copy for a coding agent
- **Word conversion prompt** (Option C) — ready-to-copy for a coding agent
- Pre-export warning report if `[TODO]`, `[CITE]`, or `[DATA]` markers remain

## Notes

- Always run `lint` before export — contradictions and stale references are harder to spot in a merged document
- Export does NOT finalize chapters — finalization is a human action: `git tag final-ch<N>` on the chapter draft
- If no citation style is configured in CLAUDE.md, default to GB/T 7714 for Chinese projects and APA for English projects
- The merged markdown is the canonical export artifact; LaTeX and Word outputs are derived from it via external tools
- University formatting requirements (margins, fonts, line spacing) vary — always check CLAUDE.md before generating the Word/LaTeX prompts
- If a chapter draft is missing, note the gap in the output but do not block the export of other chapters
- The `export/` directory is gitignored by default — add it to git manually if you want to version the export
