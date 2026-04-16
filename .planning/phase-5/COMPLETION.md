# Phase 5 — Completion Notes

**Completed:** 2026-04-17
**Commits:** `6ab846fe`, `f7c8639b`, `492073d7`, `a4ed8ce3`

---

## What was built (final state)

Phase 5 was split into 7 steps across two sessions. Steps 1–4 landed in session 2026-04-17 morning; Steps 5–7 in the afternoon of the same day.

### Step 1 — `config.py`
Added `get_embeddings_model()` — reads `GPT_EMBEDDINGS_MODEL` from Streamlit secrets. Required by Phase 6 VSS work.

### Step 2 — `duckdb_manager.py` VSS stubs
Added two placeholder methods:
- `store_entity_embeddings()` — will generate `text-embedding-3-large` embeddings for all player/team names and store in a DuckDB VSS table.
- `fuzzy_resolve_entity(user_input, entity_type)` — will resolve "Salah" → "M. Salah" via cosine similarity.

Both raise `NotImplementedError`. Nothing calls them. They reserve the implementation site for Phase 6.

### Step 3 — `agent_tool_schemas.py` (4 mother tools)
Collapsed 9 individual tool schemas into 4 mother tools in flat Responses API format (no `"function": {}` wrapper, no `"strict": True`):
- `query_player_stats` — absorbs `get_player_stat`, `count_matches_where` (player), `get_stat_over_window` (player), `get_stat_vs_opponent_group` (player)
- `query_team_stats` — absorbs `get_team_stat`, `rank_teams`, `get_stat_over_window` (team)
- `query_ranking` — absorbs `rank_players`, `compare_entities`
- `get_league_standings` — unchanged logic, updated schema format

### Step 4 — `agent_tools.py` mother tool dispatchers
Added 3 dispatcher functions (`query_player_stats`, `query_team_stats`, `query_ranking`) that route to the 9 underlying specialized functions based on args. The `Filters` dataclass and `ToolResult` dataclass were eliminated — all functions now read plain dicts via an `_f()` helper, matching what the LLM sends in OpenAI function calling.

The 9 underlying specialized functions remain intact (tested directly).

### Step 5 — `agent.py` migrated to Responses API
- `client.chat.completions.create` → `client.responses.create`
- `_last_response_id: str | None` instance variable stores the last response ID
- `previous_response_id=self._last_response_id` passed on every call after the first
- `reset()` method clears state (called by Clear chat button)
- Loop reads `response.output` items, checks `item.type == "function_call"`
- Tool results sent as `{"type": "function_call_output", "call_id": ..., "output": ...}`
- `_build_tool_map` reduced from 9 entries to 4

### Step 6 — `agent_system.yaml` prompt updated
HOW TO USE TOOLS section rewritten to reference the 4 mother tool names. Examples updated for `query_player_stats`, `query_team_stats`, `query_ranking`, `get_league_standings`.

### Step 7 — `pages/basic_stats.py` wired
- `@st.cache_resource` on `BasicStatsAgent` — agent initialized once per Streamlit server process, not on every rerun (saves 4 DuckDB queries + system prompt build each time)
- `agent.reset()` called when user clicks Clear chat — clears `_last_response_id` so conversation context resets
- `history=` kwarg removed from `_ask()` — conversation state now carried server-side via `previous_response_id`

---

## What the original PLAN.md described vs what we actually did

The `PLAN.md` in this folder was written before the second pivot (2026-04-16 scope revision). Key differences:

| Original plan | Actual implementation |
|---|---|
| 9 tools with 9 schemas | 4 mother tools dispatching to 9 specialized functions |
| `strict: true` in schemas | `strict` omitted (invalid in Responses API) |
| `"function": {}` wrapper | Flat format (name/description/parameters at root) |
| `history=[]` message list passed manually | `previous_response_id` — server carries context |
| Separate `count_matches_where` tool | Absorbed into `query_player_stats` via `match_conditions` param |
| Separate `get_stat_over_window` tool | Absorbed into `query_player_stats` / `query_team_stats` via `last_n_gameweeks` |
| Separate `get_stat_vs_opponent_group` tool | Absorbed into `query_player_stats` via `opponent_teams` param |
| Separate `compare_entities` tool | Absorbed into `query_ranking` via `rank_mode=false, entities=[...]` |

The reduction from 9 to 4 tools was the main architectural insight: OpenAI recommends fewer, wider tools rather than many narrow ones. The LLM reasons about intent better when it has fewer choices with richer parameters.

---

## Test coverage

31 unit tests passing (`tests/test_agent_tools.py`). Tests exercise the 9 underlying specialized functions directly — not the mother tool dispatchers (those are thin routing wrappers with no logic of their own).

`TestFilters` class removed (the `Filters` dataclass was eliminated in Step 4).

---

## Phase 5 exit gate

From ROADMAP.md:
> "Responses API working + 3 mother tools + follow-up history wired"

Status: **Met.** (4 mother tools, not 3 — the extra is `get_league_standings`.)
