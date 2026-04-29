---
gsd_state_version: 1.0
milestone: v2.0
milestone_name: Milestones
status: unknown
last_updated: "2026-04-29T07:30:52.319Z"
progress:
  total_phases: 2
  completed_phases: 0
  total_plans: 7
  completed_plans: 5
---

# STATE.md

## Project Reference

See: `.planning/PROJECT.md` (updated 2026-04-12)

**Core value:** Every answer must stay grounded in actual data — no invented metrics, entities, values, or support rows.
**Current milestone:** v2.0 — Function Calling Architecture + Feature Completeness
**Current focus:** Phase 10 — Self-Generated Robustness / Synthetic UAT

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

**Phase 3 — Dynamic Buckets + Comparison Questions** ✓ Complete (2026-03-29)

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
- ✓ eval_runner_v4 rerun confirmed 50/50 benchmark preserved after all Phase 3 changes (2026-04-12)

**Phase 4 — Extract & Clean** ✓ Complete (2026-04-12)

- ✓ Repo reorganized: `utils/basic_stats/core/` → `src/basic_stats/`
- ✓ `pyproject.toml` + uv + ruff + pre-commit configured
- ✓ Dead code removed (legacy eval runners, setup.py, requirements.txt)
- ✓ `league_standings` DuckDB view added to `duckdb_manager.py`
- ✓ `docs/canonicalization_rules.md` written (17 rule categories, prereq for Phase 5)
- ✓ `evals/benchmark_runner.py` — parallel runner (ThreadPoolExecutor, ~5x faster)
- ✓ `evals/smoke_test.py` — 10-question sanity check, exit 0/1
- ✓ Benchmark: 61/61 verified (2026-04-12)

**Phase 5 — Function Calling Core** ✓ Complete (2026-04-17)

**Scope revision (2026-04-16):**

- 61/61 benchmark gate DROPPED — tests known questions, not robustness signal
- New exit gate: Responses API working + 3 mother tools + follow-up history wired
- Legacy code deleted (2026-04-16): `query_planner.py`, `llm_query_engine_v2.py`, `knowledge_base.py`, `function_tools.py`, `models.py`, 3 legacy YAML prompts, legacy test + eval files (3,975 LOC removed, commit `92689d9d`)

**Work completed (session 2026-04-16):**

- ✓ `BasicStatsAgent` implemented (`src/basic_stats/agent.py`) — tool-calling loop, 9 tools
- ✓ `evals/agent_benchmark.py` + `faithfulness_judge.py` — eval harness
- ✓ Responses API confirmed working on Azure endpoint (`client.responses.create` → OK)
- ✓ Legacy architecture deleted (2026-04-16)

**Work completed (session 2026-04-17 — checkpoint):**

- ✓ Step 1: `config.py` — `get_embeddings_model()` added (commit `6ab846fe`)
- ✓ Step 2: `duckdb_manager.py` — VSS stubs added: `store_entity_embeddings()`, `fuzzy_resolve_entity()` (commit `6ab846fe`)
- ✓ Step 3: `agent_tool_schemas.py` — 9 schemas → 4, flat Responses API format, no `"function":{}` wrapper, no `"strict":True` (commit `6ab846fe`)
- ✓ Step 4: `agent_tools.py` — 3 mother tool dispatchers added; `Filters` dataclass + `ToolResult` dataclass eliminated — functions now read plain dicts via `_f()` helper, matching OpenAI function calling convention (commit `f7c8639b`)
- ✓ 44 unit tests passing across 4 test files (no LLM calls)

**Work completed (session 2026-04-17 — Phase 5 finish):**

- ✓ Step 5: `agent.py` migrated to `client.responses.create`; `_last_response_id` / `reset()` added; `_build_tool_map` reduced to 4 mother tool entries; loop reads `response.output` items, appends `function_call_output` dicts (commit `492073d7`)
- ✓ Step 6: `prompts/agent_system.yaml` HOW TO USE TOOLS rewritten for 4 mother tool names (commit `492073d7`)
- ✓ Step 7: `pages/basic_stats.py` wraps `BasicStatsAgent` in `@st.cache_resource`; calls `agent.reset()` on clear-chat; drops `history=` kwarg — state carried server-side (commit `492073d7`)
- ✓ `TestFilters` removed from test suite (Filters dataclass eliminated in Step 4); 31 tests passing

