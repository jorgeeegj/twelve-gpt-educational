"""
LLMQueryEngine — experimental replacement for MetricResolver + QueryEngine.

Instead of keyword/alias matching, the LLM receives the full column schema
and generates a structured query (JSON). The code executes it deterministically.
"""

import json
import re
from pathlib import Path

import polars as pl
import streamlit as st
from openai import AzureOpenAI


BASE = Path(__file__).resolve().parents[2]
PLAYER_DATA_PATH = BASE / "output" / "player_full_stats.parquet"
TEAM_DATA_PATH = BASE / "output" / "team_full_stats.parquet"

# Only expose columns useful for natural language queries (skip z-scores, internal IDs)
PLAYER_COLS_FOR_SCHEMA = [
    "short_name", "team_name", "main_position", "birth_date",
    "matches_played", "total_minutes",
    "total_goals", "total_assists", "goal_contributions",
    "total_yellow_cards", "total_red_cards",
    "pass_accuracy_pct", "passes_attempted", "passes_accurate",
    "progressive_passes", "forward_passes", "back_passes", "long_passes",
    "key_passes", "crosses", "passes_to_final_third", "passes_to_box",
    "through_passes", "smart_passes",
    "shots", "shots_on_target", "xg_total",
    "aerial_duels", "aerial_duels_won", "aerial_duel_won_pct",
    "defensive_duels", "defensive_duels_won", "defensive_duel_won_pct",
    "offensive_duels", "offensive_duels_won", "offensive_duel_won_pct",
    "dribbles_attempted", "dribbles_won", "dribble_success_pct",
    "recoveries", "interceptions", "clearances", "sliding_tackles",
    "fouls_committed", "fouls_suffered",
    "progressive_carries", "carry_meters_gained", "progressive_runs",
    "touches_in_box", "shot_assists", "ball_losses",
    "saves", "shots_against", "goalkeeper_exits", "reflex_saves",
    # p90 variants for the most common metrics
    "total_goals_p90", "total_assists_p90", "xg_total_p90",
    "aerial_duels_won_p90", "progressive_passes_p90", "key_passes_p90",
    "shots_on_target_p90", "passes_attempted_p90", "recoveries_p90",
    "interceptions_p90", "dribbles_won_p90", "touches_in_box_p90",
]

TEAM_COLS_FOR_SCHEMA = [
    "team_name", "matches_played",
    "total_goals", "total_goals_against", "total_assists",
    "pass_accuracy_pct", "shots_on_target_pct",
    "progressive_passes", "passes_attempted", "passes_accurate",
    "aerial_duels_won", "aerial_duel_won_pct",
    "defensive_duels_won", "defensive_duel_won_pct",
    "xg_total", "shots", "shots_on_target",
    "recoveries", "interceptions", "clearances",
    "fouls_committed", "fouls_suffered",
    "total_goals_p90", "total_goals_against_p90",
]

SCHEMA_TEXT = """
Table: players  (444 rows — Premier League 2024/25 individual player stats)
Key columns:
  Identity:    short_name, team_name, main_position, birth_date
  Playing time: matches_played, total_minutes
  Goals:       total_goals, total_assists, goal_contributions, xg_total
  Discipline:  total_yellow_cards, total_red_cards
  Passing:     pass_accuracy_pct, passes_attempted, passes_accurate,
               progressive_passes, forward_passes, back_passes, long_passes,
               key_passes, crosses, passes_to_final_third, passes_to_box,
               through_passes, smart_passes
  Shooting:    shots, shots_on_target, xg_total
  Aerial:      aerial_duels, aerial_duels_won, aerial_duel_won_pct
  Duels:       defensive_duels, defensive_duels_won, defensive_duel_won_pct,
               offensive_duels, offensive_duels_won, offensive_duel_won_pct
  Dribbles:    dribbles_attempted, dribbles_won, dribble_success_pct
  Defence:     recoveries, interceptions, clearances, sliding_tackles
  Fouls:       fouls_committed, fouls_suffered
  Carrying:    progressive_carries, carry_meters_gained, progressive_runs
  Attacking:   touches_in_box, shot_assists, ball_losses
  Goalkeeping: saves, shots_against, goalkeeper_exits, reflex_saves
  Per-90 variants: add _p90 suffix (e.g. total_goals_p90, aerial_duels_won_p90)

Table: teams  (20 rows — Premier League 2024/25 team aggregates)
Key columns:
  Identity:    team_name, matches_played
  Goals:       total_goals, total_goals_against, total_assists, xg_total
  Shooting:    shots, shots_on_target, shots_on_target_pct
  Passing:     pass_accuracy_pct, passes_attempted, passes_accurate,
               progressive_passes
  Aerial:      aerial_duels_won, aerial_duel_won_pct
  Defence:     defensive_duels_won, defensive_duel_won_pct,
               recoveries, interceptions, clearances
  Fouls:       fouls_committed, fouls_suffered
  Per-90 variants: add _p90 suffix (e.g. total_goals_p90, total_goals_against_p90)
"""

