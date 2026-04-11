# Feature Landscape: Basic Stats Analyst v2.0

**Domain:** Football statistics LLM analyst with function calling, conversation memory, league context, and NLP polish
**Researched:** 2026-04-12
**Confidence Overall:** MEDIUM (training + lesson materials + existing codebase patterns; no live ecosystem data due to access restrictions)

---

## Executive Summary

The v2.0 milestone adds four critical features to mature the existing 1.0 pipeline (which validates 61/61 benchmark questions):

1. **Function Calling** replaces regex-based canonicalization with typed Python tools — the LLM selects tool functions rather than human regex rules deciding query structure
2. **Conversation Memory** persists query context across turns — "How many goals has Haaland scored?" → "But against top 6?" requires tracking previous query filters
3. **League Context Injection** provides dynamic team classification — "top 6" and "relegation zone" emerge from league description rather than hardcoded lists
4. **NLP Polish** transforms robotic output ("E. Haaland scored 6 goals 3.44 xG") into natural prose ("Haaland has scored 6 goals with an xG of 3.44, finishing slightly above expectation")

These features move the product from isolated Q&A to conversational interaction, while maintaining the core groundedness guarantee (no invented facts).

---

## Function Calling — Table Stakes + Patterns

### What Users Expect (Table Stakes)

**Deterministic output:** LLM selects from pre-defined tools, not unreliable regex or prompt injection. Users expect stable query interpretation even as questions vary.

**Clear schema:** Each tool has explicit parameters — `player_name`, `metric`, `time_window`, `opponent_filter` — no ambiguity about what the LLM can request.

**Fallback handling:** If the LLM misuses a tool (requests non-existent metric, illegal parameter combo), the system recovers gracefully without hallucinating.

**Transparent reasoning:** Debug output shows which tool was selected and why, enabling users to understand system decisions.

### Production Patterns (from Agents Foundations Lesson 6 & codebase)

#### Tool Granularity: Flexible Parameterized > One Tool Per Query Type

**Recommended approach:** 3–5 flexible tools with rich parameters rather than 20+ narrow tools.

Example set for football stats:
- `query_player_stats(player_name, metric, filters={time_window, opponent_filter, position_filter})`
- `query_team_stats(team_name, metric, filters={...})`
- `compare_entities(entity_a, entity_b, metric, filters={...})`
- `rank_by_metric(metric, position=null, filters={...}, top_n=10)`
- `temporal_analysis(entity, metric, granularity='round|matchday|season', filters={...})`

**Why:** Narrow tools (one per query type) scale poorly — 20 tools for 20 query patterns become unmaintainable. Flexible tools let the LLM compose behavior. The existing `LLMQueryEngineV2` already identifies `table_scope` (player, team, match) and `metric`, so mapping to 3–4 tools is natural.

**Constraint:** Tools must be mutually exclusive and clearly scoped. `query_player_stats` does not accept team_name; ambiguity creates LLM confusion.

#### Parameter Design

**Required fields:** player_name, metric (or team_name + metric). These define what data to fetch.

**Optional/conditional fields:**
- `time_window`: "last 5 rounds", "matchdays 10–15", "season", null=season default
- `opponent_filter`: "vs Arsenal", "vs top 6", "vs relegation zone", null=all opponents
- `position_filter`: "midfielder", "defender", null=all positions
- `top_n`: for ranking queries (default 1, max 20)
- `comparison_type`: for dual-bucket queries ("vs rest of league", "home vs away")

**Validation:** LLM parameter validation is fragile. Pre-validate in Python:
```python
def query_player_stats(player_name: str, metric: str, filters: dict) -> dict:
    # Validate player exists
    if player_name not in valid_players:
        return {"error": f"Player '{player_name}' not found", "suggestion": did_you_mean(player_name)}
    
    # Validate metric exists
    if metric not in valid_metrics:
        return {"error": f"Metric '{metric}' not found", "valid": list_metrics()}
    
    # Validate filters
    if filters.get("opponent_filter") and filters["opponent_filter"] not in valid_opponents:
        return {"error": f"Team '{filters['opponent_filter']}' not found"}
    
    # Execute and return
    return execute_duckdb_query(...)
```

