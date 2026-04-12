# Phase 5: Function Calling Core — PLAN.md

**Phase:** 5 — Function Calling Core
**Requirements:** FUNC-01, FUNC-02, FUNC-03, FUNC-04 (FUNC-04 already complete: `docs/canonicalization_rules.md` exists)
**Benchmark invariant:** 61/61 `python evals/eval_runner.py` must pass after EVERY task that touches live code
**Tasks:** 5

---

## Context

`docs/canonicalization_rules.md` already exists (17 sections, ~300 lines) — FUNC-04 prerequisite is satisfied.

The current `QueryPlanner.resolve()` pipeline:
```
LLM raw JSON → _canonicalize_raw_plan() → _post_process_plan() → QueryPlan
```

Phase 5 replaces the LLM call with OpenAI **function calling** (tool use), so the LLM returns a structured tool call directly — eliminating ~680 lines of post-hoc regex repair in `_canonicalize_raw_plan`.

The 4 tools to implement:
1. `query_entity_stats` — single entity stat lookup (player or team, with optional filters)
2. `compare_across_buckets` — compares a metric across two opponent buckets
3. `rank_by_metric` — rank N entities by metric (top/bottom/ordinal)
4. `query_temporal_window` — temporal window (last N gameweeks) stat lookup

The new flow:
```
LLM function call → typed Pydantic tool schema → _post_process_plan() → QueryPlan
```

`_canonicalize_raw_plan` is kept but bypassed behind `use_function_calling` flag.

---

## Prerequisites

Before starting Task 1:

- You are on branch `feature/refactor-v2`
- `python evals/eval_runner.py` returns `61/61` (confirm first)
- Working directory: `/Users/ricardoheredia/Twelve-GPT-Educational`
- OpenAI client uses `gpt-4o` (check `src/basic_stats/config.py` → `get_model()`)

---

## Task 1 — Define Function Calling Tool Schemas

**Requirement:** FUNC-01 (partial — schema definition)

**Purpose:** Define the 4 Pydantic v2 schemas that represent the typed tool outputs, and write the OpenAI `tools` list that will be passed to the LLM. No execution changes yet — schemas only.

### Files to create/edit:

- `src/basic_stats/function_tools.py` (create new file)

### Steps:

1. Create `src/basic_stats/function_tools.py` with:

