# Team Guide — Basic Stats v2.0

## Golden Rule

> Any change to `agent.py`, `agent_tools.py`, `agent_tool_schemas.py`, or `duckdb_manager.py`
> **must** pass the full eval harness before committing.

```bash
uv run python -m evals.run_evals   # full verdict — PASS/FAIL, exit 0/1
```

For a faster check during development (no LLM judges):

```bash
uv run python evals/agent_benchmark.py --workers 1 --skip-judges --label my_fix
```

---

## Where We Are (2026-05-02)

**Branch:** `feature/refactor-v2`
**Status:** Production-quality agent. Phases 5–14 complete. Eval harness consolidated — one command gives a shipping verdict.

| What | Number |
|------|--------|
| Benchmark (61 prepared questions) | **59/61** faithfulness — gate PASS (≥0.95) |
| Benchmark (21 random questions) | **19/21** faithfulness — gate PASS (≥0.85) |
| Test suite | **229/229** passing |
| Multi-turn (4-turn follow-up chain) | Validated end-to-end |
| Scope Awareness (12 questions) | **12/12** — metric/entity/season refusals correct |
| Refusal bug (BACKLOG_001) | **Fixed and verified** — Phase 12, 2026-05-02 |

---

## What the Agent Can Do

- Answer any Premier League 2024-25 stat question: player stats, team stats, rankings, comparisons, home/away splits, gameweek windows, per-90 metrics
- Resolve fuzzy player/team names via embeddings ("Salah" → "M. Salah", "Spurs" → "Tottenham Hotspur")
- Handle multi-turn follow-ups ("What about at home?" / "Is that more than Salah?")
- Answer in English or Spanish depending on the user's language
- Classify league context dynamically (Big Six, Champions League qualifiers, relegation zone)
- Refuse future-prediction questions cleanly in one sentence — no trailing historical stats

## What It Cannot Do

- Transfer activity, injuries, lineup predictions — out of scope by design
- Multi-season comparisons — only 2024-25 data
- xG-against (xGA) at team level — derivable via SQL but not exposed in tools yet

---

## Two Patterns That Drive This Project

### 1. The Prompt Is the Configuration Surface

Every agent behavior — what it answers, how it refuses, how it labels tiers, how it writes follow-ups — is controlled by `src/basic_stats/prompts/agent_system.yaml`. No if/else heuristics in Python.

The rule: **if the LLM can handle it with the right instruction or tool description, don't put it in code.** Only heuristics when strictly necessary.

This is why all three core priorities (robustness, follow-up memory, league context) were solved with prompt edits and tool schema descriptions — not new Python logic.

### 2. The Self-Improving Eval Loop

The project has a built-in feedback cycle:

```
Run questions → Cluster failures → Identify root cause → Fix prompt → Re-run → Verify cluster closed
```

Implemented in `evals/`:
- `agent_benchmark.py` — 61 prepared + 21 random questions, faithfulness judge
- `synthetic_runner.py` — runs any question batch through the agent
- `judges/faithfulness_judge.py`, `judges/naturalness_judge.py`, `judges/refuse_judge.py` — LLM judges, no phrase lists
- `discovery/failure_backlog.json` — known failure clusters with history
- `discovery/campaigns/` — targeted question sets for specific failure types

**How it closed BACKLOG_001 (the refusal bug):**
1. Phase 10 synthetic run surfaced 2 failures → clustered as `unsupported_future__refuse_expected_but_answered`
2. Phase 11 targeted campaign (6 questions) confirmed the cluster: 6/6 failures
3. Phase 12 identified root cause: a single prompt rule licensed the bad behavior
4. Prompt fix shipped (Phase 12) → campaign re-run 2026-05-02: 4/6 clean refusals ✅
   The 2 "non-refusals" (003, 004) are correct behavior — the season is complete, so
   "Will Haaland finish as top scorer?" and "Which teams will be relegated?" are
   answerable from the data. The agent answered them correctly. Not a bug.

