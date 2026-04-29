---
phase: 11-iterative-synthetic-discovery-loop-v1
plan: "02"
subsystem: testing
tags: [json, failure-backlog, discovery-loop, synthetic-uat, phase11]

# Dependency graph
requires:
  - phase: 11-01
    provides: "11-SPEC.md locked — schema, append_or_update semantics, counter-idempotency invariant"
provides:
  - "evals/discovery/ package with failure_backlog.py helper and seed failure_backlog.json"
  - "load_backlog / save_backlog / find_by_signature / append_or_update / next_id public API"
  - "10 unit tests covering all 7 required cases including counter-idempotency on run_id"
affects: ["11-03", "11-04", "11-05", "11-06", "11-07"]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Counter-idempotent run_id tracking: seen_count increments only on distinct run_id values"
    - "Monotonic BACKLOG_NNN IDs zero-padded to 3 digits"
    - "Append-at-most-one new sample_answer per call (truncated to _SAMPLE_TRUNC chars)"

key-files:
  created:
    - evals/discovery/__init__.py
    - evals/discovery/failure_backlog.json
    - evals/discovery/failure_backlog.py
    - tests/test_failure_backlog.py
  modified: []

key-decisions:
  - "In-place mutation + return in append_or_update: simpler API, consistent with mutable dict pattern"
  - "Docstring carefully worded to avoid triggering 'from src.basic_stats' grep check"
  - "10 tests written (7 required + 3 bonus: next_id edge cases + ValueError on bad schema)"

patterns-established:
  - "All tests use tmp_path fixture and path= kwarg for isolation — no global state contamination"
  - "_make_cluster() helper keeps test clusters DRY while exposing all fields clearly"

requirements-completed: [LOOP-02]

# Metrics
duration: 15min
completed: 2026-04-29
---

# Phase 11 Plan 02: Failure Memory / Discovery Backlog Summary

**JSON-backed failure-memory backlog with counter-idempotent append_or_update, set-union question_ids merge, and 10 pytest-isolated unit tests confirming 11-SPEC.md §3 semantics**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-04-29T22:00:00Z
- **Completed:** 2026-04-29T22:12:24Z
- **Tasks:** 3
- **Files created:** 4

## Accomplishments

- `evals/discovery/__init__.py` created (package marker — empty)
- `evals/discovery/failure_backlog.json` seeded with `{"backlog_version": 1, "entries": []}`
- `evals/discovery/failure_backlog.py` implemented with all 5 public functions per 11-SPEC.md §3 — zero coupling to `src.basic_stats.*` or OpenAI
- `tests/test_failure_backlog.py` with 10 tests (173 + 10 = 183 total, all passing)

## Task Commits

1. **Task 1: Empty package + seed JSON** - `060b131` (chore)
2. **Task 2: failure_backlog.py helper module** - `9f56460` (feat)
3. **Task 3: test_failure_backlog.py unit tests** - `1961978` (test)

## Files Created/Modified

- `evals/discovery/__init__.py` — empty package marker
- `evals/discovery/failure_backlog.json` — seed backlog: `{"backlog_version": 1, "entries": []}`
- `evals/discovery/failure_backlog.py` — `load_backlog`, `save_backlog`, `find_by_signature`, `append_or_update`, `next_id`
- `tests/test_failure_backlog.py` — 10 unit tests covering all 7 required cases + 3 bonus

## Decisions Made

- `append_or_update` mutates in-place AND returns the backlog dict — matches Python dict-mutation conventions and keeps calling code simple.
- `next_id` is O(n) over entries (simple list scan) — appropriate for backlogs expected to stay small (dozens, not thousands of entries).
- Docstring on test file says "Zero imports from src/basic_stats or duckdb" (not "from src.basic_stats") to avoid false-positive match on the acceptance-criterion grep pattern.

## Deviations from Plan

None — plan executed exactly as written. All 7 required test functions present plus 3 bonus tests.

## Issues Encountered

Minor: the test file docstring originally contained the phrase "No imports from src.basic_stats.*" which matched the acceptance-criterion grep `grep -q 'from src\.basic_stats'`. Rewrote the docstring to "Zero imports from src/basic_stats or duckdb" to eliminate the false positive. Not a code bug — a phrasing adjustment.

**Post-completion edge-case fix (2026-04-30):** The original `append_or_update` checked `run_id != entry["last_seen_run_id"]` to decide whether to bump `seen_count`. This is insufficient for true distinct-run idempotency: an A→B→A replay would bump `seen_count` to 3 even though only two distinct run_ids appeared. Fixed by adding a durable `seen_run_ids: list[str]` field to entries. The check is now `run_id not in entry["seen_run_ids"]`. Old entries without the field are backfilled conservatively from `first_seen_run_id`/`last_seen_run_id`. 11-SPEC.md §3 schema and field semantics updated accordingly. New test `test_append_replayed_older_run_id_does_not_bump_seen_count` (A→B→A) added. Total test count: 11.

## Known Stubs

None. All functions are fully implemented; the seed JSON `failure_backlog.json` is intentionally empty (correct initial state per spec).

## Next Phase Readiness

- Plan 11-03 (Cluster Triage Rubric) can import `from evals.discovery.failure_backlog import append_or_update` directly.
- `find_by_signature`, `load_backlog`, `save_backlog`, `next_id` all available for downstream plans.
- Backlog file path: `evals/discovery/failure_backlog.json` (DEFAULT_BACKLOG_PATH).
- All Phase 10 baseline tests (173) continue passing; total suite is 183/183.

---
*Phase: 11-iterative-synthetic-discovery-loop-v1*
*Completed: 2026-04-29*
