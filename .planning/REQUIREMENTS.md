# Requirements: Basic Stats Analyst

**Defined:** 2026-03-26
**Core Value:** Every answer must stay grounded in actual data — no invented metrics, entities, values, or support rows.

## v1 Requirements

Requirements for ongoing brownfield work. Each maps to a roadmap phase.

### Project Baseline

- [x] **BASE-01**: GSD planning structure initialized and committed (PROJECT.md, REQUIREMENTS.md, ROADMAP.md, STATE.md, config.json)
- [x] **BASE-02**: Benchmark baseline confirmed — current eval_runner_v4 pass rate documented before any new changes

### Query Planner

- [x] **PLAN-01**: Any planner improvement work must start from the validated 50/50 baseline and preserve it
- [x] **PLAN-02**: Any new planner fix is accompanied by a targeted test case in `test_query_planner.py`
- [x] **PLAN-03**: Planner changes validated with `eval_runner_v4` before merging (no regressions)

### Verbalization

- [x] **VERB-01**: Verbalized answers match the grounded rows returned (no hallucinated values or phrasing)
- [x] **VERB-02**: Verbalization handles edge cases: zero results, ties, partial data

### Execution / DuckDB

- [x] **EXEC-01**: Grounded execution returns correct rows for all supported scopes (players_summary, teams_summary, player_match, player_match_event, team_match)
- [x] **EXEC-02**: Aggregation logic (sum, avg, count, rank) verified correct for relevant question types

### UI / Demo

- [x] **UI-01**: `pages/basic_stats.py` displays answers and supporting rows without breaking on edge case responses
- [x] **UI-02**: Demo behavior matches core pipeline output (no UI-level data transformation)

---

## v2 Requirements

Milestone v2.0: Function Calling Architecture + Feature Completeness

### INFRA — Codebase Foundations

- [x] **INFRA-01**: Repo reorganized to `src/basic_stats/`, `src/shared/`, `tests/`, `evals/` — all imports verified working, 61/61 benchmark passing after restructure ✓ (2026-04-12)
- [x] **INFRA-02**: Dead code deleted: `utils/basic_stats/legacy/`, 5 old eval runners (v0–v5), old benchmark JSONs, `test_embeddings.py`, `.lnk` file, `miniprueba.py`, `setup.py`, `twelve_gpt_educational.egg-info/` ✓ (2026-04-12)
- [x] **INFRA-03**: `pyproject.toml` created with ruff config, pinned deps (`openai==2.15.0` fix included), uv as package manager ✓ (2026-04-12)
- [x] **INFRA-04**: `.pre-commit-config.yaml` configured with ruff + basic hooks; passes on first commit in `feature/refactor-v2` ✓ (2026-04-12)
- [x] **INFRA-05**: `evals/eval_runner.py` (renamed from v6) + `evals/questions_benchmark.json` (renamed from v6) — single source of truth, 61/61 confirmed after rename ✓ (2026-04-12)

### FUNC — Function Calling Core

- [x] **FUNC-01**: `BasicStatsAgent` implemented with 9 typed tools and OpenAI strict-mode schemas replacing the v1 planner heuristics (`src/basic_stats/agent.py`, `agent_tools.py`, `agent_tool_schemas.py`) ✓ (2026-04-13)
- [ ] **FUNC-02**: All 61 benchmark questions pass faithfulness gate ≥95% (51/61 = 83.6% as of 2026-04-13 — 9 failures remaining)
- [x] **FUNC-03**: Legacy planner (`llm_query_engine_v2.py`, `query_planner.py`) kept as reference; new agent is the active path ✓ (2026-04-13)
- [x] **FUNC-04**: Canonicalization rules documented in `docs/canonicalization_rules.md` ✓ (2026-04-12)

### MEM — Conversation Memory

- [ ] **MEM-01**: `ConversationState` dataclass in Streamlit `session_state` tracks entity, metric, active filters, and last result across turns
- [ ] **MEM-02**: Follow-up question chain works end-to-end: "How many goals has Haaland scored?" → "But against top 6?" → "Is that more than the rest?" → "What about per 90?"
- [ ] **MEM-03**: Multi-turn test suite (10+ conversation flows) passes before Phase 6 ships

### CTX — League Context

