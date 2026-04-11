# Architecture Patterns: v2.0 Football Stats Analyst

**Domain:** Football statistics LLM analyst with function calling, conversation memory, dynamic context
**Researched:** 2026-04-12
**Confidence:** MEDIUM (patterns inferred from existing codebase + Agents Foundations training)

---

## Recommended Architecture: Enhanced Existing Pipeline

v2.0 enhances the existing planner → engine → DuckDB → verbalization pipeline with three new layers:

```
┌─────────────────────────────────────────────────────────────────┐
│                     CONVERSATION INTERFACE                       │
│              (Streamlit pages/basic_stats.py)                     │
└─────────────────┬──────────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                  CONVERSATION MEMORY LAYER (NEW)                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ Session Context: entity_focus, active_filters, metrics   │   │
│  │ Message History: full conversation transcript            │   │
│  │ Result Cache: last 2–3 query results                     │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────┬──────────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                  LEAGUE CONTEXT LAYER (NEW)                      │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ Fetch league standings from DuckDB (once per session)   │   │
│  │ Inject as markdown into system prompt                   │   │
│  │ LLM infers "top 6", "relegation zone" from text        │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────┬──────────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────────┐
│               FUNCTION CALLING LAYER (ENHANCED)                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ LLM analyzes user question → selects tool               │   │
│  │ Tool set: query_player_stats, query_team_stats,         │   │
│  │           compare_entities, rank_by_metric              │   │
│  │ LLM fills in parameters: player, metric, filters        │   │
│  │ Python validates parameters + returns errors if invalid │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────┬──────────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────────┐
│            QUERY ENGINE LAYER (MINIMAL CHANGE)                   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ Receives structured tool parameters (not regex-parsed)  │   │
│  │ Dispatches to DuckDBManager with clean intent           │   │
│  │ Returns rows + metadata (metric, context, count)        │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────┬──────────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────────┐
│            DATA EXECUTION LAYER (UNCHANGED)                      │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ DuckDBManager: executes SQL queries on views            │   │
│  │ Parquet data: player_stats, team_stats, match_results   │   │
│  │ League standings view: NEW for context injection         │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────┬──────────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────────┐
│          VERBALIZATION LAYER (ENHANCED WITH TEMPLATES)           │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ Metric templates: "goals" → "has scored X goals"        │   │
│  │ Contextual frames: "vs top 6" → bucket-specific prose   │   │
│  │ Insight rules: goals vs xG → performance evaluation     │   │
│  │ LLM fills templates + adds natural framing              │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────┬──────────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                     USER-FACING RESPONSE                         │
│              (Streamlit chat_message + debug panel)              │
└─────────────────────────────────────────────────────────────────┘
```

---

## Component Boundaries & Responsibility

### Layer 1: Conversation Interface (pages/basic_stats.py)

**Responsibility:** Handle user input, display messages, manage session state

**Communicates With:** Conversation Memory Layer

**Key Functions:**
```python
def handle_user_message(user_input: str):
    # 1. Update conversation_context (entity, filter mentions)
    # 2. Project context into system prompt
    # 3. Call LLM with conversation history + context
    # 4. Parse tool call from LLM response
    # 5. Execute tool
    # 6. Display result + debug info
    # 7. Update session_state with new context
```

**Constraints:**
- Never invoke DuckDB directly (goes through Query Engine)
- Never hallucinate context (infer only from user input or prior results)
- Update conversation_context after every LLM response

---

### Layer 2: Conversation Memory Layer (NEW)

**Responsibility:** Store and project conversation state

**Communicates With:** Interface (reads/writes session_state), Function Calling Layer (extracts parameters)

