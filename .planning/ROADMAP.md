# Roadmap: Basic Stats Analyst

**Created:** 2026-03-26
**Granularity:** Coarse (3-5 phases)
**Core Value:** Every answer must stay grounded in actual data.

## Phase Overview

| Phase | Name | Goal | Status | Plans |
|-------|------|------|--------|-------|
| 1 | Project Baseline | Clean GSD operating structure + confirmed benchmark baseline | ◆ In Progress | 0/2 |
| 2 | Planner & Execution Fixes | Resolve known failing benchmark cases with targeted, tested fixes | ○ Pending | 0/3 |
| 3 | Verbalization & UI Quality | Ensure outputs match grounded rows; UI displays correctly | ○ Pending | 0/2 |

---

## Phase 1 — Project Baseline

**Goal:** Establish a clean GSD planning structure and confirm current benchmark state before any further changes.

**Success criteria:**
- PROJECT.md, REQUIREMENTS.md, ROADMAP.md, STATE.md, config.json all committed and accurate
- `eval_runner_v4.py` run and current pass rate documented in STATE.md
- No code changes — initialization only

**Requirements covered:** BASE-01, BASE-02

**Plans:**
1. Initialize and commit all GSD planning files
2. Run eval_runner_v4 and document current pass rate

---

## Phase 2 — Planner & Execution Fixes

**Goal:** Resolve the three known failing benchmark cases (QV4_37, QV4_38, QV5_41) and verify no regressions. Each fix is small, targeted, and accompanied by a test.

**Success criteria:**
- QV4_37, QV4_38, QV5_41 pass on eval_runner_v4
- No regression in previously passing cases
- Each fix has a corresponding test case in `test_query_planner.py`

**Requirements covered:** PLAN-01, PLAN-02, PLAN-03, EXEC-01, EXEC-02

**Plans:**
1. Diagnose each failing case — identify root cause (planner interpretation vs execution vs scope dispatch)
2. Fix QV4_37 / QV4_38 with targeted planner or engine change + test
3. Fix QV5_41 with targeted planner or execution change + test

**Sensitivity:** Very high — touching `query_planner.py`, `duckdb_manager.py`, `llm_query_engine_v2.py`

---

## Phase 3 — Verbalization & UI Quality

**Goal:** Ensure verbalized answers accurately reflect retrieved rows, handle edge cases cleanly, and display correctly in the Streamlit UI.

**Success criteria:**
- Verbalization output matches supporting rows for all tested question types
- Edge cases handled: zero results, ties, partial data
- UI shows answers and supporting rows without breakage on edge cases

**Requirements covered:** VERB-01, VERB-02, UI-01, UI-02

**Plans:**
1. Audit verbalization for hallucinated phrasing or values; fix `verbalize.yaml` as needed
2. Test UI edge cases in `pages/basic_stats.py`; fix display issues without touching core logic

---

## Guardrails (apply to all phases)

- Prefer small, local fixes over large refactors
- Any change to a very-sensitive file requires eval_runner validation before closing the task
- No broad rewrites without an explicit approved plan
- Benchmark pass rate must not regress between phases

---
*Roadmap created: 2026-03-26*
*Last updated: 2026-03-26 after brownfield initialization*
