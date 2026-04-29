---
phase: 10-self-generated-robustness-synthetic-uat
plan: "04"
subsystem: testing
tags: [python, synthetic-uat, failure-clustering, markdown-report, heuristic]

# Dependency graph
requires:
  - phase: 10-03
    provides: synthetic_runner.py with _evaluate_entry producing result rows with failure_category field
provides:
  - Heuristic failure clusterer (cluster_failures) grouping by (category, failure_category)
  - Markdown report writer (write_report) with cluster table + per-cluster detail sections
  - Live runs now produce failure_clusters.json + REPORT.md alongside summary.json + results.json
affects:
  - 10-05 (regression scaffold reads failure_signature values from cluster output)
  - 10-06 (verification confirms exit gate 4: failure clustering completed)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Lazy import inside run() body (not top-level) to keep Plan 03 tests runnable before clusterer exists on disk"
    - "Heuristic cluster key: (category, failure_category) tuple — no LLM dependency"
    - "Cluster sort: count desc, then category alpha as tiebreaker"
    - "Sample answer truncation at 200 chars per SPEC schema"

key-files:
  created:
    - evals/synthetic_clusterer.py
    - tests/test_synthetic_clusterer.py
  modified:
    - evals/synthetic_runner.py

key-decisions:
  - "Lazy import of cluster_failures/write_report inside run() — avoids import-time dependency for Plan 03 isolated test runs"
  - "Cluster key is (category, failure_category) per plan spec — maps directly to SPEC section 6 guard_evidence field"
  - "Dry-run path unchanged — clustering is for live runs only (early-return before lazy import)"

patterns-established:
  - "Lazy import pattern: place heavy/new imports inside function body after early-returns to preserve isolated test runs"
  - "Heuristic clusterer: pure dict aggregation with defaultdict(list) buckets, no external dependencies"

requirements-completed:
  - SYNTH-04

# Metrics
duration: 2min
completed: 2026-04-28
---

# Phase 10 Plan 04: Heuristic Failure Clusterer + Markdown Report Summary

**Heuristic (category x guard_evidence) failure clusterer with Markdown report writer, wired into synthetic_runner.run() via lazy import — live runs now produce failure_clusters.json + REPORT.md alongside existing outputs**

## Performance

- **Duration:** 2 min
- **Started:** 2026-04-28T22:09:38Z
- **Completed:** 2026-04-28T22:11:54Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- `evals/synthetic_clusterer.py` (116 lines): `cluster_failures()` groups result rows by `(category, failure_category)` tuple into clusters matching 10-SPEC.md section 6 schema; `write_report()` writes Markdown with header, stats, cluster table, per-cluster detail sections, and next-step note
- `evals/synthetic_runner.run()` wired: after `results.json` is written, lazy-imports clusterer and writes `failure_clusters.json` + `REPORT.md` to run dir; dry-run path unchanged
- 11 new tests in `tests/test_synthetic_clusterer.py` covering empty, no-failures, single-failure, grouping, guard separation, category separation, sort order, truncation, report variants, and dry-run skip behavior
- 172/172 tests passing (161 baseline + 11 new); `src/basic_stats/` shows zero diff

## Task Commits

1. **Task 1: Implement evals/synthetic_clusterer.py** - `f752b2a` (feat)
2. **Task 2: Wire clusterer into synthetic_runner.run() + tests** - `ca70b4b` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified

- `evals/synthetic_clusterer.py` — cluster_failures() + write_report(); 116 lines, no LLM dependency
- `evals/synthetic_runner.py` — 5 new lines in run(): lazy import + cluster call + two file writes
- `tests/test_synthetic_clusterer.py` — 11 unit tests, no live LLM

## Decisions Made

- **Lazy import placement:** Import inside `run()` body after the `dry_run` early-return. This means Plan 03 test suite (`tests/test_synthetic_runner.py`) can still be run in isolation before `evals/synthetic_clusterer.py` exists, because module-load of `synthetic_runner.py` never triggers the clusterer import.
- **Cluster key = (category, failure_category):** Directly satisfies SPEC section 6; `failure_category` from `_classify_failure` maps 1:1 to `guard_evidence` in the output schema.
- **Sort key = (-count, category):** Count descending first; category alphabetical as tiebreaker for stable ordering when counts are equal.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 05 (regression scaffold) can now read `failure_signature` values from `failure_clusters.json` to author regression test docstrings
- Plan 06 verification can confirm exit gate 4 by checking that a live run produces `failure_clusters.json` + `REPORT.md`
- Clusterer is fully decoupled from production agent code — `src/basic_stats/` zero diff

## Known Stubs

None - clusterer is fully wired. Data flows from `results` list through `cluster_failures()` to `failure_clusters.json` and `REPORT.md`.

---
*Phase: 10-self-generated-robustness-synthetic-uat*
*Completed: 2026-04-28*