Returning error objects (not raising exceptions) keeps the LLM in the loop for recovery.

#### Tool Selection Flow

**Existing pattern in `query_planner.py`:**
1. LLM analyzes question → identifies intent (top scorer, comparison, temporal)
2. Planner maps to query structure (table scope, metric, filters)
3. `LLMQueryEngineV2` dispatches to DuckDBManager

**v2.0 transition:**
1. LLM sees tool definitions in system prompt
2. LLM analyzes question → selects tool(s) and parameters
3. Python validates and executes tool
4. LLM sees tool output → generates verbalization

**Key difference:** The LLM now directly selects tools instead of planner doing it. This requires:
- **Rich tool descriptions:** "Use `compare_entities` when the user asks 'vs', 'against', 'compared to', or 'which is better'."
- **Example tool calls in system prompt:** Show 2–3 correct examples per tool so the LLM learns the expected parameter format.
- **Tool schemas as OpenAI/Claude function_calling format:** Structured JSON schema, not free-form text.

### Complexity Notes

**Low risk:** Mapping existing query planner decisions to tool selection (LLM already does the hard part).
**Medium risk:** Validating LLM parameter choices without silent failures (requires robust error handling).
**High risk:** Supporting multi-step workflows ("What about per 90?" after a tool call) — this bleeds into conversation memory.

### Dependencies on Existing Pipeline

- Builds directly on `query_planner.py` intent identification (reuse metric resolution, intent routing)
- Replaces regex canonicalization with LLM function selection (reduces brittleness)
- Feeds into existing `duckdb_manager.py` and `verbalize.yaml` pipeline (no breaking changes)
- Requires conversation history projection (conversation memory, below)

---

## Conversation Memory — What State to Track

### Table Stakes for Follow-Up Questions

Users expect multi-turn continuity:
```
Q1: "How many goals has Haaland scored?"
   → A1: "Haaland has scored 6 goals this season."

Q2: "But against top 6?"
   → A2: "Against the top 6, Haaland has scored 1 goal."
   [System must infer: keep metric (goals), switch opponent filter (→ "top 6")]

Q3: "Is that more than the rest?"
   → A3: "Against non-top 6 teams, Haaland has scored 5 goals, more than his top 6 tally."
   [System must infer: compare goal count top6 vs rest]

Q4: "What about per 90?"
   → A4: "Per 90 minutes, that's 0.08 xG against top 6 vs X against the rest."
   [System must infer: normalize previous metrics to p90, maintain opponent buckets]
```

Each turn refers to prior context. The LLM must have access to:

#### Short-Term Memory Fields (Session-Level, In Context Window)

**Conversation history:** Full chat transcript from this session.
- Why: LLM needs to understand the narrative (Q3 refers to Q2 result)
- Format: List of {role: "user"|"assistant", content: "..."}
- Projection strategy: Keep full history (context window is large); drop oldest turns only if approaching limit

**Current entity focus:** Which player/team are we discussing?
- Why: "Is that more?" refers back to the entity mentioned in Q1/Q2
- Format: `{entity_type: "player"|"team", name: "Haaland", position: 8}` (position for easy reference in history)
- Update rule: Any new player/team mention → overwrite; explicit entity switch ("what about X?") → update

**Current metric context:** Which metric(s) are active?
- Why: "What about per 90?" assumes we're still talking about goals, just normalized
- Format: `{primary_metric: "total_goals", variants: ["total_goals", "total_goals_p90"], last_used: "total_goals"}`
- Update rule: New metric mention → primary_metric changes; variants auto-populate from valid p90/contextual aliases