**Phase 6 — Random Question Robustness** ✓ Complete (2026-04-20)

- ✓ Embeddings (text-embedding-3-large) for all players + teams stored in DuckDB VSS table
- ✓ `fuzzy_resolve_entity()` resolves "Salah" → "M. Salah", "Man City" → "Manchester City"
- ✓ Fuzzy resolution wired symmetrically into team filters (RQ_09 fix: Nottingham Forest)
- ✓ `resolved_entities` attached to every tool response for transparency
- ✓ Per-turn telemetry: iterations_used, tool_calls, hit_max_iterations
- ✓ System prompt trimmed: 442-player list removed, fuzzy resolve handles raw names
- ✓ `min_minutes=600` default for p90 rankings to avoid small-sample noise
- ✓ Benchmark (random_questions.json): 19/21 faithfulness (phase6_postfix run)
- Known gap: RQ_12 (yellow cards → fouls routing) fixed in postfix; RQ_17 (London clubs) deferred to Phase 8

**Phase 7 — Conversation Memory** ✓ Complete (2026-04-21)

- ✓ Replaced `previous_response_id` with explicit client-side `_history` list
- ✓ Full turn history (including tool call/output pairs) persisted so Responses API never sees unresolved function_calls between turns
- ✓ Agust's 4-turn chain validated: Haaland goals → vs Big Six → comparison → per 90 all pass
- ✓ `scripts/verify_multiturn.py` added for manual re-validation
- ✓ `reset()` clears `_history` correctly

**Phase 8 — League Context** ✓ Complete (2026-04-21)

- ✓ `docs/premier_league_2024_25_context.md` added — static standings, categories, narrative, LLM notes
- ✓ `{league_context}` placeholder injected into system prompt via `agent_prompt.py`
- ✓ Hardcoded intro paragraph + LEAGUE TIER CONVENTIONS block removed from `agent_system.yaml`
- ✓ `opponent_is_big6=true` routing rule preserved in HOW TO USE TOOLS
- ✓ 6/6 league-context questions passed (verify_league_context.py)
- ✓ Multilingüe validado manualmente: responde en español correctamente
- ✓ 95 unit tests passing (test_agent_prompt.py added to permanent suite)

**Hotfix BUG-P90-CONTEXT** ✓ Complete (2026-04-22)

- ✓ `_PLAYER_MATCH_P90_MAP` added to `agent_tools.py` (`total_goals_p90 → goals`, `assists_p90 → assists`)
- ✓ `agg="p90"` case added to `duckdb_manager._match_value_expr` → `SUM(metric)/NULLIF(SUM(minutes_played),0)*90`
- ✓ p90-contextual branch added in `get_player_stat` and `rank_players` (before existing match-context branch)
- ✓ 5 new tests added (4 in `test_agent_tools.py`, 1 in `test_duckdb_vss_stubs.py`)
- ✓ 79/79 tests passing (`uv run pytest tests/ -q -k "not fuzzy_resolve"`)
- ✓ Bug case verified: `total_goals_p90 + opponent_is_big6` → was `5.0` (raw sum), now `0.625` (correct ratio)
- Residual risk (closed by WI-2, 2026-04-23): `xg_p90`, `shots_p90` and other event-stat `*_p90` now correctly return ratios via `_PLAYER_MATCH_EVENT_P90_MAP`

**Hotfix BUG-PARALLEL-TOOLS** ✓ Complete (2026-04-22)

- ✓ `ask()` loop in `agent.py` now collects all `function_call` items per iteration (was: only the first)
- ✓ One `function_call_output` generated per `call_id` → API never sees unmatched function calls
- ✓ `tests/test_agent_parallel_tools.py` added: 2 tests (parallel 2-tool case + single-tool regression)
- ✓ 81/81 tests passing (`uv run pytest tests/ -q -k "not fuzzy_resolve"`)
- ✓ `verify_multiturn.py` all 4 turns pass: Haaland goals → vs Big Six → comparison → per 90

**Hotfix BUG-TRUTHFULNESS-APPEARANCES** ✓ Complete (2026-04-22)

