# Phase 5 — Function Calling Core (Rewrite)

**Phase:** 5 — Function Calling Core
**Status:** Rewritten 2026-04-12 after mid-execution scope pivot. See [PHASE_5_NOTES.md](./PHASE_5_NOTES.md) for why the original plan was scrapped.
**Requirements:** FUNC-01, FUNC-02, FUNC-03, FUNC-04 (FUNC-04 already complete — `docs/canonicalization_rules.md` exists)
**Tasks:** 5

---

## Goal

Build an agent that answers arbitrary Premier League 2024-25 questions by calling thin data-layer tools and writing natural language answers directly. The LLM owns semantic interpretation and verbalization. Code owns data access and domain vocabulary.

Replace the planner-based architecture (`QueryPlanner` + `_canonicalize_raw_plan` + `_post_process_plan` + templated verbalization) with a single `Agent.ask(question, history=None) → str` method that runs a tool-calling loop.

---

## How this phase relates to the rest of the v2 roadmap

The original Phase 5 was a code refactor that replaced one heuristic layer with an equivalent one. The new Phase 5 is an **architectural pivot** that makes every downstream phase 3–5x smaller:

- **Phase 6 (Conversation Memory)** — becomes a `ConversationState` dataclass passed into the agent's `history` parameter. No separate memory architecture needed; the agent loop already carries message history natively.
- **Phase 7 (League Context)** — becomes one new tool (`get_league_standings()`) and one paragraph in the system prompt. The dynamic "top 6" / "relegation zone" classification the LLM needs to do has no planner-layer dependency.
- **Phase 8 (Random Question Robustness)** — largely **pulled forward into Phase 5** as a success gate. The whole point of the agent architecture is that "unprepared questions" work without code changes. We validate that here, not later.
- **Phase 9 (Natural Language Polish)** — becomes "improve the system prompt + add insight rules." The LLM already writes the final answer, so we're no longer fighting a template engine.

**What disappears in this phase:** `_canonicalize_raw_plan` (680 lines), `_normalize_tool_args_to_plan` (180 lines), most of `_post_process_plan`, the scope inference tree, metric rename maps, dual-bucket detector, home/away detector, metric-derived bucket detector, templated verbalization.

**What stays:** `duckdb_manager.py` (data layer — untouched). `QueryPlan` Pydantic model (kept as internal return type for tool functions, not exposed to the LLM).

---

## Architecture

### The agent loop (`src/basic_stats/agent.py`)

```
Agent.ask(question, history=None)
  ├─ Build messages = [system_prompt, *history, user(question)]
  ├─ Loop (max 5 iterations):
  │    ├─ response = llm.chat.completions.create(messages, tools=ALL_TOOLS)
  │    ├─ If response has tool_calls:
  │    │    ├─ For each tool call: execute → append result to messages
  │    │    └─ continue loop
  │    └─ Else: return response.content (natural language answer)
  └─ If loop exhausted: return fallback error message
```

### The system prompt is built once at agent-init time

On `Agent.__init__`, we run a small number of introspection queries against DuckDB and bake the results into the system prompt:

- Full list of available stats per scope (from `duckdb_manager.metric_catalog`)
- Full list of player short names (for entity resolution reference)
- Full list of team names
- Full list of canonical positions (`Striker`, `Winger`, `Midfielder`, etc. — the actual DB values)
- Max matchday in the current dataset
- One paragraph describing the Premier League 2024-25 context (20 teams, 38-matchday season, Big Six, promoted sides)

**Discovery tools are not exposed to the LLM as runtime tools.** The schema is static and cacheable; burning a round-trip on `list_available_stats()` for every question is wasteful. If we later need dynamic discovery (e.g., "who plays for Chelsea *right now*"), we add it as a runtime tool then.

### The tool catalog

Six tool categories. The LLM sees each as an OpenAI tool with `strict: true` schemas and `additionalProperties: false`.

