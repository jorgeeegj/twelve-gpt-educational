---
phase: 11-iterative-synthetic-discovery-loop-v1
plan: 01
subsystem: planning
tags: [discovery-loop, failure-memory, triage-rubric, campaign-generator, iteration-runner, promotion-rules, spec]

# Dependency graph
requires:
  - phase: 10-self-generated-robustness-synthetic-uat
    provides: synthetic runner, clusterer, fixture schema, regression scaffold
provides:
  - 11-SPEC.md with all 13 locked sections as single authoritative contract for Plans 11-02..11-07
  - LOOP-01 requirement satisfied
affects:
  - 11-02-PLAN (failure-memory backlog — references §3 schema)
  - 11-03-PLAN (triage rubric — references §4 enum)
  - 11-04-PLAN (campaign generator — references §6 contract)
  - 11-05-PLAN (iteration runner — references §7 compare-runs semantics)
  - 11-06-PLAN (promotion rules — references §8 promotion table)
  - 11-07-PLAN (verification campaign — references §9 contract)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Spec-first authoring: 11-SPEC.md authored/verified before any executable code to lock contracts for downstream plans"
    - "Counter-idempotent seen_count: incremented only when run_id differs from last_seen_run_id — same-run reprocessing does NOT bump"
    - "Backlog-driven promote(): action_type is read from entry['recommended_action'], NOT passed as a parameter"
    - "Two-step backlog seeding: Phase 10 run first (seen_count=1), then new run (bumps to seen_count=2) to reach promotion eligibility"

key-files:
  created:
    - .planning/phases/11-iterative-synthetic-discovery-loop-v1/11-SPEC.md
  modified: []

key-decisions:
  - "seen_count counts distinct run_id values only — re-processing same run_id is counter-idempotent (prevents promotion gate inflation)"
  - "promote() API is backlog-driven with no action_type parameter — the action is read from entry['recommended_action']"
  - "Promotion eligibility: seen_count >= 2 (matches Phase 10 §7 regression-test reproduction requirement)"
  - "Phase 10 contracts (12-category taxonomy, fixture schema, runner, cluster schema) inherited by reference — NOT reduplicated in 11-SPEC.md"

patterns-established:
  - "13 sections (§1-§13) create stable anchors for all downstream plans to reference"
  - "Exit Gates table (§10): 9 gates with satisfied-by column mapping to LOOP-01..LOOP-07"
  - "Commit hygiene in spec (§12): stage by explicit paths only, gitignore checks inline"

requirements-completed: [LOOP-01]

# Metrics
duration: 0min (SPEC was already authored and patched during planning phase)
completed: 2026-04-29
---

# Phase 11 Plan 01: Phase 11 SPEC Summary

**11-SPEC.md (364 lines, 13 sections) authored as single authoritative contract for Plans 11-02..11-07 — all acceptance criteria pass**

## Performance

- **Duration:** Verification only (SPEC authored during planning; patched in bc95044)
- **Completed:** 2026-04-29
- **Tasks:** 2 (verified)
- **Files:** 1 (11-SPEC.md — already committed in bc95044)

## Accomplishments

- Confirmed `11-SPEC.md` (364 lines) has all 13 required sections in order
- All 7 triage action types present (`regression_test_needed`, `agent_behavior_fix_needed`, `context_missing`, `helper_tool_needed`, `fixture_issue`, `non_actionable`, `deferred`)
- Counter-idempotent `seen_count` semantics locked in §3 (distinct run_id counter; same-run reprocessing does NOT bump)
- Backlog-driven `promote()` API locked in §8 (no `action_type` parameter; reads from `entry["recommended_action"]`)
- Two-step backlog seeding strategy locked in §9 (Phase 10 run → new run → seen_count=2 for recurring clusters)
- Phase 10 inheritance confirmed in §13 (6 sections reused by reference; 12-category taxonomy NOT duplicated)
- `10-SPEC.md` referenced 12 times; `DIRECT_STATS` appears exactly 1 time (acceptable inline reference, not a block duplication)
- `src/basic_stats/` zero diff throughout

## Verification Results

All acceptance criteria pass:

```
✓ test -f .planning/phases/11-iterative-synthetic-discovery-loop-v1/11-SPEC.md
✓ grep -q 'Authoritative' 11-SPEC.md
✓ grep -q 'failure_backlog.json' 11-SPEC.md
✓ grep -q 'regression_test_needed' 11-SPEC.md
✓ grep -q 'backlog_version' 11-SPEC.md
✓ grep -q 'failure_signature' 11-SPEC.md
✓ grep -q 'unsupported_future__refuse_expected_but_answered' 11-SPEC.md
✓ grep -q 'workers 1' 11-SPEC.md
✓ grep -q 'src/basic_stats' 11-SPEC.md
✓ grep -c '10-SPEC.md' → 12 (≥4 required)
✓ grep -c 'DIRECT_STATS' → 1 (no block duplication)
✓ grep -E 'repeated|disappeared|mutated|new' → 20 hits (≥4 required)
✓ git diff --name-only src/basic_stats/ → 0 lines
```

## Key Contract Patches Applied (from bc95044)

1. **§3 seen_count semantics:** `seen_count` is a distinct-run counter. `run_id != entry["last_seen_run_id"]` → bump; `run_id == entry["last_seen_run_id"]` → do NOT bump. Counter-idempotency invariant documented.
2. **§8 promote() API:** Removed `action_type` parameter. Canonical: `def promote(backlog_entry_id: str, backlog_path: Path = DEFAULT_BACKLOG_PATH) -> Path | None`. API stability rule added — any plan introducing `action_type` parameter is a contract violation.
3. **§9 verification flow:** Two-step seeding — Phase 10 run seeded first (seen_count=1), new run updates (seen_count=2) — ensures recurring clusters reach promotion eligibility threshold.

## Deviations from Plan

None — SPEC was fully authored and patched during planning. Plan 11-01 execution = verification only.

## User Setup Required

None.

## Pending (downstream plans)

- Plan 02: `evals/discovery/failure_backlog.py` + JSON backlog + unit tests (LOOP-02)
- Plan 03: `evals/discovery/triage_rubric.py` + rubric doc + unit tests (LOOP-03)
- Plan 04: `evals/discovery/campaign_generator.py` + campaigns dir + unit tests (LOOP-04)
- Plan 05: `evals/discovery/iteration_runner.py` + unit tests (LOOP-05)
- Plan 06: `evals/discovery/promote.py` + fixture_fixes dir + unit tests (LOOP-06)
- Plan 07: Verification campaign run (checkpointed, OpenAI cost) (LOOP-07)

---
*Phase: 11-iterative-synthetic-discovery-loop-v1*
*Completed: 2026-04-29*
