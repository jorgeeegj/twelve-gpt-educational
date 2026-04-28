---
phase: 10-self-generated-robustness-synthetic-uat
plan: 01
subsystem: testing
tags: [synthetic-uat, failure-taxonomy, runner-contract, regression-tests, eval]

# Dependency graph
requires:
  - phase: 09-natural-language-polish
    provides: raw_key_guard and faithfulness_judge guards that synthetic runner reuses
provides:
  - 10-SPEC.md with 12-category failure taxonomy and frozen runner/cluster/regression contract
  - SYNTH-01..06 requirement definitions in REQUIREMENTS.md
  - Phase 10 finalized entry in ROADMAP.md
affects:
  - 10-02-PLAN (synthetic fixture — references section 3 schema)
  - 10-03-PLAN (runner — implements section 4 contract)
  - 10-04-PLAN (clusterer — implements sections 5/6 schema)
  - 10-05-PLAN (regression scaffold — implements section 7 workflow)
  - 10-06-PLAN (verification — closes exit gates from section 8)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Spec-first authoring: SPEC.md authored before any executable code to lock the contract for downstream plans"
    - "Failure taxonomy enum: 12 DIRECT_STATS..DEMO_RANDOM categories, each question tagged with exactly one"
    - "Dry-run mode: --dry-run validates fixture only, no agent calls, writes minimal summary.json + empty results.json"
    - "Multi-turn encoding: '|' separator in question string; is_multi_turn + turn_answers fields in results.json"

key-files:
  created:
    - .planning/phases/10-self-generated-robustness-synthetic-uat/10-SPEC.md
  modified:
    - .planning/REQUIREMENTS.md
    - .planning/ROADMAP.md

key-decisions:
  - "Use 12 fixed enum categories (DIRECT_STATS through DEMO_RANDOM) matching CONTEXT.md scope coverage — not generated at runtime"
  - "dry_run=False default: failure presence does not produce non-zero exit code (discovery not gating)"
  - "One BasicStatsAgent instance per question to prevent _last_response_id corruption in parallel workers"
  - "Multi-turn questions use '|' separator in question string; final-turn answer is evaluated by guards"
  - "Initial clustering is heuristic only (category x guard_evidence) — LLM sub-clustering deferred"

patterns-established:
  - "Spec section headers ## 1. through ## 10. create stable anchors for downstream plans to reference by section number"
  - "failure_category is null in results.json for passing questions; set by clusterer for failing ones"

requirements-completed: [SYNTH-01]

# Metrics
duration: 12min
completed: 2026-04-28
---

# Phase 10 Plan 01: Specification Authoring Summary

**12-category failure taxonomy, frozen synthetic_runner.run() contract, cluster schema, and regression-test workflow documented in 10-SPEC.md as single source of truth for Plans 02-06**

## Performance

- **Duration:** 12 min
- **Started:** 2026-04-28T21:43:35Z
- **Completed:** 2026-04-28T21:56:00Z
- **Tasks:** 2
- **Files modified:** 3 (1 created, 2 updated)

## Accomplishments

- Authored `10-SPEC.md` (240 lines) with all 10 required sections — failure taxonomy, fixture schema, runner contract, dry-run mode, per-question result schema, cluster schema, regression workflow, 7 exit gates, non-goals, commit hygiene
- Added 6 SYNTH-NN requirement definitions to `REQUIREMENTS.md` with full assertion text matching CONTEXT.md exit gates
- Replaced ROADMAP.md Phase 10 stub with finalized goal, success criteria, and progress tracking row

## Task Commits

Each task was committed atomically:

1. **Task 1: Write 10-SPEC.md with failure taxonomy + runner contract + report schema** - `88ecb4b` (docs)
2. **Task 2: Add SYNTH-01..06 to REQUIREMENTS.md and update ROADMAP.md Phase 10 entry** - `03e0872` (docs)

## Files Created/Modified

- `.planning/phases/10-self-generated-robustness-synthetic-uat/10-SPEC.md` — Phase 10 single contract: taxonomy, runner contract, fixture schema, cluster schema, regression workflow, 7 exit gates, non-goals
- `.planning/REQUIREMENTS.md` — Added Phase 10 section with SYNTH-01..06 definitions; updated traceability table and coverage count
- `.planning/ROADMAP.md` — Replaced Phase 10 stub; added progress tracking row (0/6, Planned)

## Decisions Made

- Used ASCII hyphen (`-`) in "Output files - dry-run" section heading instead of em-dash so the acceptance criterion `grep -E "Output files . dry-run"` matches with a single `.`
- Acceptance-driven approach: all 11 plan acceptance criteria verified before committing

## Deviations from Plan

None - plan executed exactly as written. One minor heading adjustment (em-dash to hyphen for grep-compatibility) made during verification before the first commit.

## Issues Encountered

The plan's acceptance criterion `grep -E "Output files . dry-run"` uses `.` which matches only single bytes. The em-dash `—` is a 3-byte UTF-8 character and the pattern would not match. Fixed by using a plain ASCII hyphen in that section heading before committing.

## User Setup Required

None - no external service configuration required.

## Pending (downstream plans)

- Plan 02: `evals/synthetic/seed_questions.json` fixture with ≥24 entries (SYNTH-02)
- Plan 03: `evals/synthetic_runner.py` implementation (SYNTH-03)
- Plan 04: `evals/synthetic_clusterer.py` + REPORT.md generation (SYNTH-04)
- Plan 05: `tests/test_synthetic_regressions.py` scaffold (SYNTH-05)
- Plan 06: Live run + verification + STATE.md update (SYNTH-06)

## Next Phase Readiness

- `10-SPEC.md` is the locked contract; Plans 02-06 can be executed without ambiguity
- All 7 exit gates are mapped to specific plans
- No changes to `src/basic_stats/*` (read-only constraint enforced throughout)

## Known Stubs

None — this plan produces only documentation artifacts, no code stubs.

---
*Phase: 10-self-generated-robustness-synthetic-uat*
*Completed: 2026-04-28*
