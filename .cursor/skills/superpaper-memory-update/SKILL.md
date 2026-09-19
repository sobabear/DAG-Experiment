---
name: superpaper-memory-update
description: Use at the end of every session — persists what was done, decisions made, and next steps so the next session can pick up without re-reading everything
---

# Memory Update

## When to Use

- End of every working session in a dissertation project
- User says "we're done for today", "save progress", "end session", or "I'm stopping"
- Before switching to a different project or task
- After a significant decision that should not be forgotten

## Procedure

### 1. Review the session

Scan the current conversation to identify:

- **What was done** — concrete actions taken (e.g., "outlined section 2.1", "integrated bail2018 into literature review", "revised hypothesis statement")
- **Decisions made** — any choice that affects future work (e.g., "chose panel data over cross-sectional", "removed sub-section on X", "adopted GB/T 7714 citation style")
- **Open questions** — unresolved issues that need follow-up (e.g., "need to check if zhangwei2021 covers platform context", "advisor feedback pending")
- **Next steps** — what should happen at the start of the next session
- **Section state changes** — any chapter sections that changed status (e.g., from [OUTLINED] to [DRAFTING])

Be concise. Do not dump the entire session. Extract the signal.

### 2. Read current meta/memory.md

Read `meta/memory.md` to understand the existing state before updating.

If `meta/memory.md` does not exist, create it with the standard structure (see Output Format below).

### 3. Update meta/memory.md

Apply the following changes:

**Current Focus** — Update to reflect what the project is focused on after this session. Replace the previous value if the focus has shifted.

**Recent Decisions** — Prepend new decisions with today's date. Keep the last 5–10 decisions; archive or remove older ones that are no longer relevant. Format:
```
- YYYY-MM-DD: [Decision made]
```

**Open Questions** — Add new open questions. Remove any that were resolved during this session.

**Key Insights** — Add any significant findings or realizations that should persist. Do not add minor observations.

**Next Session** — Replace with a clear, actionable list of what to do next session. This is what checkin will surface first.

### 4. Update relevant status.md files

For each chapter that had section state changes during the session:

1. Read `writings/<ch>/status.md`
2. Update the relevant section's state marker (e.g., `[TODO]` → `[OUTLINED]`, `[OUTLINED]` → `[DRAFTING]`)
3. Update the **Last Updated** field with today's date and `by memory-update`
4. Add any new blockers that emerged
5. Remove blockers that were resolved

If `writings/<ch>/status.md` does not exist and chapter work was done, create it:

```markdown
# Chapter [N] Status

## Sections
- [section number and name]: [STATE] — [brief note]

## Blockers
[none, or list]

## Last Updated
YYYY-MM-DD by memory-update
```

### 4a. Update milestones.md

If `meta/milestones.md` exists and any milestones were reached during this session, check them off in milestones.md. Add a timestamp next to completed milestones:

```markdown
| First draft complete | 2026-04-11 | [x] ✓ completed 2026-04-11 |
```

### 4b. Mark completed tasks as [DONE]

If the user completed tasks from `meta/tasks/` during the session, mark those task files as `[DONE]`:

- Add `status: done` frontmatter to the task file, or rename it with a `-done` suffix
- This prevents stale tasks from appearing in every future checkin briefing

Example: add to top of the task file:
```
---
status: done
completed: YYYY-MM-DD
---
```

### 5. Confirm what was written

Report back to the user:

```
Memory updated.

Recorded:
- [1-2 key decisions]
- [any section state changes]

Next session: [the Next Session content, summarized in one line]

Files updated:
  - meta/memory.md
  - writings/<ch>/status.md (if applicable)
```

## memory.md Output Format

```markdown
# Memory

## Current Focus
[What the project is currently focused on — one or two sentences]

## Recent Decisions
- YYYY-MM-DD: [Most recent decision]
- YYYY-MM-DD: [Earlier decision]
...

## Open Questions
- [Unresolved question]
- [Another unresolved question]

## Key Insights
- [citekey or concept]: [Insight that should persist]
...

## Next Session
- [First action to take]
- [Second action to take]
```

## Inputs

- Current conversation (what happened this session)
- `meta/memory.md` — existing cross-session brain
- `writings/*/status.md` — per-chapter section states

## Outputs

- Updated `meta/memory.md` — with new decisions, updated focus, refreshed next session
- Updated `writings/<ch>/status.md` — for any chapters with state changes

## Notes

- Timestamp all entries with today's date in YYYY-MM-DD format
- Keep Recent Decisions to the last 5–10 entries — older decisions that are still relevant should be promoted to Key Insights
- Never delete open questions without confirming they were actually resolved
- Be concise — the goal is a compact state that checkin can read in seconds
- If nothing significant happened (e.g., a very short session), still update Next Session and Last Updated
- The end of session trigger is the most important time to run this skill — skipping it breaks session continuity
- Do not include raw conversation text in memory.md — only extracted decisions and state
