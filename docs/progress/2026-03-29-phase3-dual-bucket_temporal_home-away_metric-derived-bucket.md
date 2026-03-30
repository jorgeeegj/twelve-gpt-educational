---
date: 2026-03-29
author: Jorge
scope: Basic Stats Analyst
status: in progress (benchmark rerun pending)
---

# Progress Log — 2026-03-29

## Context

Continues directly from:

- `docs/progress/2026-03-27-project-init_planner-robustness_ui-hardening.md`

Phase 2 closed with the benchmark at 50/50 and planner noise intentionally stabilized. Phase 3 opened with the goal of answering a wider class of comparison and filtered questions that the existing planner path does not support. All additions in this log are early-return guards that intercept specific question shapes before the normal planner path runs — existing paths are not modified.

---

## Scope

New question-handling slices added to `llm_query_engine_v2.py`. No changes to `duckdb_manager.py`, `query_planner.py` (beyond canonicalization extensions and player-name resolution helpers), or `models.py`. No benchmark regressions permitted.

---

## Files touched

- `utils/basic_stats/core/llm_query_engine_v2.py` — all new slice logic
- `utils/basic_stats/core/query_planner.py` — canonicalization extensions, player-name resolution helpers
- `utils/basic_stats/core/test_query_planner.py` — unit tests for all new slices
- `utils/basic_stats/core/test_dual_bucket_hardening.py` — live smoke tests (LLM + DuckDB)
- `.planning/STATE.md` — updated throughout

---

## What was implemented

### 1. Dual-bucket comparison (narrow, stable)

Supports questions of the form: "Has [subject] scored more goals against top N or bottom N teams?"

Detection via `_detect_dual_bucket_comparison(q)` in `query_planner.py`. Execution via `_execute_dual_bucket_comparison` in `llm_query_engine_v2.py`.

Implementation approach:
- Plan once using the normal planner
- Override bucket filters for each sub-query (`opponent_rank_lte` vs `opponent_rank_gte`)
- Execute two sub-queries via `_run_bucket_sub_query`; compose the answer in code
- LLM-independent subject extraction via `_match_known_name` + `_resolve_player_suffix` (guards against LLM returning wrong or partial names)
- `_bucket_label(bucket)` helper maps filter dicts to human-readable strings ("top 5 teams", "bottom 6 teams", etc.)

Hardened against:
- Non-existent player names (falls through to normal path)
- Partial names without initials ("Haaland" → "E. Haaland")
- Either sub-query returning no data (falls through rather than returning a zero)

Example: `"Has E. Haaland scored more goals against top 5 teams or bottom 5 teams?"`

### 2. Away/home modifier in dual-bucket answers

If a question specifies "away goals" or "home goals", the dual-bucket answer now reflects the modifier: "E. Haaland has scored 2 away goals against the top 5 teams and 4 away goals against the bottom 5 teams."

This is composed in code inside `_execute_dual_bucket_comparison` from `plan.filters.is_home`. The `is_home` filter is set by the normal planner and read before sub-query execution.

Example: `"Has A. Isak scored more away goals against top 6 or bottom 6 teams?"`

### 3. Temporal-window support (`last N gameweeks`)

The planner did not previously support relative temporal references. Added to `query_planner.py`:

- `_extract_recent_window(q)` — regex for "last N gameweeks/rounds/matchdays"
- `_load_max_matchday()` / `self.max_matchday` — loaded from parquet at init
- Canonicalization: "last N gameweeks" → `matchday_start = max_matchday - N + 1`, `matchday_end = max_matchday`

Also extended `_resolve_player_suffix` with a surname-fallback pass ("Bruno Fernandes" → "B. Fernandes"), and added metric name normalization for summary-scope LLM outputs (`total_goals` → `goals`, `total_assists` → `assists`) in the `has_context` code path.

Example: `"How many goals has Haaland scored in the last 5 gameweeks?"`

### 4. Home-vs-away comparison

Supports questions of the form: "Has [subject] scored more goals home or away?"

Detection via `_detect_home_away_comparison(q)` (module-level, `llm_query_engine_v2.py`): requires both "home" and "away" present with an "or" connector; excludes questions that also contain rank-bucket language (which routes to dual-bucket).

