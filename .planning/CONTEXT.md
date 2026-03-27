# CONTEXT.md

## Current phase
Phase 0: Claude Code integration and project operating baseline.

## Why this phase exists
We want Claude Code to become effective quickly inside this repo without re-briefing the project in every session and without contaminating the context window with long conversational history.

## Current decisions
- GSD will be the primary workflow spine.
- Everything Claude Code will be used as a complement, not the main process driver.
- Stable project truths live in files, not in repeated chat prompts.
- Work should start from the repo root, not only from `utils/basic_stats/`, because demo, evals, progress docs, and runners matter.
- The first meaningful working sessions should stay tightly scoped and verifiable.

## Concrete repo understanding
The core business logic is concentrated in:
- planner: `utils/basic_stats/core/query_planner.py`
- execution: `utils/basic_stats/core/duckdb_manager.py`
- orchestration: `utils/basic_stats/core/llm_query_engine_v2.py`

These are the highest-risk edit zones.

## What not to do right now
- Do not start with a broad refactor.
- Do not stuff long historical progress into live chat if it can live in files.
- Do not enable many extra MCPs or tools without clear value.
- Do not let plugin/framework defaults dictate project decisions without checking against the repo’s actual structure.

## Session default
When a new session starts:
1. read `AGENTS.md`
2. read `.planning/PROJECT.md`
3. read `.planning/REQUIREMENTS.md`
4. read `.planning/STATE.md`
5. read `.planning/CONTEXT.md`
6. define one narrow goal
7. make a short plan
8. only then implement

## Current assumption
The best first development tasks after setup will likely be one of:
- planner interpretation edge case
- execution/aggregation bug
- verbalization issue
- UI messaging mismatch
- focused regression test addition