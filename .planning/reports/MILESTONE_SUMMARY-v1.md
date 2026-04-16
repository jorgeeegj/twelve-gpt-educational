# Milestone Summary — Basic Stats Analyst v1

**Generated:** 2026-04-11
**Milestone:** v1 — Basic Stats Analyst Core Pipeline
**Benchmark:** 61/61 (100%) on eval_runner_v6
**Branch:** feature/basic-stats-analyst
**Authors:** Ricardo Heredia, Jorge (jorgeeegj)

---

## 1. Overview

The Basic Stats Analyst is an LLM-powered football statistics Q&A engine embedded in the `twelve-gpt-educational` Streamlit app. Users ask natural-language questions about Premier League player and team stats; the system plans a structured query, executes it against DuckDB/Parquet data, and verbalizes a grounded answer.

**Core value:** Every answer must stay grounded in actual data — no invented metrics, entities, values, or support rows.

**What makes this hard:** The boundary between what the LLM handles (planning, verbalization) and what code handles (execution, routing) must be carefully managed. The planner (`query_planner.py`, ~1400 lines) is the highest-risk zone — small changes can break multiple question categories simultaneously.

**Current state:** All 61 benchmark questions pass. The pipeline handles 10 distinct question categories across English and Spanish, including advanced routing for bucket comparisons, temporal windows, home/away splits, and metric-derived opponent filtering.

---

## 2. Architecture

### Pipeline (in order)

```
User question
    → BasicStatsAgent.ask()
        → KnowledgeBase (fast exact-match QA lookup)
        → LLMQueryEngineV2.ask()
            → [Early-return guards, checked in order:]
              1. Dual-bucket rank comparison detector
              2. Home-away comparison detector
              3. Metric-derived bucket detector
              → [Falls through to:]
            → QueryPlanner.plan(question) → structured intent dict
            → DuckDBManager.query(plan) → rows + metadata
            → LLM verbalization (verbalize.yaml prompt)
            → [Optional: per-90 enrichment appended]
    → Answer string + supporting rows
```

### Key files

| File | Role | Sensitivity |
|------|------|-------------|
| `utils/basic_stats/core/query_planner.py` | Parses NL question → structured plan; regex + LLM tool-use | **Very high** |
| `utils/basic_stats/core/llm_query_engine_v2.py` | Orchestrates pipeline; contains all early-return guards + enrichment | **Very high** |
| `utils/basic_stats/core/duckdb_manager.py` | Executes SQL against DuckDB/Parquet; manages views | **Very high** |
| `utils/basic_stats/core/models.py` | Pydantic data contracts (QueryPlan, QueryResult) | Sensitive |
| `utils/basic_stats/prompts/resolve_query_intent.yaml` | LLM prompt for planner's metric/entity resolution step | Sensitive |
| `utils/basic_stats/prompts/verbalize.yaml` | LLM prompt for answer verbalization | Sensitive |
| `pages/basic_stats.py` | Streamlit UI — chat interface, debug expander | Lower |
| `eval_runner_v6.py` | Benchmark runner; produces JSON results in `docs/evals/` | Lower |
| `questions_benchmark_v6.json` | 61-question ground truth benchmark | Lower |

### Data scopes

Five DuckDB views are registered at startup:
- `player_summary` — season aggregates per player
- `team_summary` — season aggregates per team
- `player_match` — per-player per-match stats
- `player_match_event` — event-level data (shots, dribbles, carries, etc.)
- `team_match` — per-team per-match stats

The planner sets `table_scope` to one of these. The engine dispatches accordingly.

---

## 3. Phases Completed

### Phase 1 — Project Baseline (2026-03-26)
**Goal:** Establish GSD planning structure and confirm benchmark before any changes.

- Initialized all `.planning/` files (PROJECT.md, REQUIREMENTS.md, ROADMAP.md, STATE.md)
- Ran eval_runner_v4: confirmed **50/50** baseline
- Zero code changes — initialization only

### Phase 2 — Planner Noise Reduction (2026-03-27)
**Goal:** Reduce `[PLANNER ERROR]` noise in `query_planner.py` without regressions.

