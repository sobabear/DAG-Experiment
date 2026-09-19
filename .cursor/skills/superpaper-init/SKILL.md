---
name: superpaper-init
description: Use when starting a new dissertation project or adopting an existing repo for dissertation work
---

# Init

## When to Use

- User says "start a new paper", "start a new dissertation project", "new paper project"
- User wants to organize an existing repo for dissertation writing
- No `meta/` directory exists in the current project
- User says "init", "initialize this project", or "set up superpaper"

## Procedure

Determine which mode applies. If the current directory has substantial existing content (markdown files, code, data), offer `init adopt`. If it is empty or has only a README, proceed with `init new`.

Ask the user to confirm the mode if unclear.

---

### Mode 1: New Project (`init new`)

Interactive setup — ask these questions one at a time before creating any files:

1. **Paper language?** (zh / en) — default: zh
2. **Paper title?**
3. **Citation style?** (GB/T 7714 / APA / Chicago / IEEE / custom) — default: GB/T 7714
4. **Chapter structure?** Offer templates:
   - Social science: Introduction, Literature Review, Theoretical Framework, Research Design, Findings, Discussion, Conclusion
   - STEM: Introduction, Literature Review, Methodology, Results, Discussion, Conclusion
   - Custom: user defines their own chapter names
5. **University?** (for dissertation formatting and context) — optional, user can skip

Once answers are collected, scaffold the full project structure:

```
<project>/
  CLAUDE.md
  AGENTS.md
  GEMINI.md

  meta/
    memory.md          # Initialize with project creation entry
    progress.md        # All chapters marked as [NOT STARTED]
    milestones.md      # Empty template
    plan.md            # Empty template
    style/
    tasks/

  writings/
    ch01-<name>/
      outline.md
      resources.md
      draft.md
      status.md
      assets/
      reviews/
    ch02-<name>/
      ...

  references/
    literature/
    results/
    docs/

  .gitignore
```

**File generation steps:**

1. Create all directories. Use `ch01-<slug>`, `ch02-<slug>`, ... based on chapter names provided.

2. Generate `meta/memory.md`:

```markdown
# Memory

## Current Focus
Project just initialized: <title>

## Recent Decisions
- <date>: Project created with <citation style> citation style, language: <language>

## Open Questions

## Key Insights

## Next Session
- Run `checkin` to begin your first session
- Consider running `brainstorm` to explore research directions
```

3. Generate `meta/progress.md`:

```markdown
# Progress

| Chapter | Status | Notes |
|---------|--------|-------|
| ch01 — <name> | [NOT STARTED] | |
| ch02 — <name> | [NOT STARTED] | |
...
```

4. Generate `meta/milestones.md`:

```markdown
# Milestones

| Milestone | Target Date | Status |
|-----------|-------------|--------|
| Topic finalized | | [ ] |
| Literature review complete | | [ ] |
| Outline approved | | [ ] |
| First draft complete | | [ ] |
| Revisions complete | | [ ] |
| Submission | | [ ] |
```

5. Generate `meta/plan.md` as an empty template with headers: `# Plan`, `## Timeline`, `## Weekly Routine`.

6. Generate `writings/ch0N-<name>/status.md` for each chapter:

```markdown
# <Chapter Name> Status

## Sections
(to be filled during outline)

## Blockers

## Last Updated
<date> by init
```

6b. Generate `writings/ch0N-<name>/outline.md` for each chapter as an empty placeholder:

```markdown
# Chapter N: <Chapter Name>

## Outline

*To be drafted. Run `superpaper-outline` to plan this chapter.*
```

6c. Generate `writings/ch0N-<name>/draft.md` for each chapter as an empty placeholder:

```markdown
# Chapter N: <Chapter Name>

## Draft

*Not yet started. Complete the outline first, then run `superpaper-draft`.*
```

6d. Generate `writings/ch0N-<name>/resources.md` for each chapter as an empty placeholder:

```markdown
# Chapter N: <Chapter Name> — Resources

## Literature

*No references yet. Run `superpaper-ingest` to add literature.*

## Results

*No analysis results yet.*
```

7. Generate `CLAUDE.md` with full project settings (see template below).

8. Generate `AGENTS.md` referencing the same project settings and skill mapping as CLAUDE.md.

9. Generate `GEMINI.md` with tool mapping reference (activate_skill maps to Skill tool in Claude Code).

10. Generate `.gitignore` (see template below).

11. Run:
```bash
# If git not already initialized, run git init first
git init   # safe to run even if already initialized (no-op)
git add .
git commit -m "init: <title>"
```
Note: Check if `.git/` already exists. If so, skip `git init` to avoid confusing output — run `git add . && git commit -m "init: <title>"` directly.

12. Print next steps:
> Project scaffolded. Run `checkin` to start your first session, or `brainstorm` to explore research directions.

---

### Mode 2: Adopt Existing Repo (`init adopt`)

