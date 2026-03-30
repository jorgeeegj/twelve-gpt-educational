---
date: 2026-03-30
author: Jorge
scope: Basic Stats Analyst
status: stable — benchmark rerun after wording-only pass recommended but not yet run
---

# Progress Log — 2026-03-30

## Context

Continues directly from:

- `docs/progress/2026-03-29-phase3-dual-bucket_temporal_home-away_metric-derived-bucket.md`

Phase 3 closed with all new routing slices implemented (dual-bucket, home-away, metric-derived bucket, temporal-window). This log covers two subsequent passes that do not change routing or SQL behavior:

1. **Contextual per-90 enrichment** — appends a per-90 rate sentence to answers that already have a correct factual value, across all Phase 3 and some planner-path answers.
2. **Verbalization polish** — wording consistency fixes in code-composed answer paths and one targeted prompt update.

Both passes left the benchmark at 50/50. No planner, DuckDB, or routing changes in either pass.

---

## Scope

All changes in this log are in:

- `utils/basic_stats/core/llm_query_engine_v2.py` — enrichment logic, answer composition wording
- `utils/basic_stats/prompts/verbalize.yaml` — one targeted entity-value instruction

No changes to `query_planner.py`, `duckdb_manager.py`, or `models.py`.

---

## Part 1 — Contextual per-90 enrichment (complete, 50/50 validated)

### Goal

Append a short contextual per-90 sentence to answers that already contain a correct grounded value, giving the user a rate-based frame of reference. Factual answer always comes first; enrichment is always best-effort (wrapped in `try/except`; failure leaves factual answer intact).

### Per-90 conventions

- **Player**: `val / subset_minutes * 90`
- **Team**: `val / subset_match_count` (standard 90-min-per-match)
- Season baseline from `player_full_stats.parquet` / `team_full_stats.parquet` `_p90` fields (already loaded as `self.players_df` / `self.teams_df`)

### Enrichment added per path

#### Metric-derived bucket (`_execute_metric_derived_bucket`)

SQL extended to also fetch `SUM(pms.minutes)` (player) or `COUNT(*)` (team) alongside `metric_value`. Season baseline looked up from `players_df` / `teams_df` by `short_name` / `team_name`.

Example output:
> M. Salah has scored 3 goals against the 3 teams that have conceded the fewest goals: Arsenal, Chelsea, Manchester City. That is 0.90 per 90 in this subset, compared with 0.54 per 90 across the full season.

#### Dual-bucket comparison (`_execute_dual_bucket_comparison`)

New instance method `_fetch_subset_denominator(plan, bucket)` mirrors the filter logic of `_run_bucket_sub_query` (same WHERE conditions, same rank JOIN when needed) without touching `duckdb_manager.py`. Returns `SUM(minutes)` for player scope, `COUNT(*)` for team scope.

New module-level function `_compute_p90(val, denominator, is_player)` shared across paths.

Example output:
> E. Haaland has scored 6 goals against the top 5 teams and 3 goals against the bottom 5 teams, so E. Haaland has scored more goals against the top 5 teams. That is 0.75 per 90 against the top 5 teams and 0.50 per 90 against the bottom 5 teams.

#### Home-away comparison (`_execute_home_away_comparison`)

Reuses `_fetch_subset_denominator` and `_compute_p90`. Shows two subset p90s (one per side). No season comparison (there is no single season baseline for a home-or-away split).

Example output:
> M. Salah has scored 8 away goals and 12 home goals, so M. Salah has scored more goals at home. That is 0.62 per 90 away and 0.80 per 90 at home.

#### Temporal entity-value (planner path, `ask()`)

New instance method `_fetch_temporal_denominator(table, player_name, team_name, matchday_start, matchday_end)` fetches the denominator for temporal subset questions. Player tables always query `player_match_stats` for minutes even when result table is `player_match_event_stats` (which has no `minutes` column).

New instance method `_append_temporal_p90_enrichment(answer, result)` looks up season baseline via `_PLAYER_P90_MAP` / `_TEAM_P90_MAP` module-level dicts.

Guard in `ask()`: fires only when `ranking.mode == "entity_value"` AND (`matchday_start` or `matchday_end` is set). Whole-season entity-value questions have no matchday filter and are intentionally left non-enriched.

Example output:
> Bruno Fernandes has made 2 assists in the last 3 rounds. That is 0.67 per 90 in this subset, compared with 0.27 per 90 across the full season.

### Module-level additions

```
_PLAYER_P90_MAP  — metric → player_full_stats p90 column name
_TEAM_P90_MAP    — metric → team_full_stats p90 column name
_compute_p90(val, denominator, is_player) → float | None
```

### Validation status (Part 1)

| What | Status |
|------|--------|
| `eval_runner_v4` benchmark | **50/50** — no regression |
| Metric-derived enrichment (live) | Verified |
| Dual-bucket enrichment (live) | Verified |
| Home-away enrichment (live) | Verified |
| Temporal enrichment — assists window | Verified inline |
| Temporal enrichment — shot_assists range | Verified inline |
| Whole-season non-enrichment guard | Verified |

---

## Part 2 — Verbalization polish (wording-only, lightly validated)

### Goal

Improve the natural-language quality and consistency of code-composed answer paths without touching logic, routing, SQL, or the planner. No new capabilities added.

### Changes made

#### `_BUCKET_METRIC_LABEL` (`llm_query_engine_v2.py`)

Three entries updated for naturalness and consistency:

| Key | Before | After |
|-----|--------|-------|
| `("total_goals", True)` | `"score the most goals"` | `"have scored the most goals"` |
| `("shots", True)` | `"score the most shots"` | `"take the most shots"` |
| `("shots", False)` | `"score the fewest shots"` | `"take the fewest shots"` |