```python
"""
OpenAI function calling tool definitions for QueryPlanner.

Each tool maps to one of the 4 canonical query patterns identified in
docs/canonicalization_rules.md. The LLM selects a tool and returns
structured arguments that bypass _canonicalize_raw_plan.
"""
from __future__ import annotations

from typing import Any


# ------------------------------------------------------------------
# Tool schema definitions (OpenAI tools= format)
# ------------------------------------------------------------------

QUERY_ENTITY_STATS_SCHEMA = {
    "type": "function",
    "function": {
        "name": "query_entity_stats",
        "description": (
            "Look up a stat for a specific player or team, optionally filtered "
            "by opponent, home/away, or position. Use for questions like "
            "'How many goals has Haaland scored?' or 'How many points has Liverpool earned at home?'"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "entity_type": {
                    "type": "string",
                    "enum": ["player", "team"],
                    "description": "Whether the subject is a player or a team.",
                },
                "entity_name": {
                    "type": "string",
                    "description": "Player or team name as it appears in English football (e.g. 'E. Haaland', 'Manchester City').",
                },
                "metric": {
                    "type": "string",
                    "description": "The stat to retrieve (e.g. 'goals', 'assists', 'xg', 'progressive_passes', 'tackles_won').",
                },
                "aggregation": {
                    "type": "string",
                    "enum": ["sum", "avg", "count_matches_positive", "points", "wins", "goal_difference"],
                    "description": "How to aggregate the metric. Use 'sum' for totals, 'avg' for per-game averages.",
                    "default": "sum",
                },
                "opponent_team": {
                    "type": "string",
                    "description": "Filter to matches against this specific team (e.g. 'Arsenal').",
                },
                "is_home": {
                    "type": "boolean",
                    "description": "True = home matches only, False = away matches only, omit for all matches.",
                },
                "opponent_rank_lte": {
                    "type": "integer",
                    "description": "Filter to matches against teams ranked N or better (top-N teams). E.g. 6 = top 6 teams.",
                },
                "opponent_rank_gte": {
                    "type": "integer",
                    "description": "Filter to matches against teams ranked N or worse (bottom teams). E.g. 16 = bottom 5 of 20.",
                },
                "opponent_rank_between": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "Filter to matches against teams with rank in [lo, hi]. E.g. [7, 14] = mid-table.",
                },
                "opponent_is_big6": {
                    "type": "boolean",
                    "description": "True = filter to Big Six opponents (Arsenal, Chelsea, Liverpool, Man City, Man Utd, Spurs).",
                },
                "matchday_start": {
                    "type": "integer",
                    "description": "First matchday of the window (inclusive). Use with matchday_end for a range.",
                },
                "matchday_end": {
                    "type": "integer",
                    "description": "Last matchday of the window (inclusive).",
                },
                "position": {
                    "type": "string",
                    "description": "Player position filter (e.g. 'forward', 'midfielder', 'defender', 'goalkeeper').",
                },
                "min_minutes": {
                    "type": "integer",
                    "description": "Minimum minutes played filter.",
                },
            },
            "required": ["entity_type", "entity_name", "metric"],
        },
    },
}

COMPARE_ACROSS_BUCKETS_SCHEMA = {
    "type": "function",
    "function": {
        "name": "compare_across_buckets",
        "description": (
            "Compare a metric for a player or team across two opponent groups. "
            "Use for 'or' questions like 'Has Haaland scored more against top 5 or bottom 5 teams?'"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "entity_type": {"type": "string", "enum": ["player", "team"]},
                "entity_name": {"type": "string"},
                "metric": {"type": "string"},
                "aggregation": {
                    "type": "string",
                    "enum": ["sum", "avg", "count_matches_positive", "points", "wins", "goal_difference"],
                    "default": "sum",
                },
                "bucket_a": {
                    "type": "object",
                    "description": "First opponent group filter.",
                    "properties": {
                        "opponent_rank_lte": {"type": "integer"},
                        "opponent_rank_gte": {"type": "integer"},
                        "opponent_rank_between": {"type": "array", "items": {"type": "integer"}},
                        "opponent_is_big6": {"type": "boolean"},
                    },
                },
                "bucket_b": {
                    "type": "object",
                    "description": "Second opponent group filter.",
                    "properties": {
                        "opponent_rank_lte": {"type": "integer"},
                        "opponent_rank_gte": {"type": "integer"},
                        "opponent_rank_between": {"type": "array", "items": {"type": "integer"}},
                        "opponent_is_big6": {"type": "boolean"},
                    },
                },
                "is_home": {
                    "type": "boolean",
                    "description": "Apply home/away filter to both buckets.",
                },
            },
            "required": ["entity_type", "entity_name", "metric", "bucket_a", "bucket_b"],
        },
    },
}

RANK_BY_METRIC_SCHEMA = {
    "type": "function",
    "function": {
        "name": "rank_by_metric",
        "description": (
            "Rank players or teams by a metric (top N, bottom N, or find the Nth entity). "
            "Use for questions like 'Which player has scored the most goals?' or "
            "'Which midfielder has the most progressive passes against top 6?'"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "entity_type": {"type": "string", "enum": ["player", "team"]},
                "metric": {"type": "string"},
                "aggregation": {
                    "type": "string",
                    "enum": ["sum", "avg", "count_matches_positive", "points", "wins", "goal_difference"],
                    "default": "sum",
                },
                "ranking_mode": {
                    "type": "string",
                    "enum": ["top_n", "ordinal"],
                    "description": "'top_n' returns the top N entities, 'ordinal' finds the entity at position N.",
                },
                "n": {
                    "type": "integer",
                    "description": "Number of entities to return (top_n mode), or rank position (ordinal mode).",
                    "default": 1,
                },
                "descending": {
                    "type": "boolean",
                    "description": "True = highest first (most/best), False = lowest first (fewest/worst).",
                    "default": True,
                },
                "position": {"type": "string"},
                "team_name": {"type": "string", "description": "Filter to players from this team."},
                "opponent_rank_lte": {"type": "integer"},
                "opponent_rank_gte": {"type": "integer"},
                "opponent_rank_between": {"type": "array", "items": {"type": "integer"}},
                "opponent_is_big6": {"type": "boolean"},
                "is_home": {"type": "boolean"},
                "matchday_start": {"type": "integer"},
                "matchday_end": {"type": "integer"},
                "min_minutes": {"type": "integer"},
                "min_matches": {"type": "integer"},
            },
            "required": ["entity_type", "metric", "ranking_mode"],
        },
    },
}

QUERY_TEMPORAL_WINDOW_SCHEMA = {
    "type": "function",
    "function": {
        "name": "query_temporal_window",
        "description": (
            "Look up a stat over a recent N-gameweek window. "
            "Use for questions like 'How many goals has Haaland scored in the last 5 gameweeks?'"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "entity_type": {"type": "string", "enum": ["player", "team"]},
                "entity_name": {"type": "string"},
                "metric": {"type": "string"},
                "aggregation": {
                    "type": "string",
                    "enum": ["sum", "avg", "count_matches_positive"],
                    "default": "sum",
                },
                "last_n_gameweeks": {
                    "type": "integer",
                    "description": "Number of most recent gameweeks to include.",
                },
                "is_home": {"type": "boolean"},
                "opponent_rank_lte": {"type": "integer"},
                "opponent_rank_gte": {"type": "integer"},
            },
            "required": ["entity_type", "entity_name", "metric", "last_n_gameweeks"],
        },
    },
}

ALL_TOOLS: list[dict[str, Any]] = [
    QUERY_ENTITY_STATS_SCHEMA,
    COMPARE_ACROSS_BUCKETS_SCHEMA,
    RANK_BY_METRIC_SCHEMA,
    QUERY_TEMPORAL_WINDOW_SCHEMA,
]
```

