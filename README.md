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

### Architecture

```
Question
   ↓
QueryPlanner (LLM extracts intent → deterministic canonicalization)
   ↓
DuckDBManager (structured query against parquet datasets)
   ↓
LLM verbalization (grounded in retrieved rows only)
   ↓
Answer
```

1. **LLM extracts intent** — metric, entity, filters, ranking
2. **~680 deterministic rules** canonicalize the raw plan (scope, metric aliases, opponent filters, time windows)
3. **DuckDB queries parquet files** — no invented data
4. **LLM verbalizes** only from grounded result rows

### Source layout

```
src/basic_stats/
├── agent.py                 ← entry point
├── config.py                ← Azure OpenAI client + paths
├── llm_query_engine_v2.py   ← main engine (dual-bucket, home/away, temporal)
├── query_planner.py         ← LLM plan extraction + canonicalization
├── duckdb_manager.py        ← SQL query execution against parquet
├── models.py                ← Pydantic schemas
├── knowledge_base.py        ← static Q&A (definitions)
└── prompts/
    ├── resolve_metric.yaml
    ├── verbalize.yaml
    └── resolve_query_intent.yaml

evals/
├── questions_benchmark.json ← 61-question benchmark (source of truth)
├── eval_runner.py           ← sequential runner
├── benchmark_runner.py      ← parallel runner (~5x faster)
└── smoke_test.py            ← 10-question sanity check

docs/
└── canonicalization_rules.md ← all 17 rule categories documented
```

### Benchmark

```bash
python evals/smoke_test.py                    # 10 questions ~2 min
python evals/benchmark_runner.py --workers 5  # 61 questions ~5 min
```

Current status: **61/61** ✓

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

> Any change to `query_planner.py`, `llm_query_engine_v2.py`, or `duckdb_manager.py`
> **must** pass the smoke test before committing.

```bash
python evals/smoke_test.py && git commit
```

---

## Original project

Design and code by Matthias Green, David Sumpter and Ágúst Pálmason Merthens.
v2.0 development by Álvaro Molina, Ricardo Heredia, and Jorge Gómez.

Contact: hello@twelve.football