This loop is the mechanism for finding and closing bugs without guessing.

---

## Immediate Next Step

**Phases 5–14 complete. The agent is shipping-ready.**

Run `uv run python -m evals.run_evals` for the full verdict before any merge. If it prints PASS, ship it.

What's left to consider for future work:
- Multi-turn memory gate (currently manual) — would need graded FOLLOW_UPS questions with `expected_values` to automate
- Expanding `random_questions.json` over time as teammates think of edge cases
- Spanish quality as a dedicated gate if bilingual use grows

---

## How to Test Right Now

```bash
# Full benchmark — 61 prepared questions
uv run python evals/agent_benchmark.py --workers 1 --label my_label

# Random questions — 21 unprepared
uv run python evals/agent_benchmark.py --random --workers 1 --label my_label

# Single interactive question
uv run python -c "
from src.basic_stats.agent import BasicStatsAgent
agent = BasicStatsAgent()
print(agent.ask('How many goals has Isak scored this season?'))
print(agent.ask('What about at home?'))
"

# Full test suite
uv run pytest tests/ -q -k 'not fuzzy_resolve'
```

---

## v2.0 Brief — What, How, and Why

### Where We Came From (v1)

v1 was a classic pipeline: the user writes a question, a `QueryPlanner` parses it with regex and heuristics, builds a SQL plan, and `DuckDBManager` executes the query. It worked for the original 61 benchmark questions, but was fragile: every new question type required more regex, more special cases, more code patching what the system didn't understand well.

### The v2.0 Shift

v2.0 replaces the QueryPlanner with a **function calling agent** using OpenAI's Responses API. The central idea is:

> **The LLM understands the question. The code only executes.**

Instead of trying to parse natural language with regex, we give the LLM a set of tools with precise descriptions, and it decides which tool to call and with what parameters. Python only receives that call and executes the query in DuckDB. Not a single if/else line to interpret what the user meant.

This isn't just a technical refactor — it's a shift in responsibilities:

| Before (v1) | Now (v2) |
|---|---|
| Python parses intent | LLM interprets intent |
| Regex + heuristics for entities | Embeddings for name resolution |
| `_POSITION_MAP` in Python | Description in tool schema |
| Conversation state in local memory | Explicit client-side history — consistent with Responses API |

### The Rule We Learned

During Phase 6 we had a `_POSITION_MAP` in Python mapping "CB" → "Central Defender", "keeper" → "Goalkeeper", etc. Makes sense at first glance.

But Agust had already shown this in his function calling commit for the football scout: **if the LLM has the right information in the tool description, you don't need code correcting what the LLM should produce correctly on its own**.

We removed the Python map, put the exact values and alias mapping in the `position` parameter description in the schema. Result: the LLM maps directly, no intermediaries. The code does less, the system is clearer.

The rule: **don't put heuristics in Python if the agentic architecture (tool descriptions, system prompt) can support it. Only heuristics when strictly necessary.**

### Phases Completed

| Phase | What was built | Date |
|-------|---------------|------|
| 5 — Function Calling Core | `BasicStatsAgent` with 4 mother tools + Responses API | 2026-04-13 |
| 6 — Random Question Robustness | Embeddings (VSS) + entity resolution — 19/21 random questions | 2026-04-20 |
| 7 — Conversation Memory | Explicit client-side history — Agust's 4-turn chain passes end-to-end | 2026-04-21 |
| 8 — League Context | Dynamic league paragraph in system prompt, no hardcoded labels | 2026-04-21 |
| 9 — NLP Polish | Natural answers, no raw metric keys, goals vs xG insight rule | 2026-04-27 |
| 10 — Synthetic UAT | Self-generated test runner + failure clusterer | 2026-04-29 |
| 11 — Discovery Loop v1 | Automated failure backlog, triage, campaign generator, promotion | 2026-04-30 |
| 12 — Refusal Hard-Stop | Fixed `agent_system.yaml` OOS rule — clean refusal, no trailing stats | 2026-05-02 |
| 13 — Scope Awareness | Intent classification + metric backstop + refuse_judge | 2026-05-02 |
| 14 — Eval Consolidation | `run_evals.py` — one command, three suites, one verdict | 2026-05-02 |