- ✓ `query_player_match_context()` enriched: added `COUNT(*) AS appearances` and `SUM(pms.minutes_played) AS total_minutes` to SELECT
- ✓ LLM now receives grounded data instead of inventing appearances/minutes from training priors
- ✓ Ground-truth case verified: Haaland vs Big Six → "5 goals in 8 appearances" (was "5 goals in 5 appearances")
- ✓ 1 new test in `test_agent_tools.py` (`TestMatchContextGrounding.test_haaland_vs_big6_appearances_and_minutes`)
- ✓ 82/82 tests passing

**Phase 9 — Natural Language Polish** ✓ Complete (2026-04-27)

- ✓ NLP-01: `find_violations()` guard added to benchmark; 61/61 answers raw-key clean (v4 run)
- ✓ NLP-02: Contextual framing rules added to `agent_system.yaml` HOW TO WRITE YOUR ANSWER — HOME/AWAY, BUCKET (canonical labels), TEMPORAL (matchday prose), no raw filter keys in clarification offers
- ✓ NLP-03: Goals vs xG insight rule implemented — delta ≥+1.0 → "finishing above expectation", ≤−1.0 → "underperforming xG"; deterministic, no probabilistic language
- ✓ Team per-90 `_p90` suffix rule added to AVAILABLE STATS; Spanish away-wins mapping added; team-vs-dynamic-bucket N-separate-calls pattern documented; player-vs-dynamic-bucket concrete example (Salah/Liverpool) added
- ✓ `evals/raw_key_guard.py` + `tests/test_raw_key_guard.py` written — parse-from-prompt design, word-boundary regex, prose allowlist
- ✓ Benchmark (phase9_post_fix_v4): faithfulness **0.967** (59/61, gate 0.95 PASS) | raw_keys **0** violations (gate 0 PASS)
- ✓ 98/98 unit tests passing (pre-Phase-9 baseline)

**Phase 10 — Self-Generated Robustness / Synthetic UAT** ✓ Complete (2026-04-29)

- ✓ Gate 1 (SPEC): `.planning/phases/10-self-generated-robustness-synthetic-uat/10-SPEC.md` authored — 12-category failure taxonomy, runner contract, cluster schema, regression workflow.
- ✓ Gate 2 (Fixture): `evals/synthetic/seed_questions.json` — 24 entries spanning all 12 categories; Tottenham CL edge case + Top6/Big6 distinction + contextual p90 + Spanish phrasing included.
- ✓ Gate 3 (Runner): `evals/synthetic_runner.py` reuses BasicStatsAgent, find_violations, judge_faithfulness, _ask_with_retry pattern. CLI exposes `--dry-run`, `--skip-judges`, `--workers`, `--label`.
- ✓ Gate 4 (Clustering): `evals/synthetic_clusterer.py` — heuristic (category, guard_evidence) clustering; `failure_clusters.json` + `REPORT.md` produced on every live run.
- ✓ Gate 5 (Regression scaffold): `tests/test_synthetic_regressions.py` ships with workflow doc-block + xfail example; no real regressions added pre-emptively.
- ✓ Gate 6 (Baseline preserved): `uv run pytest tests/ -q --ignore=tests/test_fuzzy_resolve.py` exits 0 with 173 tests passing (160 baseline + 13 Phase 10 tests).
- ✓ Gate 7 (Evidence): live run `2026-04-29_09-51-54__synthetic_phase10_first` — total_questions=24, total_failures=2, cluster_count=1. Run output gitignored under `evals/runs/`; not staged.
- Read-only constraint honoured: `git diff --name-only src/basic_stats/` reports zero files.
- Next steps (out of Phase 10 scope): triage the surfaced cluster (`unsupported_future__refuse_expected_but_answered`, SYN_019/020), decide whether to add regression test in `tests/test_synthetic_regressions.py`, and whether fix opens as a hotfix or follow-on phase.

*Last updated: 2026-04-29 — Phase 10 Plan 05 complete: regression scaffold committed; 173/173 tests green; SYNTH-05 satisfied. Plan 06 (full run) is next.*

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

## v2.0 Roadmap Summary (revised 2026-04-16)

**6 phases, 19 requirements — exit gate is robustness, not 61/61 benchmark**

