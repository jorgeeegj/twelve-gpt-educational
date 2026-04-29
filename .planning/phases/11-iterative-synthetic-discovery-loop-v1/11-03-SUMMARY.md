---
phase: 11-iterative-synthetic-discovery-loop-v1
plan: "03"
subsystem: testing
tags: [triage, rubric, classifier, discovery-loop, phase11]

# Dependency graph
requires:
  - phase: 11-01
    provides: "11-SPEC.md locked — §4 action-type enum"
  - phase: 11-02
    provides: "failure_backlog.py — cluster shape consumed by classifier"
provides:
  - "evals/discovery/triage_rubric.md — human rubric document with 7 sections + Decision Order"
  - "evals/discovery/triage_rubric.py — deterministic classify(cluster, hints) -> ActionType"
  - "14 unit tests covering all 7 action types, default fallthrough, override, and edge cases"
affects: ["11-04", "11-05", "11-06", "11-07"]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Deterministic rule-chain classifier: guard_evidence + category → action_type, no LLM"
    - "Manual override via hints['force_action_type'] (rule 1, highest precedence)"
    - "seen_count guard in rule 5: falls through if field absent from cluster dict"

key-files:
  created:
    - evals/discovery/triage_rubric.md
    - evals/discovery/triage_rubric.py
    - tests/test_triage_rubric.py
  modified: []

key-decisions:
  - "Rule 5 (DEMO_RANDOM non_actionable) only fires when seen_count is present in cluster dict — avoids false non_actionable on clusters sourced from live backlog entries where the field lives on the entry, not the cluster shape"
  - "14 tests written (10 required + 4 bonus: champions_league rule 6, demo_random without seen_count, None vs {} hints parity, ACTION_TYPES count sanity)"

patterns-established:
  - "Decision order in rubric.md §Decision Order must match classify() implementation 1:1"
  - "Promotion artefact paths sourced from 11-SPEC.md §8 emission table"

requirements-completed: [LOOP-03]

# Metrics
duration: 10min
completed: 2026-04-30
---

# Phase 11 Plan 03: Cluster Triage Rubric Summary

**Deterministic 7-action-type triage classifier with rubric doc and 14 pytest-isolated unit tests confirming 11-SPEC.md §4 semantics**

## Performance

- **Duration:** ~10 min
- **Started:** 2026-04-30T00:25:00Z
- **Completed:** 2026-04-30T00:35:00Z
- **Tasks:** 3
- **Files created:** 3

## Accomplishments

- `evals/discovery/triage_rubric.md` — human rubric with one section per action type, each containing definition, "When it applies" bullets, Phase-10-grounded worked example, and promotion artefact path. Includes "Decision Order" section matching classifier implementation 1:1.
- `evals/discovery/triage_rubric.py` — `classify(cluster, hints) -> ActionType` with 8-rule decision chain. Zero coupling to `src.basic_stats.*`, `openai`, or any network library.
- `tests/test_triage_rubric.py` — 14 tests (10 required + 4 bonus). All 217 project tests pass.

## Task Commits

1. **Tasks 1-3: triage_rubric.md + triage_rubric.py + test_triage_rubric.py** — `1d9cbd1` (feat)

## Files Created/Modified

- `evals/discovery/triage_rubric.md` — 7 sections, Decision Order, Phase-10 examples
- `evals/discovery/triage_rubric.py` — `classify()`, `ACTION_TYPES`, `ActionType` Literal
- `tests/test_triage_rubric.py` — 14 unit tests

## Decisions Made

- Rule 5 (`DEMO_RANDOM non_actionable`) checks `cluster.get("seen_count")` rather than requiring the field — the cluster shape from the clusterer may not carry `seen_count` (it lives on the backlog entry). The rule only fires when the field is explicitly present.
- Manual override (rule 1) accepts only values in `ACTION_TYPES`; unknown strings silently fall through, preserving determinism without raising exceptions.

## Deviations from Plan

None — plan executed exactly as written. 14 tests (10 required + 4 bonus) written.

## Issues Encountered

None.

## Known Stubs

None. All classifier logic fully implemented; `triage_rubric.md` Decision Order matches `triage_rubric.py` rules 1:1.

## Next Phase Readiness

- Plan 11-04 (Targeted Campaign Generator) can import `from evals.discovery.triage_rubric import classify, ACTION_TYPES`.
- Plan 11-05 (Iteration Runner) can call `classify(cluster, hints)` after clustering a run.
- `triage_rubric.md` serves as the human reference for manual triage decisions.
- All 217 project tests pass; baseline suite (184) unaffected.

---
*Phase: 11-iterative-synthetic-discovery-loop-v1*
*Completed: 2026-04-30*