**Data Structure (Session State):**
```python
conversation_context = {
    "entity_focus": {
        "type": "player" | "team",
        "name": str,
        "position": int  # Index in recent_results for quick lookup
    },
    "active_filters": {
        "opponent_filter": str | None,  # "vs Arsenal", "vs top 6", null
        "time_window": str | None,       # "season", "last 5 rounds", "matchdays 10-15"
        "position_filter": str | None,   # "midfielder", "defender", null
    },
    "active_metrics": {
        "primary": str,                  # "total_goals"
        "variants": [str],               # ["total_goals", "total_goals_p90"]
        "last_used": str                 # For context carry-forward
    },
    "recent_results": [
        {
            "turn": int,
            "entity": str,
            "metric": str,
            "value": float,
            "context_label": str,  # "vs top 6", "season", etc
            "full_rows": [dict]    # Top 1–3 rows for reference
        }
    ],
    "conversation_history": [
        {"role": "user" | "assistant", "content": str}
    ]
}
```

**Update Rules:**
- **Entity focus:** Any mention of new player/team → update; explicit "switch to X" → update
- **Filters:** Explicit mention ("against top 6") → add/update filter; no mention → carry forward
- **Metrics:** New metric in question → primary becomes new metric; implied variant (per 90) → add to variants
- **Recent results:** After each tool execution → append to list, keep 2–3 most recent
- **History:** Every user message and LLM response → append; never delete

**Projection into LLM Context:**

```python
def build_system_prompt_with_context(league_context: str, conversation_context: dict) -> str:
    return f"""
You are a football data analyst.

{league_context}

CONVERSATION CONTEXT:
Current entity: {conversation_context['entity_focus']['name']} ({conversation_context['entity_focus']['type']})
Active filters: {json.dumps(conversation_context['active_filters'])}
Recent queries: {json.dumps(conversation_context['recent_results'][-2:], indent=2)}

Guidelines:
- Carry forward active filters unless the user explicitly changes them
- If the user says "How many goals?" without specifying vs. whom, use the current opponent_filter
- If the user says "per 90?", use the primary_metric but apply the p90 variant
- Refer back to recent_results if user asks comparative questions ("Is that more than...?")
"""
```

---

### Layer 3: League Context Layer (NEW)

**Responsibility:** Provide dynamic team classification without hardcoding

**Communicates With:** Data Execution Layer (reads league_standings), Function Calling Layer (via system prompt)

**Implementation:**
```python
def fetch_and_format_league_context() -> str:
    """Fetch standings from DuckDB; format as markdown for system prompt."""
    standings = duckdb.query("""
        SELECT team_name, league_position, points, matches_played
        FROM league_standings
        ORDER BY league_position
    """).to_df()
    
    top_6 = standings[standings['league_position'] <= 6]['team_name'].tolist()
    relegation = standings[standings['league_position'] > 17]['team_name'].tolist()
    
    return f"""
CURRENT LEAGUE STANDINGS (Matchday X):

Top 6 (European qualification): {', '.join(top_6)}
Relegation zone (bottom 3): {', '.join(relegation)}

When the user mentions "top 6" or "big teams", they refer to: {', '.join(top_6)}
When the user mentions "relegation zone" or "bottom teams", they refer to: {', '.join(relegation)}
"""
```

**Called Once Per Session:**
- `pages/basic_stats.py` initialization → fetch standings
- Inject into every system prompt (no per-query refresh for MVP)

---

### Layer 4: Function Calling Layer (ENHANCED)

**Responsibility:** Provide tools for structured query; validate parameters

**Communicates With:** Conversation Memory (extracts context), Query Engine (passes clean parameters)

**Tool Definitions (Claude API format):**

```json
{
  "tools": [
    {
      "name": "query_player_stats",
      "description": "Get statistics for a specific player",
      "input_schema": {
        "type": "object",
        "properties": {
          "player_name": {
            "type": "string",
            "description": "Full or partial player name (e.g., 'Haaland', 'E. Haaland')"
          },
          "metric": {
            "type": "string",
            "enum": ["total_goals", "total_assists", "xg_total", "pass_accuracy_pct", ...],
            "description": "Which statistic to retrieve"
          },
          "filters": {
            "type": "object",
            "properties": {
              "opponent_filter": {
                "type": "string",
                "description": "Optional: 'vs Arsenal', 'vs top 6', 'vs relegation zone', or null for all"
              },
              "time_window": {
                "type": "string",
                "description": "Optional: 'season', 'last 5 rounds', or null for full season"
              },
              "position_filter": {
                "type": "string",
                "description": "Optional: 'midfielder', 'defender', or null for all"
              }
            }
          }
        },
        "required": ["player_name", "metric"]
      }
    },
    {
      "name": "compare_entities",
      "description": "Compare two players or teams on the same metric",
      "input_schema": { ... }
    },
    {
      "name": "rank_by_metric",
      "description": "Rank all players/teams by a metric",
      "input_schema": { ... }
    }
  ]
}
```