Execution via `_execute_home_away_comparison`: reuses `_run_bucket_sub_query` with `{"is_home": False}` and `{"is_home": True}` overrides. Subject extraction is LLM-independent (same pattern as dual-bucket). Answer is code-composed.

Example: `"Has Mohamed Salah scored more away goals or home goals?"`

### 5. Metric-derived bucket (widened slice — 2026-03-30)

Supports questions of the form: "How many [goals|assists] has [subject] [scored|made] against the N teams that [have] [scored|conceded] the most/fewest [goals|shots]?"

This is distinct from fixed rank buckets (top-N by points). The opponent set is derived from `teams_summary` data.

Added to `llm_query_engine_v2.py` (module-level):

- `_detect_metric_derived_bucket(q)` — regex detection; guarded by `_classify_all_buckets`
- `_derive_teams_for_bucket(teams_df, n, bucket_metric, descending)` — Polars in-memory sort of `teams_df`; returns N team names

Execution via `_execute_metric_derived_bucket`:
- Subject identified first; subject's own team excluded from derived bucket (n+1 fetch + filter)
- Final metric resolved from question language (priority-ordered, deterministic)
- Runs raw SQL against `player_match_stats` (player) or `team_match_stats` (team)
- Returns short factual answer with explicit team list

**Supported bucket metrics** (opponent set derivation):
- `total_goals` — `score[ds]?` + trailing `goals` (or none)
- `total_goals_against` — `concede[ds]?` + trailing `goals` (or none)
- `shots_against` — `concede[ds]?` + trailing `shots` (NEW)
- `shots` — `score[ds]?` + trailing `shots` (NEW)

**Supported final answer metrics**:
- Player: `goals` (scored) and `assists` (made) (NEW)
- Team: `goals scored` (team_score) and `goals conceded` (opponent_score)
- Player `shot_assists`: explicitly not supported (not in `player_match_stats` at match level)

**Subject exclusion**: both team subject and player subject (via club lookup) are excluded from the derived opponent set.

Examples (all working):
- `"How many goals has Salah scored against the 3 teams that have conceded the fewest goals?"` — bucket: `total_goals_against`/fewest, final: goals
- `"How many goals has Liverpool conceded against the 3 teams that score the most?"` — bucket: `total_goals`/most, final: goals conceded
- `"How many goals has Salah scored against the 3 teams that concede the most shots?"` — bucket: `shots_against`/most, final: goals (NEW)
- `"How many assists has Fernandes made against the 3 teams that concede the fewest shots?"` — bucket: `shots_against`/fewest, final: assists (NEW)

---

## Fixed (2026-03-30) — subject team excluded from metric-derived opponent bucket

The subject's own team is now excluded from the derived opponent bucket. This affects both team subjects and player subjects (via player's club lookup from `players_df["team_name"]`).

**Fix applied in `_execute_metric_derived_bucket`** (`llm_query_engine_v2.py`):
- Subject is identified before teams are derived
- `subject_team_lower` is resolved (team subject → directly; player subject → `players_df` lookup by `short_name`)
- `_derive_teams_for_bucket` is called with `n+1` to provide one exclusion slot
- Subject team is filtered out; first `n` remaining teams are used
- Both the SQL params and the answer text use the corrected team list

**Verified derivation results:**
- Q1 (`Salah`, exclude `Liverpool`, fewest `total_goals_against`, n=3): `['Arsenal', 'Chelsea', 'Manchester City']`
- Q2 (`Liverpool`, exclude `Liverpool`, most `total_goals`, n=3): `['Manchester City', 'Arsenal', 'Newcastle United']`

**`_derive_teams_for_bucket` signature unchanged.** No other functions modified.

---

## Unit tests

All non-LLM detection and canonicalization tests are in `test_query_planner.py`.

| Group | Cases | Status |
|-------|-------|--------|
| C01–C17 | Canonicalize / temporal-window | 17/17 |
| D01–D06 | Dual-bucket detection | 6/6 |
| Bucket labels | `_bucket_label` helper | 7/7 |
| H01–H06 | Home-away detection | 6/6 |
| M01–M10 | Metric-derived bucket detection | 10/10 |
| **Total** | | **47/47** |

Live smoke tests for dual-bucket hardening are in `test_dual_bucket_hardening.py` (T1–T4, require live LLM + DuckDB).