| Phase | Name | Key Deliverables | Status |
|-------|------|------------------|--------|
| 4 | Extract & Clean | Repo reorg + pyproject.toml + pre-commit + dead code removal + `league_standings` view | ✓ Complete |
| 5 | Function Calling Core | Responses API + 4 mother tools + follow-up history via `previous_response_id` | ✓ Complete |
| 6 | Random Question Robustness ⬆️ | Embeddings (VSS) + entity resolution + 20+ unprepared questions ≥80% pass | ✓ Complete |
| 7 | Conversation Memory ⬆️ | Client-side history + Agust's 4-turn chain passes end-to-end | ✓ Complete |
| 8 | League Context ⬆️ | Dynamic league paragraph in system prompt + no hardcoded labels | ✓ Complete |
| 9 | Natural Language Polish | Natural answers + no raw metric keys + insight rules | ✓ Complete |

---

## Operating Rules

- `duckdb_manager.py` is the highest-risk file — no change without smoke test validation
- `agent.py`, `agent_tools.py`, `agent_tool_schemas.py` are sensitive — run `evals/agent_benchmark.py` after changes
- `pages/basic_stats.py`, `docs/` are lower sensitivity — can change more freely
- A task is done only when: implemented + relevant verification run + results checked + STATE.md updated

## Phase Progression

| Phase | Name | Status | Exit Gate |
|-------|------|--------|-----------|
| 1 | Project Baseline | ✓ Complete | — |
| 2 | Planner Fixes | ✓ Complete | 50/50 benchmark |
| 3 | Verbalization | ✓ Complete | 50/50 benchmark |
| 4 | Extract & Clean | ✓ Complete | 61/61 benchmark |
| 5 | Function Calling Core | ✓ Complete | Responses API + 4 mother tools + follow-up history wired |
| 6 | Robustness ⬆️ | ✓ Complete | 19/21 faithfulness on random questions |
| 7 | Memory ⬆️ | ✓ Complete | Agust's 4-turn chain passes end-to-end |
| 8 | League Context ⬆️ | ✓ Complete | 6/6 context questions + no hardcoded labels |
| 9 | NLP Polish | ✓ Complete | 61/61 raw-key clean; faithfulness 0.967 (59/61) |
| 10 | Self-Generated Robustness / Synthetic UAT | ✓ Complete | All 7 SPEC exit gates met; live run `2026-04-29_09-51-54__synthetic_phase10_first` produced 4 output files |

---

## Context Files

| File | Purpose |
|------|---------|
| `.planning/PROJECT.md` | Stable project description, validated requirements, key decisions |
| `.planning/REQUIREMENTS.md` | Scoped v1 + v2 requirements with traceability (Phases 1–9) |
| `.planning/ROADMAP.md` | Full phase structure and success criteria (v1 + v2.0) |
| `.planning/STATE.md` | Live status, benchmark baseline, next step (this file) |
| `.planning/config.json` | GSD workflow settings |
| `docs/progress/` | Historical session logs — read for context, not as live planning surface |
| `docs/evals/` | Eval run outputs — read for historical data |

---

**Pre-Phase-9 Robustness Closeout** (minifase, branch `feature/refactor-v2`)

- ✓ WI-1 Subject Exclusion + Postfix — 2026-04-23
  - `get_stat_vs_opponent_group`: filtra el equipo propio del jugador/equipo antes de SQL; añade `excluded_note`; extiende a entity_type="team"; auto-backfill via `fill_stat`/`fill_descending` (reemplaza los N equipos excluidos con los siguientes válidos del ranking)
  - `get_player_stat`: early return semántico si `opponent_team == equipo propio` (player)
  - `get_team_stat`: early return semántico si `opponent_team == team_name` (Fix B para teams); alias routing `total_goals_against` → `opponent_score` en match context (fix QV6_57)
  - `rank_teams` + `query_summary_context`: parámetro `exclude_teams` para excluir proactivamente el equipo del sujeto del pool de candidatos
  - `query_player_stats`: parámetros `opponent_teams_fill_stat` / `opponent_teams_fill_descending` expuestos al LLM vía schema
  - `query_team_stats`: parámetro `exclude_teams` expuesto al LLM vía schema
  - Helpers: `_lookup_player_teams` (sin cambio); `_TEAM_CONCEDED_ALIASES` frozenset nuevo
  - 5 tests nuevos adicionales en `TestSubjectExclusion` — 89/89 ✓ (84 baseline + 5 nuevos)
  - QV6_56 validado: Salah 3 goles (Arsenal+Chelsea+Everton, Liverpool excluido + backfill Everton)
  - QV6_57 validado: Brentford 13 goles concedidos (alias total_goals_against → opponent_score)
  - Multi-turn chain 4/4 ✓