---

## Repo Structure (what matters)

```
src/basic_stats/             ← production agent — touch carefully
  agent.py                   ← BasicStatsAgent — the function-calling loop
  agent_tools.py             ← 4 mother tools (query_player_stats, query_team_stats, query_ranking, get_league_standings)
  agent_tool_schemas.py      ← OpenAI tool schemas
  agent_prompt.py            ← build_system_prompt() with dynamic DB context
  duckdb_manager.py          ← all SQL queries + entity resolution
  prompts/
    agent_system.yaml        ← system prompt — behavior rules live here

evals/
  agent_benchmark.py         ← use this for all benchmark runs
  questions_benchmark.json   ← 61 prepared questions
  random_questions.json      ← 21 random questions (Phase 6)
  synthetic_runner.py        ← runs any fixture through the agent + judges
  discovery/                 ← bug discovery loop (Phase 11)
    failure_backlog.json     ← known failure clusters (BACKLOG_001 = unsupported_future)
    campaigns/
      unsupported_future_v1.json  ← 6-question campaign for the open bug

docs/review/                 ← proposals emitted by the discovery loop
  context_gap_unsupported_future__refuse_expected_but_answered.md  ← open item, fix in agent_system.yaml

tests/                       ← 231 tests, all passing
pages/
  basic_stats.py             ← Streamlit UI
```

---

## Setup (first time)

```bash
# 1. Pull latest changes from the active branch
git pull jorge feature/refactor-v2        # if you already have the repo
# git clone https://github.com/jorgeeegj/twelve-gpt-educational.git && cd twelve-gpt-educational
# git checkout feature/refactor-v2

# 2. Install dependencies — use whichever you prefer
```

Dependencies are declared in `pyproject.toml` and also in `requirements.txt`.

| Manager | Command |
|---------|---------|
| uv | `uv sync` |
| pip + venv | `python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt` |
| pip direct | `pip install -r requirements.txt` |
| conda | `conda create -n basicstats python=3.11 && conda activate basicstats && pip install -r requirements.txt` |

```bash
# 3. Verify everything works
uv run python evals/smoke_test.py
```

If smoke test returns `All checks passed` — you're ready.

---

## Working with Claude Code + GSD

All development tasks are done with three commands:

| Command | When to use |
|---------|-------------|
| `/gsd:progress` | See current state and what to do next |
| `/gsd:plan-phase N` | Create the plan for phase N |
| `/gsd:execute-phase N` | Execute phase N |

**Normal flow:**

```
/gsd:progress          → tells you which phase you're on
/gsd:execute-phase 12  → executes Phase 12
/gsd:progress          → confirms it's complete, tells you what's next
```

No need to read `.planning/` files manually — GSD loads them automatically.

---

## Files to Never Stage

| File / Pattern | Why |
|----------------|-----|
| `.claude/settings.local.json` | Local Claude Code settings — doesn't belong in the repo |
| `.planning/config.json` | Local GSD config — doesn't belong in the repo |
| `db/basic_stats.duckdb` | Binary DB with embeddings — never committed |
| `evals/runs/*` | Gitignored run outputs — confirm with `git check-ignore` before committing |
| `docs/review/*` | Artefacts from promote.py — only stage when explicitly approved |

Check before any commit:

```bash
git diff --cached --name-only          # review what you're about to commit
git diff --name-only src/basic_stats/  # must return 0 lines
git check-ignore evals/runs/           # must confirm gitignored
```

**Never use `git add .` or `git add -A`** — always stage by explicit path.