**1. Entity stat lookup**
- `get_player_stat(player_name, stat, filters)` — returns `{value, supporting_rows}`
- `get_team_stat(team_name, stat, filters)` — same shape

**2. Ranking**
- `rank_players(stat, filters, limit, position, descending)` — returns top/bottom N rows
- `rank_teams(stat, filters, limit, descending)` — same shape

**3. Comparison**
- `compare_entities(entity_type, entities, stat, filters)` — returns one row per entity

**4. Match-level aggregation**
- `count_matches_where(entity_type, entity_name, conditions, filters)` — e.g., "matches with goals>=2 AND assists>=1". Handles Q33/Q34-style questions generically.

**5. Temporal window**
- `get_stat_over_window(entity_type, entity_name, stat, last_n_gameweeks, filters)` — thin convenience wrapper; could be folded into (1) but explicit tool makes "last 5 gameweeks" intent unambiguous.

**6. League context (placeholder for Phase 7)**
- `get_league_standings()` — returns current rank table. Used for "top 6" / "bottom 5" / "mid-table" semantics in Phase 5 already; Phase 7 adds the dynamic classification layer on top.

### The `filters` object (shared across tools)

A single typed shape used by all tools that support filtering. Kept flat for LLM reasoning per OpenAI best practices:

```
{
  opponent_team: str | None,
  is_home: bool | None,
  opponent_rank_max: int | None,   # top-N opponents (rank <= N)
  opponent_rank_min: int | None,   # bottom-N opponents (rank >= N)
  matchday_start: int | None,
  matchday_end: int | None,
  min_minutes: int | None,
  min_matches: int | None,
  age_max: int | None,
}
```

No `opponent_is_big6` flag — "Big Six" is just `opponent_rank_max=6` in context. The LLM learns this from the league-context paragraph in the system prompt. No scope-specific metric names — `stat="goals"` works whether we're hitting `players_summary` or `player_match`; the tool picks the right table based on which filters are set.

### Tool implementations are thin

Each tool function:
1. Takes typed args
2. Decides which DuckDB table to hit based on whether match-level filters are present
3. Runs the SQL query
4. Returns `{value: ..., supporting_rows: [...]}` (or raises `ToolError` with a human-readable message the LLM can read and react to)

**No canonicalization. No scope inference heuristics beyond "if match filter set → use match table, else summary table". No metric renames. No regex on question text.**

---

## Benchmark (new eval harness)

The current `evals/questions_benchmark.json` + `evals/eval_runner.py` tests "does the planner produce the expected row for this exact question." With the new architecture that's the wrong question — we care about **end-to-end answer quality**, not internal plan shape.

New harness: `evals/agent_benchmark.py` with four categories:

### 1. Faithfulness (auto-judge, hard gate)

For each prepared question, we also store a ground-truth SQL query that independently computes the expected value(s). After the agent answers, we extract numbers from its text and verify each number appears in either (a) the ground-truth query result or (b) a number the agent computed from returned rows and can be re-derived.

**Gate:** >=95% of answers faithful to data (zero hallucinated numbers).

### 2. Naturalness (LLM-as-judge, soft gate)

A second LLM (GPT-4) rates each answer on a 1–5 scale:
- 5 = sounds like a football analyst — fluent, contextual, informative
- 3 = correct but dry / robotic phrasing
- 1 = unreadable (JSON dump, raw column names, broken grammar)

**Gate:** average >=4.0 across all answered questions.

### 3. Prepared questions (the old 61)

The existing benchmark questions get ported. Expected values stay; the scoring method changes from "plan field-match" to "faithful answer." Some questions may be dropped if they're genuinely ambiguous — we document each drop with a reason.

**Gate:** >=58/61 faithful + natural (allowing up to 3 documented drops).

### 4. Random questions (pulled forward from Phase 8)

Before running the final benchmark, each team member (Ricardo, Álvaro, Jorge) writes 7 unprepared questions — 21 total. Rules:
- No looking at the benchmark file
- No looking at the code
- Must be answerable from PL 2024-25 DuckDB data
- Mix of simple and complex

