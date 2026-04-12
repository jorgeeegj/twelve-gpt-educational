# Phase 5 — Scope Pivot Notes

**Date:** 2026-04-12
**Status:** Original Phase 5 scope deprecated and rewritten mid-execution.

---

## What the original Phase 5 plan said to do

Replace `_canonicalize_raw_plan` (~680 lines of regex) with 4 Pydantic tool schemas, then run a `dual_run_validate.py` script that compared the new function-calling planner's `QueryPlan` against the legacy planner's `QueryPlan` field-by-field. Success = exact field parity for all 61 benchmark questions.

## What we actually built before stopping

- `function_tools.py` — 4 OpenAI tool schemas
- `_call_llm_with_tools` + `_normalize_tool_args_to_plan` in `query_planner.py` (~180 lines)
- `evals/dual_run_validate.py`
- `USE_FUNCTION_CALLING=1` env flag

Final score with the flag on: **46/61**. 15 questions failed on plan-shape parity.

## Why the original scope was wrong

The original plan replaced `_canonicalize_raw_plan` (680 lines of regex on free-text JSON) with `_normalize_tool_args_to_plan` (180 lines of regex on structured JSON). Same heuristic layer, one level down. The LLM was still a fancy keyword extractor — code still did the scope inference, metric renaming, position mapping, filter coercion, and dual-bucket detection.

This approach was structurally wrong for three reasons:

1. **It didn't unlock downstream phases.** The whole point of function calling is to enable multi-turn follow-ups (Phase 6) and dynamic league context (Phase 7). An LLM that can't carry conversation state forward through tool results doesn't unlock either.

2. **Field-by-field plan parity is the wrong success metric.** We were testing "does the new pipeline produce the same internal data structure as the old one?" What we should test is "does the agent produce a faithful natural-language answer?" Two different plans can produce the same correct answer; one plan can produce a wrong one.

3. **It kept the if/else heuristic layer we were trying to eliminate.** Every one of the 15 failures was fixable only by adding more normalization code — exactly the thing the phase was supposed to delete.

## What changes in the rewrite

The new Phase 5 treats function calling as an **agent architecture**, not a drop-in replacement for the planner. The LLM owns semantic interpretation (what stat, what filter, what entity) AND verbalization (writing the answer). Code owns data access (DuckDB queries) and domain vocabulary (injected into the system prompt at agent-init time from the actual DB).

See the rewritten `PLAN.md` in this folder for the new task breakdown.

## What we're keeping from the first attempt

- The `USE_FUNCTION_CALLING` flag pattern for safe rollback (renamed `USE_LEGACY_PLANNER` in the new design — flag default flips)
- The commits themselves stay in git history as a documented false start
- `function_tools.py` gets rewritten from scratch in Task 2 of the new plan
- `_normalize_tool_args_to_plan` gets deleted in Task 2
- `dual_run_validate.py` gets deleted in Task 1