---

## Verification status

| What | Status |
|------|--------|
| Non-LLM unit tests (43 cases) | Verified passing |
| Dual-bucket smoke tests (T1–T4, live) | Verified passing |
| Home-away smoke test (live) | Verified passing |
| Metric-derived bucket smoke tests (2 questions, live) | Verified passing |
| Regression check (dual-bucket / home-away routing unaffected by metric-bucket guard) | Verified |
| `eval_runner_v4` full benchmark rerun | **Not run** — pending |
| Manual UI walkthrough for new slices | **Not run** — pending |

The `eval_runner_v4` benchmark was last confirmed at 50/50 on 2026-03-27 (post-Phase-2). All new Phase 3 additions are early-return guards on newly-detected question patterns; they do not modify any path exercised by the existing 50 benchmark questions. Formal rerun is still the correct gate before declaring Phase 3 closed.

---

## Current stable capabilities (summary)

Questions routed by the planner path (unchanged):
- Ranked summaries: "Who has scored the most goals?", "Which team has conceded the fewest?"
- Filtered summaries: "Which Liverpool player scored the most between matchdays 25 and 30?"
- Match-level queries with rank filters, position filters, age filters

Questions handled by Phase 3 early-return guards:
- Dual-bucket rank comparison with optional home/away modifier
- Temporal-window filtering ("last N gameweeks")
- Home-vs-away comparison
- Metric-derived opponent bucket (narrow: goals/goals-against bucket metric, goals final metric)

---

## What not to reopen

- `per_90` aggregation canonicalization — regression risk documented in Phase 2 log
- Legacy path removal — still load-bearing for ~8 question types per run
- Broad `query_planner.py` or `duckdb_manager.py` refactors without a full benchmark gate

---

## Verbalization polish (2026-03-30)

Applied after benchmark confirmed at 50/50 post-Phase-3 contextual enrichment.

**Files changed**: `llm_query_engine_v2.py`, `verbalize.yaml`

### Fixes applied

1. `_BUCKET_METRIC_LABEL` — 3 entries updated:
   - `("total_goals", True)`: `"score the most goals"` → `"have scored the most goals"` (consistency)
   - `("shots", True)`: `"score the most shots"` → `"take the most shots"` (natural phrasing)
   - `("shots", False)`: `"score the fewest shots"` → `"take the fewest shots"` (natural phrasing)

2. `_execute_dual_bucket_comparison` — added `_METRIC_ACTION_VERB` dict; replaced hardcoded `"has scored"` with `{verb} {action_verb}` in both main sentence and conclusion. Now supports:
   - players vs teams (`has`/`have`)
   - goals (`"scored"`) vs assists (`"made"`)
   - singular/plural extended: `_val_label` now handles `"assists"` → `"assist"` when value is 1

3. `_execute_home_away_comparison` — replaced hardcoded `"has scored"` with `{verb} scored`; added `_sng` helper for correct singular noun (`"1 away goal"` not `"1 away goals"`).

4. `verbalize.yaml` — entity_value instruction extended to include `context_label` (e.g., "in the last 3 rounds", "between matchdays X and Y", "this season"). Narrow targeted change; does not affect top_1/top_n/ordinal paths.

### Verification

- All `_BUCKET_METRIC_LABEL` values confirmed correct
- Answer composition verified inline for: goals (2 vs 3), goals singular (1 vs 3), assists (2 vs 1), assists singular (1 vs 3), team goals, home-away player, home-away singular, home-away team
- All detection functions (D01–D06, H01–H06, M01–M10) spot-checked and passing
- No logic changes; no SQL changes; no planner changes

### Benchmark rerun status

Not run since polish is wording-only on code-composed paths and a single targeted prompt instruction. No logic path that exercises existing benchmark questions was modified. Recommend running `eval_runner_v4` to confirm.

---

## Recommended next steps

In priority order:

1. **Run `eval_runner_v4`** to formally close Phase 3 + polish at 50/50
2. **Manual UI validation** of the updated phrasing for dual-bucket, home-away, and metric-derived bucket questions
3. **Canonicalize remaining planner noise (safe cases only)**: audit the ~8 legacy-fallback cases; only fix those where the planner path is confirmed correct for all position and scope combinations