These are the real robustness test. No iteration allowed after collection — we run them once and record the score.

**Gate:** >=80% faithful + natural (17/21).

---

## Task breakdown

### Task 1 — Pivot commit and cleanup

**Purpose:** Close out the failed first attempt cleanly so the new work starts from a known state.

**Steps:**
1. Write `PHASE_5_NOTES.md` (already done as part of this plan)
2. Delete `evals/dual_run_validate.py`
3. Delete `_call_llm_with_tools` and `_normalize_tool_args_to_plan` from `src/basic_stats/query_planner.py`
4. Remove `USE_FUNCTION_CALLING` env var logic from `QueryPlanner.__init__`
5. Keep `src/basic_stats/function_tools.py` but replace contents with a one-line deprecation comment (will be rewritten in Task 2 — keeping the file so git history is linear)
6. Verify legacy benchmark still passes: `python evals/eval_runner.py` → 61/61

**Commit:** `chore(FUNC): revert failed function-calling attempt before architecture pivot`

---

### Task 2 — Build the data-layer tools

**Purpose:** Implement the 6 tool categories as thin Python functions. Each function takes typed args, hits DuckDB, returns structured results. No heuristics.

**Files:**
- Create `src/basic_stats/agent_tools.py` — tool function implementations
- Create `src/basic_stats/agent_tool_schemas.py` — OpenAI tool schema definitions (strict mode, flat shapes)
- Create `tests/test_agent_tools.py` — unit tests per tool

**Tool functions to implement:**
- `get_player_stat(player_name: str, stat: str, filters: Filters | None) -> StatResult`
- `get_team_stat(team_name: str, stat: str, filters: Filters | None) -> StatResult`
- `rank_players(stat: str, filters: Filters | None, limit: int, position: str | None, descending: bool) -> RankResult`
- `rank_teams(stat: str, filters: Filters | None, limit: int, descending: bool) -> RankResult`
- `compare_entities(entity_type: Literal["player","team"], entities: list[str], stat: str, filters: Filters | None) -> CompareResult`
- `count_matches_where(entity_type: Literal["player","team"], entity_name: str, conditions: list[Condition], filters: Filters | None) -> StatResult`
- `get_stat_over_window(entity_type, entity_name, stat, last_n_gameweeks, filters) -> StatResult`
- `get_league_standings() -> list[StandingRow]`

**Tool schemas:**
Each schema uses `strict: true`, `additionalProperties: false`, and includes `enum` constraints where the vocabulary is small (positions, entity_type). The full stat vocabulary goes into `stat` field descriptions with examples, not enum (too many values for enum to be ergonomic).

**Unit tests:**
At least 3 test cases per tool: (a) happy path with no filters, (b) with match-level filters, (c) edge case (unknown entity, empty result). No LLM calls in these tests — direct function calls only.

**Commit:** `feat(FUNC-01): add agent data-layer tools with typed schemas and unit tests`

---

### Task 3 — Build the agent loop

**Purpose:** Implement `Agent.ask()` with tool-calling loop, system prompt builder, and message history support (stub for Phase 6).

**Files:**
- Create `src/basic_stats/agent.py` — `Agent` class
- Create `src/basic_stats/agent_prompt.py` — system prompt builder (reads from DuckDB at init)

**`Agent.__init__`:**
1. Connect to DuckDB via `duckdb_manager`
2. Build static domain context: stats list per scope, player names, team names, positions, max matchday, league description paragraph
3. Bake domain context into `self.system_prompt`
4. Register tool schemas and tool function map

**`Agent.ask(question, history=None)`:**
1. Build messages = `[system, *history, user(question)]`
2. Call `llm.chat.completions.create(model, messages, tools, tool_choice="auto")`
3. If response has `tool_calls`:
   - Execute each tool call with the function map
   - Append assistant message + tool result messages
   - Continue loop
