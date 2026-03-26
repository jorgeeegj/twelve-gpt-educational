# Architecture

**Analysis Date:** 2026-03-26

## Pattern Overview

**Overall:** Multi-layered data-driven chatbot framework with Streamlit frontend, built for natural language querying of sports analytics data.

**Key Characteristics:**
- Chat-centric UX: Multiple specialized chat interfaces (PlayerChat, WVSChat, PersonChat) backed by data
- LLM-agnostic: Pluggable backend supporting OpenAI, Azure OpenAI, and Google Gemini
- Data-first architecture: DuckDB for analytical queries, Parquet for summary data, embeddings for semantic search
- Domain-specific tooling: Query planning, metric resolution, structured data retrieval, and LLM-driven verbalization
- Session-state management: Streamlit's native session_state for conversation persistence

## Layers

**Presentation Layer:**
- Purpose: Render Streamlit UI components, manage chat display, handle user input
- Location: `pages/`, `app.py`, `utils/page_components.py`
- Contains: Streamlit page definitions, chat message rendering, form inputs, sidebar navigation
- Depends on: `classes.chat` (Chat, PlayerChat, WVSChat, PersonChat)
- Used by: End users via web browser

**Chat/Orchestration Layer:**
- Purpose: Coordinate conversation flow, manage message history, route queries to appropriate handlers
- Location: `classes/chat.py`
- Contains: Base Chat class with instruction_messages(), get_relevant_info(), handle_input(), display_messages()
- Depends on: LLM clients (OpenAI, Gemini), embeddings, descriptions, visuals
- Used by: Page layers to handle user interactions

**Data Retrieval & Semantic Layer:**
- Purpose: Find relevant context for user queries using embeddings or direct QA matching
- Location: `classes/embeddings.py`, `utils/basic_stats/core/knowledge_base.py`, `utils/basic_stats/core/query_planner.py`
- Contains: PlayerEmbeddings, CountryEmbeddings, PersonEmbeddings for semantic search; KnowledgeBase for exact/substring QA matching
- Depends on: Embedding models, parquet/CSV data sources
- Used by: Chat layer to fetch relevant_info before LLM generation

**Query Engine Layer:**
- Purpose: Parse natural language queries into structured database operations and fetch results
- Location: `utils/basic_stats/core/llm_query_engine_v2.py`, `utils/basic_stats/core/query_planner.py`, `utils/basic_stats/core/agent.py`
- Contains: LLMQueryEngineV2 (orchestrates full pipeline), QueryPlanner (resolves intent to structured plan), BasicStatsAgent (entry point combining KB + engine)
- Depends on: LLM for planning/metric resolution, DuckDB for execution
- Used by: `pages/basic_stats.py` for analytical queries

**Data Access Layer:**
- Purpose: Execute queries against analytical databases, manage connections, normalize results
- Location: `utils/basic_stats/core/duckdb_manager.py`, `classes/data_source.py`
- Contains: DuckDBManager (query execution, view registration), Data/PlayerStats/etc (raw data loading and processing)
- Depends on: DuckDB instance, Parquet files, CSV data
- Used by: Query engine layer and legacy page logic

**Description/Verbalization Layer:**
- Purpose: Transform raw data and query results into natural language summaries
- Location: `classes/description.py`, `utils/basic_stats/core/models.py`, prompts in `utils/basic_stats/prompts/`
- Contains: PlayerDescription, CountryDescription, PersonDescription (synthesize_text()); LLM prompt templates for metric resolution and response generation
- Depends on: Data objects, LLM client
- Used by: Chat layer for relevant_info synthesis and query results verbalization

**Visual Layer:**
- Purpose: Render statistical visualizations and distribution plots
- Location: `classes/visual.py`
- Contains: Visual base class, DistributionPlot, DistributionPlotPersonality
- Depends on: Data sources, matplotlib/plotly
- Used by: Chat layer to display_content() with visual objects

**Configuration & Infrastructure:**
- Purpose: Centralize secrets, model selection, and path management
- Location: `settings.py`, `utils/basic_stats/core/config.py`
- Contains: LLM credentials and model selection (GPT-3.5, GPT-4, Gemini), Azure endpoint config, data file paths
- Depends on: Streamlit secrets backend
- Used by: All LLM-dependent modules

## Data Flow

**Chat Query Flow (General):**

1. User sends message via `st.chat_input()` in page
2. Chat.handle_input() constructs message list with system instructions
3. Chat.get_relevant_info() fetches context (embeddings search + data descriptions)
4. LLM generates response with relevant_info + user query
5. Response appended to session_state.messages_to_display
6. Chat.display_messages() renders conversation grouped by role

**Analytical Query Flow (Basic Stats):**

1. User asks question in basic_stats.py
2. BasicStatsAgent.ask() routes to KnowledgeBase (fast QA lookup) or LLMQueryEngineV2
3. QueryPlanner parses question → structured intent (table, metric, filters, ranking)
4. LLMQueryEngineV2 dispatches by table_scope (players/teams)
5. DuckDBManager executes generic query with filters/ordering
6. QueryResult (rows + metadata) passed to verbalization
7. LLM synthesizes rows into natural language answer via prompts/verbalize.yaml
8. Result cached in session_state.messages_to_display

