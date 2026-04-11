# Technology Stack: v2.0 Football Stats Analyst

**Project:** Basic Stats Analyst v2.0 (Function Calling, Memory, League Context, NLP Polish)
**Researched:** 2026-04-12
**Confidence:** MEDIUM (existing codebase + training data; no live ecosystem validation)

---

## Recommended Stack

No new infrastructure required for v2.0 MVP. All changes are within the existing pipeline.

### Core Framework & Query Engine

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Claude API | 3.5 Sonnet (or Haiku 4.5 for cost) | LLM backbone for tool selection, reasoning, verbalization | Existing choice; excellent at function calling and structured reasoning |
| DuckDB | 1.0+ | In-process OLAP engine for query execution | Existing; performant for analytical queries, native Parquet support |
| Streamlit | 1.28+ | Web UI for chat interface | Existing; sufficient for session state management |
| Polars | 0.19+ | Data manipulation (query result processing) | Existing; faster than Pandas for large result sets |
| Python | 3.10+ | Runtime | Existing |

### Function Calling (v2.0 New)

| Technology | Version | Purpose | When to Use |
|------------|---------|---------|-------------|
| Claude Functions (native) | Sonnet 3.5+ | Tool definition and selection | v2.0 MVP — built into Claude API; no external library needed |
| Pydantic | 2.0+ | Tool parameter validation | Optional; already in environment; useful for schema validation |
| Python Enum | stdlib | League context groupings ("top_6", "relegation_zone") | For strongly-typed league_context parameter |

**Why not others:**
- LangChain tool decorator: Adds abstraction layer; existing code uses direct LLM calls
- LiteLLM: Not needed; already using Claude API directly
- Custom tool registry: Reinventing the wheel; Claude handles tool dispatch natively

### Conversation Memory (v2.0 New)

| Technology | Version | Purpose | When to Use |
|------------|---------|---------|------------|
| Streamlit session_state | 1.28+ | Short-term memory (conversation history + context) | v2.0 MVP — native to Streamlit; no external DB needed |
| JSON (Python dict) | stdlib | Serialize/store conversation_context | For session state storage and debug output |
| Pickle (optional) | stdlib | Persist conversation_context across sessions | v2.1+; currently not needed (session resets) |

**Not for v2.0 MVP:**
- Vector DB (Chroma, Pinecone) — use for v2.1 episodic memory if users need query history recall
- Knowledge graph (Neo4j) — scale-up only if semantic relationships become critical
- PostgreSQL — overkill for session-level storage

### Data Storage & Context

| Technology | Version | Purpose | When to Use |
|------------|---------|---------|------------|
| Parquet files | 2.0+ | Static player/team/match data | Existing; cost-effective for analytical queries |
| DuckDB views | 1.0+ | Pre-computed aggregations (league_standings, player_stats) | New in v2.0: add league_standings view for context injection |
| YAML (prompts) | stdlib | System prompts, metric templates | Existing; now expanded for metric templates + contextual frames |

### LLM Integration

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Claude API SDK (`anthropic`) | 0.25+ | LLM calls with function_calling support | Existing; native support for tools; excellent error handling |
| Azure OpenAI SDK (optional) | 1.0+ | Fallback for Azure endpoints | Existing; supported but not primary |

**Note:** Current codebase uses `get_llm_client()` abstraction (see `config.py`). v2.0 should NOT change this; extend it to support Claude function_calling parameter.

---

## Changes from v1.0

### New Dependencies (None Required)

**No new pip packages needed for MVP.** All upgrades are within existing tech stack.

Optional additions for robustness:
```bash
# Already likely installed
pip install pydantic>=2.0  # For tool parameter validation (optional)
pip install anthropic>=0.25  # Already required; ensure version supports tool_use
```

### Modified Files (No Breaking Changes)

