# Requirements: Basic Stats Analyst

**Defined:** 2026-03-26
**Core Value:** Every answer must stay grounded in actual data — no invented metrics, entities, values, or support rows.

## v1 Requirements

Requirements for ongoing brownfield work. Each maps to a roadmap phase.

### Project Baseline

- [ ] **BASE-01**: GSD planning structure initialized and committed (PROJECT.md, REQUIREMENTS.md, ROADMAP.md, STATE.md, config.json)
- [ ] **BASE-02**: Benchmark baseline confirmed — current eval_runner_v4 pass rate documented before any new changes

### Query Planner

- [ ] **PLAN-01**: Known failing benchmark cases resolved: QV4_37, QV4_38, QV5_41
- [ ] **PLAN-02**: Any new planner fix is accompanied by a targeted test case in `test_query_planner.py`
- [ ] **PLAN-03**: Planner changes validated with `eval_runner_v4` before merging (no regressions)

### Verbalization

- [ ] **VERB-01**: Verbalized answers match the grounded rows returned (no hallucinated values or phrasing)
- [ ] **VERB-02**: Verbalization handles edge cases: zero results, ties, partial data

### Execution / DuckDB

- [ ] **EXEC-01**: Grounded execution returns correct rows for all supported scopes (players_summary, teams_summary, player_match, player_match_event, team_match)
- [ ] **EXEC-02**: Aggregation logic (sum, avg, count, rank) verified correct for relevant question types

### UI / Demo

- [ ] **UI-01**: `pages/basic_stats.py` displays answers and supporting rows without breaking on edge case responses
- [ ] **UI-02**: Demo behavior matches core pipeline output (no UI-level data transformation)

## v2 Requirements

Deferred. Not in current roadmap.

### Tech Debt

- **DEBT-01**: Align openai SDK to >=1.0.0 and update all import sites
- **DEBT-02**: Move hardcoded Azure endpoint to secrets/env var
- **DEBT-03**: Add `tiktoken` version pin to requirements.txt
- **DEBT-04**: Consolidate redundant NEGATIVE_METRICS / column definitions into `constants.py`
- **DEBT-05**: Archive or remove `utils/basic_stats/legacy/`

### Test Coverage

- **TEST-01**: Add unit tests for `QueryPlanner` core methods (resolve_player_name, resolve_metric, filter building)
- **TEST-02**: Add unit tests for data source transformations (z-score, rank, pct_rank) in `classes/data_source.py`
- **TEST-03**: Fix and test async embedding paths in `utils/embeddings_utils.py`

## Out of Scope

| Feature | Reason |
|---------|--------|
| Broad architectural rewrites | Risk of regressions; no justified need at current scale |
| New product features (Scout, WVS, etc.) | Not the active development focus |
| Distributed query engines | Current dataset fits in-process DuckDB |
| Mobile / API-first interfaces | Streamlit web is sufficient |
| OAuth / auth changes | Not relevant to Basic Stats module |
| Local LLM fallback | Not required for current usage pattern |
| Query result caching layer | Premature; tackle if latency becomes a real problem |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| BASE-01 | Phase 1 | In Progress |
| BASE-02 | Phase 1 | Pending |
| PLAN-01 | Phase 2 | Pending |
| PLAN-02 | Phase 2 | Pending |
| PLAN-03 | Phase 2 | Pending |
| VERB-01 | Phase 3 | Pending |
| VERB-02 | Phase 3 | Pending |
| EXEC-01 | Phase 2 | Pending |
| EXEC-02 | Phase 2 | Pending |
| UI-01 | Phase 3 | Pending |
| UI-02 | Phase 3 | Pending |

**Coverage:**
- v1 requirements: 11 total
- Mapped to phases: 11
- Unmapped: 0 ✓

---
*Requirements defined: 2026-03-26*
*Last updated: 2026-03-26 after brownfield initialization*