**Active filters:** Opponent, time window, position, competition context
- Why: "Against top 6?" adds opponent_filter; "What about last 3 rounds?" adds time_window
- Format: `{opponent_filter: null|"vs Arsenal"|"vs top 6", time_window: "season"|"last 3 rounds", position_filter: null}`
- Update rule: Explicit mention → set; no mention → carry forward from previous turn (unless new entity switches context)

**Last query result:** Top 1–3 rows from the previous query
- Why: User might say "How much is that?" or "Compare to Y" — need to reference previous numbers
- Format: `{rows: [{player: "Haaland", total_goals: 6, ...}], metric: "total_goals", context: "season"}`
- Retention: Keep most recent 2–3 queries for chained comparisons

#### Long-Term Memory Fields (Optional for MVP, Design for Later)

**Episodic:** "On turn 5, user asked about Haaland's goals vs top 6 (result: 1 goal)"
- Use case: Answer "How many goals did Haaland score against top 6 again?" hours later
- Storage: Vector DB (e.g., Chroma) with summary embeddings
- Projection: Retrieve relevant episodes into context window if user asks about past results

**Semantic:** "User prefers Haaland stats in xG context", "User often compares home vs away"
- Use case: Anticipate context (offer p90 proactively, suggest comparisons)
- Storage: Structured JSON in external DB
- Projection: Inject into system prompt as user preferences

### State Projection Strategy

**In context window:** Full conversation history + current entity/metric/filters (keep compressed, ~2KB)

**Example state projection (Claude API format):**
```json
{
  "conversation_context": {
    "entity_focus": {"type": "player", "name": "E. Haaland"},
    "active_filters": {
      "opponent": "vs top 6",
      "time_window": "season"
    },
    "recent_results": [
      {
        "turn": 2,
        "metric": "total_goals",
        "value": 1,
        "context": "vs top 6 teams"
      }
    ]
  },
  "messages": [
    {"role": "user", "content": "How many goals has Haaland scored?"},
    {"role": "assistant", "content": "Haaland has scored 6 goals this season."},
    {"role": "user", "content": "But against top 6?"},
    {"role": "assistant", "content": "Against the top 6, Haaland has scored 1 goal."},
    ...
  ]
}
```

When the user asks Q4 ("What about per 90?"), the LLM can reason:
- "The entity is still Haaland (from context)"
- "The opponent filter is still vs top 6 (from active_filters)"
- "The primary metric should be total_goals, but the user asked for per 90, so I select total_goals_p90"
- "I'll call `query_player_stats(Haaland, total_goals_p90, opponent_filter='vs top 6')`"

### Implementation

**Session storage (Streamlit):** Use `st.session_state` to hold conversation_context as a dict. Update after each LLM response.

```python
# In pages/basic_stats.py
def update_conversation_context(user_input, llm_response, query_result):
    if "conversation_context" not in st.session_state:
        st.session_state.conversation_context = {
            "entity_focus": None,
            "active_filters": {},
            "recent_results": []
        }
    
    ctx = st.session_state.conversation_context
    
    # Extract entity from query result (or LLM inference)
    if query_result and "player" in query_result.get("rows", [{}])[0]:
        ctx["entity_focus"] = {
            "type": "player",
            "name": query_result["rows"][0]["player"]
        }
    
    # Extract filters from LLM reasoning or hardcoded
    # (Next section: how LLM infers filter updates)
    
    # Store recent result
    ctx["recent_results"].append({
        "turn": len(st.session_state.messages),
        "metric": query_result.get("metric"),
        "value": query_result["rows"][0].get(metric) if query_result["rows"] else None,
        "context": query_result.get("context_label")
    })
```

**Projection into system prompt:** Add conversation_context as JSON in the system message.

### Complexity Notes