| File | Change | Impact | Risk |
|------|--------|--------|------|
| `query_planner.py` | Tool selection logic added (LLM chooses tool name + params) | Removes regex parsing; cleaner intent → tool mapping | Low (parallel path, fallback to v1 if needed) |
| `llm_query_engine_v2.py` | Accept tool call results instead of generating own queries | Simplifies execution; LLM already did the planning | Low (inverts control, doesn't break DuckDB layer) |
| `verbalize.yaml` | Expand with metric templates, contextual frames, insight rules | Better prose generation | Low (template-based; can revert if needed) |
| `config.py` | Add `get_llm_function_calling_schema()` to expose tools | Optional helper; doesn't change existing config | Very Low (additive) |
| `pages/basic_stats.py` | Add conversation_context to session_state, project into system prompt | Session layer only | Low (isolated to Streamlit page) |
| `duckdb_manager.py` | Add league_standings view initialization | New view, doesn't break existing queries | Very Low (additive) |

### Not Changing (Intentional)

- `classes/chat.py` — Core chat orchestration stays stable
- `classes/description.py` — Stays as fallback; doesn't need modification
- `utils/basic_stats/core/duckdb_manager.py` (DuckDB queries themselves) — No changes to core SQL logic
- Authentication/infra — No changes

---

## Installation & Setup

### For v2.0 MVP

No new environment setup. Existing Streamlit app continues to work.

```bash
# Verify dependencies (should already exist)
pip show anthropic | grep Version  # Ensure >= 0.25
pip show duckdb | grep Version     # Ensure >= 1.0
pip show streamlit | grep Version  # Ensure >= 1.28

# If upgrading:
pip install --upgrade anthropic duckdb streamlit polars pydantic
```

### Data Setup (Required for League Context)

1. **Create league_standings table from existing data:**
   ```sql
   -- In duckdb_manager.py initialization:
   CREATE VIEW league_standings AS
   SELECT 
     team_name,
     COUNT(DISTINCT match_id) as matches_played,
     SUM(CASE WHEN result = 'win' THEN 3 WHEN result = 'draw' THEN 1 ELSE 0 END) as points,
     ROW_NUMBER() OVER (ORDER BY points DESC) as league_position
   FROM match_results
   GROUP BY team_name
   ORDER BY league_position;
   ```

2. **Verify table is accessible:**
   ```python
   standings = duckdb.query("SELECT * FROM league_standings LIMIT 5").to_df()
   ```

### Configuration Changes (Optional)

No changes to `.env` or `settings.json` required for MVP.

Optional (for testing):
```python
# .claude/settings.json
{
  "model": "claude-3-5-sonnet-20241022",  # Ensure function_calling support
  "alwaysThinkingEnabled": true          # Helps with function call reasoning
}
```

---

## Tools & Integrations

### Development Tools

| Tool | Purpose | Status |
|------|---------|--------|
| `eval_runner_v4.py` | Benchmark validation | Existing; use to verify no regressions after v2.0 changes |
| `eval_runner_v5.py` | Focused debug runner | Existing; extend to test function calling behavior |
| `test_query_planner.py` | Unit tests | Existing; add tests for new tool selection logic |

### Deployment & Monitoring

No changes to production deployment. Same Streamlit app.

Optional monitoring improvements (v2.1+):
- Log function calls made by LLM (for debugging)
- Track conversation context size (watch for context window creep)
- Monitor fallback to non-function-calling queries

---

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| Function Calling Library | Claude native | LangChain, LiteLLM | Adds abstraction; existing code uses direct API calls |
| Conversation Memory Store | Streamlit session_state | Redis, PostgreSQL | Overkill for session-level storage; MVP doesn't need persistence |
| League Context Source | System prompt injection | Dynamic tool retrieval | Simpler for MVP; upgrade to dynamic if needed later |
| LLM Reasoning Tool | Extended Thinking | ReAct loop | Extended thinking built into Claude; simpler than ReAct |
| Metric Templating | YAML + Python rules | LLM-only generation | Hybrid approach is more reliable and auditable |

---

## Scaling Considerations (Future Phases)

### Phase 2: Episodic Memory
When users ask "Did we discuss Haaland's xG before?"

| Technology | Purpose | Timeline |
|------------|---------|----------|
| Chroma / Weaviate | Vector DB for conversation embeddings | v2.1 (optional) |
| Datetime tracking | Timestamp conversations for temporal queries | v2.1 (optional) |

### Phase 3: Multi-User / API-First
When moving beyond single-session Streamlit app

| Technology | Purpose | Timeline |
|------------|---------|----------|
| PostgreSQL | Persistent conversation storage + user sessions | v3.0+ |
| FastAPI | REST API for LLM queries | v3.0+ |
| Redis | Cache for standings, frequently-queried stats | v3.0+ |

### Phase 4: Advanced Features (Out of Scope)
- Real-time data ingestion (live match events)
- Fine-tuning (if patterns emerge requiring custom LLM behavior)
- GraphQL API (complex query composition)

---

## Sources

| Source | Type | Confidence |
|--------|------|------------|
| Existing `requirements.txt` | Codebase | HIGH |
| Anthropic API docs (training data) | Documentation | HIGH |
| `config.py` LLM client setup | Codebase | HIGH |
| Claude API function_calling support (training) | Training material | MEDIUM |

