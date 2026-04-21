---
phase: phase-8
plan: "01"
subsystem: agent-prompt
tags: [league-context, system-prompt, yaml-template, verification]
dependency_graph:
  requires: [phase-4-standings-view, phase-5-agent-prompt]
  provides: [league-context-injection]
  affects: [agent_prompt.py, agent_system.yaml]
tech_stack:
  added: []
  patterns: [file-read-at-init, template-format-injection]
key_files:
  created:
    - scripts/verify_league_context.py
    - tests/test_agent_prompt.py
  modified:
    - src/basic_stats/agent_prompt.py
    - src/basic_stats/prompts/agent_system.yaml
decisions:
  - Read markdown file at init time (not DB query) — file is static and already generated from standings data
  - Instantiate fresh BasicStatsAgent per question in verify script to avoid conversation history contamination
metrics:
  duration: ~15min
  completed: "2026-04-21"
  tasks_completed: 4
  files_modified: 4
---

# Phase 8 Plan 01: League Context Injection Summary

Injected `docs/premier_league_2024_25_context.md` into the agent system prompt via `{league_context}` template placeholder, replacing two hardcoded blocks in the YAML that listed team tier assignments inline.

## Changes per File

**`src/basic_stats/agent_prompt.py`**
Added `_DOCS_DIR` constant pointing to the repo's `docs/` directory, reads `premier_league_2024_25_context.md` inside `build_system_prompt()`, and passes the content as `league_context=` to `template.format()`. No other changes.

**`src/basic_stats/prompts/agent_system.yaml`**
Removed the `PREMIER LEAGUE 2024-25 CONTEXT` intro paragraph (9 lines with hardcoded Big Six list, CL/EL rules, promoted sides) and removed the `LEAGUE TIER CONVENTIONS` block (10 lines). Replaced the latter with a single `{league_context}` placeholder. Added one Big Six routing rule (`opponent_is_big6`) at the top of the `HOW TO USE TOOLS` section to preserve the tool-dispatch instruction that was inside the deleted block.

**`scripts/verify_league_context.py`**
New script that instantiates a fresh `BasicStatsAgent()` per question, runs 6 league-knowledge questions via `agent.ask()`, checks keyword presence case-insensitively, and exits 0 if ≥5/6 pass.

**`tests/test_agent_prompt.py`**
New unit test `test_build_system_prompt_structure` that calls `build_system_prompt()` with a real `DuckDBManager` and asserts structural properties of the returned string — no LLM calls, deterministic.

## Verification Questions and Results

| # | Question | Expected Keywords | Result |
|---|----------|------------------|--------|
| 1 | Which teams finished in the top 4 this season? | Liverpool, Arsenal, Manchester City, Chelsea | PASS |
| 2 | Which teams were relegated from the Premier League in 2024-25? | Leicester, Ipswich, Southampton | PASS |
| 3 | Who are the Big Six clubs in the Premier League? | Arsenal, Chelsea, Liverpool, Manchester City, Manchester United, Tottenham | PASS |
| 4 | Which teams qualified for the Champions League this season? | Newcastle | PASS |
| 5 | Which team finished 7th and what European competition did they qualify for? | Nottingham Forest, Europa | PASS |
| 6 | How many points did the champions finish with this season? | 84 | PASS |

**Result: 6/6 questions passed. Exit code: 0.**

## Grep Confirmation — Zero Hardcoded Team Group Lists in Modified Files

```
grep -rn "Big Six\|top.6.*Arsenal\|top.4.*Liverpool\|relegation.*Leicester" src/basic_stats/agent_prompt.py src/basic_stats/prompts/agent_system.yaml
(no output — zero results)
```

The three matches returned by the full `src/basic_stats/*.py` glob are in `agent_tool_schemas.py` (untouched, pre-existing tool parameter descriptions), not tier assignment lists.

## Deviations from Plan

**1. [Rule 3 - Blocking] Fresh agent per question in verify script**
- **Found during:** Task 3 verification (second run showed 4/6 due to conversation contamination)
- **Issue:** `agent.ask()` maintains conversation history across calls; question 6 received the context from question 5's answer (Nottingham Forest), causing the LLM to answer the wrong question.
- **Fix:** Instantiate a new `BasicStatsAgent()` before each question so each runs with a clean slate.
- **Files modified:** `scripts/verify_league_context.py`
- **Commit:** 1c4a151f

## Known Stubs

None.

## Self-Check: PASSED

- `src/basic_stats/agent_prompt.py` — exists and modified
- `src/basic_stats/prompts/agent_system.yaml` — exists and modified
- `scripts/verify_league_context.py` — exists and created
- `tests/test_agent_prompt.py` — exists and created
- Commit bbd20b6a — tasks 1+2
- Commit c2521a6f — task 3
- Commit 3c705b1e — task 4
- Commit 1c4a151f — deviation fix
- All 95 tests pass, verify script exits 0 with 6/6
