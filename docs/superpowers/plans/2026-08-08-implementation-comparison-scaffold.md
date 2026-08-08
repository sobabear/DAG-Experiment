# Implementation Comparison Scaffold — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create `apps/implementation-comparison/` with the approved layout, migrate the draft plan markdown, and remove the misspelled `src/apps/` path — without changing `dagcore`.

**Architecture:** Top-level consumer app under `apps/`. Plan follows Artificial Analysis Coding Agent Index–style scoring. Tracks: `dag-bpd/`, `dag-yonsei/`, `general-agent-system/`, plus `results/`. Optional harness at `src/impl_comparison/`.

**Tech Stack:** Markdown + directory layout only (no new Python runtime deps in this phase).

**Spec:** `docs/superpowers/specs/2026-08-08-implementation-comparison-design.md`

---

### Task 1: Create app tree and README

**Files:**
- Create: `apps/implementation-comparison/README.md`
- Create: `apps/implementation-comparison/dag/.gitkeep`
- Create: `apps/implementation-comparison/dag/runs/.gitkeep`
- Create: `apps/implementation-comparison/general-agent-system/.gitkeep`
- Create: `apps/implementation-comparison/general-agent-system/runs/.gitkeep`
- Create: `apps/implementation-comparison/results/.gitkeep`
- Create: `apps/implementation-comparison/src/impl_comparison/__init__.py`
- Create: `apps/implementation-comparison/tests/.gitkeep`

- [x] **Step 1:** Create directories listed above
- [x] **Step 2:** Write a short README describing DAG vs General Agent System, rubric pointer, and where tool runs go
- [x] **Step 3:** Add empty `__init__.py` for the optional harness package

### Task 2: Migrate plan and remove draft path

**Files:**
- Move: `src/apps/implementation-comparision/implementation-comparison-plan.md` → `apps/implementation-comparison/implementation-comparison-plan.md`
- Delete: `src/apps/implementation-comparision/` (and empty `src/apps/`)

- [x] **Step 1:** Move the plan file (preserve contents)
- [x] **Step 2:** Remove the old typo’d directory tree
- [x] **Step 3:** Verify `src/dagcore/` and root `pyproject.toml` unchanged

### Task 3: Smoke check

- [x] **Step 1:** Confirm final tree matches the design layout
- [x] **Step 2:** Confirm no files remain under `src/apps/`
