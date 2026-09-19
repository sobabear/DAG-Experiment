---
name: superpaper-plan
description: Use when the user wants to create or update a project timeline — after topic and outline are settled, when milestones or deadlines change, or when weekly goals need to be set
---

# Plan

## When to Use

- After topic and chapter outline are settled and the user is ready to plan execution
- User mentions a submission deadline, defense date, or university requirement
- Existing plan needs updating due to changed circumstances
- User asks "when should I finish X?" or "how do I fit this in before my deadline?"

## Procedure

## Step 0: STOP AND ASK

Before generating any output, you MUST confirm the following. If the answers are already clear from the user's triggering message, verify with a single confirmation question. If any are unclear, ASK BEFORE PROCEEDING. Do not embed these as "clarifying questions" in the output document — ask them conversationally first.

**Mandatory confirmations:**
- Specific defense date (not just month — e.g., "June 15, 2027", not "June 2027")
- Submission deadline (often 2–8 weeks before defense at Chinese universities — do not assume)
- Any intermediate milestones: **proposal defense (开题报告 — required at most Chinese universities before empirical work)**, advisor review deadlines, committee draft submissions
- Current chapter status (cross-check with progress.md if it exists)

Only proceed to the next steps once these are confirmed.

### 1. Gather inputs

Read the following if they exist:

- `meta/progress.md` — current chapter status and completion levels
- `meta/milestones.md` — any existing milestones already recorded
- `meta/plan.md` — any existing plan to update rather than replace

Then ask the user for any missing information:

1. **Submission deadline** — What is the university submission date? (exact date)
2. **Defense date** — Is there a defense/viva date? (if applicable)
3. **Chapter count** — How many chapters are planned? What are they?
4. **Chapter status** — Which chapters are done, in progress, or not started? (cross-check with progress.md if it exists)
5. **Weekly capacity** — How many hours per week can you realistically dedicate?
6. **Buffer preference** — How much buffer time do you want before the submission deadline?

### 2. Work backward from the submission deadline

Use backward planning from the submission deadline:

1. Reserve buffer time before the deadline (suggest 1–2 weeks minimum)
2. Reserve time for final formatting, proofreading, and export (suggest 1 week)
3. Reserve time for final review pass across all chapters (suggest 1–2 weeks)
4. Allocate remaining time to chapters based on their current status:
   - [TODO] chapters need the most time (drafting + review)
   - [OUTLINED] chapters need less (drafting + review)
   - [DRAFTING] chapters need moderate time (finish draft + review)
   - [REVIEWING] chapters need the least (finish review cycle)
5. Set milestones for each chapter: outline complete, first draft, reviewed
6. Set weekly goals that are achievable given the user's stated capacity

### 3. Check for realism

Flag if the plan is infeasible:

- If there is not enough time to complete all chapters before the deadline, say so clearly
- Suggest what to prioritize if time is tight (core chapters first)
- Suggest what could be cut or condensed if needed
- Recommend a minimum viable dissertation path if deadlines are very tight

### 4. Write meta/plan.md

Output the plan to `meta/plan.md` using this structure:

```markdown
# Dissertation Plan

## Deadlines
- Submission: [date]
- Defense: [date, if applicable]
- Advisor review cutoff: [date — buffer before submission]

## Phases

### Phase 1: [Name] — [date range]
Goal: [What should be achieved]
Chapters: [Which chapters to focus on]
Milestone: [Concrete deliverable]

### Phase 2: [Name] — [date range]
...

## Weekly Goals

### Week of [date]
- [ ] [Specific, achievable goal]
- [ ] [Specific, achievable goal]

### Week of [date]
...

## Buffer Time
- [Start date] – [submission date]: Final review, formatting, proofreading

## Assumptions
- Weekly writing capacity: [N] hours
- [Any other assumptions made]

## Risks
- [Any identified risks or tight spots in the timeline]
```

### 5. Update meta/milestones.md

If `meta/milestones.md` exists, update it with the milestone dates from the plan.
If it does not exist, create it with the key milestones identified.

### 6. Summarize and confirm

Present a brief summary of the plan to the user:

- Key dates and phases
- Most critical near-term weekly goals
- Any risks or tight spots
- Ask if they want to adjust anything

## Inputs

- `meta/progress.md` — chapter completion status
- `meta/milestones.md` — existing milestone tracking (if present)
- `meta/plan.md` — existing plan to update (if present)
- User-provided: submission deadline, defense date, chapter count, weekly capacity

## Outputs

- `meta/plan.md` — timeline with phases, milestones, weekly goals, and buffer time
- Updated `meta/milestones.md` — milestone dates

## Notes

- Always work backward from the deadline — this is the most reliable planning method
- Be honest about infeasibility. A tight plan is useless; a realistic one is actionable.
- Weekly goals should be concrete and small enough to actually complete in a week
- Buffer time is non-negotiable — always include it before the submission deadline
- Revisit the plan when progress.md shows chapters are behind or ahead of schedule
- University submission dates are hard deadlines; defense dates may have more flexibility
- If the user does not know their deadlines yet, help them estimate based on typical dissertation timelines

**Chinese university context:** Most Chinese PhD programs require a proposal defense (开题报告 / kaiti baogao) before significant empirical work. This typically happens 3–6 months into the PhD and must be on the timeline. Also common: midterm evaluation (中期考核), pre-defense review (预答辩), and formal defense (正式答辩). For international/US programs, these may be called: prospectus defense, qualifying exams, committee meetings, defense.