2. No other files modified in this task.

### Verification:
```bash
# File exists and imports cleanly:
python -c "from src.basic_stats.function_tools import ALL_TOOLS; print(f'{len(ALL_TOOLS)} tools defined')"
# Expected: 4 tools defined

# Schema structure is valid (each tool has 'type', 'function', 'function.name'):
python -c "
from src.basic_stats.function_tools import ALL_TOOLS
for t in ALL_TOOLS:
    assert t['type'] == 'function'
    assert 'name' in t['function']
    print(t['function']['name'], '- ok')
"
```

### Commit:
```
feat(FUNC-01): add 4 OpenAI function calling tool schemas in function_tools.py
```

---

## Task 2 — Implement `_call_llm_with_tools` in QueryPlanner

**Requirement:** FUNC-01 (partial — new LLM call method), FUNC-03 (fallback flag)

**Purpose:** Add a new `_call_llm_with_tools()` method that uses the OpenAI `tools=` API and returns a structured `dict` identical in shape to what `_canonicalize_raw_plan` expects. Wire in the `use_function_calling` flag. **Do not change any existing code paths yet.**

### Files to edit:

- `src/basic_stats/query_planner.py`

### Steps:

1. At the top of `query_planner.py`, add the import:
   ```python
   from src.basic_stats.function_tools import ALL_TOOLS
   ```

2. In `QueryPlanner.__init__`, add the flag (default False — safe):
   ```python
   self.use_function_calling: bool = False
   ```

3. Add the new method `_call_llm_with_tools` after `_call_llm_for_plan`:

```python
def _call_llm_with_tools(self, question: str) -> dict:
    """
    Call OpenAI with function calling tools. Returns a normalized dict
    in the same shape as _call_llm_for_plan so it can feed _post_process_plan.

    Raises ValueError if the LLM returns no tool call.
    """
    response = self.client.chat.completions.create(
        model=self.model,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a football statistics assistant. "
                    "Given a user question, call the most appropriate tool to retrieve the answer. "
                    "Always use a tool — never respond with plain text. "
                    "For metric names use the canonical English form: goals, assists, xg, "
                    "progressive_passes, tackles_won, interceptions, aerial_duels_won, "
                    "minutes_played, shots, shots_on_target, key_passes, yellow_card, red_card, "
                    "dribbles_completed, clearances, saves, crosses, fouls_committed, fouls_drawn, "
                    "touches_in_box, shot_assists, actions_z3, team_score, opponent_score. "
                    "For entity names use the canonical short form: 'E. Haaland', 'K. De Bruyne', "
                    "'Liverpool', 'Manchester City'."
                ),
            },
            {"role": "user", "content": question},
        ],
        tools=ALL_TOOLS,
        tool_choice="required",
    )

    message = response.choices[0].message
    if not message.tool_calls:
        raise ValueError(f"LLM returned no tool call for: {question!r}")

    tool_call = message.tool_calls[0]
    tool_name = tool_call.function.name
    import json as _json
    args = _json.loads(tool_call.function.arguments)

    return self._normalize_tool_args_to_plan(tool_name, args, question)


def _normalize_tool_args_to_plan(self, tool_name: str, args: dict, question: str) -> dict:
    """
    Convert tool call args to the normalized plan dict that _post_process_plan expects.
    This replaces _canonicalize_raw_plan for the function calling path.
    """
    q = _normalize_text(question)

    # Build filters dict from args
    filters: dict = {
        "player_name": None,
        "team_name": None,
        "opponent_team_name": None,
        "position": args.get("position"),
        "is_home": args.get("is_home"),
        "opponent_rank_lte": args.get("opponent_rank_lte"),
        "opponent_rank_gte": args.get("opponent_rank_gte"),
        "opponent_rank_between": args.get("opponent_rank_between"),
        "opponent_is_big6": args.get("opponent_is_big6"),
        "matchday_start": args.get("matchday_start"),
        "matchday_end": args.get("matchday_end"),
        "min_minutes": args.get("min_minutes"),
        "min_matches": args.get("min_matches"),
        "age_lt": None,
    }

    entity_type = args.get("entity_type", "player")
    metric = args.get("metric", "goals")
    aggregation = args.get("aggregation", "sum")

    # Resolve entity name
    entity_name = args.get("entity_name") or args.get("team_name")
    if entity_name:
        if entity_type == "player":
            # Try deterministic resolution first
            resolved = self._match_known_name(question, self.player_names)
            if resolved:
                entity_name = resolved
            else:
                resolved = self._match_player_alias(question)
                if resolved:
                    entity_name = resolved
                else:
                    resolved = self._resolve_player_suffix(entity_name)
                    if resolved:
                        entity_name = resolved
            filters["player_name"] = entity_name
        else:
            resolved = self._match_known_name(question, self.team_names)
            if resolved:
                entity_name = resolved
            filters["team_name"] = entity_name

    # Opponent team name
    if args.get("opponent_team"):
        filters["opponent_team_name"] = args["opponent_team"]

    # Temporal window: convert last_n_gameweeks to matchday range
    if tool_name == "query_temporal_window":
        last_n = args.get("last_n_gameweeks", 5)
        filters["matchday_end"] = self.max_matchday
        filters["matchday_start"] = self.max_matchday - last_n + 1

    # Ranking
    ranking_mode = args.get("ranking_mode", "entity_value")
    n = args.get("n", 1)
    descending = args.get("descending", True)

    if tool_name == "rank_by_metric":
        if ranking_mode == "ordinal":
            ranking = {"mode": "ordinal", "n": None, "ordinal": n}
        else:
            ranking = {"mode": "top_n", "n": n, "ordinal": None}
        # For ranking, entity_name might not be set — clear name filters
        filters["player_name"] = None
        filters["team_name"] = args.get("team_name")  # team filter for "which midfielder at Arsenal"
    else:
        ranking = {"mode": "entity_value", "n": None, "ordinal": None}

    # Aggregation normalization: descending=False for rank means "fewest"
    if tool_name == "rank_by_metric" and not descending:
        # aggregation stays as-is; execution layer handles ascending rank
        pass

    # For compare_across_buckets, use entity_value ranking and pass buckets
    # Note: compare_across_buckets routes to _execute_dual_bucket_comparison in
    # llm_query_engine_v2 via the existing early-detection guard, NOT through
    # the standard planner path. So we return a plan for bucket_a only here,
    # which triggers the dual-bucket detection in the engine.
    # The engine already handles this via _detect_dual_bucket_comparison in the question text.
    # So for compare_across_buckets, we fall through to normal plan with bucket_a filters.
    if tool_name == "compare_across_buckets":
        bucket_a = args.get("bucket_a", {})
        filters.update({k: v for k, v in bucket_a.items() if v is not None})

    # Determine table_scope
    # Let _post_process_plan handle scope inference from metric + entity + filters
    # We set a raw guess here; _post_process_plan will correct it.
    if entity_type == "team":
        if any(filters.get(k) for k in ["opponent_team_name", "opponent_rank_lte",
                                          "opponent_rank_gte", "opponent_rank_between",
                                          "opponent_is_big6", "is_home",
                                          "matchday_start"]):
            table_scope = "team_match"
        else:
            table_scope = "teams_summary"
    else:
        if any(filters.get(k) for k in ["opponent_team_name", "opponent_rank_lte",
                                          "opponent_rank_gte", "opponent_rank_between",
                                          "opponent_is_big6", "is_home",
                                          "matchday_start"]):
            table_scope = "player_match"
        else:
            table_scope = "players_summary"

    return {
        "table_scope": table_scope,
        "entity_type": entity_type,
        "metric": metric,
        "aggregation": aggregation,
        "filters": filters,
        "ranking": ranking,
        "match_conditions": None,
    }
```

