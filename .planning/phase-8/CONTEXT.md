---
phase: phase-8
created: 2026-04-21
status: final
---

# Phase 8 — League Context: Design Decisions

All decisions below are locked. Downstream agents (researcher, planner, executor) must not reopen them.

## Decision 1: Static file, not DB query

**Decision:** Read `docs/premier_league_2024_25_context.md` at agent init time. Do not query `league_standings` DuckDB view at runtime.

**Rationale:** The 2024-25 season is over — standings will not change. The markdown file contains standings + team categories + season narrative + LLM usage notes. Only the standings are in the DB; the rest (narrative, categories, notes) would need to be hardcoded anyway. No reason to split the content across two sources. `duckdb_manager.py` is the highest-risk file — unnecessary changes are prohibited.

**CTX-02 note:** Satisfied by the markdown file having been derived from the `league_standings` view data. No code change to the view is required.

---

## Decision 2: Injection mechanism

**Decision:** Add `{league_context}` placeholder to `agent_system.yaml`. In `build_system_prompt()` in `agent_prompt.py`, read the markdown file and pass `league_context=<contents>` to the existing `template.format()` call.

**Implementation:**
- Add `_DOCS_DIR = Path(__file__).parent.parent.parent / "docs"` constant alongside `_PROMPTS_DIR`
- Inside `build_system_prompt()`: `league_context = (_DOCS_DIR / "premier_league_2024_25_context.md").read_text(encoding="utf-8")`
- Add `league_context=league_context` to `template.format()`
- No error handling — the file is in the repo and will always exist

---

## Decision 3: Remove both hardcoded blocks from agent_system.yaml

**Decision:** Remove **both** of the following from `agent_system.yaml`:
1. The `PREMIER LEAGUE 2024-25 CONTEXT` intro paragraph (lines 7–15) — hardcodes Big Six list, CL/EL spots, promoted sides
2. The `LEAGUE TIER CONVENTIONS` block (lines 66–76) — hardcodes Big Six = [Arsenal, Chelsea, Liverpool, Man City, Man United, Tottenham]

The injected `{league_context}` covers all of this more accurately and completely.

---

## Decision 4: Preserve opponent_is_big6 routing rule

**Decision:** After removing the LEAGUE TIER CONVENTIONS block, add the following routing rule to the top of the **HOW TO USE TOOLS** section:

```
- "Big Six" or "top 6 teams" (by historical identity) → use filters.opponent_is_big6=true
  (NOT opponent_rank_max — Man United finished 15th, Tottenham 17th in 2024-25)
```

**Rationale:** `opponent_is_big6` is a real DB filter used in `agent_tools.py` and `duckdb_manager.py`. Without this routing instruction, the LLM falls back to rank-based filtering which gives wrong results for Big Six queries (Man United = 15th, Tottenham = 17th).

---

## Decision 5: Verification script

**Decision:** Create `scripts/verify_league_context.py` with 6 live questions against the agent. Exit 0 if ≥5 pass.

**Questions:**
1. "Which teams finished in the top 4 this season?" → must mention Liverpool, Arsenal, Manchester City, Chelsea
2. "Which teams were relegated from the Premier League in 2024-25?" → must mention Leicester, Ipswich, Southampton
3. "Who are the Big Six clubs in the Premier League?" → must mention Arsenal, Chelsea, Liverpool, Manchester City, Manchester United, Tottenham
4. "Which teams qualified for the Champions League?" → must mention Newcastle (5th-place extra CL spot)
5. "Which team finished 7th and what European competition did they qualify for?" → must mention Nottingham Forest and Europa League
6. "How many points did the champions finish with?" → must mention 84

**API:** `agent.ask(question)` — not `agent.chat()`.

---

## Files touched

| File | Change |
|------|--------|
| `src/basic_stats/agent_prompt.py` | Add `_DOCS_DIR`, read markdown, pass `league_context=` to `template.format()` |
| `src/basic_stats/prompts/agent_system.yaml` | Remove intro paragraph + TIER CONVENTIONS block; add `{league_context}`; add Big Six routing rule to HOW TO USE TOOLS |
| `scripts/verify_league_context.py` | New — 6 verification questions, exit 0 if ≥5 pass |
| `tests/test_agent_prompt.py` | New — unit test for prompt structure (no LLM, joins permanent test suite) |

## Files NOT touched

- `src/basic_stats/duckdb_manager.py` — high-risk, no need
- `src/basic_stats/agent.py` — no change
- `src/basic_stats/agent_tools.py` — no change
- `src/basic_stats/agent_tool_schemas.py` — no change