Changes to `query_planner.py`:
- Extended `METRIC_ALIASES` with 7 scope-aware entries
- Added `mean`/`average` → `avg` aggregation canonicalization
- Added metric key writeback after `_normalize_metric_key`
- Fixed scope guard: `total_goals → team_score` gated to `table_scope == "team_match"` only
- Added 11 unit tests (C01–C11) in `test_query_planner.py`

Result: Benchmark held at **50/50**. ~8 `[PLANNER ERROR]` cases per run remain intentionally (legacy path gives correct results for `per_90` + position-filter queries).

### Phase 3 — Dynamic Buckets + Advanced Routing (2026-03-27 to 2026-04-01)
**Goal:** Handle comparative, temporal, and opponent-context questions deterministically.

This was the largest phase. Implemented in slices:

**3a. Mid-table bucket detection**
- `_extract_mid_table_bucket` in `query_planner.py`
- "mid-table" → `opponent_rank_between=[7,14]`
- Tests C12–C13

**3b. Dual-bucket rank comparison**
- `_classify_all_buckets`, `_detect_dual_bucket_comparison` in `query_planner.py`
- `_execute_dual_bucket_comparison` in `llm_query_engine_v2.py`
- Questions: "Has Haaland scored more goals against top 5 or bottom 5 teams?"
- LLM-independent subject extraction; code-composed factual answer
- Tests D01–D06

**3c. Player name hardening (Issues A + B)**
- Issue A: `_extract_bottom_rank_bucket` narrowed to prevent "last 5 gameweeks" setting rank filters
- Issue B (3 parts): `_resolve_player_suffix` added; scope guard extended; dual-bucket comparison extraction hardened
- Tests: 4/4 live smoke tests in `test_dual_bucket_hardening.py`

**3d. Temporal window queries**
- `_extract_recent_window` detects "last N gameweeks/rounds/matchdays"
- `_load_max_matchday` loads max gameweek from parquet at init
- "last N gameweeks" → `matchday_start=max_matchday-N+1, matchday_end=max_matchday`
- Tests C14–C17

**3e. Home-vs-away comparison**
- `_detect_home_away_comparison` in `llm_query_engine_v2.py`
- `_execute_home_away_comparison` reuses `_run_bucket_sub_query` with `is_home` overrides
- Tests H01–H06

**3f. Metric-derived opponent bucket**
- `_detect_metric_derived_bucket` and `_execute_metric_derived_bucket` in `llm_query_engine_v2.py`
- "scored against the 3 teams that have conceded the fewest goals" → dynamic team list from Polars sort
- Tests M01–M06

**3g. Contextual per-90 enrichment (2026-03-30)**
- Appends per-90 rate sentence to factual answers across all Phase 3 paths + temporal entity-value
- `_fetch_subset_denominator`, `_compute_p90`, `_fetch_temporal_denominator`, `_append_temporal_p90_enrichment`
- Always best-effort (wrapped in try/except); factual answer always comes first
- Benchmark held at **50/50**

**3h. Verbalization polish (2026-03-30)**
- `_BUCKET_METRIC_LABEL` wording fixes ("take the most shots" vs "score the most shots")
- `_METRIC_ACTION_VERB` dict: goals → "scored", assists → "made"
- `_val_label` and `_sng` helpers for grammatical singularization
- `verbalize.yaml` entity_value instruction updated to include `context_label`

**3i. Player alias resolution hardening (2026-04-01, Jorge)**
- `_build_player_alias_map` built at init from `player_full_stats.parquet`
- Three alias types per player: full name, first+last-word, unique surname
- Longest-first deterministic match always overrides LLM-extracted player name
- Smart-quote normalization in `_normalize_text` (U+2019 → U+0027)
- Benchmark upgraded to v6 (61 questions): **61/61** confirmed

---

## 4. Key Decisions