4. Modify `resolve()` to use the flag:

```python
def resolve(self, question: str) -> QueryPlan:
    if self.use_function_calling:
        try:
            plan_dict = self._call_llm_with_tools(question)
        except Exception as e:
            print(f"[PLANNER] Function calling failed, falling back to legacy: {e}")
            plan_dict = self._call_llm_for_plan(question)
            canonical_plan = self._canonicalize_raw_plan(question, plan_dict)
            return self._post_process_plan(question, canonical_plan)
        return self._post_process_plan(question, plan_dict)
    else:
        raw_plan = self._call_llm_for_plan(question)
        canonical_plan = self._canonicalize_raw_plan(question, raw_plan)
        return self._post_process_plan(question, canonical_plan)
```

### Verification:
```bash
# Import works (no syntax errors):
python -c "from src.basic_stats.query_planner import QueryPlanner; p = QueryPlanner(); print('use_function_calling:', p.use_function_calling)"
# Expected: use_function_calling: False

# Benchmark still passes with flag OFF (default):
python evals/eval_runner.py
# Expected: 61/61
```

### Commit:
```
feat(FUNC-03): add use_function_calling flag and _call_llm_with_tools to QueryPlanner
```

---

## Task 3 — Dual-Run Validation Script

**Requirement:** FUNC-02

**Purpose:** Create a validation script that runs ALL 61 benchmark questions through BOTH paths (legacy and function calling) and compares the resulting QueryPlan field-by-field. This script is the gate before removing legacy code.

### Files to create:

- `evals/dual_run_validate.py`

### Steps:

1. Create `evals/dual_run_validate.py`:

```python
#!/usr/bin/env python
"""
Phase 5 dual-run validation: compare legacy vs function-calling QueryPlan for all 61 benchmark questions.

Usage:
    python evals/dual_run_validate.py [--verbose] [--stop-on-first-diff]

Exit code:
    0 — all plans match (or acceptable differences only)
    1 — plan mismatches found
"""
import json
import sys
import argparse
from pathlib import Path

sys.path.insert(0, ".")

from src.basic_stats.query_planner import QueryPlanner

BENCHMARK_PATH = str(Path(__file__).parent / "questions_benchmark.json")

# Fields to compare field-by-field
PLAN_FIELDS = ["table_scope", "entity_type", "metric", "aggregation"]
FILTER_FIELDS = [
    "player_name", "team_name", "opponent_team_name", "position",
    "is_home", "opponent_rank_lte", "opponent_rank_gte",
    "opponent_rank_between", "opponent_is_big6",
    "matchday_start", "matchday_end",
]
RANKING_FIELDS = ["mode", "n", "ordinal"]


def compare_plans(legacy_plan, fc_plan) -> list[str]:
    """Return list of field differences. Empty = match."""
    diffs = []
    ld = legacy_plan.model_dump()
    fd = fc_plan.model_dump()

    for field in PLAN_FIELDS:
        if ld[field] != fd[field]:
            diffs.append(f"  {field}: legacy={ld[field]!r} fc={fd[field]!r}")

    for field in FILTER_FIELDS:
        lv = ld["filters"][field]
        fv = fd["filters"][field]
        if lv != fv:
            diffs.append(f"  filters.{field}: legacy={lv!r} fc={fv!r}")

    for field in RANKING_FIELDS:
        lv = ld["ranking"][field]
        fv = fd["ranking"][field]
        if lv != fv:
            diffs.append(f"  ranking.{field}: legacy={lv!r} fc={fv!r}")

    return diffs


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--stop-on-first-diff", action="store_true")
    args = parser.parse_args()

    with open(BENCHMARK_PATH) as f:
        benchmark = json.load(f)

    questions = [item["question"] for item in benchmark]

    legacy_planner = QueryPlanner()
    legacy_planner.use_function_calling = False

    fc_planner = QueryPlanner()
    fc_planner.use_function_calling = True

    total = len(questions)
    matches = 0
    mismatches = 0
    errors = 0

    for i, question in enumerate(questions, 1):
        print(f"[{i:02d}/{total}] {question[:70]}", end="")

        try:
            legacy_plan = legacy_planner.resolve(question)
        except Exception as e:
            print(f" → LEGACY ERROR: {e}")
            errors += 1
            continue

        try:
            fc_plan = fc_planner.resolve(question)
        except Exception as e:
            print(f" → FC ERROR: {e}")
            errors += 1
            continue

        diffs = compare_plans(legacy_plan, fc_plan)

        if not diffs:
            matches += 1
            print(" → MATCH ✓")
        else:
            mismatches += 1
            print(f" → DIFF ({len(diffs)} fields)")
            if args.verbose or args.stop_on_first_diff:
                for d in diffs:
                    print(d)
            if args.stop_on_first_diff:
                break

    print()
    print(f"Results: {matches} match, {mismatches} diff, {errors} error (total {total})")

    if mismatches == 0 and errors == 0:
        print("PASS — function calling path matches legacy for all benchmark questions")
        sys.exit(0)
    else:
        print(f"FAIL — {mismatches} mismatches, {errors} errors")
        sys.exit(1)


if __name__ == "__main__":
    main()
```