**Low:** Storing and projecting conversation history (standard pattern in ChatGPT, Sonnet memory)
**Medium:** Automatically inferring filter updates from user input ("Against top 6" must be parsed as opponent_filter update)
**Medium-High:** Resolving ambiguous refer-backs ("Is that more?") — requires robust entity/metric linking
**High:** Long-term memory (episodic/semantic) — adds complexity without immediate ROI for MVP

### Dependencies

- Requires function calling (tools emit structured query metadata for filter extraction)
- Requires LLM context window large enough to hold ~5–10 turns + state (~4–8K tokens)
- Integrates with existing Streamlit session_state pattern (no new infrastructure)

---

## League Context — Injection Approaches

### What Users Expect (Table Stakes)

When the user asks "How do top 6 players compare to the rest?", the system must know:
- Which teams are in "top 6"? (Arsenal, Man City, Liverpool, Aston Villa, Chelsea, Man United based on current league standings)
- How is "top 6" defined? (By league position, not hardcoded)
- Can the system generalize? ("relegation zone" → bottom 3, "European spots" → top 4)

This must be **dynamic** (reflect current league state) and **injectable** (LLM can reason about it without hardcoding).

### Production Patterns

#### Approach 1: System Prompt Injection (Recommended for MVP)

**Mechanism:** Provide league description paragraph at the top of the system prompt, before each query.

```
System Prompt (before user query):

You are a football data analyst for the English Premier League.

Current League Context:
The league consists of 20 teams. The standings snapshot (as of Matchday 25) are:
- Top 6 (European qualification): Arsenal (48pts), Man City (47pts), Liverpool (46pts), Aston Villa (44pts), Chelsea (43pts), Man United (41pts)
- Mid-table (7–14): Nottingham (38pts), Fulham (36pts), Brighton (33pts), Brentford (31pts), Wolves (29pts), Newcastle (28pts), Bournemouth (25pts), West Ham (24pts)
- Lower (15–20): Everton (22pts), Southampton (20pts), Luton (18pts), Leicester (15pts), Ipswich (10pts), Palace (8pts)
- Relegation zone (bottom 3): Sheffield (6pts), Forest (5pts), Bolton (4pts)

Use these groupings to interpret user questions like "vs top 6", "against relegation teams", etc.
```

**Pros:**
- Simple: No changes to DuckDB queries or tool definitions
- Transparent: Users see the context if they ask for debug output
- Fast: One extra API call per session (fetch standings), then reuse for all queries
- Flexible: LLM can infer "top 4" (European spots), "big 6" (top 6 by tradition), "mid-table", etc.

**Cons:**
- Not fully dynamic: Standings refresh per session, not per query (acceptable for MVP; add per-query refresh later)
- LLM must parse English description (low risk for modern models, but not structured)

#### Approach 2: Structured Tool Parameter

**Mechanism:** Add `league_context` parameter to tools; LLM selects the relevant grouping.

```python
def query_player_stats(
    player_name: str,
    metric: str,
    filters: dict = None,
    league_context: str = None  # "top_6", "relegation_zone", "mid_table", "big_6", None
) -> dict:
    # If league_context="top_6", auto-populate opponent_filter with current top 6
    if league_context:
        context_mapping = {
            "top_6": get_top_6_teams(),
            "relegation_zone": get_bottom_3_teams(),
            "mid_table": get_mid_table_teams(),
        }
        filters = filters or {}
        filters["opponent_filter"] = context_mapping.get(league_context)
    
    return execute_query(...)
```

**Pros:**
- Structured: LLM selects from a fixed enum (less hallucination)
- Composable: Can combine league_context with time_window, position_filter, etc.
- Auditable: Debug output shows exactly which context was applied

**Cons:**
- Requires tool schema update (moderate change to function_calling interface)
- Hardcodes groupings in Python (less flexible than LLM reasoning)

#### Approach 3: Dynamic Retrieval (Best for Future Scaling)

**Mechanism:** Query a standings database on each call; let the LLM fetch context as needed.