QUERY_SYSTEM_PROMPT = """You are a football data query planner.
Given a natural language question and a database schema, output a JSON query plan.

Rules:
- Choose table "players" or "teams" based on the question.
- sort_by: the exact column name to rank by.
- descending: true for "most/highest/best", false for "fewest/lowest/worst/least".
- filters: list of filter strings in Python/Polars syntax. Examples:
    "main_position.str.to_lowercase().str.contains('midfielder')"
    "matches_played >= 10"
    "total_minutes >= 900"
    "birth_date < '2002-08-01'"   (for players under 23 as of season start 2024-08-01)
- top_n: number of results (default 1, use question context).
- Use _p90 column variant when question says "per 90", "per game rate", or "p90".
- Output ONLY valid JSON with keys: table, sort_by, descending, filters, top_n.
"""


class LLMQueryEngine:
    def __init__(self):
        self.players_df = pl.read_parquet(PLAYER_DATA_PATH)
        self.teams_df = pl.read_parquet(TEAM_DATA_PATH)

        if "goal_contributions" not in self.players_df.columns:
            if {"total_goals", "total_assists"}.issubset(set(self.players_df.columns)):
                self.players_df = self.players_df.with_columns(
                    (pl.col("total_goals") + pl.col("total_assists")).alias("goal_contributions")
                )

        self.client = AzureOpenAI(
            api_key=st.secrets["GPT_KEY"],
            api_version=st.secrets["GPT_VERSION"],
            azure_endpoint="https://twelve-courses.openai.azure.com",
        )
        self.model = st.secrets["GPT_CHAT_MODEL"]

    def _plan_query(self, question: str) -> dict | None:
        """Ask LLM to produce a structured query plan from the question."""
        user_prompt = f"""Schema:
{SCHEMA_TEXT}

Question: {question}

Return ONLY a JSON object with keys: table, sort_by, descending, filters, top_n.
"""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": QUERY_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        )
        raw = response.choices[0].message.content.strip()
        # Strip markdown code fences if present
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None

    def _execute_plan(self, plan: dict) -> dict | None:
        """Execute the query plan against the appropriate dataframe."""
        table = plan.get("table", "players")
        sort_by = plan.get("sort_by")
        descending = plan.get("descending", True)
        filters = plan.get("filters", [])
        top_n = plan.get("top_n", 1)

        df = self.players_df if table == "players" else self.teams_df

        # Validate sort_by column exists
        if sort_by not in df.columns:
            return {"error": f"Column '{sort_by}' not found in {table} table."}

        # Apply filters
        for f in filters:
            try:
                df = df.filter(eval(f"pl.col({f!r})" if "." not in f else f, {"pl": pl, "df": df}))
            except Exception:
                # If a filter fails, skip it rather than crash
                pass

        # Sort and take top_n
        sorted_df = df.sort(sort_by, descending=descending, nulls_last=True)
        top_df = sorted_df.head(top_n)

        # For top_n=1, include all tied rows
        if top_n == 1:
            boundary = top_df[sort_by][-1]
            top_df = sorted_df.filter(pl.col(sort_by) == boundary)

        # Select display columns
        if table == "players":
            display_cols = ["short_name", "team_name", "main_position", sort_by, "matches_played", "total_minutes"]
        else:
            display_cols = ["team_name", sort_by, "total_goals", "total_goals_against"]

        display_cols = [c for c in display_cols if c in df.columns]
        # Deduplicate preserving order
        seen = set()
        display_cols = [c for c in display_cols if not (c in seen or seen.add(c))]

        result_df = top_df.select(display_cols)

        # Round floats
        result_df = result_df.with_columns([
            pl.col(c).round(2)
            for c, t in zip(result_df.columns, result_df.dtypes)
            if t in (pl.Float64, pl.Float32)
        ])

        return {
            "table": table,
            "sort_by": sort_by,
            "result_df": result_df,
            "plan": plan,
        }

    def _verbalize(self, question: str, execution: dict) -> str:
        """Ask LLM to verbalize the result."""
        rows = execution["result_df"].to_dicts()

        prompt = f"""You are a football data analyst.
Answer the user's question using ONLY the data below.
Do not invent numbers. Use exact values. Round decimals to 2 places.
Do not use bullet points. Write one concise sentence.
If the result is a single player, mention name, team, and the metric value.
The first row in the data is the correct answer — lead with it.

Question: {question}
Metric used: {execution["sort_by"]}
Data: {rows}
"""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "Answer strictly from the provided data. Never invent facts."},
                {"role": "user", "content": prompt},
            ],
        )
        return response.choices[0].message.content.strip()

    def ask(self, question: str) -> dict:
        plan = self._plan_query(question)

        if plan is None:
            return {
                "type": "text",
                "content": "I couldn't generate a query plan for that question.",
                "debug": {"error": "plan_parse_failed"},
            }

        execution = self._execute_plan(plan)

        if execution is None or "error" in execution:
            return {
                "type": "text",
                "content": f"Query planning failed: {execution.get('error') if execution else 'unknown'}",
                "debug": {"plan": plan, "error": execution},
            }

        answer = self._verbalize(question, execution)

        return {
            "type": "text",
            "content": answer,
            "debug": {
                "plan": plan,
                "metric": execution["sort_by"],
                "table": execution["table"],
                "rows": execution["result_df"].to_dicts(),
            },
        }
