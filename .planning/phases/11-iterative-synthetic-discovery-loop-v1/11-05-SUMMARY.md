---
phase: 11-iterative-synthetic-discovery-loop-v1
plan: "05"
subsystem: testing
tags: [iteration-runner, compare-runs, discovery-loop, synthetic-uat, phase11]

# Dependency graph
requires:
  - phase: 11-01
    provides: "11-SPEC.md locked — §7 compare_runs contract"
  - phase: 11-02
    provides: "failure_backlog.py — backlog entry shape"
provides:
  - "evals/discovery/iteration_runner.py — run_campaign / compare_runs / write_diff / helpers"
  - "8 unit tests covering all required cases"
affects: ["11-07"]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Lazy import: synthetic_runner imported inside run_campaign body — module collectable without DuckDB/openai"
    - "compare_runs operates purely on failure_clusters.json JSON — no agent/runner/DuckDB"
    - "mutated bucket: cluster-based detection (same qid, different signature) — no results.json needed"
    - "write_diff names file diff_against_<older_dir_name>.json"

key-files:
  created:
    - evals/discovery/iteration_runner.py
    - tests/test_iteration_runner.py
  modified: []

key-decisions:
  - "Lazy import of synthetic_runner inside run_campaign keeps the module importable for pure compare_runs tests without DuckDB/OpenAI"
  - "mutated detection uses cluster JSON (same qid, different failure_signature) — simpler than reading results.json, matches most common real-world case"
  - "max_workers defaults to 1 — preserves Phase 10 DuckDB concurrency lesson"

patterns-established:
  - "compare_runs is a pure function over two failure_clusters.json files"
  - "write_diff derives filename from diff['older_run'] (directory name, not full path)"

requirements-completed: [LOOP-05]

# Metrics
duration: 10min
completed: 2026-04-30
---

# Phase 11 Plan 05: Iteration Runner / Compare Runs Summary

**Pure-JSON compare_runs primitive with lazy-imported run_campaign wrapper — zero OpenAI/DuckDB cost in test mode**

## Performance

- **Duration:** ~10 min
- **Started:** 2026-04-30T01:00:00Z
- **Completed:** 2026-04-30T01:10:00Z
- **Tasks:** 2
- **Files created:** 2

## Accomplishments

- `evals/discovery/iteration_runner.py` — 5 functions per 11-SPEC.md §7. `run_campaign` lazily imports `synthetic_runner.run`. `compare_runs` classifies cluster differences into `repeated / disappeared / mutated / new` buckets. `write_diff` writes `diff_against_<older_run>.json` to the newer run directory.
- `tests/test_iteration_runner.py` — 8 tests (all required). 238/238 project tests pass.

## Task Commits

1. **Tasks 1-2** — `4e7d2e6` (feat)

## Files Created/Modified

- `evals/discovery/iteration_runner.py`
- `tests/test_iteration_runner.py`

## Decisions Made

- Lazy import of `synthetic_runner` inside `run_campaign` body — the module is collectable without DuckDB or OpenAI installed, enabling `compare_runs` tests to run freely.
- `mutated` bucket uses cluster-based detection: same `question_id` appearing in both runs' clusters under different `failure_signature` values. Simpler than reading `results.json`; documented in docstring.
- `max_workers=1` default preserves the Phase 10 DuckDB concurrency lesson.

## Deviations from Plan

None. All 8 required tests implemented. `_load_clusters`, `_index_by_signature`, `_index_question_to_signature` implemented as specified.

## Issues Encountered

Minor: test file docstring contained "from src.basic_stats" as a natural-language phrase which triggered the `! grep -q 'from src\.basic_stats'` acceptance check. Fixed by rephrasing to "No src.basic_stats or BasicStatsAgent imports."

## Known Stubs

- `run_campaign` is wired but not exercised end-to-end in this plan's tests (requires DuckDB + OpenAI). Live execution is in Plan 11-07.

## Next Phase Readiness

- Plan 11-06 (Promotion Rules) can `from evals.discovery.iteration_runner import compare_runs` directly.
- Plan 11-07 (Verification Campaign) will call `run_campaign(path, label=...)` and then `compare_runs(phase10_run_dir, new_run_dir)`.
- All 238 project tests pass; baseline suite (173) unaffected.

---
*Phase: 11-iterative-synthetic-discovery-loop-v1*
*Completed: 2026-04-30*
