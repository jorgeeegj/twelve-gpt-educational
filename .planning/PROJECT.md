# Basic Stats Analyst — Brownfield Operating Baseline

## What This Is

An LLM-powered football statistics analyst embedded in the `twelve-gpt-educational` Streamlit app. Users ask natural-language questions about player and team stats; the system plans a structured query, executes it against DuckDB/Parquet data, and verbalizes a grounded answer with supporting rows. The active development focus is `utils/basic_stats/` and its core pipeline.

## Core Value

Every answer must stay grounded in actual data — no invented metrics, entities, values, or support rows.

## Requirements

### Validated

- ✓ QueryPlanner → LLMQueryEngineV2 → DuckDBManager → Verbalization pipeline — existing
- ✓ DuckDB/Parquet data layer with player, team, match, and event scopes — existing
- ✓ Streamlit UI (`pages/basic_stats.py`) with chat-style interaction — existing
- ✓ Benchmark suite (`eval_runner_v4.py`, `questions_benchmark_v4.json`) — existing
- ✓ Focused debug runner (`eval_runner_v5.py`) — existing
- ✓ English and Spanish question support — existing
- ✓ Tool-use pattern via `agent.py` wrapper — existing

### Active

- [ ] Claude Code project baseline: clean GSD structure for ongoing brownfield work
- [ ] Accurate STATE.md and REQUIREMENTS.md that eliminate repeated briefing
- [ ] Verified benchmark baseline — confirm current pass rate before any future change
- [ ] Planner edge case fixes for known failing cases (QV4_37, QV4_38, QV5_41)
- [ ] Verbalization quality: output matches grounded rows and avoids hallucinated phrasing

### Out of Scope

- Broad architectural rewrites — risk of regressions, no justified need
- New product features (Football Scout, WVS Chat, etc.) — not the active focus
- Async embedding paths — broken and out of scope for this work
- Distributed query engines — current scale doesn't require it
- OAuth / auth changes — not relevant to this module
- Mobile or API-first interfaces — web Streamlit is sufficient

## Context

- **Brownfield codebase**: pipeline already works end-to-end; the most valuable work is targeted fixes and validations, not greenfield builds.
- **Benchmark history**: `docs/progress/` contains session-by-session improvement logs; `docs/evals/` holds JSON eval outputs. Do not treat these as the live planning surface — read them for historical context only.
- **QueryPlanner fragility**: ~1405 lines of mixed regex + LLM logic; highly sensitive; modify only with targeted tests and eval validation.
- **Known issues**: Three benchmark cases fail (QV4_37, QV4_38, QV5_41); async embedding functions are broken but unused in the active path.
- **Tech debt to note but not fix urgently**: openai SDK version mismatch, hardcoded Azure endpoint, legacy code in `utils/basic_stats/legacy/`.
- **Sensitivity map**:
  - Very sensitive: `query_planner.py`, `duckdb_manager.py`, `llm_query_engine_v2.py`
  - Sensitive: `models.py`, `resolve_query_intent.yaml`, `verbalize.yaml`
  - Lower: `pages/basic_stats.py`, `docs/`

## Constraints

- **Architecture**: Preserve planner → engine → DuckDB → verbalization unless a change is clearly justified
- **Change size**: Prefer small, local fixes over large refactors — one problem, one fix
- **Validation**: Any change to a very-sensitive file requires eval_runner or targeted test confirmation before merging
- **Groundedness**: Verbalization must never introduce facts not present in the retrieved rows
- **Regression safety**: Run `eval_runner_v4.py` to check for regressions before closing any task that touches core files

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| LLMQueryEngineV2 as main engine | Tool-use pattern + deterministic filters → 20/20 benchmark | ✓ Good |
| DuckDB as query engine | In-process, fast, parquet-native, no infra overhead | ✓ Good |
| YAML-based prompts | Editable without code changes; version-trackable | ✓ Good |
| eval_runner_v4 as official benchmark | Stable 66-question set, reference quality bar | ✓ Good |
| eval_runner_v5 for targeted debug | Focused subset runner, faster iteration loop | ✓ Good |
| Keep legacy/ directory untouched | Reference only; no active imports; safe to ignore | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd:transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-03-26 after brownfield GSD initialization*
