# STACK.md — Technology Stack

## Language & Runtime
- **Language:** Python 3.12.4
- **Package manager:** pip + venv (`venv/`)
- **Setup:** `setup.py` with `twelve_gpt_educational` package

## Frameworks & UI
| Package | Version | Role |
|---------|---------|------|
| `streamlit` | 1.31.0 | Web UI framework (multi-page app) |
| `fastapi` | 0.104.1 | API server (declared in requirements, minimal use) |
| `uvicorn` | 0.24.0.post1 | ASGI server for FastAPI |

## AI / LLM
| Package | Version | Role |
|---------|---------|------|
| `openai` | 0.28.1 | Azure OpenAI chat + embeddings (legacy SDK) |
| `google-generativeai` | 0.7.2 | Google Gemini (optional alternative) |
| `tiktoken` | latest | Token counting for OpenAI models |

**LLM configuration** (`settings.py`, `.streamlit/secrets.toml`):
- Default model: GPT-3.5 (switchable to GPT-4 via `GPT_DEFAULT`)
- Azure endpoint: `GPT_BASE`, `GPT_VERSION`, `GPT_KEY`, `GPT_ENGINE`
- Gemini: `GEMINI_API_KEY`, `GEMINI_CHAT_MODEL`, `GEMINI_EMBEDDING_MODEL`

## Data & Storage
| Package | Version | Role |
|---------|---------|------|
| `pandas` | 2.2.0 | DataFrames, CSV/Parquet I/O |
| `polars` | latest | High-performance DataFrame queries |
| `duckdb` | latest | In-process SQL analytics engine |
| `numpy` | 1.26.3 | Numerical arrays |
| `pyarrow` | latest | Parquet serialization |

**Data storage:**
- `db/basic_stats.duckdb` — DuckDB persistent database
- `output/*.parquet` — Pre-built stat tables (player/team full, match, event)
- `data/*.parquet` — Raw entity data (players, teams, matches, minutes)
- `data/embeddings/*.parquet` — Pre-computed embedding vectors

## Visualization
- `matplotlib` — Static plots
- `plotly.express` — Interactive charts
- `scipy`, `scikit-learn` — Statistical computation, ML helpers

## Auth & Security
- `python-jose` 3.3.0 — JWT token handling
- `requests` 2.29.0 — HTTP client

## Other
- `customerio` 2.1.0 — Analytics/event tracking
- `tenacity` — Retry logic (referenced in legacy code)

## Configuration
- **Secrets:** `.streamlit/secrets.toml` (gitignored; `.streamlit/secrets_example.toml` for reference)
- **App config:** `.streamlit/config.toml`
- **Central settings:** `settings.py` — reads from `st.secrets` and exposes GPT_* globals

## Dev Environment
- `.devcontainer/devcontainer.json` — VS Code devcontainer support
- `venv/` — Local virtual environment
- No CI/CD config found