**Parameter Validation (Python):**

```python
def validate_and_execute_tool(tool_name: str, tool_params: dict) -> dict:
    if tool_name == "query_player_stats":
        player_name = tool_params["player_name"]
        metric = tool_params["metric"]
        filters = tool_params.get("filters", {})
        
        # Validate player exists
        if not player_exists(player_name):
            return {
                "error": f"Player '{player_name}' not found",
                "suggestion": suggest_player(player_name)  # Fuzzy match
            }
        
        # Validate metric
        if metric not in valid_metrics:
            return {
                "error": f"Metric '{metric}' not found",
                "valid_metrics": list_valid_metrics()
            }
        
        # Validate filters
        if filters.get("opponent_filter") and not team_exists(filters["opponent_filter"]):
            return {
                "error": f"Team/grouping '{filters['opponent_filter']}' not found"
            }
        
        # Execute
        result = execute_query_player_stats(player_name, metric, filters)
        return {"rows": result, "metric": metric, "context_label": f"{filters}"}
    
    # ... other tools
```

**LLM Tool Selection Example:**

```
User: "How many goals has Haaland scored against top 6?"

LLM thinks:
1. Entity: Haaland (player)
2. Metric: total_goals
3. Filter: opponent_filter = "vs top 6"
4. Tool: query_player_stats

LLM response:
{
  "tool_name": "query_player_stats",
  "tool_input": {
    "player_name": "Haaland",
    "metric": "total_goals",
    "filters": {
      "opponent_filter": "vs top 6"
    }
  }
}
```

---

### Layer 5: Query Engine Layer (MINIMAL CHANGE)

**Responsibility:** Translate validated tool parameters into DuckDB queries; return structured results

**Communicates With:** Function Calling (receives validated params), Data Execution (dispatches to DuckDB)

**Example Implementation:**

```python
class LLMQueryEngineV2Enhanced:
    def execute_tool_call(self, tool_name: str, tool_params: dict) -> dict:
        """Execute tool call by delegating to DuckDB."""
        
        if tool_name == "query_player_stats":
            player_name = tool_params["player_name"]
            metric = tool_params["metric"]
            filters = tool_params.get("filters", {})
            
            # Build DuckDB query
            query = self._build_player_query(player_name, metric, filters)
            
            # Execute
            result_df = duckdb.query(query).to_df()
            
            # Return structured result
            return {
                "rows": result_df.to_dicts(),
                "metric": metric,
                "context_label": self._format_context(filters),
                "answer_type": "entity_value"
            }
    
    def _build_player_query(self, player_name: str, metric: str, filters: dict) -> str:
        """Build DuckDB SQL for player stats query."""
        # Reuse existing query_planner logic; just cleaner inputs
        # (No more regex parsing — parameters are already validated)
```

**No Changes to Core SQL Logic:**
- Existing `duckdb_manager.py` queries remain untouched
- Only the input → query mapping is simplified (cleaner parameters)

---

### Layer 6: Data Execution Layer (MINIMAL ADDITION)

**Responsibility:** Persist and retrieve data; provide views for querying

**Communicates With:** Query Engine

**New: League Standings View**

```sql
CREATE VIEW league_standings AS
SELECT 
  team_name,
  league_position,
  points,
  matches_played,
  goals_for,
  goals_against
FROM (
  SELECT 
    team_name,
    ROW_NUMBER() OVER (ORDER BY points DESC, goal_difference DESC) as league_position,
    points,
    matches_played,
    goals_for,
    goals_against
  FROM team_stats
)
ORDER BY league_position;
```

