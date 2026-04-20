# Basic Stats Analyst — Brownfield Operating Baseline

## Primary Goal

**Answer any factual question about the Premier League 2024-25 season using available data.**

This is the north star from Agust (course instructor). Every architectural decision, prompt change, and tool improvement should be evaluated against this: does it help the agent answer more questions correctly?

## Current Milestone: v2.0 — Function Calling Architecture + Feature Completeness

**Goal:** Replace regex-based canonicalization with typed function calling tools, add conversation memory for follow-up questions, and polish the analyst to production quality for the course final weeks.

**Target features:**
- Repo reorganization + quality tooling (ruff, pre-commit, pyproject.toml via uv)
- Function calling core (4 typed tools replace ~2,000 lines of planner + detector code)
- Conversation memory via `ConversationState` (Agust's top request: follow-up questions)
- League context injection (dynamic team classification, no hardcoded labels)
- Random question robustness hardening (stress test with diverse unprepared questions)
- Natural language verbalization polish (fix robotic number dumps)

**Branch:** `feature/refactor-v2` from `ricardoherediaj/main`
**Benchmark gate:** 61/61 `evals/eval_runner.py` after every phase

---

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

- [x] Claude Code project baseline: clean GSD structure for ongoing brownfield work
- [x] Accurate STATE.md and REQUIREMENTS.md that eliminate repeated briefing
- [x] Verified benchmark baseline — current validated pass rate documented before future changes
- [ ] Decide the next highest-value task now that the benchmark baseline is fully green
- [ ] Verbalization quality: output matches grounded rows and avoids hallucinated phrasing
- [x] Reduce internal planner fragility/noise where it adds value without risking benchmark regressions

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
- **Known issues**: The current validated benchmark baseline is 50/50 with no failing cases. After Phase 2 noise reduction, ~8 `[PLANNER ERROR]` cases remain per run — these are intentional (legacy fallback gives correct answers for per_90 + position-filter queries). Safe metric aliases have been added for the other noisy cases.
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
| LLMQueryEngineV2 as main engine | Tool-use pattern + deterministic filters provide the current validated end-to-end baseline | ✓ Good |
| DuckDB as query engine | In-process, fast, parquet-native, no infra overhead | ✓ Good |
| YAML-based prompts | Editable without code changes; version-trackable | ✓ Good |
| eval_runner_v4 as official benchmark | Use the latest real benchmark run as source of truth for quality status | ✓ Good |
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
*Last updated: 2026-03-27 after Phase 2 planner noise reduction — 50/50 preserved*