4. If response is plain text: return it
5. Safety cap: max 5 iterations. If exceeded, return a clear "I couldn't answer that" message.

**Error handling:**
- Tool raises `ToolError` → tool message has the error text, LLM can retry with different args
- Tool raises unexpected exception → log + return error message from agent
- LLM returns malformed tool call → one retry, then give up

**System prompt structure:**
```
You are a Premier League 2024-25 stats analyst.

DOMAIN CONTEXT
- 20 teams, 38-matchday season, as of matchday {max_matchday}
- Big Six: Arsenal, Chelsea, Liverpool, Manchester City, Manchester United, Tottenham
- Positions: {list from DB}
- Teams: {list from DB}
- Players (short names): {list from DB}

AVAILABLE STATS
{stats grouped by scope, with brief descriptions}

HOW TO ANSWER
- Use tools to fetch data; never invent numbers
- When the user asks for a ranking, call rank_players/rank_teams
- For "top 6 teams" use filters.opponent_rank_max=6
- For "bottom 5 teams" use filters.opponent_rank_min=16
- Write the final answer as a football analyst would — fluent, informative, grounded in the numbers
- If a tool returns an error or empty result, explain what you tried and why it didn't work
```

**Commit:** `feat(FUNC-01): add Agent class with tool-calling loop and static domain prompt`

---

### Task 4 — Build the new eval harness

**Purpose:** Replace the planner-shape benchmark with a 4-category answer-quality benchmark.

**Files:**
- Create `evals/agent_benchmark.py` — new harness entry point
- Create `evals/judges/faithfulness_judge.py` — extracts numbers from text, compares to ground truth
- Create `evals/judges/naturalness_judge.py` — GPT-4 rating prompt
- Create `evals/agent_questions.json` — ported 61 questions + ground-truth SQL
- Create `evals/random_questions.json` — collected from team (one-time collection)

**Faithfulness judge implementation:**
1. Parse agent answer for numeric tokens (integers, decimals, percentages)
2. Run the ground-truth SQL, collect all values
3. For each number in the answer: check whether it matches any value in ground-truth set (exact match or within rounding tolerance)
4. Fail if any number in the answer has no match in ground-truth
5. Edge case: some numbers (e.g., "3 teams", matchday "38") are meta — allow a small whitelist of common integers if not from DB

**Naturalness judge prompt (GPT-4):**
```
You are rating a football stats analyst's answer on naturalness.

Scale:
5 = Fluent analyst voice. Informative, contextual, reads like a human wrote it.
4 = Clear and correct. Slightly dry but still natural.
3 = Correct information in robotic phrasing. Readable but awkward.
2 = Barely natural. Sounds like machine output with some grammar.
1 = Unreadable. JSON dumps, raw column names, broken sentences.

Question: {question}
Answer: {answer}

Return JSON: {"score": int, "rationale": "..."}
```

**Ground-truth SQL per question:**
For each of the 61 questions, write a canonical SQL query in `agent_questions.json`. This is manual one-time work but it gives us a solid oracle. For ambiguous questions (the ones we suspect will be dropped), document the ambiguity.

**Random question collection:**
Don't run this task until we have the questions. Ricardo coordinates with Álvaro and Jorge to collect 7 questions each. Deliver as a simple JSON file. **No ground truth required for random questions** — faithfulness is checked by having the judge run a tool-based verification pass rather than comparing to pre-written SQL.

**Commit:** `feat(FUNC-02): add agent benchmark harness with faithfulness + naturalness judges`

---

### Task 5 — Wire it in, run the benchmarks, ship behind a flag

**Purpose:** Flip Streamlit to use the new agent. Keep legacy planner behind `USE_LEGACY_PLANNER=1` for rollback. Run all four benchmark categories. Commit when green.