**Existing Views (Unchanged):**
- `player_stats`
- `team_stats`
- `match_results`
- `event_log`

---

### Layer 7: Verbalization Layer (ENHANCED WITH TEMPLATES)

**Responsibility:** Transform raw rows + metadata into natural prose

**Communicates With:** Data Execution (receives rows), Interface (returns prose)

**Enhancements:**

1. **Metric Templates** (YAML)
```yaml
metric_templates:
  total_goals:
    singular: "{entity} has scored {value} goal"
    plural: "{entity} has scored {value} goals"
    
  total_goals_p90:
    template: "{entity} scores {value:.2f} goals per 90 minutes"
```

2. **Contextual Frames** (YAML)
```yaml
contextual_frames:
  vs_opponent:
    template: "Against {opponent}, {entity} has {metric} {value}."
    insight: "{comparison_to_rest}"
```

3. **Insight Rules** (Python)
```python
def evaluate_goals_vs_xg(goals: float, xg: float) -> str:
    ratio = goals / xg if xg > 0 else 1.0
    if ratio >= 1.15:
        return "finishing well above expectation"
    # ...
```

**LLM Integration:**
```python
def verbalize_result(query_result: dict, conversation_context: dict) -> str:
    metric = query_result["metric"]
    rows = query_result["rows"]
    
    # Load templates
    metric_template = load_metric_template(metric)
    contextual_frame = load_contextual_frame(query_result.get("context_type"))
    
    # Build system prompt with templates
    system = build_verbalization_prompt(metric_template, contextual_frame)
    
    # Call LLM to fill template + add insight
    prose = llm_call(
        system_prompt=system,
        user_message=f"Verbalize these results: {json.dumps(rows)}",
        max_tokens=150
    )
    
    return prose
```

---

## Data Flow Example: Multi-Turn Follow-Up

**Turn 1:**
```
User: "How many goals has Haaland scored?"

1. Conversation Interface → extracts entity (Haaland)
2. Conversation Memory → stores entity_focus = {type: "player", name: "Haaland"}
3. Function Calling → LLM selects query_player_stats(Haaland, total_goals)
4. Query Engine → builds query, executes
5. DuckDB → returns [{"player": "E. Haaland", "total_goals": 6}]
6. Verbalization → "Haaland has scored 6 goals this season."
7. Conversation Memory → stores recent_result = {metric: "total_goals", value: 6}
8. Interface → displays response, updates session_state
```

**Turn 2:**
```
User: "But against top 6?"

1. Conversation Interface → parses "against top 6" as opponent_filter update
2. Conversation Memory → updates active_filters = {opponent_filter: "vs top 6"}
3. Function Calling → LLM sees context + league_context
   → selects query_player_stats(Haaland, total_goals, filters={opponent_filter: "vs top 6"})
   (LLM infers: keep entity Haaland, keep metric total_goals, add opponent filter)
4. Query Engine → builds query with opponent filter
5. DuckDB → returns [{"player": "E. Haaland", "total_goals": 1}]
6. Verbalization → "Against the top 6, Haaland has scored 1 goal."
7. Conversation Memory → appends recent_result
8. Interface → displays response
```

**Turn 3:**
```
User: "Is that more than the rest?"

1. Conversation Interface → parses "rest" as comparison marker
2. Conversation Memory → infers: compare (1 goal vs top 6) to (6 - 1 = 5 goals vs rest)
3. Function Calling → LLM selects compare_entities(Haaland, total_goals, 
                      opponent_filter1: "vs top 6", opponent_filter2: "vs rest")
   (LLM reasons from context: I need to compare the same metric across bucket splits)
4. Query Engine → builds two parallel queries (vs top 6, vs rest)
5. DuckDB → returns comparison rows
6. Verbalization → "No, Haaland has 5 goals against non-top-6 teams, more than his 1 goal against the top 6."
7. Conversation Memory → updates active_filters to reflect dual-bucket context
```

---

## Patterns to Follow

### Pattern 1: Tool Selection by Intent

