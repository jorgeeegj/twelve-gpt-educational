# Phase 6 — Random Question Robustness

**Status:** Not started (Phase 5 complete as of 2026-04-17)
**Requirements:** ROB-01, ROB-02
**Why this matters:** Agust's #1 priority. The agent can answer the 61 prepared benchmark questions, but "Salah", "Man City", or "which striker" with a typo will return empty rows or wrong data. This phase fixes that with embedding-based entity resolution.

---

## Goal

Make the agent handle arbitrary Premier League questions it has never seen — no hardcoded entity lists, no regex fallbacks. The LLM already picks the right tool and filters; this phase ensures the *entity names* it passes match what's in the DB.

---

## The Problem

The agent calls tools with entity names exactly as the LLM extracts them from the question:
- User says "Salah" → LLM passes `player_name="Salah"` → DB has `"M. Salah"` → empty rows
- User says "Man City" → LLM passes `player_team="Man City"` → DB has `"Manchester City"` → empty rows
- User says "center backs" → LLM passes `position="Center Back"` → DB has `"Central Defender"` → empty rows

The system prompt lists all exact names, which helps for direct questions. But on follow-ups ("what about him?", "the Liverpool striker"), under ambiguous phrasing, or with abbreviations, the LLM still extracts wrong strings.

---

## Solution: Embedding-based fuzzy resolution in the tool layer

Rather than changing the LLM's extraction behavior (fragile), we resolve entity names *after* extraction, *before* the DB query. The tool functions call `duck.fuzzy_resolve_entity(name, "player")` and get back the canonical DB name.

This keeps the resolution logic in one place and makes it testable without LLM calls.

---

## Architecture

### Step 1 — Generate and store embeddings

`duckdb_manager.store_entity_embeddings()` (the stub from Phase 5):
1. Query all `DISTINCT short_name` from `players_summary` → player list
2. Query all `DISTINCT team_name` from `players_summary` → team list
3. For each name, call `client.embeddings.create(model="text-embedding-3-large", input=name)`
4. Store in a DuckDB persistent table:
   ```sql
   CREATE TABLE IF NOT EXISTS entity_embeddings (
       entity_type VARCHAR,   -- 'player' | 'team'
       canonical_name VARCHAR,
       embedding FLOAT[3072]  -- text-embedding-3-large dimension
   )
   ```
5. Install and load the DuckDB VSS extension (`INSTALL vss; LOAD vss`)
6. Create an HNSW index on the embedding column for fast cosine similarity search

This runs once at setup time (not on every agent init). A CLI script `scripts/build_embeddings.py` triggers it.

### Step 2 — Implement `fuzzy_resolve_entity()`

`duckdb_manager.fuzzy_resolve_entity(user_input, entity_type)`:
1. Embed `user_input` using the same model
2. Run cosine similarity search against the VSS table filtered by `entity_type`
3. Return the `canonical_name` with highest similarity
4. If similarity < threshold (0.75), return `user_input` unchanged — don't force a wrong resolution

```python
def fuzzy_resolve_entity(self, user_input: str, entity_type: str) -> str:
    # embed user_input, query VSS, return canonical name or original if below threshold
```

### Step 3 — Wire resolution into tool functions

In `agent_tools.py`, the 9 underlying functions that accept `player_name` or `team_name` call `fuzzy_resolve_entity` before passing the name to `duckdb_manager`:

```python
# In get_player_stat:
player_name = duck.fuzzy_resolve_entity(player_name, "player")

# In get_team_stat:
team_name = duck.fuzzy_resolve_entity(team_name, "team")
```

Position strings ("center back" → "Central Defender") handled by a small local mapping in `agent_tools.py`, not VSS (positions are a closed set of ~5 values).

### Step 4 — Validate on 20-name test set

`tests/test_fuzzy_resolve.py` — no LLM calls, uses pre-stored embeddings:
- "Salah" → "M. Salah"
- "Haaland" → "E. Haaland"
- "Man City" → "Manchester City"
- "Spurs" → "Tottenham Hotspur"
- "De Bruyne" → "K. De Bruyne"
- 15+ more covering common abbreviations and partial names

Gate: ≥95% accuracy on the 20-name set.

### Step 5 — Run unprepared questions

Each team member (Ricardo, Álvaro, Jorge) writes 7 questions they haven't seen in the benchmark. Collect into `evals/random_questions.json`. Run once with `evals/agent_benchmark.py --category random`.

Gate: ≥80% faithful answers (≥17/21).

---

## Task breakdown

| Step | What | Files | Gate |
|------|------|-------|------|
| 1 | Build embeddings store | `duckdb_manager.py` (fill stub), `scripts/build_embeddings.py` | Script runs without error, ~600 rows in table |
| 2 | Implement `fuzzy_resolve_entity()` | `duckdb_manager.py` (fill stub) | Unit test: 20-name set ≥95% |
| 3 | Wire into tool functions | `agent_tools.py` | Existing 31 tests still pass |
| 4 | Position mapping | `agent_tools.py` | Tests for "forward", "CB", "keeper" etc. |
| 5 | Collect + run random questions | `evals/random_questions.json` | ≥17/21 faithful |

---

## Key decisions

**Why VSS (vector similarity) instead of fuzzy string matching?**
Fuzzy string matching (Levenshtein) works for typos but fails on semantic aliases: "Spurs" ↔ "Tottenham Hotspur", "the Norwegian" ↔ "E. Haaland". Embeddings handle both.

**Why `text-embedding-3-large`?**
Already configured in `GPT_EMBEDDINGS_MODEL`. Consistent with rest of project. 3072 dimensions gives very high resolution for short strings like player names. The corpus is tiny (~600 names) so index build time is negligible.

**Why resolve in the tool layer, not the agent loop?**
The agent loop shouldn't know about DB entity names — that's data-layer knowledge. The tool functions already handle the DB boundary; resolution belongs there. It also makes testing simpler (no LLM needed in tests).

**Why a similarity threshold?**
Without a threshold, "Arsenal" would always resolve to something even if the user typed a completely unrelated string. A threshold of 0.75 means "confident enough" — below it, pass the original string through and let the DB return empty rows (the LLM already handles empty results gracefully).

**Where is the embeddings table stored?**
In `db/basic_stats.duckdb` (the persistent DuckDB file). The table is populated once by `scripts/build_embeddings.py` and stays. The VSS HNSW index is recreated if the table is repopulated.

---

## What the stubs look like now (Phase 5 artifacts)

```python
# duckdb_manager.py — Phase 5 stubs to be filled in Phase 6

def store_entity_embeddings(self) -> None:
    raise NotImplementedError("store_entity_embeddings will be implemented in Phase 6")

def fuzzy_resolve_entity(self, user_input: str, entity_type: str) -> str:
    raise NotImplementedError("fuzzy_resolve_entity will be implemented in Phase 6")
```

Both are in `DuckDBManager` at the bottom of the file. Implementation fills them in-place.

---

## Exit gate

From ROADMAP.md:
> "text-embedding-3-large embeddings for all player/team names stored in DuckDB VSS; fuzzy_resolve_entity resolves with ≥95% accuracy on 20-name test set; ≥80% faithful on 20+ unprepared questions"
