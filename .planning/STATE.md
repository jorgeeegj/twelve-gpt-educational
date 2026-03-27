# STATE.md

## Project Reference

See: `.planning/PROJECT.md` (updated 2026-03-26)

**Core value:** Every answer must stay grounded in actual data — no invented metrics, entities, values, or support rows.
**Current focus:** Phase 2 — Planner noise reduction (complete)

---

## Current Phase Status

**Phase 1 — Project Baseline** ✓ Complete
- ✓ GSD planning files written (PROJECT.md, REQUIREMENTS.md, ROADMAP.md, STATE.md, config.json)
- ✓ eval_runner_v4 baseline run completed and documented (50/50, 2026-03-26)

**Phase 2 — Planner Noise Reduction** ✓ Complete (2026-03-27)
- ✓ Reduced non-fatal `[PLANNER ERROR]` noise in `query_planner.py` while preserving 50/50 benchmark
- ✓ Changes made to `query_planner.py`:
  - Extended `METRIC_ALIASES` with 7 new scope-aware entries: `yellow_cards`, `yellow_card`, `goals_per_90`, `progressive_passes_per_90`, `passing_accuracy`, `offsides_drawn`, `team_score` (summary scopes)
  - Added `mean`/`average` → `avg` aggregation canonicalization
  - Added metric key writeback after `_normalize_metric_key` call
  - Fixed scope guard: `total_goals → team_score` conversion now gated to `table_scope == "team_match"` only (prevents invalid conversion for `teams_summary`)
  - `per_90`/`per90` aggregation intentionally NOT canonicalized — these correctly fall back to legacy path which handles position-filter + p90 queries correctly
- ✓ Added 11 unit tests in `test_query_planner.py` (`CANONICALIZE_CASES` C01-C11, no LLM required)
- ✓ Benchmark verified at 50/50 after all changes (2026-03-27)

**Remaining noise (intentional legacy fallbacks):** ~8 `[PLANNER ERROR]` cases per run:
  - `dribble_success_rate`, `shots_on_target_per_90`: alias deliberately excluded — planner path gives wrong results for position=forward queries
  - `recoveries+per_90`, `aerial_duels_won+per_90`, `touches_in_box+per_90`, `key_passes_per_90`: `per_90` aggregation correctly falls to legacy
  - `pass_accuracy` (without `_pct`): minor LLM variant, handled by legacy
  - `total` aggregation: unsupported, handled by legacy

**Next immediate step:** Decide the next highest-value task (see PROJECT.md Active requirements)

---

## Benchmark Baseline

### 2026-03-27 — Post noise reduction
Command: `PYTHONIOENCODING=utf-8 python eval_runner_v4.py`
Pass rate: 50/50
Failing cases: none
Saved outputs:
  - docs/evals/latest_eval_results_v4.json
  - docs/evals/2026-03-27_13-22-06_eval_results_v4.json

### 2026-03-26 — Original baseline
Command: `python eval_runner_v4.py --label "Sprint 6 - final fix - checking"`
Pass rate: 50/50
Failing cases: none
Saved outputs:
  - docs/evals/2026-03-26_21-58-26_eval_results_v4.json
  - docs/evals/2026-03-26_21-58-26__sprint_6_-_final_fix_-_checking.json

---

## Operating Rules

- `query_planner.py`, `duckdb_manager.py`, `llm_query_engine_v2.py` are very sensitive — no change without test + eval validation
- `models.py`, `resolve_query_intent.yaml`, `verbalize.yaml` are sensitive — validate outputs after any change
- `pages/basic_stats.py`, `docs/` are lower sensitivity — can change more freely
- A task is done only when: implemented + relevant verification run + results checked + STATE.md updated

## Phase Progression

| Phase | Status | Pass Rate (entry) | Pass Rate (exit) |
|-------|--------|-------------------|------------------|
| 1 | ✓ Complete | — | 50/50 |
| 2 | ✓ Complete | 50/50 | 50/50 |
| 3 | ○ Pending | — | — |

---

## Context Files

| File | Purpose |
|------|---------|
| `.planning/PROJECT.md` | Stable project description, validated requirements, key decisions |
| `.planning/REQUIREMENTS.md` | Scoped v1 requirements with traceability |
| `.planning/ROADMAP.md` | Phase structure and success criteria |
| `.planning/STATE.md` | Live status, benchmark baseline, next step (this file) |
| `.planning/config.json` | GSD workflow settings |
| `docs/progress/` | Historical session logs — read for context, not as live planning surface |
| `docs/evals/` | Eval run outputs — read for historical data |

---
*Last updated: 2026-03-27 after planner noise reduction (Phase 2) — 50/50 benchmark preserved*