**Key principle: adopt mode never moves or deletes existing files without explicit confirmation from the user.** This is non-negotiable — NEVER alter or remove existing content without asking.

For repos with existing content:

1. **Paper language?** (zh / en)
2. **Paper title?**
3. **Citation style?** (GB/T 7714 / APA / Chicago / IEEE / custom)

4. **Scan the repo** for content patterns:
   - Markdown files → potential chapter drafts
   - PDF files → potential literature copies
   - Code/data directories → potential results/analysis
   - Zotero exports (CSL-JSON, BibTeX `.bib` files) → literature references
   - Existing directory structure

5. **Present proposed mapping** to the user. Example:

```
Found content:
  chapters/intro.md  →  writings/ch01-introduction/draft.md (symlink/record in CLAUDE.md)
  chapters/lit.md    →  writings/ch02-literature/draft.md
  data/              →  references/results/
  refs.bib           →  references/literature/ (after ingest)

No files will be moved. Mapping recorded in CLAUDE.md.
Confirm? (yes / adjust)
```

6. After user confirmation, create the `meta/` layer on top:
   - `meta/memory.md` — initial entry describing the adoption and what was found
   - `meta/progress.md` — chapters with existing drafts marked as `[IN PROGRESS]`, others as `[NOT STARTED]`
   - Per-chapter `status.md` for each identified chapter

7. If the existing structure uses different directory names (e.g., `chapters/` instead of `writings/`), record the mapping in `CLAUDE.md` under a `## Directory Mapping` section. Do not rename directories.

8. Generate `CLAUDE.md` / `AGENTS.md` / `GEMINI.md`.

9. Commit: `"init: adopt existing repo — <title>"`

---

## CLAUDE.md Template

Generate this in the user's project root:

```markdown
# <Paper Title>

## Project Settings
- Language: <language>
- Citation style: <citation style>
- University: <from question 5, or blank if user skipped>

## Skills
This project uses superpaper.
Before any task, check for a matching skill.

### Project Manager
- Session start → superpaper-checkin
- New materials → superpaper-ingest
- End of session → superpaper-memory-update

### Research Facilitator
- Topic exploration → superpaper-brainstorm
- Literature gaps → superpaper-research
- Data questions → superpaper-data-explore / superpaper-analysis

### Writing Assistant
- Chapter planning → superpaper-outline
- Writing → superpaper-draft
- Reviewing → superpaper-review

### Quality Assurance
- Audit → superpaper-lint
- Submission prep → superpaper-export

## Context Loading
1. Read meta/memory.md — recent history and decisions
2. Read meta/progress.md — overall state
3. Read relevant writings/<ch>/status.md — chapter details
4. Read relevant references/<key>/summary.md — don't re-read originals

## Writing Principles
- Mark uncertainty: [TODO], [CITE], [DATA]. Never fabricate.
- Always structurally complete. Missing sections have placeholders.
- Respect human edits. Never overwrite without asking.
- Follow meta/style/style-guide.md — extracted from sample paragraphs/chapters you provide.
- Shorter is better.
- Task files in `meta/tasks/` should have a status header: `status: pending | in-progress | done`. Stale done tasks can be archived to `meta/tasks/archive/`.

## Boundaries
- Do not fabricate data, results, or citations
- Do not mark chapters as finalized (human only)
- Do not make major structural changes without asking
- Do not delete human content without permission
- For deep research: generate prompts, don't pretend to search
- For coding/analysis: generate specs, don't write code
```

---

## .gitignore Template

```
# PDFs (markdown-first — PDFs are local reference copies)
*.pdf

# Data files
*.csv
*.xlsx
*.dta
*.sav
*.rds

# Large binary files
*.zip
*.tar.gz

# Assets (figures regenerated from code)
writings/*/assets/*
!writings/*/assets/.gitkeep

# OS
.DS_Store
Thumbs.db

# Editor
.idea/
.vscode/
*.swp

# Exported drafts (regenerate with export skill)
export/
```

---

## Inputs

- User's answers to interactive prompts (language, title, citation style, chapter structure)
- For adopt mode: existing repo content

## Outputs

- Full project directory structure
- `meta/memory.md`, `meta/progress.md`, `meta/milestones.md`, `meta/plan.md`
- Per-chapter `writings/ch0N-<name>/` directories with placeholder files
- `references/literature/`, `references/results/`, `references/docs/`
- `CLAUDE.md`, `AGENTS.md`, `GEMINI.md` with project settings and skill mapping
- `.gitignore`
- Initial git commit

## Notes

- Chapter directories: `ch01-<slug>`, `ch02-<slug>`, etc. Slugify names (lowercase, hyphens).
- Generated files should match the project language setting (use Chinese headings for `zh` projects).
- The generated `CLAUDE.md` is what any agent reads when entering the dissertation project.
- For adopt mode: if no title is found, ask before proceeding.
- Suggest `checkin` as the very next skill to run after `init` completes.