- [ ] **CTX-01**: League description paragraph injected into LLM system prompt so "top 6", "big 6", "relegation zone" are classified dynamically without hardcoded labels
- [ ] **CTX-02**: `league_standings` DuckDB view created from existing `team_match` data (standings derivable from match results)
- [ ] **CTX-03**: At least 5 league-context questions answered correctly that previously failed or required hardcoded lookup

### ROB — Random Question Robustness

- [ ] **ROB-01**: 20+ diverse unprepared questions tested beyond the 61-question benchmark; pass rate documented
- [ ] **ROB-02**: Alias gaps identified and resolved for common player/team name variants (accents, abbreviations, nicknames)

### NLP — Natural Language Polish

- [ ] **NLP-01**: Verbalized answers use natural language — no raw metric keys, no robotic number dumps (e.g. "Haaland has scored 6 goals with an xG of 3.44" not "Haaland 6 goals 3.44 xG")
- [ ] **NLP-02**: Contextual framing for comparison answers (home/away, bucket, temporal) using updated `verbalize.yaml` templates
- [ ] **NLP-03**: At least one deterministic insight rule implemented (e.g., goals vs xG relationship expressed as natural language interpretation)

---

## Out of Scope

| Feature | Reason |
|---------|--------|
| Broad architectural rewrites beyond v2 plan | Risk of regressions; no justified need at current scale |
| New product features (Scout, WVS, etc.) | Not the active development focus |
| Distributed query engines | Current dataset fits in-process DuckDB |
| Mobile / API-first interfaces | Streamlit web is sufficient |
| OAuth / auth changes | Not relevant to Basic Stats module |
| Local LLM fallback | Not required for current usage pattern |
| Vector DB / long-term memory (mem0) | Short-term session memory is sufficient for follow-ups |
| Qualities integration | Out of scope per Agust (course constraint) |
| Visualization (shot maps, heatmaps) | Backlog — interesting but not next step |
| PR to upstream Twelve-Educational/main | Not planned for v2; fork is source of truth |

---

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| BASE-01 | Phase 1 | Complete |
| BASE-02 | Phase 1 | Complete |
| PLAN-01 | Phase 2 | Complete |
| PLAN-02 | Phase 2 | Complete |
| PLAN-03 | Phase 2 | Complete |
| VERB-01 | Phase 3 | Complete |
| VERB-02 | Phase 3 | Complete |
| EXEC-01 | Phase 3 | Complete |
| EXEC-02 | Phase 3 | Complete |
| UI-01 | Phase 3 | Complete |
| UI-02 | Phase 3 | Complete |
| INFRA-01 | Phase 4 | Complete ✓ (2026-04-12) |
| INFRA-02 | Phase 4 | Complete ✓ (2026-04-12) |
| INFRA-03 | Phase 4 | Complete ✓ (2026-04-12) |
| INFRA-04 | Phase 4 | Complete ✓ (2026-04-12) |
| INFRA-05 | Phase 4 | Complete ✓ (2026-04-12) |
| FUNC-01 | Phase 5 | Complete ✓ (2026-04-13) |
| FUNC-02 | Phase 5 | In Progress — 51/61 = 83.6% (2026-04-13) |
| FUNC-03 | Phase 5 | Complete ✓ (2026-04-13) |
| FUNC-04 | Phase 5 | Complete ✓ (2026-04-12) |
| MEM-01 | Phase 6 | Pending |
| MEM-02 | Phase 6 | Pending |
| MEM-03 | Phase 6 | Pending |
| CTX-01 | Phase 7 | Pending |
| CTX-02 | Phase 7 | Pending |
| CTX-03 | Phase 7 | Pending |
| ROB-01 | Phase 8 | Pending |
| ROB-02 | Phase 8 | Pending |
| NLP-01 | Phase 9 | Pending |
| NLP-02 | Phase 9 | Pending |
| NLP-03 | Phase 9 | Pending |

**Coverage:**
- v1 requirements: 11 total — all complete ✓
- v2 requirements: 19 total — 8 complete, 1 in progress (FUNC-02), 10 pending
- Mapped to phases: 30/30 ✓

---

*Requirements defined: 2026-03-26*
*v2 requirements added: 2026-04-12 — function calling, conversation memory, league context, robustness, NLP polish*
*Phase 4 (INFRA) marked complete: 2026-04-12*
*FUNC-01/03/04 marked complete: 2026-04-13 — FUNC-02 in progress at 51/61*