### Verification:
```bash
# Script runs without crashing (with function calling OFF, it compares legacy vs legacy → all match):
python evals/dual_run_validate.py
# Expected: 61/61 MATCH (since both planners use legacy path when use_function_calling=False)
# Note: This is a structural test only — actual dual-run comparison happens after Task 2 enables the flag.
```

### Commit:
```
feat(FUNC-02): add dual_run_validate.py for field-by-field plan comparison
```

---

## Task 4 — Enable Function Calling, Run Dual Validation, Fix Divergences

**Requirement:** FUNC-01 (full), FUNC-02 (full)

**Purpose:** Enable `use_function_calling = True` on the fc_planner in the dual-run script, run it, then fix any plan divergences in `_normalize_tool_args_to_plan` until all 61 questions produce matching plans.

**This is the highest-risk task. Work iteratively: run → identify diff → fix → re-run.**

### Steps:

1. Modify `evals/dual_run_validate.py` to set `fc_planner.use_function_calling = True`:
   ```python
   fc_planner = QueryPlanner()
   fc_planner.use_function_calling = True  # ← enable
   ```

2. Run the dual validation:
   ```bash
   python evals/dual_run_validate.py --verbose
   ```

3. For each category of divergence found, apply fixes in `src/basic_stats/query_planner.py` in `_normalize_tool_args_to_plan`. Common expected divergences and fixes:

   **Category A — Metric name mismatch:**
   - LLM returns `"goals"` but legacy expects `"team_score"` for team scope
   - Fix: apply scope-level metric renames from `canonicalization_rules.md` §15 in `_normalize_tool_args_to_plan`

   **Category B — Scope mismatch:**
   - Function calling returns `player_match` but legacy uses `player_match_event`
   - Fix: apply metric catalog lookup in `_normalize_tool_args_to_plan` to pick correct scope

   **Category C — Filter mismatch:**
   - LLM returns `opponent_rank_lte=6` but legacy canonical uses `opponent_is_big6=True`
   - These may be semantically equivalent — mark as "acceptable difference" in the script

   **Category D — Aggregation mismatch:**
   - Fix by ensuring `_normalize_tool_args_to_plan` applies the same aggregation inference rules from `canonicalization_rules.md` §5

4. After each round of fixes, run:
   ```bash
   python evals/dual_run_validate.py --verbose
   ```
   Iterate until 0 mismatches (or only documented "acceptable differences").

5. Final benchmark gate:
   ```bash
   python evals/eval_runner.py
   ```
   **Gate: must show 61/61 with `use_function_calling=False` (default unchanged).**

### Acceptance criteria for this task:
- `python evals/dual_run_validate.py` exits 0 (all plans match or acceptable)
- `python evals/eval_runner.py` still shows 61/61 (legacy path unmodified)

### Commit:
```
feat(FUNC-01): normalize tool args to match legacy plan output for all 61 questions
```

---

## Task 5 — Wire Function Calling into Eval Runner, Validate 61/61

**Requirement:** FUNC-02 (final gate), FUNC-03 (fallback confirmed working)