- ✓ WI-2 p90 Event Stats Coverage — 2026-04-23
  - `_PLAYER_MATCH_EVENT_P90_MAP` added to `agent_tools.py`: 12 entries mapping event-stat `*_p90` names → base event-stat columns (shots, xg_total, key_passes, progressive_passes, touches_in_box, shot_assists, recoveries, interceptions, dribbles_won, aerial_duels_won; plus xg_p90/shots_on_target_p90 aliases)
  - `total_assists_p90` alias added to `_PLAYER_MATCH_P90_MAP`
  - `get_player_stat`: new branch — if stat in `_PLAYER_MATCH_EVENT_P90_MAP` and match context present → routes to `query_player_match_event_context(agg="p90")` instead of falling to raw-sum match branch
  - `rank_players`: same branch with `min_minutes=600` default to avoid small-sample artefacts
  - `query_player_match_event_context` in `duckdb_manager.py`: added `min_minutes` param (filters via `ps.total_minutes`); added `agg="p90"` support via `LEFT JOIN player_match_stats pms_mins ON player_id + gameweek` → `SUM(event_metric)/NULLIF(SUM(pms_mins.minutes_played),0)*90`
  - 4 new tests in `TestEventStatP90`: parametrized shots/xg/key_passes × Big6 context → ratio (not raw sum); ranking test — 93/93 ✓
  - Verified: shots_p90=2.875 (23 shots / 720min * 90), xg_total_p90=0.473 (3.78 / 8 games); raw would have been 23 and 3.78
  - Multi-turn chain 4/4 ✓
  - Resolved residual risk from BUG-P90-CONTEXT: "xg_p90, shots_p90 and other event-stat *_p90 silently degrade" — **closed**
- ✓ Post-WI2 Residuals Closeout — 2026-04-23
  - **Fix A (QV4_13 schema)**: `agent_tool_schemas.py` position description — `'CF'/'forward' → 'Striker'` replaced with `'CF' → 'Striker'; 'forward'/'attacker' → null` (Wingers now included in forward queries)
  - **Fix B (QV4_13 code)**: `agent_tools.py` rank_players summary fallback — `min_minutes=600` default replaced with `min_matches=5` when neither filter is set; `_P90_MIN_MATCHES_DEFAULT = 5` constant added; D. Malen (381 min, 14 matches, 1.89 shots_on_target_p90) now appears at top
  - **Fix C (QV6_56/61 system prompt)**: `agent_system.yaml` HOW TO USE TOOLS — derived-bucket two-step rule made imperative with explicit NEVER clause forbidding N individual `query_player_stats` calls
  - **Fix D (QV6_61 alias)**: `agent_tools.py` `get_stat_vs_opponent_group` — `_MATCH_STAT_ALIASES = {"total_goals": "goals", "total_assists": "assists"}` applied before routing so LLM's `total_assists` no longer silently falls to `goals` fallback
  - `agent_system.yaml` PLAYER POSITIONS mapping updated: `"forward" or "attacker" → position=null (covers Striker + Winger; do not filter)`
  - 5 new tests: `TestQV4_13Residual` (3) + `TestQV6_61Residual` (2) — 98/98 ✓
  - Benchmark `post_residual_closeout_final`: **59/61 faithfulness (0.967) — ALL GATES PASS** (threshold 0.95)
  - QV4_13 ✓ (D. Malen 1.89 shots_on_target_p90), QV6_56 ✓ (Salah 3 goals), QV6_61 ✓ (Salah 2 assists)
  - Remaining 2 failures: QV4_31 (ordinal ranking non-determinism), QV5_49 (hallucinated total, pre-existing) — both out of scope
- WI-3, WI-4, WI-5 — pendientes

*Last updated: 2026-04-29 — Phase 10 (Self-Generated Robustness / Synthetic UAT) complete. Synthetic UAT runner + clusterer + regression scaffold shipped; live run `2026-04-29_09-51-54__synthetic_phase10_first` produced summary.json + results.json + failure_clusters.json + REPORT.md (24 questions, 2 failures, 1 cluster: unsupported_future__refuse_expected_but_answered).*