```python
def get_league_context(grouping: str = None) -> dict:
    """Fetch current league standings, optionally filtered by grouping."""
    standings = duckdb_query("SELECT team_name, points, league_position FROM league_standings ORDER BY league_position")
    
    if grouping == "top_6":
        return standings[:6]
    elif grouping == "relegation_zone":
        return standings[-3:]
    else:
        return standings  # Full standings
```

Expose as a tool: `get_league_context(grouping: "top_6" | "relegation_zone" | null)`

**Pros:**
- Fully dynamic: Latest standings fetched on-demand
- Composable: User can ask "Show me the top 6 this week" and get fresh data
- Generalizable: Easily extends to other sports/leagues

**Cons:**
- Requires LLM to call tool before querying player stats (adds latency, extra API call)
- More complex orchestration (multi-step tool use)

### Recommendation for v2.0 MVP

**Use Approach 1 (System Prompt Injection) for Phase 1:**
- Fetch standings snapshot once per session
- Inject into system prompt as English text
- Let LLM reason naturally about "top 6 teams are ..."
- Low implementation cost (one function to format standings, one system prompt template)

**Plan Approach 2 (Tool Parameter) for Phase 2 if:**
- LLM confusion with league context is observed (unlikely with modern models)
- Need more deterministic behavior for edge cases

**Plan Approach 3 (Dynamic Retrieval) for Phase 3+ if:**
- Users expect per-query freshness (e.g., "standings changed this week")
- Scaling to multiple leagues/seasons needed

### League Context Data Source

**Current state (from existing codebase):** Football data is in DuckDB/Parquet with player and team stats. **League standings are not explicitly stored.**

**Required fix:**
1. Extract team points/position from match results or hardcode for current season (1-time setup)
2. Store in DuckDB view: `league_standings(team_name, league_position, points, matches_played)`
3. Query on session start: `SELECT team_name, league_position, points FROM league_standings ORDER BY league_position`

### Complexity Notes

**Low:** System prompt injection (standard practice)
**Low-Medium:** Tool parameter approach (schema change, but straightforward)
**Medium:** Dynamic retrieval (requires tool orchestration, extra API calls)
**High:** Multi-season/multi-league context (requires historical standings tracking)

### Dependencies

- Requires league standings data (currently missing; needs 1–2 hour data engineering)
- Integrates with function calling (tool parameters or system prompt reasoning)
- Optional dependency on conversation memory (user might ask "Compare to last week's standings")

---

## NLP Polish — Natural Language Patterns

### What Users Expect (Table Stakes)

**Before (v1.0):**
```
"E. Haaland has scored 6 goals with 3.44 xG in the season."
```

**After (v2.0):**
```
"Haaland has scored 6 goals with an xG of 3.44. He's finishing well above expectation — converting more opportunities than predicted by his shot quality."
```

Users expect:
- **Readable names** (not "E. Haaland", not "Erling Haaland (Man City | Player ID 12345)")
- **Contextual framing** (not just the fact, but the "so what?")
- **Metric relationships** (xG vs goals tells a story: outperformance)
- **Natural phrasing** (no exposed internal metric names like `total_goals_p90`, `xg_total`)
- **Comparison anchoring** (6 goals among 8 scorers is different than 6 goals among 20)

### Production Patterns

#### Pattern 1: Metric Aliasing + Natural Templates

**Current state (from `verbalize.yaml`):** LLM is given metric_label as context:
```
metric_label: "Total Goals"
context_label: "this season"
```

LLM then generates prose manually. **This works but is fragile:**
- Relies on LLM staying grounded (prone to hallucination on edge cases)
- No consistent phrasing across similar queries

**Improvement:** Create **metric templates** that the LLM fills in:

```yaml
metric_templates:
  total_goals:
    singular: "{entity} has scored {value} goal"
    plural: "{entity} has scored {value} goals"
    comparative: "{entity} has scored {value} goals{context}, {comparison_insight}"
    
  total_goals_p90:
    singular: "{entity} scores {value:.2f} goals per 90 minutes"
    plural: null  # N/A
    comparative: "That's {comparison_direction} than {comparison_entity} ({comparison_value:.2f} per 90)"
  
  xg_total:
    singular: "{entity} has accumulated {value:.2f} expected goals (xG)"
    plural: null
    comparative: "{entity}'s xG of {value:.2f} suggests {insight}"

  goals_vs_xg_ratio:
    template: "{entity} has scored {goals} goals from {xg:.2f} xG, {performance}"
    performance_rules:
      - "ratio >= 1.15": "finishing well above expectation"
      - "1.05 <= ratio < 1.15": "finishing slightly above expectation"
      - "0.95 <= ratio < 1.05": "converting at expected rate"
      - "0.85 <= ratio < 0.95": "slightly underperforming xG"
      - "ratio < 0.85": "underperforming expected goals significantly"
```

**How LLM uses it:**
1. LLM identifies query type (top 1, ranking, comparison, entity_value)
2. LLM looks up metric_template for the metric
3. LLM fills in template variables: entity, value, context, comparison
4. LLM optionally adds insight (e.g., performance_rules evaluation)

**Output:**
```
"Haaland has scored 6 goals from 3.44 xG, finishing well above expectation. 
He's converting more opportunities than the underlying shot quality would suggest."
```

#### Pattern 2: Contextual Framing by Bucket Type

Different buckets warrant different framings:

**Opponent bucket (vs top 6, vs rest):**
```
Template: "{entity} has {metric} {value}{context}. Against {opponent}, that's {opponent_value}."
Insight: "{opponent_value} {comparison_direction} than {non_opponent_value}."
```

Example:
```
"Haaland has scored 6 goals this season. Against the top 6, that's 1 goal — 
showing a significant drop in output against elite defenses."
```

**Home/away bucket:**
```
Template: "{entity} has {metric} {value}. At home, {home_value}; away, {away_value}."
Insight: "{home_context} {home_away_insight}."
```

Example:
```
"Man City has scored 48 goals this season. At home, that's 28 goals (more prolific); 
away, 20 goals (more conservative approach)."
```

**Temporal bucket (rounds 1–10 vs 11–20):**
```
Template: "{entity} has {metric} {value}. In {period_1}, {period_1_value}; in {period_2}, {period_2_value}."
Insight: "{trend}: {growth_rate} more in the second half."
```

Example:
```
"Liverpool has scored 45 goals in the first 19 rounds. In rounds 1–10, they scored 20 goals; 
rounds 11–19, 25 goals — showing improvement and momentum."
```

#### Pattern 3: Ranking Context

When returning top N results, give scale context:

**Before:**
```
"Top 5 scorers: Salah (29), Haaland (23), Kane (21), Son (19), Watkins (18)"
```

**After:**
```
"Top 5 scorers (out of 251 outfield players): 
Salah leads with 29 goals, followed by Haaland (23), Kane (21), Son (19), and Watkins (18). 
The gap between #1 and #2 is 6 goals — a notable lead."
```

**Template:**
```yaml
ranking_context:
  template: "Top {top_n} {entity_plural} (out of {total_count}): {list}"
  leader_insight: "Lead: {leader} with {leader_value} — {margin_from_next} {margin_direction} than #{2}"
  gap_insight: "Average gap between ranks: {avg_gap:.1f} {metric}"
```

#### Pattern 4: Natural Metric Naming

**Internal metrics → User-facing labels:**

| Internal | User-Facing | Notes |
|----------|-------------|-------|
| `total_goals` | "goals" | plain |
| `total_goals_p90` | "goals per 90" | always with unit |
| `xg_total` | "expected goals (xG)" | expand acronym first mention |
| `pass_accuracy_pct` | "pass accuracy" | drop %, show as "76% of passes" |
| `aerial_duels_won_pct` | "aerial duel win rate" | more natural than %, show as "won 12 of 18 aerial duels" |
| `goals_vs_top6` | not exposed; inferred | never expose internal metric, use context |
| `shot_assists_vs_big6` | not exposed; inferred | never expose, use context |

