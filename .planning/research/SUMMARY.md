# Research Summary — Basic Stats Analyst v2.0

## Executive Summary

v2.0 adds four capability layers to a validated 61/61 baseline: **function calling** (replacing ~680 lines of regex canonicalization), **conversation memory** (multi-turn follow-ups), **league context injection** (semantic team classification), and **NLP polish** (natural verbalization). Zero new external dependencies. 6-phase brownfield migration preserving benchmark gate at each phase.

**Critical finding:** requirements.txt declares `openai==0.28.1` but environment has `2.15.0`. Must be fixed in Phase 1 before function calling starts.

---

## Stack Additions

| What | Status | Action |
|------|--------|--------|
| `openai==2.15.0` | Already installed, wrong pin | Update requirements.txt in Phase 1 |
| `pydantic==2.12.5` | Already installed | Use `model_json_schema()` for tool schemas |
| `uv` | Already installed (0.10.6) | Create `pyproject.toml` in Phase 1 |
| `ruff` | Not configured | Add to pyproject.toml in Phase 1 |
| `pre-commit` | Not configured | Add `.pre-commit-config.yaml` in Phase 1 |

**No new runtime dependencies.** Memory → Streamlit `session_state`. Function calling → Pydantic v2 + openai native tools. Quality tooling → uv + pyproject.toml.

---

## Feature Table Stakes

### Function Calling (Phase 2)
- 3–5 flexible parameterized tools (NOT 20+ narrow ones): `query_entity_stats`, `compare_across_buckets`, `rank_by_metric`, `query_temporal_window`
- Deterministic tool selection — no hallucination on unfamiliar filters
- Pre-validation in Python (return error objects, not exceptions)
- **Must preserve** all implicit canonicalization rules from old planner (~400 rules documented before Phase 2)
- Graceful fallback flag (`use_function_calling`) — old planner stays until 100% tool coverage verified

### Conversation Memory (Phase 3)
- Track: entity focus, active filters (opponent, time window, position), last metric, last result rows
- Sliding window: last 3–5 turns (not full history)
- Token budget cap: max 1,500 tokens of context before LLM call
- Multi-turn test suite (10–15 flows) defined BEFORE implementation

### League Context (Phase 4)
- System prompt injection approach: inject league standings paragraph once per session
- Timestamp all injected context ("as of Matchday X")
- **Data blocker:** `league_standings` DuckDB view must be created in Phase 1 tail
- Hardcode 2024–25 standings for MVP; dynamic later

### NLP Polish (Phase 6)
- Never expose internal metric names (`total_goals_p90` → "goals per 90")
- Metric templates + contextual frames in `verbalize.yaml`
- Deterministic insight rules (goals/xG ratio ≥1.15 → "finishing above expectation") — no LLM elaboration
- Singular/plural/comparative forms per metric

---

## Build Order

| Phase | Name | Rationale |
|-------|------|-----------|
| 1 | Extract & Clean | Clean directory structure + tooling before touching core logic |
| 2 | Function Calling Core | Replace planner — unblocks Phases 3–4; critical path |
| 3 | Conversation Memory | Depends on Phase 2 structured query metadata |
| 4 | League Context | Depends on Phase 1 standings view + Phase 2 tool structure |
| 5 | Random Question Robustness | Stress test after architecture is stable |
| 6 | Natural Language Polish | Low-risk text changes on stable foundation |

**Benchmark gate: 61/61 eval_runner_v6 after every phase. No exceptions.**

---

## Top 5 Pitfalls

1. **Silent behavior change (Phase 2, CRITICAL)** — Implicit canonicalization rules not captured in tool schemas; LLM produces valid JSON with wrong semantics. Prevention: document all rules in `canonicalization_rules.md` before Phase 2; dual-run old vs new planner on all 61 questions field-by-field.

2. **Premature planner deletion (Phase 2, HIGH)** — Old planner removed before tools cover 100% of cases; benchmark drops. Prevention: `use_function_calling` flag; only delete after tool coverage matrix shows 100%.

3. **State pollution (Phase 3, HIGH)** — Context cached too aggressively; follow-up re-uses wrong filters. Prevention: define explicit carry-forward rules (carry opponent + time window; reset position filter on entity change); validate with multi-turn test suite.

4. **Broken imports during restructure (Phase 1, HIGH)** — 40+ import points; missing some breaks eval_runner and Streamlit. Prevention: grep import manifest before Phase 1; write import validation script; run before Phase 1 close.

5. **Token budget overflow (Phase 3, MEDIUM)** — Conversation state exhausts context by turn 10–15. Prevention: sliding window design from day 1; token counting assertion in every LLM call; 20-turn stress test.

---

## Open Questions for Roadmapper

1. **Phase 2 tool set:** Start with 3 tools or 4? (Recommend: 4 — `query_entity_stats`, `compare_across_buckets`, `rank_by_metric`, `query_temporal_window`)
2. **Phase 3 window size:** 3 turns or 5 with 2K token budget? (Recommend: 3 for safety)
3. **Phase 4 standings:** Dynamic extraction from existing match data, or hardcode? (Recommend: extract from `team_match` view — data already exists)
4. **Phase 1 pages/ scope:** Reorganize `pages/basic_stats.py` in Phase 1 or leave until after function calling? (Recommend: leave — minimize Phase 1 blast radius)
5. **Fallback strategy:** If Phase 2 function calling fails a question, should it silently fall back to old planner or surface the error? (Recommend: silent fallback with logging during Phase 2; remove fallback in Phase 5)

---

*Generated: 2026-04-12 — 4 parallel researchers + synthesizer*
