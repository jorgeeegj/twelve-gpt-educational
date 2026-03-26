# INTEGRATIONS.md — External Services & Integrations

## LLM APIs

### Azure OpenAI (Primary)
- **Client:** `openai` v0.28.1 (legacy API style)
- **Usage:** Chat completions + embeddings
- **Config keys** (via `settings.py` + `.streamlit/secrets.toml`):
  - `GPT_BASE` — Azure endpoint URL (e.g. `https://twelve-courses.openai.azure.com`)
  - `GPT_VERSION` — API version string
  - `GPT_KEY` — API key
  - `GPT_ENGINE` / `GPT_CHAT_MODEL` — Deployment name
  - `GPT_EMBEDDINGS_ENGINE` / `GPT_EMBEDDINGS_MODEL` — Embeddings deployment
  - GPT4o variants: `GPT4o_BASE`, `GPT4o_VERSION`, `GPT4o_KEY`, `GPT4o_ENGINE`
- **Used in:** `classes/embeddings.py`, `classes/chat.py`, `utils/basic_stats/core/config.py`

### Google Gemini (Optional)
- **Client:** `google-generativeai` 0.7.2
- **Toggle:** `USE_GEMINI=true` in secrets
- **Config keys:** `GEMINI_API_KEY`, `GEMINI_CHAT_MODEL`, `GEMINI_EMBEDDING_MODEL`
- **Used in:** `utils/gemini.py`, `settings.py`

## Database

### DuckDB (In-Process)
- **Type:** Embedded SQL analytics engine (no separate server)
- **Path:** `db/basic_stats.duckdb`
- **Manager:** `utils/basic_stats/core/duckdb_manager.py` (`DuckDBManager` class)
- **Tables loaded from Parquet:**
  - `player_full_stats` ← `output/player_full_stats.parquet`
  - `team_full_stats` ← `output/team_full_stats.parquet`
  - `player_match_stats` ← `output/player_match_stats.parquet`
  - `player_match_event_stats` ← `output/player_match_event_stats.parquet`
  - `team_match_stats` ← `output/team_match_stats.parquet`

## Data Files (Local Filesystem)

### Parquet files
- `data/players.parquet`, `data/teams.parquet`, `data/matches.parquet`, `data/minutes.parquet`
- `data/player_stats_summary.parquet`, `data/player_qualities.parquet`
- `data/embeddings/*.parquet` — Pre-computed semantic embeddings
- `output/*.parquet` — Aggregated stat tables (built by `scripts/build_*.py`)

### Source data
- `data/data_raw.csv` — Raw event/stats CSV
- `data/event_data/*.json` — Individual match event JSON (~620 files)
- `data/events/` — Player/match events CSVs and JSONs

## Analytics / Tracking

### Customer.io
- **Package:** `customerio` 2.1.0
- **Purpose:** User event tracking / analytics
- **Config:** credentials likely in `.streamlit/secrets.toml`

## Authentication
- **Mechanism:** Streamlit secrets-based (no external OAuth/SSO provider)
- **JWT support:** `python-jose` 3.3.0 available (not prominently used in current pages)
- **Access control:** Enforced via Streamlit secrets check in `utils/page_components.py`

## No External Webhooks / Message Queues
- No Kafka, RabbitMQ, or webhook endpoints found
- All data is local filesystem + in-process DuckDB
