# STRUCTURE.md — Directory Layout & Organization

## Top-Level Layout

```
twelve-gpt-educational/
├── app.py                    # Streamlit entrypoint (home page)
├── settings.py               # Global LLM config (reads st.secrets)
├── setup.py                  # Package install config
├── requirements.txt          # Python dependencies
├── pages/                    # Streamlit multi-page app pages
├── classes/                  # Core domain abstractions
├── utils/                    # Utilities & feature-specific modules
│   ├── basic_stats/          # Basic Stats Analyst feature (main active feature)
│   └── datalib/              # General data helpers
├── data/                     # Raw data, embeddings, resources
├── output/                   # Built parquet stat tables (gitignored)
├── db/                       # DuckDB database file
├── scripts/                  # Data pipeline build scripts
├── evaluation/               # Evaluation framework (embeddings/descriptions)
├── eval_runner*.py           # LLM query engine benchmark runners (v1–v5)
├── questions_benchmark*.json # Benchmark question sets
├── docs/                     # Progress logs, eval results
└── .streamlit/               # Streamlit config + secrets
```

## `pages/` — Streamlit App Pages
| File | Feature |
|------|---------|
| `pages/basic_stats.py` | Basic Stats Analyst (LLM + DuckDB query chatbot) |
| `pages/football_scout.py` | Football Scout (player comparison) |
| `pages/wvs_chat.py` | World Values Survey chatbot |
| `pages/personality_test.py` | Big Five personality test |
| `pages/shots.py` | Shot/xG analysis |
| `pages/embedder.py` | Embedding explorer |
| `pages/quality_builder.py` | Player quality builder |
| `pages/own_page.py` | User-customizable page template |
| `pages/about.py` | About page |

## `classes/` — Core Domain Abstractions
| File | Purpose |
|------|---------|
| `classes/chat.py` | Base `Chat` class — LLM chat session management |
| `classes/data_source.py` | `DataSource` — loads and holds a dataset |
| `classes/data_point.py` | `DataPoint` — single entity (player/country) |
| `classes/description.py` | `Description` — LLM-generated text descriptions |
| `classes/embeddings.py` | `Embeddings` — vector embedding store + search |
| `classes/visual.py` | `Visual` — matplotlib/plotly chart generation |

## `utils/basic_stats/` — Active Feature Module
```
utils/basic_stats/
├── core/
│   ├── config.py             # Paths, LLM client factory (get_llm_client, get_model)
│   ├── duckdb_manager.py     # DuckDBManager — SQL query execution
│   ├── query_planner.py      # QueryPlanner — LLM-based intent → SQL plan
│   ├── llm_query_engine_v2.py# Main query orchestration engine
│   ├── models.py             # Pydantic-like data models (MetricResolution, QueryResult)
│   ├── knowledge_base.py     # Static metric/entity knowledge
│   ├── agent.py              # Agent wrapper (tool-use pattern)
│   └── test_query_planner.py # Manual test runner for query planner
├── legacy/                   # Superseded engine versions (kept for reference)
│   ├── llm_query_engine.py
│   ├── intent_router.py
│   ├── metric_resolver.py
│   ├── query_engine.py
│   └── response_generator.py
├── prompts/
│   ├── verbalize.yaml        # Verbalization prompt template
│   ├── resolve_metric.yaml   # Metric resolution prompt
│   └── resolve_query_intent.yaml # Query intent parsing prompt
├── verbal_model.py           # Verbal model wrapper
└── aliases_para_ricardo.json # Player/team name aliases
```

## `data/` — Data Assets
```
data/
├── data_raw.csv              # Raw football event data
├── *.parquet                 # Entity tables (players, teams, matches, minutes)
├── event_data/*.json         # ~620 individual match event files
├── events/                   # Player/match event CSVs + JSON
├── embeddings/*.parquet      # Pre-computed embeddings per data source
├── describe/*.xlsx/.csv      # LLM description source files
├── gpt_examples/*.xlsx       # GPT few-shot example files
├── wvs/                      # World Values Survey data + preprocessing
├── ressources/
│   ├── fonts/                # Gilroy font family (OTF/TTF)
│   └── img/                  # Logos, icons, brand assets
└── style.css                 # Streamlit custom CSS
```

## `scripts/` — ETL Pipeline
Build scripts that populate `output/*.parquet` from `data/`:
- `build_player_full_stats.py`
- `build_player_match_stats.py`
- `build_player_match_event_stats.py`
- `build_player_stats_summary.py`
- `build_team_full_stats.py`
- `build_team_match_stats.py`
- `build_team_stats_summary.py`

## `evaluation/` — Description Evaluation
- `analysis_pipeline.py` — Runs embedding-similarity evaluation
- `generate_data_for_evaluation.py` — Generates eval data
- `data/` — Ground truth CSVs (player, country, person)
- `prompts/` — Prompt versions (v0, v1) per entity type

## Naming Conventions
- **Files:** `snake_case.py`
- **Classes:** `PascalCase`
- **Eval runners:** `eval_runner_v{N}.py` (versioned)
- **Benchmark files:** `questions_benchmark_v{N}.json`
- **Legacy code:** lives in `utils/basic_stats/legacy/` — do not modify
- **Prompts:** YAML files in `utils/basic_stats/prompts/`