**Rule:** Never expose internal metric names in verbalization. Always translate to natural football terminology.

#### Pattern 5: Uncertainty & Edge Cases

**What to do when:**

| Case | Pattern |
|------|---------|
| Player in data but 0 results in filter | "Haaland has not scored against the top 6 this season." (vs "0 goals") |
| Tie in ranking | "{player1} and {player2} are tied with {value} {metric}, both leading the league." |
| Insufficient data (< 3 games) | "Haaland has played only 2 games, so the per-90 stats are not yet reliable." |
| Metric not available for entity | "Saves are only tracked for goalkeepers. {player} is a {position}." |

### Implementation

**Phase 1 (MVP):** Expand `verbalize.yaml` to include metric templates and context frames.

```yaml
# utils/basic_stats/prompts/verbalize.yaml (updated)
system: |
  You are a football data analyst.
  Use the metric_templates below to generate natural-language answers.
  Never expose internal metric names.
  Frame results with context: compare to teammates, show performance level (top 10%, mid-tier, etc.), explain "so what?".

metric_templates:
  total_goals: ...
  xg_total: ...
  # ... (as above)

contextual_framings:
  vs_opponent: ...
  home_away: ...
  # ... (as above)

user: |
  <question>
  {question}
  </question>
  
  <answer_type>
  {answer_type}
  </answer_type>
  
  <metric>
  {metric}
  </metric>
  
  <context>
  {context_label}
  </context>
  
  <data>
  {rows}
  </data>
  
  <metric_template>
  {metric_template_for_metric}
  </metric_template>
  
  <contextual_framing>
  {contextual_framing_if_applicable}
  </contextual_framing>
  
  <instructions>
  Use the metric_template to structure the answer.
  Apply the contextual_framing if provided.
  Never repeat the question.
  Always include the exact value from the data.
  Add insight where applicable (e.g., performance evaluation, trend, comparison).
  </instructions>
```

**Phase 2:** Automate insight generation for specific metric pairs (e.g., goals vs xG ratio).

```python
# utils/basic_stats/core/insights.py
def evaluate_goals_vs_xg_insight(goals: float, xg: float) -> str:
    ratio = goals / xg if xg > 0 else 1.0
    if ratio >= 1.15:
        return "finishing well above expectation"
    elif 1.05 <= ratio < 1.15:
        return "finishing slightly above expectation"
    # ... etc
    
    return ""
```

### Complexity Notes

**Low:** Metric aliasing and natural naming (lookup table, no LLM changes)
**Low-Medium:** Simple contextual framing (template filling, straightforward LLM instruction)
**Medium:** Insight generation for metric pairs (requires computation, but deterministic rules)
**Medium-High:** Ranking context and scale framing (requires aggregate stats, slightly more complex)

### Dependencies

- Requires accurate metric labels (from `resolve_metric.yaml`)
- Requires contextual metadata from query result (context_label, bucket_type, total_count)
- Integrates with existing `verbalize.yaml` pipeline (extension, not replacement)
- Optional: Requires insight rules for specific metric combinations

---

## Complexity & Effort Notes

### By Feature & Phase

| Feature | Phase | Complexity | Effort (Dev + Test) | Dependencies | Risk |
|---------|-------|-----------|-------------------|--------------|------|
| Function Calling | 1 | Medium | 3–4 days | Existing planner, DuckDB | Low (no planner change needed) |
| Conversation Memory | 2 | Medium | 3–4 days | Function calling, session_state | Low (isolated to session layer) |
| League Context (Approach 1) | 2 | Low | 1–2 days | Data source (standings table) | Low (system prompt, no logic change) |
| NLP Polish (Phase 1) | 1–2 | Low-Medium | 2–3 days | verbalize.yaml, prompts | Low (template-based, no core change) |
| Long-term Memory | 3+ | High | 5–7 days | Vector DB, episodic storage | Medium (new infrastructure) |