| Decision | Why | Status |
|----------|-----|--------|
| LLM-independent subject extraction in early-return guards | LLM sometimes returns canonical short_name, sometimes full name — deterministic regex is more reliable | ✓ Validated |
| Early-return guards chain before planner | Comparative/temporal questions require different execution paths, not just different plans | ✓ Good |
| `_resolve_player_suffix` always overrides LLM player_name | LLM was sometimes returning non-canonical names; deterministic alias wins | ✓ Validated |
| `per_90` aggregation NOT canonicalized | Planner path gives wrong results for position+per90 queries; legacy path handles correctly | ✓ Intentional |
| Legacy path preserved (~8 question types) | Removing it would break correct-passing cases | ✓ Intentional |
| eval_runner_v6 as official benchmark | v6 adds 11 questions covering Phase 3 capabilities; v4 (50q) used as regression check during dev | ✓ Current |
| Best-effort per-90 enrichment | Enrichment should never break a correct factual answer | ✓ Good |
| Deterministic alias map overrides LLM | "Erling Haaland", "Erling Braut Haaland", "Haaland" all resolve to "E. Haaland" deterministically | ✓ Validated (Jorge) |

---

## 5. Requirements Status

### Completed (v1)
- **BASE-01** ✓ GSD planning structure initialized
- **BASE-02** ✓ Benchmark baseline confirmed and documented
- **PLAN-01** ✓ All planner work starts from 50/50 baseline
- **PLAN-02** ✓ Every planner fix has a corresponding test
- **PLAN-03** ✓ All changes validated with eval_runner before merge

### Still Open
- **EXEC-01** — Grounded execution verified across all scopes (partial — covered by benchmark, not explicit unit tests)
- **EXEC-02** — Aggregation logic (sum, avg, count, rank) unit tested
- **VERB-01** — Verbalized answers never hallucinate values (addressed by prompt; no systematic audit done)
- **VERB-02** — Verbalization handles zero results, ties, partial data
- **UI-01/02** — UI edge case testing

### Deferred to v2 (Tech Debt)
- **DEBT-01** `openai` SDK upgrade to >=1.0.0 (currently locked to legacy 0.28.1)
- **DEBT-02** Move hardcoded Azure endpoint to secrets/env var
- **DEBT-03** Pin `tiktoken` version
- **DEBT-04** Consolidate `NEGATIVE_METRICS`/column definitions into `constants.py`
- **DEBT-05** Archive `utils/basic_stats/legacy/`
- **TEST-01/02/03** Unit test coverage for planner core methods, data transformations, async embeddings

---

## 6. Known Tech Debt & Fragile Areas

**Do not touch without full benchmark validation:**
- `query_planner.py` — ~1400 lines, regex + LLM mixed; brittle to small changes
- `llm_query_engine_v2.py` — early-return guard order matters; each guard must not collide with others
- `duckdb_manager.py` — SQL generation; changes break silently (no schema errors, wrong rows)

**Known broken (out of scope):**
- `utils/embeddings_utils.py` async paths (`aget_embedding`, `aget_embeddings`) — call undefined function; only sync paths are used
- Gemini embedding path — FIXME comments; untested

**Dependency risk:**
- `openai==0.28.1` — legacy 2021 SDK, security/API drift risk
- `google-generativeai==0.7.2` — rapidly evolving API, may break on upgrade

**Intentional non-issues:**
- ~8 `[PLANNER ERROR]` log lines per benchmark run — these are expected legacy fallbacks, not bugs

---

## 7. Getting Started

### Run the app
```bash
streamlit run app.py
```
Navigate to the Basic Stats page in the sidebar.

### Run the benchmark
```bash
python eval_runner_v6.py
# Results written to docs/evals/
```

### Run focused debug on specific questions
```bash
python eval_runner_v5.py --ids QV4_37,QV4_38
```

### Run unit tests (no LLM required)
```bash
python -m pytest test_query_planner.py -v
# 43+ unit tests, all LLM-free
```

### Understand a failing benchmark case
1. Check `docs/evals/latest_eval_results_v6.json` for the failed question
2. Check `STATE.md` for the relevant operating rule
3. Run `eval_runner_v5.py` with the specific ID to isolate
4. Add a failing test case to `test_query_planner.py` before fixing

### Critical invariant
**Any change to a very-sensitive file (`query_planner.py`, `llm_query_engine_v2.py`, `duckdb_manager.py`) must be validated with `eval_runner_v6.py` before closing the task.** Benchmark pass rate must not regress.

---

*Summary generated: 2026-04-11*
*Based on: .planning/PROJECT.md, REQUIREMENTS.md, ROADMAP.md, STATE.md, CONTEXT.md, codebase/*, docs/progress/*, docs/evals/latest_eval_results_v6.json*
