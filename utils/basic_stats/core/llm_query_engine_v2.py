"""
LLMQueryEngine v2 — hybrid deterministic + generative.

LLM (tool use)   → resolves metric column from question (constrained to real columns)
Code             → applies all filters deterministically (your ground truth)
LLM (verbalize)  → writes final sentence from grounded data
"""

import json
import re
from pathlib import Path

import polars as pl
import yaml

from utils.basic_stats.core.config import (
    PLAYER_DATA_PATH,
    TEAM_DATA_PATH,
    PROMPTS_DIR,
    get_llm_client,
    get_model,
)
from utils.basic_stats.core.models import MetricResolution, QueryResult


# ── Columns exposed to the LLM (no z-scores, no internal IDs) ──────────────
PLAYER_COLS = [
    "total_goals", "total_assists", "goal_contributions", "xg_total",
    "total_yellow_cards", "total_red_cards", "total_minutes", "matches_played",
    "pass_accuracy_pct", "passes_attempted", "passes_accurate",
    "progressive_passes", "forward_passes", "back_passes", "long_passes",
    "key_passes", "crosses", "passes_to_final_third", "passes_to_box",
    "through_passes", "smart_passes", "shots", "shots_on_target",
    "aerial_duels", "aerial_duels_won", "aerial_duel_won_pct",
    "defensive_duels", "defensive_duels_won", "defensive_duel_won_pct",
    "offensive_duels", "offensive_duels_won", "offensive_duel_won_pct",
    "dribbles_attempted", "dribbles_won", "dribble_success_pct",
    "recoveries", "interceptions", "clearances", "sliding_tackles",
    "fouls_committed", "fouls_suffered", "progressive_carries",
    "carry_meters_gained", "progressive_runs", "touches_in_box",
    "shot_assists", "ball_losses", "saves", "shots_against",
    "goalkeeper_exits", "reflex_saves",
    "total_goals_p90", "total_assists_p90", "xg_total_p90",
    "aerial_duels_won_p90", "progressive_passes_p90", "key_passes_p90",
    "shots_on_target_p90", "recoveries_p90", "interceptions_p90",
    "dribbles_won_p90", "touches_in_box_p90", "fouls_committed_p90",
    "shot_assists_p90", "clearances_p90",
]

TEAM_COLS = [
    "total_goals", "total_goals_against", "total_assists", "xg_total",
    "pass_accuracy_pct", "shots_on_target_pct", "progressive_passes",
    "passes_attempted", "aerial_duels_won", "aerial_duel_won_pct",
    "defensive_duels_won", "shots", "shots_on_target",
    "recoveries", "interceptions", "clearances", "fouls_committed", "fouls_suffered",
    "total_goals_p90", "total_goals_against_p90",
    "key_passes_p90", "progressive_passes_p90", "offsides",
]

POSITION_MAP = {
    "attacking midfielder": "attacking midfielder|am|cam",
    "central defender":     "central defender|cb",
    "goalkeepers":          "goalkeeper|gk",
    "goalkeeper":           "goalkeeper|gk",
    "midfielders":          "midfielder|cm|dm|am",
    "midfielder":           "midfielder|cm|dm|am",
    "defenders":            "central defender|full back|cb|lb|rb|wb|back|def",
    "defender":             "central defender|full back|cb|lb|rb|wb|back|def",
    "full back":            "full back|lb|rb|wb",
    "forwards":             "striker|winger|cf|st|lw|rw|forward",
    "forward":              "striker|winger|cf|st|lw|rw|forward",
    "strikers":             "striker|cf|st|forward",
    "striker":              "striker|cf|st|forward",
    "wingers":              "winger|lw|rw",
    "winger":               "winger|lw|rw",
}


def _load_prompt(name: str) -> dict:
    return yaml.safe_load((PROMPTS_DIR / f"{name}.yaml").read_text())


def _extract(pattern: str, text: str) -> int | None:
    m = re.search(pattern, text.lower())
    return int(m.group(1)) if m else None


