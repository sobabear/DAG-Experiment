---
name: superpaper-ingest
description: Use when new material is added to the project — literature notes, Zotero/BetterBibTeX exports, CSL-JSON files, copied text, result figures, or analysis output
---

# Ingest

## When to Use

- User pastes or provides a Zotero export (CSL-JSON, BetterBibTeX JSON, or BibTeX)
- User provides markdown reading notes for a paper
- User provides result figures or tables from an analysis
- User pastes copied text from a paper or other source
- New literature needs to be organized into the project
- Analysis results from a coding agent need to be integrated

## Procedure

### 1. Detect input type

Examine what the user has provided:

| Signal | Input type |
|--------|-----------|
| JSON with `"type": "article-journal"`, `"id"`, `"author"` fields | Zotero CSL-JSON export |
| JSON with `"citekey"` field or BetterBibTeX format | Zotero BetterBibTeX export |
| `.bib` file content or `@article{...}` syntax | BibTeX |
| Markdown text with headings and prose | Reading notes |
| Image files (`.png`, `.jpg`, `.pdf` of figures) | Result figures |
| Plain text excerpts from papers | Copied text / quotes |
| Markdown with analysis descriptions | Result notes |
| User provides author/title/year in prose form, no structured data, no file attachment | Plain text paper description |

**Plain text paper description** handling: parse the user's text for author/title/year/venue. Ask for any missing fields. Confirm the citekey — use user-provided citekey if given (e.g., "here's bail2018..."), else suggest `authorYEAR` format.

If the type is ambiguous, ask the user: "Is this literature notes, a Zotero export, result figures, or something else?"

### 2. Handle literature input

For Zotero CSL-JSON, BetterBibTeX, or BibTeX:

1. **Extract the citekey** — use the `id` or `citekey` field from the JSON, or construct it from the BibTeX key. Follow the pattern `authorYEAR` (e.g., `bail2018`). If the user's input already includes an explicit citekey (e.g., "here's bail2018..."), use it as-is. Don't try to re-generate a citekey from the author/year if the user provided one.
2. **Create the directory** `references/literature/<citekey>/`
3. **Create `references/literature/<citekey>/notes.md`** — a blank reading notes file with the paper's title, authors, year, and journal as a header. Leave space for the user to add their own notes.
4. **Create `references/literature/<citekey>/summary.md`** — follow this template exactly to ensure consistency across all papers in the project:

```markdown
# <Paper Title>

**Citekey:** <citekey>
**Authors:** <authors>
**Year:** <year>
**Venue:** <journal/publisher>
**Type:** <empirical / theoretical / methodological / review>

## One-line summary
<single sentence capturing the main point>

## Main argument
<2-3 sentences on the central claim>

## Key findings
- <finding 1>
- <finding 2>
- <finding 3>

## Methodology
<brief description, if empirical>

## Relevance to this dissertation
<why this paper matters for our project, which sections it supports>

## Limitations / caveats
<what the paper doesn't do, important limitations>

## Connected work
- [[citekey1]] — <how it connects>
- [[citekey2]] — <how it connects>
```

Fill in what is known from the export/input. Leave fields as `[TODO]` if information is not available rather than fabricating.
5. **Create `references/literature/<citekey>/citations.md`** — a template for key quotes:
   ```markdown
   # Key Citations — <citekey>

   <!-- Add key quotes with page numbers here. Format: -->
   <!-- > "Quote text" (p. XX) -->
   ```

For markdown reading notes provided directly:

1. Ask for the citekey if not obvious from the content
2. Create the same directory structure as above
3. Put the provided notes into `notes.md`
4. Extract any structured information for `summary.md`
5. Create `citations.md` template

For copied text / quotes:

1. Ask which paper it is from (citekey or title)
2. Add to the existing `references/literature/<citekey>/citations.md`, or create the entry if needed

### 3. Handle result input

For result figures or analysis output:

1. Ask for the result key (analysis project name) if not provided — use a short descriptive slug (e.g., `polarization-model`, `panel-regression`)
2. **Create the directory** `references/results/<key>/`
3. **For figures:** copy or note the file path into `references/results/<key>/figures/`
4. **Create `references/results/<key>/spec.md`** — if the analysis spec exists (the prompt given to the coding agent), record it here. Otherwise, create a placeholder:
   ```markdown
   # Analysis Spec — <key>

   <!-- Record the prompt/spec given to the coding agent here. -->
   ```
5. **Create `references/results/<key>/summary.md`** — summarize the results based on what the user provides:
   - What analysis was run
   - Key findings (numeric results, significant variables, model fit)
   - Interpretation notes
   - How to cite in the dissertation (e.g., "As shown in Figure X...")

### 4. Update resources.md

If the input can be associated with specific chapter(s):

- Ask the user: "Which chapter(s) does this relate to?" (or infer from context)
- A reference can be attributed to multiple chapters. Accept comma-separated lists and update `resources.md` for each relevant chapter.
- Add the citekey or result key to `writings/<ch>/resources.md` for each applicable chapter
- If `resources.md` does not exist for a chapter, create it with the new entry

Format for literature in resources.md:
```markdown
## Literature

- `bail2018` — [short description of relevance to this chapter]
```

Format for results in resources.md:
```markdown
## Results

- `polarization-model` — [description of what results to use and where]
```

### 5. Report what was created

After ingesting, report:

```
Ingested: <citekey or result key>
Created:
  - references/literature/<citekey>/notes.md
  - references/literature/<citekey>/summary.md
  - references/literature/<citekey>/citations.md
Updated:
  - writings/<ch>/resources.md (if chapter association was made)

Next: Open notes.md to add your reading notes, or use superpaper-research to find related literature.
```

## Inputs

- Zotero CSL-JSON or BetterBibTeX export (JSON)
- BibTeX file content
- Markdown reading notes
- Result figures or analysis output
- Copied text / quotes from papers

## Outputs

- `references/literature/<citekey>/notes.md` — reading notes (blank template or populated)
- `references/literature/<citekey>/summary.md` — structured summary with citation details
- `references/literature/<citekey>/citations.md` — key quotes template
- `references/results/<key>/spec.md` — analysis spec (for result ingestion)
- `references/results/<key>/summary.md` — results summary (for result ingestion)
- `references/results/<key>/figures/` — figures directory (for result ingestion)
- Updated `writings/<ch>/resources.md` — when chapter association is clear

## Notes

- Auto-detect citekey from Zotero export `id` or `citekey` field. Do not invent citekeys — ask if unclear.
- Citekeys follow `authorYEAR` format to match Zotero BetterBibTeX defaults (e.g., `bail2018`, `zhangwei2021`)
- **Chinese author citekeys:** Use pinyin for Chinese family names. For single-character family names (张), use `zhang`. For author 张伟 → `zhangwei2021`. For author 王小明 → `wangxiaoming2023`. If user provides a citekey directly, use it as-is.
- Never overwrite existing `notes.md` content — if the file already exists, append or ask
- PDFs are gitignored — note their local path in summary.md but do not add them to git
- If the user provides multiple items at once, process each one in sequence
- For Zotero exports with multiple items, create a directory for each citekey
- The `results/` path is for analysis outputs from coding agents, not for raw data