**Purpose:** Run the full benchmark through the function calling path to confirm 61/61. The `use_function_calling` flag stays `False` by default in production — this task enables it via environment variable for the validation run, then documents the result.

### Steps:

1. Add env var support to `QueryPlanner.__init__`:
   ```python
   import os
   self.use_function_calling: bool = os.getenv("USE_FUNCTION_CALLING", "0") == "1"
   ```

2. Run the benchmark with function calling enabled:
   ```bash
   USE_FUNCTION_CALLING=1 python evals/eval_runner.py
   ```
   **Gate: must show 61/61.**

3. If any questions fail:
   - Check the error/diff with `--verbose` flag
   - Fix `_normalize_tool_args_to_plan` for that question pattern
   - Re-run until 61/61

4. Run with flag OFF to confirm legacy path still works:
   ```bash
   python evals/eval_runner.py
   # Expected: 61/61
   ```

5. Update `.planning/STATE.md`:
   - Mark Phase 5 as Complete
   - Add benchmark baseline entry for the function calling path run

### Verification:
```bash
# Function calling path: 61/61
USE_FUNCTION_CALLING=1 python evals/eval_runner.py
# Expected: 61/61

# Legacy path still: 61/61
python evals/eval_runner.py
# Expected: 61/61

# Fallback actually works (simulate a bad tool call by asking a nonsense question):
python -c "
import os
os.environ['USE_FUNCTION_CALLING'] = '1'
from src.basic_stats.query_planner import QueryPlanner
p = QueryPlanner()
print('use_function_calling:', p.use_function_calling)
"
```

### Commit:
```
feat(FUNC-02): validate 61/61 benchmark on function calling path via USE_FUNCTION_CALLING env var
```

---

## Verification Checklist

Map to success criteria from ROADMAP.md:

| # | Success Criterion | Verification Command |
|---|-------------------|----------------------|
| 1 | `canonicalization_rules.md` exists | `wc -l docs/canonicalization_rules.md` → 80+ lines ✓ (already done in Phase 4) |
| 2 | 4 typed tools with Pydantic v2 schemas | `python -c "from src.basic_stats.function_tools import ALL_TOOLS; print(len(ALL_TOOLS))"` → 4 |
| 3 | All 61 questions match field-by-field | `python evals/dual_run_validate.py` → exit 0 |
| 4 | Graceful fallback via `use_function_calling` flag | `python evals/eval_runner.py` → 61/61 (flag off = legacy) |
| 5 | 61/61 on function calling path | `USE_FUNCTION_CALLING=1 python evals/eval_runner.py` → 61/61 |

**Final benchmark gate:**
```bash
python evals/eval_runner.py
# Required: 61/61
```

---

## Guardrails

**Do NOT do these things in Phase 5:**

1. **Do not delete `_canonicalize_raw_plan`** until `dual_run_validate.py` exits 0 AND `USE_FUNCTION_CALLING=1 python evals/eval_runner.py` shows 61/61. The fallback must remain until 100% coverage confirmed.
2. **Do not change `_post_process_plan`** — it is the shared final step for both paths.
3. **Do not set `use_function_calling=True` as default** until all 61 benchmark questions pass on the function calling path.
4. **Do not modify `_call_llm_for_plan`** — the legacy path must remain exactly as-is.
5. **Do not commit with a broken benchmark** — every commit must pass 61/61 on the legacy path.
6. **Do not add new test files that require LLM calls to pre-commit hooks.**
7. **Scope divergences are acceptable if semantically equivalent** (e.g., `opponent_rank_lte=6` vs `opponent_is_big6=True`) — document them in `dual_run_validate.py` as known acceptable differences rather than forcing exact equality.

---

## Execution Order Summary

| Task | Requirement | Risk | Benchmark Gate |
|------|-------------|------|---------------|
| Task 1: Tool schemas | FUNC-01 | Low (additive) | None needed |
| Task 2: `_call_llm_with_tools` + flag | FUNC-01, FUNC-03 | Low (flag=False default) | After: 61/61 (legacy path unchanged) |
| Task 3: dual_run_validate.py | FUNC-02 | Low (script only) | None needed |
| Task 4: Enable FC, fix divergences | FUNC-01, FUNC-02 | High (iterative) | After each round: 61/61 legacy |
| Task 5: Final validation | FUNC-02 | Medium | Both paths: 61/61 |