class LLMQueryEngineV2:
    def __init__(self):
        self.players_df = pl.read_parquet(PLAYER_DATA_PATH)
        self.teams_df   = pl.read_parquet(TEAM_DATA_PATH)

        if "goal_contributions" not in self.players_df.columns:
            self.players_df = self.players_df.with_columns(
                (pl.col("total_goals") + pl.col("total_assists")).alias("goal_contributions")
            )

        self.client = get_llm_client()
        self.model  = get_model()

        # Constrain enums to columns that actually exist in the parquets
        self._player_enum = [c for c in PLAYER_COLS if c in self.players_df.columns]
        self._team_enum   = [c for c in TEAM_COLS   if c in self.teams_df.columns]

        self._resolve_prompt   = _load_prompt("resolve_metric")
        self._verbalize_prompt = _load_prompt("verbalize")

    #Helper determinista para preguntas muy simples 
    def _resolve_fast_path(self, q: str) -> MetricResolution | None:
        # player basics
        if "most minutes" in q or "played the most minutes" in q or "most total minutes" in q:
            return MetricResolution(metric="total_minutes", descending=True, table="players")

        if "most assists" in q:
            return MetricResolution(metric="total_assists", descending=True, table="players")

        if "most yellow cards" in q or "received the most yellow cards" in q:
            return MetricResolution(metric="total_yellow_cards", descending=True, table="players")

        # player / team goals
        if "most goals" in q and "team" not in q:
            return MetricResolution(metric="total_goals", descending=True, table="players")

        if "most goals" in q and "team" in q:
            return MetricResolution(metric="total_goals", descending=True, table="teams")

        # team basics
        if (
            "fewest goals conceded" in q
            or "conceded the fewest" in q
            or "fewest conceded goals" in q
        ):
            return MetricResolution(metric="total_goals_against", descending=False, table="teams")

        
        

        if "provokes the most offsides" in q or "most offsides" in q:
            return MetricResolution(metric="offsides", descending=True, table="teams")

        return None

    # ── Step 1: LLM resolves metric via tool use ────────────────────────────

    def _resolve_metric(self, question: str) -> MetricResolution:
        col_descriptions = self._resolve_prompt["column_descriptions"]

        q = question.lower()

        fast = self._resolve_fast_path(q)
        if fast:
            return fast
        

        def _tool(name: str, enum: list[str]) -> dict:
            return {
                "type": "function",
                "function": {
                    "name": name,
                    "description": self._resolve_prompt["tools"][name]["description"],
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "metric": {
                                "type": "string",
                                "enum": enum,
                                "description": "\n".join(
                                    f"{c}: {col_descriptions[c]}"
                                    for c in enum if c in col_descriptions
                                ),
                            },
                            "descending": {"type": "boolean"},
                        },
                        "required": ["metric", "descending"],
                    },
                },
            }

        tools = [_tool("query_players", self._player_enum), _tool("query_teams", self._team_enum)]

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self._resolve_prompt["system"]},
                {"role": "user",   "content": question},
            ],
            tools=tools,
            tool_choice="required",
        )

        call  = response.choices[0].message.tool_calls[0]
        args  = json.loads(call.function.arguments)
        table = "players" if call.function.name == "query_players" else "teams"
        return MetricResolution(metric=args["metric"], descending=args["descending"], table=table)

    # ── Step 2: Code applies deterministic filters ──────────────────────────

    def _execute(self, question: str, resolution: MetricResolution) -> QueryResult:
        df      = self.players_df if resolution.table == "players" else self.teams_df
        q       = question.lower()
        filters = {}

        if resolution.table == "players":
            for key, pattern in POSITION_MAP.items():
                if key in q:
                    df = df.filter(pl.col("main_position").str.to_lowercase().str.contains(pattern))
                    filters["position"] = key
                    break

            age_lt = _extract(r"\bunder\s+(\d+)\b", q) or _extract(r"\byounger than\s+(\d+)\b", q)
            if age_lt and "birth_date" in df.columns:
                df = df.with_columns(
                    ((pl.lit(20240801) - pl.col("birth_date").str.replace_all("-", "").cast(pl.Int64)) / 10000)
                    .cast(pl.Int64).alias("age")
                ).filter(pl.col("age") < age_lt)
                filters["age_lt"] = age_lt

            min_min = _extract(r"\bwith at least\s+(\d+)\s+minutes\b", q) or _extract(r"\bmore than\s+(\d+)\s+minutes\b", q)
            if min_min:
                df = df.filter(pl.col("total_minutes") >= min_min)
                filters["min_minutes"] = min_min

            min_apps = _extract(r"\bminimum\s+(\d+)\s+(?:appearances|matches|games)\b", q) or \
                       _extract(r"\bat least\s+(\d+)\s+(?:appearances|matches|games)\b", q)
            if min_apps:
                df = df.filter(pl.col("matches_played") >= min_apps)
                filters["min_matches"] = min_apps

        top_n  = next(
            (int(re.search(p, q).group(1)) for p in [
                r"\btop\s+(\d+)\b", r"\bbest\s+(\d+)\b",
                r"\b(\d+)\s+(?:teams|players)\b",
            ] if re.search(p, q)),
            1,
        )

        sorted_df = df.sort(resolution.metric, descending=resolution.descending, nulls_last=True)
        result_df = sorted_df.head(top_n)

        if top_n == 1:
            boundary  = result_df[resolution.metric][-1]
            result_df = sorted_df.filter(pl.col(resolution.metric) == boundary)

        display = (
            ["short_name", "team_name", "main_position", "age", resolution.metric, "matches_played", "total_minutes"]
            if resolution.table == "players"
            else ["team_name", resolution.metric, "total_goals", "total_goals_against"]
        )
        
        display = list(dict.fromkeys(c for c in display if c in df.columns))

        result_df = result_df.select(display)
        result_df = result_df.with_columns([
            pl.col(c).round(2)
            for c, t in zip(result_df.columns, result_df.dtypes)
            if t in (pl.Float64, pl.Float32)
        ])

        return QueryResult(
            table=resolution.table,
            metric=resolution.metric,
            rows=result_df.to_dicts(),
            filters_applied=filters,
        )

    # ── Step 3: LLM verbalizes grounded result ──────────────────────────────

    def _verbalize(self, question: str, result: QueryResult) -> str:
        p = self._verbalize_prompt
        prompt = p["user"].format(question=question, metric=result.metric, rows=result.rows)
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": p["system"]},
                {"role": "user",   "content": prompt},
            ],
        )
        return response.choices[0].message.content.strip()

    # ── Public interface ─────────────────────────────────────────────────────

    def ask(self, question: str) -> dict:
        resolution = self._resolve_metric(question)
        result = self._execute(question, resolution)
        answer = self._verbalize(question, result)

        return {
            "type": "text",
            "content": answer,
            "debug": {
                "engine": "llm_query_engine_v2",
                "table": result.table,
                "metric": result.metric,
                "descending": resolution.descending,
                "filters": result.filters_applied,
                "rows": result.rows,
            },
        }

    
