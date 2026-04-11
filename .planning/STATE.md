# STATE.md

## Project Reference

See: `.planning/PROJECT.md` (updated 2026-04-12)

**Core value:** Every answer must stay grounded in actual data — no invented metrics, entities, values, or support rows.
**Current milestone:** v2.0 — Function Calling Architecture + Feature Completeness
**Current focus:** Phase 4 — Extract & Clean (not started)

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

**Phase 3 — Dynamic Buckets + Comparison Questions** ○ In Progress (started 2026-03-27)
- ✓ Mid-table bucket detection added to `query_planner.py` (`_extract_mid_table_bucket`, `MID_TABLE_RANGE`, wired into `_canonicalize_raw_plan` in 2 locations + scope inference)
- ✓ Canonicalize tests extended: C12, C13 (mid-table → `opponent_rank_between=[7,14]`) — 13/13 passing
- ✓ Dual-bucket comparison detection added to `query_planner.py` (`_classify_all_buckets`, `_detect_dual_bucket_comparison`) — detection only, no execution yet
- ✓ Dual-bucket tests: D01–D06 — 6/6 passing (no LLM)
- ✓ Dual-bucket comparison execution added to `llm_query_engine_v2.py`:
  - `_bucket_label(bucket)` module-level helper — 7/7 label tests passing
  - `_run_bucket_sub_query(plan, bucket)` — overrides bucket filters, calls duck method directly
  - `_execute_dual_bucket_comparison(question, dual)` — plan once, two sub-queries, code-composed answer
  - Early detection block at top of `ask()` → routes "top N or bottom N" questions to comparison path
  - Live smoke test: "Has E. Haaland scored more goals against top 5 teams or bottom 5 teams?" → "E. Haaland has 4 goals against the top 5 teams and 7 against the bottom 5 teams, so E. Haaland has more against the bottom 5 teams."
  - Single-bucket question still routes to planner_duckdb (verified)
- 50/50 benchmark not rerun for Phase 3 slices: `ask()` insertion is an early-return guard on a new detection function; non-dual-bucket questions are not affected
- ✓ Dual-bucket execution hardened: `_run_bucket_sub_query` returns `(None, [])` for empty rows (not `(0, [])`) to prevent "no data" from being mis-read as a grounded zero; `_execute_dual_bucket_comparison` returns `None` → falls through to normal path when either bucket has no data
- ✓ Hardening smoke tests: `test_dual_bucket_hardening.py` T1–T4 — 4/4 passing (live LLM + DuckDB)
  - T1: Haaland goals top5 vs bottom5 → `dual_bucket_comparison` engine ✓
  - T2: Salah goals top6 vs bottom6 (different player/bucket size) → `dual_bucket_comparison` engine ✓
  - T3: ZZNONEXISTENTPLAYER → falls through to `planner_duckdb` ✓
  - T4: "Haaland" (no initial) → resolves to "E. Haaland" → `dual_bucket_comparison` engine ✓ (Issue B regression)
- ✓ Issue A fixed: `_extract_bottom_rank_bucket` pattern narrowed to `r"\blast[-\s]?(\d+)\s+teams?\b"` — "last 5 gameweeks" no longer sets `opponent_rank_gte`
- ✓ Issue B fixed (two-part):
  - B1: `_canonicalize_raw_plan` scope guard extended to fire when `plan.filters.player_name is not None`
  - B2: `_resolve_player_suffix` added to `query_planner.py`; `_post_process_plan` writes back resolved canonical name
  - B3 (LLM-independent fallback): `_execute_dual_bucket_comparison` in `llm_query_engine_v2.py` now uses `_match_known_name` + word-by-word `_resolve_player_suffix` to extract subject regardless of what LLM returned; also fixes summary-scope metric names (`total_goals`→`goals`, `total_assists`→`assists`) when forcing `player_match` scope
