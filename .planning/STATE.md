# STATE.md

## Project Reference

See: `.planning/PROJECT.md` (updated 2026-03-26)

**Core value:** Every answer must stay grounded in actual data — no invented metrics, entities, values, or support rows.
**Current focus:** Phase 1 — Project Baseline

---

## Current Phase Status

**Phase 1 — Project Baseline**
- ✓ GSD planning files written (PROJECT.md, REQUIREMENTS.md, ROADMAP.md, STATE.md, config.json)
- ○ eval_runner_v4 baseline run — not yet done

**Next immediate step:** Run `eval_runner_v4.py` and record the current pass rate here before touching any code.

---

## Benchmark Baseline

> Fill in after running eval_runner_v4.py:

```
Date run:
Pass rate: XX/66
Failing cases: (list here)
Notes:
```

Known pre-existing failures from codebase map: QV4_37, QV4_38, QV5_41

---

## Operating Rules

- `query_planner.py`, `duckdb_manager.py`, `llm_query_engine_v2.py` are very sensitive — no change without test + eval validation
- `models.py`, `resolve_query_intent.yaml`, `verbalize.yaml` are sensitive — validate outputs after any change
- `pages/basic_stats.py`, `docs/` are lower sensitivity — can change more freely
- A task is done only when: implemented + relevant verification run + results checked + STATE.md updated

## Phase Progression

| Phase | Status | Pass Rate (entry) | Pass Rate (exit) |
|-------|--------|-------------------|------------------|
| 1 | ◆ In Progress | — | — |
| 2 | ○ Pending | — | — |
| 3 | ○ Pending | — | — |

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
*Last updated: 2026-03-26 after brownfield GSD initialization*
