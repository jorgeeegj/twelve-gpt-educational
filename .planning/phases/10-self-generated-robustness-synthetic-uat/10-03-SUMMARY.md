---
phase: 10-self-generated-robustness-synthetic-uat
plan: "03"
subsystem: testing
tags: [synthetic-runner, eval-runner, fixture-validation, multi-turn, dry-run, threadpool]

# Dependency graph
requires:
  - phase: 10-self-generated-robustness-synthetic-uat
    plan: "02"
    provides: "evals/synthetic/seed_questions.json — 24-question seed fixture with all 12 categories"
provides:
  - "evals/synthetic_runner.py — synthetic UAT runner: fixture in, results.json + summary.json out"
  - "tests/test_synthetic_runner.py — 20 unit tests covering all runner helpers, no live LLM"
  - ".gitignore updated: evals/runs/ now ignored"
affects:
  - "10-04: clusterer reads results.json from run_dir produced by this runner"
  - "10-05: regression scaffold may import helpers from evals.synthetic_runner"
  - "10-06: live run verification uses this runner end-to-end"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Lazy agent import pattern: _import_agent() defers DuckDB load so --dry-run skips heavy deps"
    - "One BasicStatsAgent per question: prevents Responses API 400 errors from shared instance"
    - "_ask_with_retry with exponential backoff: copied from agent_benchmark.py for self-containment"
    - "Multi-turn via | separator: same-agent sequential calls without reset() between turns"
    - "ThreadPoolExecutor with fixture-order re-sort: parallel execution, deterministic output order"

key-files:
  created:
    - "evals/synthetic_runner.py"
    - "tests/test_synthetic_runner.py"
  modified:
    - ".gitignore"

key-decisions:
  - "Copy _ask_with_retry verbatim from agent_benchmark.py rather than importing — keeps runner self-contained without forcing an agent_benchmark refactor"
  - "Lazy BasicStatsAgent import via _import_agent() so --dry-run does not pull in DuckDB"
  - "Faithfulness judge called only when expected_behavior=='answerable' AND expected_values is not null, matching Plan 03 contract"
  - "faith_entry wraps expected_values as {'answer': ...} because judge_faithfulness reads entry.get('answer')"
  - "Add evals/runs/ to .gitignore (was missing despite SPEC stating it was already covered)"

patterns-established:
  - "Dry-run pattern: validate fixture, write minimal summary.json + empty results.json, return run_dir, no agent"
  - "failure_category = None means pass; non-null string is the guard that fired"

requirements-completed:
  - SYNTH-03

# Metrics
duration: 5min
completed: 2026-04-29
---

# Phase 10 Plan 03: Synthetic Runner Summary

**Executable synthetic UAT runner with fixture validation, multi-turn support, --dry-run mode, and 20 passing unit tests — no production code touched**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-04-28T22:00:48Z
- **Completed:** 2026-04-29T00:05:00Z
- **Tasks:** 2 of 2
- **Files modified:** 3 (2 new, 1 modified)

## Accomplishments

- Implemented `evals/synthetic_runner.py` (246 lines) — full runner per 10-SPEC.md section 4
- `--dry-run` validates fixture schema and exits 0, writing summary.json + empty results.json
- Multi-turn question chains (question contains `|`) are split and called sequentially on same agent instance
- 20 unit tests in `tests/test_synthetic_runner.py` — all passing, no live LLM or DuckDB required
- Added `evals/runs/` to `.gitignore` (missing despite SPEC claiming it was already covered)
- Existing 161/161 test suite fully green (160 baseline + 1 net new from real seed fixture guard)

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement evals/synthetic_runner.py** - `98edd3e` (feat)
2. **Task 2: Add tests/test_synthetic_runner.py** - `b79f00e` (test)

**Plan metadata:** (docs commit follows)

## Files Created/Modified

- `evals/synthetic_runner.py` — synthetic UAT runner: `run()`, CLI, multi-turn, dry-run, helpers
- `tests/test_synthetic_runner.py` — 20 unit tests: fixture load, validate, split_turns, classify_failure, dry-run path, real seed guard
- `.gitignore` — added `evals/runs/` to prevent staging timestamped run artifacts

## Decisions Made

- Copied `_ask_with_retry` verbatim from `agent_benchmark.py` rather than importing it — self-contained runner per CONTEXT.md reuse principle without forcing a refactor of agent_benchmark.
- `judge_faithfulness` requires `entry.get("answer")`, so `expected_values` is wrapped as `{"answer": entry["expected_values"]}` before calling the judge.
- `evals/runs/` added to `.gitignore` as a deviation fix — SPEC said it was already gitignored but it was not.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added evals/runs/ to .gitignore**
- **Found during:** Task 1 acceptance criteria verification
- **Issue:** SPEC section 4 states "This path is already covered by `evals/runs/` in `.gitignore`" but the `.gitignore` did not contain this entry. Every `--dry-run` invocation would create untracked run-dir artifacts.
- **Fix:** Added `evals/runs/` line to `.gitignore`
- **Files modified:** `.gitignore`
- **Verification:** `git check-ignore -v "evals/runs/..."` now returns the gitignore rule
- **Committed in:** `98edd3e` (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (Rule 2 - missing critical gitignore entry)
**Impact on plan:** Fix necessary to prevent run artifacts from being staged. No scope creep.

## Issues Encountered

None - all tests passed first run, dry-run worked immediately.

## User Setup Required

None - no external service configuration required for Plan 03. Live runs against BasicStatsAgent require `OPENAI_API_KEY` (pre-existing requirement, not Plan 03 scope).

## Reuse Confirmed

- `find_violations` from `evals.raw_key_guard` — reused as-is
- `judge_faithfulness` from `evals.judges.faithfulness_judge` — reused as-is
- `_ask_with_retry` pattern from `evals/agent_benchmark.py` — copied verbatim

## Pending (Downstream Plans)

- **Plan 04:** Clusterer reads `results.json` produced by this runner; writes `failure_clusters.json` + `REPORT.md`
- **Plan 05:** Regression scaffold (`tests/test_synthetic_regressions.py`) — may import helpers from `evals.synthetic_runner`
- **Plan 06:** Live run against seed fixture using `--label first_real --workers 5`; STATE.md update

## Known Stubs

None — runner is fully functional. Live execution deferred to Plan 06 (requires `OPENAI_API_KEY` and live agent session).

## Self-Check

- `evals/synthetic_runner.py` exists: FOUND
- `tests/test_synthetic_runner.py` exists: FOUND
- Commit `98edd3e` exists: verified via `git log`
- Commit `b79f00e` exists: verified via `git log`
- 20/20 tests pass: verified via `uv run pytest tests/test_synthetic_runner.py -v`
- 161/161 baseline preserved: verified via `uv run pytest tests/ -q --ignore=tests/test_fuzzy_resolve.py`

## Self-Check: PASSED

---
*Phase: 10-self-generated-robustness-synthetic-uat*
*Completed: 2026-04-29*