**When LLM should select each tool:**
- `query_player_stats`: "Who", "How many", "Show me X's Y"
- `query_team_stats`: "Which team", "Show me Arsenal's"
- `compare_entities`: "vs", "against", "compared to", "more than", "less than"
- `rank_by_metric`: "Top 10", "Top scorer", "Ranking", "Leaderboard"
- `temporal_analysis`: "Trend", "Over time", "This week vs last week"

### Pattern 2: Filter Carry-Forward

When user doesn't specify a filter, carry forward from prior turn:
```
Turn 1: "How many goals has Haaland scored against Arsenal?"
        → active_filters = {opponent_filter: "vs Arsenal"}

Turn 2: "What about assists?"
        → Carry forward opponent_filter (still vs Arsenal)
        → query_player_stats(Haaland, total_assists, filters={opponent_filter: "vs Arsenal"})
```

### Pattern 3: Metric Variant Inference

When user asks for "per 90" or related variant:
```
Turn 1: "How many goals?"
        → primary_metric = "total_goals"

Turn 2: "What about per 90?"
        → Infer: keep total_goals, apply p90 variant
        → query_player_stats(Haaland, total_goals_p90)
        → Update primary_metric to still be "total_goals" (variant is temporary)
```

### Pattern 4: Entity Switch Detection

When user explicitly switches entity:
```
Turn 2: "What about Kane?"
        → Detect: "about Kane" = new entity
        → Reset active_filters to defaults
        → Update entity_focus = {type: "player", name: "Kane"}
        → Don't carry filters from Haaland context
```

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Hallucinated Context

**What goes wrong:** System infers a filter the user never mentioned.

**Example:**
```
User: "How many goals?"
Wrong: Assume opponent_filter="vs Arsenal" because Arsenal was mentioned in Turn 2
Right: opponent_filter=null (all opponents) unless explicitly re-mentioned
```

**Prevention:** Only infer from explicit user statements or prior results. If unsure, ask.

### Anti-Pattern 2: Silent Parameter Injection

**What goes wrong:** Tool fills in missing parameters without telling LLM what happened.

**Example:**
```
Tool call: query_player_stats(Haaland, total_goals, opponent_filter="vs top 6")
LLM doesn't know the opponent_filter was inferred from context, thinks it's the user's explicit request
Result: LLM might re-ask "Which team?" even though the tool already filtered
```

**Prevention:** Return tool output that explicitly states what filters were applied:
```python
{
  "rows": [...],
  "metric": "total_goals",
  "context_label": "against the top 6",  # Make explicit
  "applied_filters": {opponent_filter: "vs top 6"}  # Show what was used
}
```

### Anti-Pattern 3: Context Explosion

**What goes wrong:** Conversation context grows unbounded; context window fills with noise.

**Example:**
```
After 50 turns, conversation_context has:
- 50 entries in conversation_history (most irrelevant)
- 50 entries in recent_results (user rarely references old ones)
Result: System message is 80% conversation history, 20% actual instructions
```

**Prevention:** Implement projection rules:
- Keep full message history (LLM can search it)
- Keep only 2–3 most recent results in context
- Drop old context if context window exceeds 70%

---

## Scalability Considerations

| Concern | At 10 Turns | At 50 Turns | At 100 Turns | Solution |
|---------|------------|------------|-------------|----------|
| Context window growth | ~2KB | ~8KB | ~15KB | Summarize old turns; keep metadata only |
| Result cache size | 30–50 rows | 150–250 rows | 300+ rows | Keep only 2–3 recent results; discard old |
| LLM reasoning time | <1s | <2s | ~3s | Likely acceptable; monitor latency |
| Session state memory | <1MB | <5MB | <10MB | No issue for single session; problem if 1000+ users |

For v3.0+ (multi-user API):
- Move session state to PostgreSQL
- Implement async query execution
- Add caching layer for frequent queries

---

## Sources

| Source | Type | Confidence |
|--------|------|------------|
| Existing codebase architecture | Codebase | HIGH |
| Agents Foundations Lesson 6 & 10 | Training material | HIGH |
| Query planner design patterns | Codebase | HIGH |
| DuckDB view design | Codebase | HIGH |

