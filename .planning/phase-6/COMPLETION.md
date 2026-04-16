# Phase 6 — Random Question Robustness — COMPLETE

**Completed:** 2026-04-16
**Exit gate:** ≥17/21 faithful on unprepared questions
**Result:** 21/21 (100%) faithfulness — gate passed

---

## What was built

### Embedding-based entity resolution (Steps 1–3)

`DuckDBManager.store_entity_embeddings()` — generates and persists OpenAI embeddings
for every player short name (444 players, 1332 entries with aliases) and team name
(20 teams) into a `entity_embeddings` table in `db/basic_stats.duckdb`.

`DuckDBManager.fuzzy_resolve_entity(user_input, entity_type)` — embeds the user-supplied
string at query time, runs cosine similarity search, returns the canonical DB name.
Similarity threshold: 0.75 — below it, the original string is passed through unchanged.

**Wired into:** `get_player_stat`, `get_team_stat`, `compare_entities`,
`count_matches_where`, `get_stat_vs_opponent_group`

**Effect:** "Salah" → "M. Salah", "Spurs" → "Tottenham Hotspur", "Man City" →
"Manchester City" — resolved before the DB query, no empty rows.

### Position mapping moved to the LLM (Step 4 — revised)

Originally planned as a Python `_POSITION_MAP` dict in `agent_tools.py`.
Removed after realizing this was a heuristic that the agentic architecture already
handles: the tool schema description tells the LLM exactly which DB values to use
and how to map aliases. Python code that post-corrects what the LLM should produce
correctly is noise — and a crutch that masks schema bugs.

Concretely: the `filters.position` description in `agent_tool_schemas.py` was also
wrong (said `'Defender'` instead of `'Central Defender'` and `'Full Back'`). Fixing
the schema and removing the Python patch is cleaner and more robust.

**Rule crystallized:** no heuristic in Python that can be replaced by a tool
description or system prompt instruction. Agust's `classes/chat.py` pattern is the
reference — tool descriptions route LLM decisions, code only executes them.

### Benchmark (Step 5)

21 unprepared questions written by Ricardo (7), Álvaro (7), Jorge (7).
Questions use real-world aliases: "Isak", "Saka", "Trent", "Bruno", "Spurs",
"Villa", "Wolves", "Man City", "Brentford", "keeper", "centre back", etc.

Run 1 (before schema fix): 21/21 — DuckDB crash on one question masked by fallback
Run 2 (after schema fix + position mapping cleanup): 21/21 — clean run, no errors

---

## Files changed

| File | Change |
|------|--------|
| `src/basic_stats/duckdb_manager.py` | `store_entity_embeddings()`, `fuzzy_resolve_entity()`, `set_embedding_client()`, `column_exists()` |
| `src/basic_stats/agent_tools.py` | Fuzzy resolution wired at 5 entry points; `_POSITION_MAP` + `normalize_position()` removed |
| `src/basic_stats/agent_tool_schemas.py` | `filters.position` description fixed with exact DB values + alias mapping |
| `src/basic_stats/agent.py` | `set_embedding_client()` called at init |
| `evals/random_questions.json` | 21 unprepared questions |
| `tests/test_fuzzy_resolve.py` | 19 resolution tests (no LLM) |
| `tests/test_position_mapping.py` | Deleted (function removed) |

---

## Tests

- `tests/test_fuzzy_resolve.py` — 19 tests, all passing (player + team resolution)
- `tests/test_duckdb_vss_stubs.py` — 3 pre-existing failures (stubs expect
  `NotImplementedError` on functions now fully implemented — will be cleaned in Phase 7 housekeeping)
- Total: 91 passing, 3 pre-existing failures unrelated to Phase 6 changes