### Critical Path for v2.0

**Mandatory (MVP):**
1. Function calling (required for tool-based architecture in v2)
2. Conversation memory (required for follow-up questions)
3. NLP polish Phase 1 (required for product quality)
4. League context (low effort, high UX value)

**Optional (v2.1+):**
- Long-term memory (episodic/semantic)
- Advanced insights (multi-metric correlations)
- Dynamic league context per query (Approach 3)

### Data Engineering Dependency

**Blocker:** League standings table not currently in DuckDB.

**Fix required (1–2 hours):**
1. Extract team points/position from match results or hardcode for 2024–25 season
2. Create DuckDB view: `CREATE VIEW league_standings AS SELECT team_name, position, points FROM ...`
3. Add to `duckdb_manager.py` initialization

---

## Feature Dependencies Map

```
Function Calling ← Query Planner (existing), LLM tool selection
    ↓
Conversation Memory ← Session state, context projection
    ↓
Follow-Up Questions ← Entity/metric/filter inference from memory
    ↓
League Context ← Standings data, system prompt injection
    ↓
NLP Polish ← Metric templates, contextual frames
    ↓
↓
Table Stakes Achieved: Natural conversation about football stats with follow-ups and context awareness
```

---

## Anti-Features (What Not to Build)

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Predictive stats (e.g., "Who will score next?") | Outside grounded data scope | Answer only historical/current season stats |
| Multi-language conversation switching mid-turn | Adds complexity; users choose language at start | Support Spanish + English per session, not mixed |
| Autonomous memory updates without user review | Risk of false positives | Keep memory updates explicit (user confirms context) |
| Hardcoded "smart suggestions" (e.g., "You might also like...") | Hallucination risk | Only suggest follow-ups if explicitly asked |
| Real-time league updates per query | Adds latency without clear ROI | Refresh standings per session, not per query |

---

## Confidence Assessment

| Area | Confidence | Reason |
|------|------------|--------|
| Function Calling Patterns | MEDIUM | Training + Lesson 6; no live ecosystem data; patterns inferred from codebase planner design |
| Conversation Memory State | MEDIUM | Lesson 10 + memory.md provide architecture; football-specific fields inferred from benchmark |
| League Context Injection | MEDIUM-HIGH | System prompt approach is standard (ChatGPT, Claude); standings data availability not verified |
| NLP Polish | MEDIUM | Templates inferred from existing verbalize.yaml; metric relationships require domain validation |
| Overall | MEDIUM | No access to live production data; research grounded in training + existing codebase patterns |

---

## Gaps to Address in Phase-Specific Research

- **Data modeling:** How to store/query league standings by matchday (for temporal context)
- **Tool error handling:** Exact format for returning errors vs results to LLM
- **Context projection limits:** At what conversation length should old turns be summarized?
- **Metric inference logic:** Rules for "assume same metric if not mentioned" vs "require explicit metric"
- **Football domain specifics:** Valid team groupings per league (top 6 vs top 4 vs European spots)

---

## Sources

| Source | Type | Confidence |
|--------|------|------------|
| Agents Foundations Lesson 6: Tools | Training material | HIGH |
| Agents Foundations Lesson 10: Memory | Training material | HIGH |
| /Users/ricardoheredia/Twelve-GPT-Educational/.planning/PROJECT.md | Project doc | HIGH |
| /Users/ricardoheredia/Twelve-GPT-Educational/utils/basic_stats/core/ | Codebase | HIGH |
| /Users/ricardoheredia/Twelve-GPT-Educational/questions_benchmark_v4.json | Validated data | HIGH |
| /Users/ricardoheredia/Twelve-GPT-Educational/utils/basic_stats/prompts/verbalize.yaml | Existing pattern | HIGH |