**State Management:**

- `st.session_state.messages_to_display`: List of {"role": str, "content": str|Visual} for chat history
- `st.session_state.chat_state_hash`: Identifies which entity is being discussed (used to reset on selection change)
- `st.session_state.chat_state`: Generic state field for chat implementations
- Per-page session keys: e.g., CHAT_KEY = "basic_stats_messages" in basic_stats.py

## Key Abstractions

**Chat (Base Class):**
- Purpose: Represent a conversation context around a subject (player, country, person)
- Examples: `classes/chat.py` → PlayerChat, WVSChat, PersonChat
- Pattern: Template method (instruction_messages, get_relevant_info are overridable; handle_input orchestrates)
- Lifecycle: Instantiated per page with chat_state_hash; persists messages in session_state

**Data Source (Base Class):**
- Purpose: Encapsulate raw data loading, processing, and filtering
- Examples: `classes/data_source.py` → PlayerStats, TeamStats, CountryStats
- Pattern: Template method (get_raw_data, process_data are overridable; get_processed_data orchestrates)
- Lifecycle: Instantiated once per page load; df cached

**QueryPlanner:**
- Purpose: Parse natural language intent into structured query representation
- Pattern: LLM-driven tool use with Pydantic validation (MetricResolution output contract)
- Input: User question (string)
- Output: Structured dict with table, metric, filters, ranking_mode, etc.

**BasicStatsAgent:**
- Purpose: Two-stage fallback: fast QA (KnowledgeBase) before expensive LLM query
- Pattern: Chain of responsibility
- Flow: KnowledgeBase.find_answer() → LLMQueryEngineV2.ask() if not found

**DuckDBManager:**
- Purpose: Centralize database connection, view registration, and query execution
- Pattern: Singleton-like (instantiated per request but manages single DB connection)
- Views registered: player_summary, team_summary, player_match, player_match_event, team_match

**Embeddings (PlayerEmbeddings, etc.):**
- Purpose: Semantic search over pre-computed embeddings for context retrieval
- Pattern: Search → retrieve top_n similar passages, return as string list
- Data: Loaded from pre-computed embedding indices (e.g., PlayerEmbeddings uses internal embedding files)

## Entry Points

**Streamlit App Entrypoint:**
- Location: `app.py`
- Triggers: `streamlit run app.py`
- Responsibilities: Load page config/CSS, render sidebar navigation, display about page content

**Page Entrypoints:**
- Location: `pages/*.py` (football_scout.py, basic_stats.py, wvs_chat.py, personality_test.py, etc.)
- Triggers: User clicks page link in sidebar
- Responsibilities: Initialize data source, set up chat, handle per-page state, render content

**Script Entrypoints:**
- Location: `scripts/*.py` (build_player_full_stats.py, etc.)
- Triggers: `python scripts/build_*.py`
- Responsibilities: Data preprocessing, aggregation, Parquet generation for app to consume

**Evaluation Entrypoints:**
- Location: `eval_runner_v*.py`, `evaluation/analysis_pipeline.py`
- Triggers: `python eval_runner_v*.py`
- Responsibilities: Benchmark query engine against test cases, collect results

## Error Handling

**Strategy:** Try-except with user-facing fallbacks; silent degradation for non-critical features.

**Patterns:**

1. **LLM Response Fallback:** If LLM returns invalid JSON or Pydantic validation fails, log error and retry or fallback to summary
   - See: `utils/basic_stats/core/llm_query_engine_v2.py` retry logic

2. **Data Not Found:** Return empty result with explanation message
   - Example: "This player is not in the dataset"
   - See: `classes/description.py` handling of missing data points

3. **Display Content Polymorphism:** Try Visual.show() → .get_string() → ValueError
   - Location: `classes/chat.py` display_content()
   - Allows visual objects to degrade gracefully to text

4. **Secret/Config Missing:** Error on startup via `st.secrets` access
   - Location: `settings.py`, `utils/basic_stats/core/config.py`
   - Fails fast if LLM credentials absent

5. **Query Validation:** Pydantic ValidationError caught and logged
   - Location: `utils/basic_stats/core/query_planner.py`
   - Returns error message to user if plan cannot be structured

## Cross-Cutting Concerns

**Logging:** Console output via print() and st.write(); debug expanders in pages for transparency
- Example: `show_debug` checkbox in basic_stats.py expands debug_info

**Validation:**
- Input: Message length checks in Chat.get_input() (max 500 chars)
- Data: Pydantic models (MetricResolution, QueryResult) enforce schema
- LLM Output: Structured output validation with fallback to text

**Authentication:**
- App-level: None (public Streamlit app)
- LLM: API keys in st.secrets (Azure, OpenAI, Gemini)
- Data: No row-level security; all data accessible to all users

**State Isolation:**
- Per-page: CHAT_KEY namespacing (e.g., "basic_stats_messages")
- Per-user: Streamlit session_state is per-browser-session
- Concurrent: Multiple Streamlit server processes; no global state

---

*Architecture analysis: 2026-03-26*
