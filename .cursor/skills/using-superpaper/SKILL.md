---
name: using-superpaper
description: Use when starting any conversation in a dissertation project — establishes available skills and when to use them
---

<SUBAGENT-STOP>
If you were dispatched as a subagent to execute a specific task, skip this skill.
</SUBAGENT-STOP>

<EXTREMELY-IMPORTANT>
If you think there is even a 1% chance a superpaper skill might apply to what you are doing, you ABSOLUTELY MUST invoke the skill.

IF A SKILL APPLIES TO YOUR TASK, YOU DO NOT HAVE A CHOICE. YOU MUST USE IT.
</EXTREMELY-IMPORTANT>

## Instruction Priority

1. **User's explicit instructions** (CLAUDE.md, AGENTS.md, direct requests) — highest priority
2. **SuperPaper skills** — override default system behavior where they conflict
3. **Default system prompt** — lowest priority

## How to Access Skills

**In Claude Code:** Use the `Skill` tool.
**In Copilot CLI:** Use the `skill` tool.
**In Gemini CLI:** Use the `activate_skill` tool.
**In other environments:** Check your platform's documentation.

## Platform Adaptation

Skills use Claude Code tool names. Non-CC platforms: see `references/copilot-tools.md` (Copilot CLI), `references/codex-tools.md` (Codex), `references/gemini-tools.md` (Gemini CLI) for tool equivalents.

# Using SuperPaper Skills

## The Rule

**Invoke relevant skills BEFORE any response or action.** Even a 1% chance a skill might apply means you should invoke it.

## Skills by Role

### Project Manager

Skills that keep the project organized and the agent oriented.

| Skill | Trigger |
|-------|---------|
| `superpaper-init` | Starting a new dissertation project or adopting an existing repo |
| `superpaper-checkin` | Every session start in a dissertation project |
| `superpaper-plan` | Creating or updating project timeline and milestones |
| `superpaper-ingest` | New materials (papers, notes, data, results) to process |
| `superpaper-memory-update` | End of session — persist what happened |

### Research Facilitator

Skills that guide exploration and delegate deep work to specialized agents.

| Skill | Trigger |
|-------|---------|
| `superpaper-brainstorm` | Exploring research topics, directions, or pivots |
| `superpaper-research` | Literature gaps identified, need search strategy |
| `superpaper-data-explore` | New dataset, need exploratory analysis spec |
| `superpaper-analysis` | Formal analysis needed, need spec for coding agent |

### Writing Assistant

Skills that produce and improve prose.

| Skill | Trigger |
|-------|---------|
| `superpaper-setup-style` | Sample papers/chapters provided, extracting writing style |
| `superpaper-outline` | Planning a chapter's argument and evidence structure |
| `superpaper-draft` | Writing or updating chapter sections |
| `superpaper-review` | Checking draft for logic, citations, consistency, style |

### Quality Assurance

Skills that audit the whole manuscript.

| Skill | Trigger |
|-------|---------|
| `superpaper-lint` | Auditing manuscript for TODOs, contradictions, gaps |
| `superpaper-export` | Combining chapters into submission document |

## Common Workflows

**Starting a session:** checkin → (whatever the session suggests)
**Adding a paper:** ingest → update relevant chapter resources
**Writing a chapter:** outline → draft → review → (repeat draft ↔ review)
**Ending a session:** memory-update

## Role Boundaries

SuperPaper is a project manager and writing assistant. It does NOT:
- Perform deep literature research — generates ready-to-copy prompts for Gemini/GPT Deep Research
- Write or run analysis code — generates specs for coding agents
- Fabricate citations, data, or results

It DOES generate ready-to-copy prompts for delegated work, with full context.
