---
date: 2026-03-27
author: Jorge
scope: Basic Stats Analyst
status: completed
---

# Progress Log — 2026-03-27

## Context

Continues directly from:

- `docs/progress/2026-03-26-fixes_&_improving_verbalizing.md`

After closing the benchmark at 50/50 and improving verbalization, this block focused on three things:

1. Initializing a proper Claude Code / GSD project structure for ongoing brownfield work
2. Reducing non-fatal planner noise (without touching the pipeline success path)
3. A small UI hardening to avoid leaking internal error details to users

---

## Scope

No architecture changes. No benchmark regressions permitted.

---

## Files touched

### Planning / config
- `AGENTS.md` (created)
- `.planning/PROJECT.md` (created)
- `.planning/REQUIREMENTS.md` (created)
- `.planning/ROADMAP.md` (created)
- `.planning/STATE.md` (created)
- `.planning/config.json` (created)

### Core
- `utils/basic_stats/core/query_planner.py`
- `utils/basic_stats/core/test_query_planner.py`

### UI
- `pages/basic_stats.py`

---

## What was done

### 1. GSD project initialization

Set up a Claude Code / GSD planning structure for the repo so future sessions don't re-derive context from scratch.

- `AGENTS.md`: project identity, constraints, collaboration rules
- `.planning/PROJECT.md`: stable description, validated requirements, key decisions, sensitivity map
- `.planning/REQUIREMENTS.md`: traceability from requirements to phases
- `.planning/ROADMAP.md`: phase structure
- `.planning/STATE.md`: live status, benchmark baseline, operating rules, next step
- `.planning/config.json`: GSD workflow settings

**Correction applied**: the initial GSD pass generated planning docs using inferred assumptions rather than actual repo state. A second pass corrected this by running `eval_runner_v4.py` for real and documenting the actual 50/50 baseline rather than estimated values. Planning docs were rewritten to reflect confirmed facts only.

### 2. Planner noise reduction (Phase 2)

The eval runner was emitting multiple `[PLANNER ERROR]` lines per run even when final answers passed. These came from the LLM returning plausible-but-non-canonical metric names or aggregations that failed `_validate_scope_and_metric`, triggering the legacy fallback path.

Changes made to `query_planner.py`:

- **Extended `METRIC_ALIASES`** with 7 scope-aware entries:
  - `yellow_cards`, `yellow_card` → `total_yellow_cards` (players_summary)
  - `goals_per_90` → `total_goals_p90` (players/teams summary)
  - `progressive_passes_per_90` → `progressive_passes_p90` (players/teams summary)
  - `passing_accuracy` → `pass_accuracy_pct` (players/teams summary)
  - `offsides_drawn` → `offsides` (teams_summary)
  - `team_score` → `total_goals` (summary scopes only)
- **Aggregation canonicalization**: `mean` / `average` → `avg`
- **Metric key writeback**: after `_normalize_metric_key`, writes the result back to `plan["metric"]`
- **Scope guard fix**: `total_goals → team_score` conversion was applying to all team queries including `teams_summary` (wrong). Gated to `table_scope == "team_match"` only.

Added **11 unit tests** in `test_query_planner.py` (`CANONICALIZE_CASES` C01–C11):
- Metric alias normalization (no LLM)
- Aggregation canonicalization
- Scope guard behavior

### 3. Critical finding: some planner noise must stay

Attempts to also canonicalize `per_90` / `per90` aggregations (and add aliases for `dribble_success_rate`, `shots_on_target_per_90`) caused benchmark regressions on questions with `position=forward` filters.

Root cause: when `per_90` is canonicalized to a valid aggregation, the planner path runs — but the planner DuckDB query with `position=forward` + p90 metrics returns empty or wrong results. The legacy `_resolve_metric` path handles these correctly.

**Decision**: `per_90` / `per90` aggregation is intentionally left as-is in `_canonicalize_raw_plan`. The validation failure sends it to legacy, which gives the correct answer.

Remaining `[PLANNER ERROR]` cases per run (~8): `dribble_success_rate`, `shots_on_target_per_90`, `recoveries+per_90`, `aerial_duels_won+per_90`, `touches_in_box+per_90`, `key_passes_per_90`, `pass_accuracy`, `total` aggregation. All correctly handled by legacy fallback. Do not attempt to "fix" these without first auditing the DuckDB position-filter path.

### 4. UI hardening (pages/basic_stats.py)

On pipeline exception, the UI previously showed `f"Something went wrong: {e}"` directly in the chat — leaking raw exception strings including potential API endpoint details.

Changes:
- Chat message on exception: `"Sorry, I couldn't answer that question. Enable debug info for details."`
- Debug panel now renders `debug["error"]` via `st.code()` when present (previously stored but never rendered)

---

## Benchmark status

| Run | Date | Result |
|-----|------|--------|
| Post-Phase-2 verification | 2026-03-27 | **50/50** |
| Pre-Phase-2 baseline | 2026-03-26 | 50/50 |

Saved outputs:
- `docs/evals/latest_eval_results_v4.json`
- `docs/evals/2026-03-27_13-22-06_eval_results_v4.json`

---

## Current repo state

- Planning docs initialized and consistent with real repo state
- Benchmark locked at 50/50
- ~8 intentional `[PLANNER ERROR]` cases per run (legacy fallbacks, correct answers)
- Verbalization improved in the previous session but not the current priority
- UI is clean: exception path hardened, debug panel complete

**Sensitivity map (unchanged):**
- Very sensitive: `query_planner.py`, `duckdb_manager.py`, `llm_query_engine_v2.py`
- Sensitive: `models.py`, `resolve_query_intent.yaml`, `verbalize.yaml`
- Lower: `pages/basic_stats.py`, `docs/`

---

## What not to reopen

- Broad planner rewrites
- `per_90` aggregation canonicalization (regression risk, see finding above)
- Verbalization architecture changes (current output quality is acceptable for now)
- Legacy path removal (it is actively load-bearing for multiple question types)

---

## Next recommended step

Any of these, smallest-first:

1. **EXEC-01/02**: Verify execution correctness across all supported scopes (`players_summary`, `teams_summary`, `player_match`, `player_match_event`, `team_match`) — add targeted queries for any scope not fully covered by the benchmark
2. **UI-01/02**: Remaining UI edge cases in `pages/basic_stats.py` (zero-result handling, tie display for top-n > 1)
3. **PLAN noise (safe only)**: Audit remaining 8 legacy-fallback cases; fix only those where the planner path is confirmed correct for all position filters

Any change to a very-sensitive file requires running `eval_runner_v4.py` before closing the task.
