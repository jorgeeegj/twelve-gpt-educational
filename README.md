# TwelveGPT Educational

A Streamlit app for building AI-powered football data assistants. Includes a general RAG chatbot for player reports and a **Basic Stats Analyst** — a grounded question-answering engine for Premier League statistics.

> This is **not** the Twelve GPT product. It is a stripped-down educational version under GNU GPL — free to use, fork, and learn from.

---

## What's in this repo

| Page | What it does |
|---|---|
| `app.py` | Player report chatbot with radar charts and GPT-generated summaries |
| `pages/basic_stats.py` | Basic Stats Analyst — factual Q&A grounded in structured match data |

---

## Basic Stats Analyst

Answers factual football questions directly from structured datasets — no hallucination, no invented stats.

**Examples:**
- *Who has scored the most goals this season?*
- *Which midfielder has played the most progressive passes against top-6 teams?*
- *Has Haaland scored more goals against top 5 or bottom 5 teams?*
- *How many goals has Salah scored in the last 5 gameweeks?*

### Architecture (v2 — Function Calling)

```
Question
   ↓
BasicStatsAgent (OpenAI function-calling loop, max 6 iterations)
   ↓
9 typed tools — the LLM decides which to call and with what args
   ↓
DuckDBManager (SQL against parquet datasets — no invented data)
   ↓
LLM verbalizes grounded results only
   ↓
Answer
```

The LLM owns semantic interpretation (which stat, which entity, which filters) and writes the final answer. Code owns data access only. No regex heuristics.

**9 tools:** `get_player_stat`, `get_team_stat`, `rank_players`, `rank_teams`, `compare_entities`, `count_matches_where`, `get_stat_over_window`, `get_league_standings`, `get_stat_vs_opponent_group`

### Source layout

```
src/basic_stats/
├── agent.py                 ← BasicStatsAgent — function-calling loop
├── agent_tools.py           ← 9 tool implementations
├── agent_tool_schemas.py    ← OpenAI strict-mode schemas
├── agent_prompt.py          ← dynamic system prompt builder
├── config.py                ← Azure OpenAI client + paths
├── duckdb_manager.py        ← SQL query execution against parquet
├── models.py                ← Pydantic schemas
├── knowledge_base.py        ← static Q&A (definitions)
├── llm_query_engine_v2.py   ← v1 pipeline (legacy reference)
├── query_planner.py         ← v1 pipeline (legacy reference)
└── prompts/
    └── agent_system.yaml    ← system prompt for the agent

evals/
├── questions_benchmark.json ← 61-question benchmark (source of truth)
├── agent_benchmark.py       ← Phase 5 benchmark with faithfulness judge
├── judges/
│   └── faithfulness_judge.py ← deterministic: verifies numbers in answer
├── benchmark_runner.py      ← v1 parallel runner (reference)
└── smoke_test.py            ← v1 sanity check (reference)

docs/
├── canonicalization_rules.md ← v1 rule categories (reference)
└── progress/                 ← session logs
```

### Benchmark

```bash
# New agent benchmark (Phase 5)
python evals/agent_benchmark.py --workers 1 --label my_label

# Skip faithfulness judge (faster iteration)
python evals/agent_benchmark.py --skip-judges --workers 1 --label my_label
```

Current status: **51/61 = 83.6%** ◐ (Phase 5 in progress — target ≥58/61)

---

## Setup

### Requirements

- Python 3.11+
- Azure OpenAI API access (keys in `.streamlit/secrets.toml`)

### Install

```bash
# Clone the active branch
git clone https://github.com/jorgeeegj/twelve-gpt-educational.git
cd twelve-gpt-educational
git checkout feature/refactor-v2

# Install dependencies — pick your tool
pip install -r requirements.txt           # pip
python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt  # venv
uv sync                                   # uv
conda create -n basicstats python=3.11 && conda activate basicstats && pip install -r requirements.txt  # conda
```

### Secrets

Create `.streamlit/secrets.toml`:

```toml
GPT_KEY     = "your-azure-key"
GPT_VERSION = "your-api-version"
```

### Run

```bash
streamlit run app.py
```

---

## Development

This project uses [GSD](https://github.com/getshitdone-ai/gsd) for structured development with Claude Code.

```bash
/gsd:progress       # see current phase and what's next
/gsd:execute-phase 5  # execute next phase
```

See `.planning/TEAM.md` for full team onboarding guide.

### Golden rule

> Any change to `agent.py`, `agent_tools.py`, `agent_tool_schemas.py`, or `duckdb_manager.py`
> **must** pass the agent benchmark before committing.

```bash
python evals/agent_benchmark.py --workers 1 --label verify && git commit
```

---

## Original project

Design and code by Matthias Green, David Sumpter and Ágúst Pálmason Merthens.
v2.0 development by Álvaro Molina, Ricardo Heredia, and Jorge Gómez.

Contact: hello@twelve.football