**Files:**
- Modify `src/basic_stats/__init__.py` or wherever the entry point lives to default to `Agent`
- Keep `QueryPlanner` importable for the legacy path
- Modify Streamlit app to call `Agent.ask()` by default, falling back to `QueryPlanner` when `USE_LEGACY_PLANNER=1`
- Update `.planning/STATE.md` with Phase 5 completion entry

**Gates (all must pass before commit):**
1. `python evals/agent_benchmark.py --category prepared` → faithfulness >=95%, naturalness avg >=4.0, >=58/61 passing
2. `python evals/agent_benchmark.py --category random` → >=17/21 passing
3. `USE_LEGACY_PLANNER=1 python evals/eval_runner.py` → still 61/61 (rollback path intact)
4. Manual smoke test via Streamlit UI — ask 3 random questions, verify answers

**If a gate fails:**
- Faithfulness < 95%: inspect which numbers were hallucinated, improve system prompt with specific constraints
- Naturalness < 4.0: inspect low-scoring answers, improve system prompt with tone guidance
- Prepared < 58/61: inspect failures, either fix (if tool-level bug) or document the drop (if question is ambiguous)
- Random < 17/21: the real robustness signal — iterate on system prompt and tools, re-run ONCE with a new random set from the team (no unlimited iteration allowed)

**Commit:** `feat(FUNC-02,FUNC-03): ship agent architecture with benchmarked quality gates`

---

## Success criteria (maps to ROADMAP.md Phase 5)

| # | Original criterion | How the rewrite satisfies it |
|---|---|---|
| 1 | `canonicalization_rules.md` exists | Already satisfied (Phase 4) |
| 2 | 4 typed tools with Pydantic schemas | Rewritten as **6–8 tools** with strict OpenAI schemas; Pydantic models used internally for tool returns |
| 3 | All 61 benchmark questions produce identical results via function calling | Rewritten as **>=58/61 faithful + natural answers** (allowing 3 documented drops of ambiguous questions) |
| 4 | Graceful fallback via `use_function_calling` flag | Rewritten as `USE_LEGACY_PLANNER=1` env var (default flips — agent is primary path now) |
| 5 | 61/61 eval_runner.py passes on function calling path | Replaced with agent benchmark gates: faithfulness >=95%, naturalness >=4.0, random >=80% |

**Additional gate not in original plan:** random-question robustness (>=17/21), pulled forward from Phase 8.

---

## Guardrails

1. **No heuristics in tool functions.** If you find yourself writing `if "top 6" in question` inside a tool, stop. That belongs in the system prompt, not in code. Tools take typed args and hit the DB.
2. **No plan-shape tests.** If you find yourself comparing `QueryPlan` objects field-by-field, you're testing the wrong thing. Test the final answer.
3. **No backward-compat with `QueryPlanner.resolve()`.** It's deprecated. Legacy path exists only for emergency rollback, not for gradual migration.
4. **Random questions are collected before running, not after iterating.** The whole point is to measure unprepared robustness. Iterating until random questions pass defeats the purpose.
5. **Naturalness judge bias check.** GPT-4 tends to rate its own writing highly. If we see average naturalness ceiling at 4.8+ suspiciously fast, spot-check with human review.
6. **Token budget awareness.** The agent loop is 3–5x more expensive per question than the planner. Measure cost in Task 5 and document it. If it's above acceptable thresholds, cache the system prompt and reduce tool schema verbosity before optimizing elsewhere.

---

## Execution order summary

| Task | Output | Risk | Gate |
|---|---|---|---|
| 1. Pivot cleanup | Failed attempt reverted, legacy 61/61 intact | Low | 61/61 legacy |
| 2. Data-layer tools | `agent_tools.py` + schemas + unit tests | Low (no LLM) | All unit tests green |
| 3. Agent loop | `agent.py` + system prompt builder | Medium | Manual smoke tests |
| 4. Benchmark harness | `agent_benchmark.py` + judges + ground-truth SQL | Medium | Judges verified on 3 sample answers |
| 5. Ship + gate | Streamlit wired, all gates passing | High | 4 benchmark gates all green |