These labels appear in metric-derived bucket answers: `"against the N teams that {label}: ..."`. The `"take"` form is more natural and matches common question phrasings ("the teams that take the most shots", "the teams that attempt the most shots").

#### `_execute_dual_bucket_comparison`

- Added `_METRIC_ACTION_VERB` dict: `goals`/`team_score` → `"scored"`, `assists` → `"made"`.
- Replaced hardcoded `has scored` with `{verb} {action_verb}` in both the main sentence and the conclusion. `verb` was already correctly `"has"` / `"have"` for player/team.
- Extended `_val_label` to singularize `"assists"` → `"assist"` when value is 1 (previously only `"goals"` was handled).

Before: `"E. Haaland has scored 2 assists against the top 5 teams ..."`
After: `"E. Haaland has made 2 assists against the top 5 teams ..."`

Before: `"E. Haaland has scored 1 assists against the top 5 teams ..."`
After: `"E. Haaland has made 1 assist against the top 5 teams ..."`

#### `_execute_home_away_comparison`

- Replaced hardcoded `has scored` with `{verb} scored` (correct for teams: `"have scored"`).
- Added `_sng(v, noun)` helper to singularize `"goals"` → `"goal"` / `"assists"` → `"assist"` when value is 1. Previously `"1 away goals"` was possible.

Before (team): `"Arsenal has scored 10 away goals ..."`
After (team): `"Arsenal have scored 10 away goals ..."`

Before (singular): `"Salah has scored 1 away goals ..."`
After (singular): `"Salah has scored 1 away goal ..."`

#### `verbalize.yaml`

Existing entity_value instruction:
```
If answer_type is "entity_value", state the exact value for that player or team.
```

Updated to:
```
If answer_type is "entity_value", state the exact value for that player or team,
and include the context_label in your answer (e.g., "in the last 3 rounds",
"between matchdays X and Y", "against Arsenal", "this season").
```

The `context_label` was already being passed to the LLM in the prompt template; this instruction makes its inclusion explicit. Whole-season entity-value answers will include "this season"; temporal subset answers will include the window phrase.

### Validation status (Part 2)

This pass was wording-only. Validation was correspondingly lighter:

| What | Status |
|------|--------|
| `_BUCKET_METRIC_LABEL` values | Asserted via Python |
| Dual-bucket composition (goals, singular, assists, team) | Verified inline — 5 cases |
| Home-away composition (player, singular, team) | Verified inline — 3 cases |
| Detection spot-checks D01–D06, H01–H06, M01–M10 | Passing |
| Planner unit tests | **12/12** (two independent runs) |
| `eval_runner_v4` full benchmark | **Not run** — recommended but not strictly required |

No logic paths that exercise existing benchmark questions were modified.

### Caveat to watch

The `verbalize.yaml` entity-value instruction change is the only change that affects LLM output. The expected effect is that entity-value answers now more consistently include context phrases like `"in the last 3 rounds"` or `"this season"`. This is intended and beneficial. However:

- If any existing benchmark entity-value question currently passes with a bare answer (no context phrase), the new instruction will add context phrasing — which is still factually correct but slightly different in form.
- Watch this in the next benchmark rerun and in UI smoke tests. If any case regresses, the fix is to revert the single instruction line in `verbalize.yaml`.

---

## Current stable capabilities (summary)

### Questions routed by planner path (unchanged)

- Ranked summaries: `"Who has scored the most goals?"`, `"Which team has conceded the fewest?"`
- Filtered summaries: `"Which Liverpool player scored the most between matchdays 25 and 30?"`
- Match-level queries with rank filters, position filters, age filters

### Questions handled by Phase 3 early-return guards

- **Dual-bucket rank comparison** with optional home/away modifier
  - Example: `"Has E. Haaland scored more goals against top 5 teams or bottom 5 teams?"`
- **Temporal-window filtering** ("last N gameweeks/rounds")
- **Home-vs-away comparison**
  - Example: `"Has Mohamed Salah scored more away goals or home goals?"`
- **Metric-derived opponent bucket** (goals, goals-against, shots, shots-against bucket metrics; goals and assists as final player metrics; goals scored/conceded as final team metrics)
  - Example: `"How many goals has Brentford conceded against the 4 teams that take the most shots?"`

### Contextual per-90 enrichment (appended to factual answer, best-effort)

- Metric-derived bucket: subset p90 + season p90 comparison
- Dual-bucket: subset p90 for each bucket (no season comparison)
- Home-away: subset p90 for each side (no season comparison)
- Temporal entity-value (planner path): subset p90 + season p90 comparison
  - Examples: `"How many assists has Bruno Fernandes made in the last 3 rounds?"`, `"How many shot assists has Salah produced between matchdays 25 and 30?"`

### Intentionally non-enriched

- Whole-season entity-value questions (no matchday filter set)
- Top-N and ordinal ranking answers

---

## What not to reopen

- `per_90` aggregation canonicalization — regression risk documented in Phase 2 log
- Legacy path removal — still load-bearing for ~8 question types per run
- Broad `query_planner.py` or `duckdb_manager.py` refactors without a full benchmark gate

---

## Recommended next steps

In priority order:

1. **Run `eval_runner_v4`** to formally close this phase at 50/50 and confirm no edge-case regression from the `verbalize.yaml` entity-value instruction change
2. **Manual UI smoke test** of the updated phrasing for dual-bucket, home-away, and metric-derived bucket questions (verify "take the most shots", "has made 2 assists", etc. display correctly)
3. **Canonicalize remaining planner noise (safe cases only)**: audit the ~8 legacy-fallback cases; only fix those where the planner path is confirmed correct for all position and scope combinations
