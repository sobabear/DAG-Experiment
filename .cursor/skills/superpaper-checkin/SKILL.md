---
name: superpaper-checkin
description: Use at the start of every session in a dissertation project — restores context and suggests what to work on
---

# Checkin

## When to Use

- Beginning of any session in a dissertation project
- User says "what should I work on?" or "where did I leave off?"
- After a long break from the project

## Procedure

### 1. Check project exists

Check if `meta/memory.md` exists — this is the canonical signal that superpaper has been initialized here. CLAUDE.md alone is not sufficient (many projects have CLAUDE.md without being superpaper projects).

If `meta/memory.md` does not exist, stop and tell the user:

> "This doesn't look like a superpaper project yet. Run `init` to set one up."

Do not proceed further if no project is found.

### ### 2. Read context (in this order)

Read each of these files, noting what is present:

1. `meta/memory.md` — recent decisions, current focus, open questions, key insights, next session plan
2. `meta/progress.md` — overall chapter status overview
3. Scan `writings/*/status.md` — per-chapter section states, blockers, last updated dates
4. Check `meta/tasks/` — any pending AI-generated task suggestions. Only surface tasks marked as `[PENDING]` or without a status header. Ignore files marked `[DONE]` or `[ARCHIVED]`. If `meta/tasks/` is empty or has no pending tasks, skip this step silently — don't include it in the briefing.

### 3. Synthesize a Session Briefing

Present a concise status report:

```
## Session Briefing

**Current focus:** [from memory.md Current Focus]
**Last session:** [summary of what happened from Recent Decisions]

### Chapter Status
- Ch01 Introduction: [DRAFTING] — sections 1.1-1.3 done, 1.4 TODO
- Ch02 Literature Review: [OUTLINED] — outline ready, not yet drafted
- ...

### Open Questions
- [from memory.md]

### Blockers
- [from status.md files]

### Suggested Next Steps
1. [Most impactful task based on progress and blockers]
2. [Second priority]
3. [Third priority]
```

Keep the briefing concise — this is orientation, not a verbose dump of all files.

**Omit sections from the briefing that have no content.** Don't show empty headers like 'Open Questions:' when there are no open questions. For a freshly-initialized project, the briefing can be as short as 2-3 sentences.

### 4. Suggest next steps

Prioritise based on:

- What `memory.md`'s "Next Session" section says
- Which chapters have blockers that can be resolved now
- Which chapters are closest to completion
- Any pending tasks in `meta/tasks/`
- General lifecycle progression: don't outline before brainstorming; don't draft before outlining

### 5. Ask what the user wants to focus on

After presenting the briefing and suggestions, ask:

> "What would you like to work on this session?"

Based on their answer, suggest the appropriate superpaper skill to invoke.

## Inputs

- `meta/memory.md` — cross-session brain
- `meta/progress.md` — chapter completion overview
- `writings/*/status.md` — per-chapter details
- `meta/tasks/` — pending task suggestions

## Outputs

- Concise status briefing (NOT a verbose dump of all files)
- Prioritized task suggestions
- Skill recommendation based on user's choice

## Notes

- Never fabricate progress — only report what's actually in the files
- If files are empty or minimal, say so honestly
- If the last session was recent (within a day), keep it short: "Last session you were working on X. Ready to continue?"
- If the last session was long ago, provide more context to help the user re-orient
- If `meta/memory.md` doesn't exist, the project hasn't been initialized — suggest running `init`