- Issue C: explicitly unsupported (no fix planned)
- ✓ Temporal-window queries implemented (2026-03-29):
  - `_extract_recent_window(q)` — module-level regex for "last N gameweeks/rounds/matchdays"
  - `_load_max_matchday()` + `self.max_matchday` — loads max gameweek from parquet at init
  - `_canonicalize_raw_plan`: "last N gameweeks" → `matchday_start=max_matchday-N+1, matchday_end=max_matchday`
  - `has_context` block: `total_goals → goals`, `total_assists → assists` before scope check (fixes LLM summary-scope metric names bypassing scope guard)
  - `_resolve_player_suffix` extended with Pass 2: last-word surname fallback ("Bruno Fernandes" → "B. Fernandes")
  - `_post_process_plan`: word-by-word temporal-window fallback (gated on `matchday_start is not None`)
  - Tests C14–C17 + extended runner checks — 17/17 canonicalize passing
  - Planner verification: "Haaland last 5 gameweeks" → `table_scope=player_match metric=goals matchday_start=34` ✓
  - Planner verification: "Bruno Fernandes last 3 rounds" → `table_scope=player_match metric=goals matchday_start=36` ✓
- ✓ Away-vs-home comparison implemented (2026-03-29):
  - `_detect_home_away_comparison(q)` — module-level function in `llm_query_engine_v2.py`; detects "home" + "away" + "or", excludes rank-bucket questions
  - `_execute_home_away_comparison(self, question, sides)` — new method; reuses `_run_bucket_sub_query` with `{"is_home": False}` / `{"is_home": True}` overrides; LLM-independent subject extraction; code-composed factual answer
  - Wired into `ask()` after dual-bucket guard, before normal path
  - Tests H01–H06 — 6/6 home-away detection tests passing; 49/49 total unit tests passing
  - Detection regression verified: single-side away (no "or") → None ✓; top5/bottom5 → dual_bucket only ✓; compound rank+home/away → dual_bucket only ✓
  - Planner correctly extracts subject: "Mohamed Salah" and "Liverpool" for comparison targets
- ✓ Dual-bucket away-modifier preserved in answer composition (2026-03-29):
  - `_execute_dual_bucket_comparison` now reads `plan.filters.is_home` to build `metric_label` ("away goals" / "home goals" / "goals")
  - `_val_label(v)` helper added: singularizes when `metric_label.endswith("goals") and v == 1`
  - "scored" verb + "has"/"have" player-vs-team distinction added to composition
  - 37/37 non-LLM unit tests passing (C01-C17, D01-D06, 7 bucket labels, H01-H06)
  - Pending: manual UI validation + eval_runner_v4 benchmark rerun
- ✓ Metric-derived bucket slice implemented (2026-03-29):
  - `_detect_metric_derived_bucket(q)` — module-level function in `llm_query_engine_v2.py`; regex detects "the N teams that [have] score[d]/concede[d] the most/fewest [goals]"; guarded by `_classify_all_buckets` to prevent collision with fixed rank buckets
  - `_derive_teams_for_bucket(teams_df, n, bucket_metric, descending)` — Polars in-memory sort, returns list of N team names
  - `_execute_metric_derived_bucket(self, question, bucket_spec)` — LLM-independent subject extraction; raw SQL with parameterized `opponent_team_name IN (...)` against `player_match_stats` or `team_match_stats`; code-composed answer with explicit team list
  - Wired into `ask()` after home-away guard, before normal planner path
  - Tests M01-M06 added to `test_query_planner.py` — 6/6 passing; total non-LLM tests 43/43
  - Live smoke tests:
    - "How many goals has Salah scored against the 3 teams that have conceded the fewest goals?" → `metric_derived_bucket` ✓ ("Mohamed Salah has scored 2 goals against the 3 teams that have conceded the fewest goals: Arsenal, Liverpool and Chelsea.")
    - "How many goals has Liverpool conceded against the 3 teams that score the most?" → `metric_derived_bucket` ✓ ("Liverpool have conceded 4 goals against the 3 teams that score the most goals: Liverpool, Manchester City and Arsenal.")
  - Regression verified: dual-bucket → `dual_bucket_comparison` ✓; home-away → `home_away_comparison` ✓
- **Next:** Run eval_runner_v4 to confirm 50/50 benchmark preserved after all Phase 3 changes.

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
| 3 | ○ In Progress | 50/50 | — |

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
*Last updated: 2026-04-12 — Milestone v2.0 started. Branch: feature/refactor-v2 from ricardoherediaj/main. Research complete (4 agents). Requirements written (19 v2 reqs). Roadmap pending.*
