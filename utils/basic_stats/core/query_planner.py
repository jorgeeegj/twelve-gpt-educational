import json
import re
import unicodedata
from pathlib import Path
from typing import Any

import polars as pl
import yaml
from pydantic import BaseModel, Field, ValidationError

from utils.basic_stats.core.config import (
    PLAYER_DATA_PATH,
    TEAM_DATA_PATH,
    PROMPTS_DIR,
    get_llm_client,
    get_model,
)


def _normalize_text(text: str) -> str:
    text = text.strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", text)


def _extract_numeric_ordinal(q: str) -> int | None:
    patterns = [
        r"\b(\d+)(?:st|nd|rd|th)\b",
        r"\b(\d+)[ºª]\b",
        r"\bpuesto\s+(\d+)\b",
        r"\bposition\s+(\d+)\b",
    ]
    for pattern in patterns:
        m = re.search(pattern, q)
        if m:
            return int(m.group(1))
    return None

def _targets_player_subject(q: str) -> bool:
    patterns = [
        r"^\s*which player\b",
        r"^\s*what player\b",
        r"^\s*who\b",
        r"^\s*que jugador\b",
        r"^\s*qué jugador\b",
    ]
    return any(re.search(p, q) for p in patterns)


def _targets_team_subject(q: str) -> bool:
    patterns = [
        r"^\s*which team\b",
        r"^\s*what team\b",
        r"^\s*which club\b",
        r"^\s*which side\b",
        r"^\s*que equipo\b",
        r"^\s*qué equipo\b",
    ]
    return any(re.search(p, q) for p in patterns)

def _has_match_like_question(q: str) -> bool:
    return any([
        "against" in q,
        "vs " in q,
        "versus" in q,
        "contra" in q,
        "away" in q,
        "fuera de casa" in q,
        "at home" in q,
        "en casa" in q,
        "between matchdays" in q,
        "between gameweeks" in q,
        "entre jornadas" in q,
        "big six" in q,
        "big6" in q,
        "big 6" in q,
        "top-" in q,
        "top " in q,
        "bottom" in q,
    ])

class QueryFilters(BaseModel):
    player_name: str | None = None
    team_name: str | None = None
    opponent_team_name: str | None = None
    position: str | None = None
    is_home: bool | None = None
    opponent_rank_lte: int | None = None
    opponent_rank_gte: int | None = None
    opponent_rank_between: list[int] | None = None
    opponent_is_big6: bool | None = None
    matchday_start: int | None = None
    matchday_end: int | None = None
    min_minutes: int | None = None
    min_matches: int | None = None
    age_lt: int | None = None


class RankingPlan(BaseModel):
    mode: str = Field(description="top_n | ordinal | entity_value")
    n: int | None = None
    ordinal: int | None = None

class MatchCondition(BaseModel):
    metric: str
    operator: str
    value: float | int


class QueryPlan(BaseModel):
    table_scope: str
    entity_type: str
    metric: str
    aggregation: str
    filters: QueryFilters
    ranking: RankingPlan
    match_conditions: list[MatchCondition] | None = None


class QueryPlanner:
    """
    LLM-assisted structured query planner.

    Responsibilities:
    - resolve a natural-language question into a structured JSON plan
    - validate that the plan uses allowed scopes/metrics/aggregations
    - enrich / repair some fields deterministically (player/team names, ordinal hints)
    - keep the LLM in charge of semantic interpretation, while code remains the guardrail
    """

    POSITION_HINTS = {
        "midfielder": ["midfielder", "midfielders", "centrocampista", "mediocampista"],
        "defender": ["defender", "defenders", "defensa", "defensas"],
        "forward": ["forward", "forwards", "striker", "strikers", "delantero", "delanteros"],
        "goalkeeper": ["goalkeeper", "goalkeepers", "portero", "porteros"],
        "full back": ["full back", "full backs", "lateral", "laterales"],
        "winger": ["winger", "wingers", "extremo", "extremos"],
        "attacking midfielder": ["attacking midfielder", "cam", "mediapunta"],
        "central defender": ["central defender", "center back", "cb", "central"],
    }

    SCOPE_ALIASES = {
        "player_season_summary": "players_summary",
        "player_season_stats": "players_summary",
        "player_season_totals": "players_summary",
        "player_summary": "players_summary",
        "player_stats": "players_summary",
        "player_statistics": "players_summary",
        "players": "players_summary",

        "team_season_summary": "teams_summary",
        "team_season_stats": "teams_summary",
        "team_summary": "teams_summary",
        "team_performance": "team_match",
        "teams": "teams_summary",

        "player_match_stats": "player_match",
        "player_matches": "player_match",
        "player_goals": "player_match",

        "player_passes": "player_match_event",
        "player_events": "player_match_event",
        "player_event_stats": "player_match_event",

        "season_matches": "team_match",
        "team_matches": "team_match",
        "team_performance_by_opponent": "team_match",
        "team_actions_vs_opponent": "team_match",
        "zone_actions": "team_match",
        "team_actions_by_opponent_zone": "team_match",
    }
    METRIC_ALIASES = {
        "goals": {
            "players_summary": "total_goals",
            "teams_summary": "total_goals",
            "player_match": "goals",
            "player_match_event": "shots",
            "team_match": "team_score",
        },
        "assists": {
            "players_summary": "total_assists",
            "teams_summary": "total_assists",
            "player_match": "assists",
            "team_match": "assists",
        },
        "minutes": {
            "players_summary": "total_minutes",
            "player_match": "minutes_played",
        },
        "minutes_played": {
            "players_summary": "total_minutes",
            "player_match": "minutes_played",
        },
        "goals_conceded": {
            "teams_summary": "total_goals_against",
            "team_match": "opponent_score",
        },
        "away_goals": {
            "player_match": "goals",
            "team_match": "team_score",
        },
        "points": {
            "team_match": "team_score",
        },
        "actions_in_z3": {
            "team_match": "actions_z3",
            "player_match_event": "actions_z3",
        },
        "z3_actions": {
            "team_match": "actions_z3",
            "player_match_event": "actions_z3",
        },
    }

    def _default_filters_dict(self) -> dict:
        return {
            "player_name": None,
            "team_name": None,
            "opponent_team_name": None,
            "position": None,
            "is_home": None,
            "opponent_rank_lte": None,
            "opponent_rank_gte": None,
            "opponent_rank_between": None,
            "opponent_is_big6": None,
            "matchday_start": None,
            "matchday_end": None,
            "min_minutes": None,
            "min_matches": None,
            "age_lt": None,
        }

    def _default_ranking_dict(self) -> dict:
        return {
            "mode": "top_n",
            "n": 1,
            "ordinal": None,
        }
    
    def _infer_scope_from_question(self, question: str, current_scope: str | None, metric: str | None) -> str | None:
        q = _normalize_text(question)

        has_match_context = any([
            "against" in q,
            "vs " in q,
            "versus" in q,
            "contra" in q,
            "away" in q,
            "fuera de casa" in q,
            "at home" in q,
            "home " in q,
            "en casa" in q,
            "between matchdays" in q,
            "between gameweeks" in q,
            "entre jornadas" in q,
            "big six" in q,
            "big6" in q,
            "big 6" in q,
            "top-" in q,
            "top " in q,
            "bottom" in q,
        ])

        player_match_metrics = {
            "goals", "assists", "own_goals", "yellow_card", "red_card", "minutes_played",
            "total_goals", "total_assists", "total_minutes",
        }

        player_event_metrics = {
            "passes_attempted", "passes_accurate", "progressive_passes", "forward_passes",
            "back_passes", "long_passes", "key_passes", "crosses", "passes_to_final_third",
            "passes_to_box", "through_passes", "smart_passes", "shots", "shots_on_target",
            "xg_total", "aerial_duels", "aerial_duels_won", "defensive_duels",
            "defensive_duels_won", "offensive_duels", "offensive_duels_won",
            "dribbles_attempted", "dribbles_won", "recoveries", "interceptions",
            "clearances", "sliding_tackles", "fouls_committed", "fouls_suffered",
            "progressive_carries", "carry_meters_gained", "progressive_runs",
            "touches_in_box", "shot_assists", "ball_losses", "goalkeeper_exits",
            "shots_against", "saves", "reflex_saves",
            "actions_z1", "actions_z2", "actions_z3", "actions_z4", "actions_z5",
            "pass_z2_to_z4", "pass_z2_to_z5", "pass_z3_to_z4", "pass_z3_to_z5",
            "carry_z2_to_z4", "carry_z2_to_z5", "carry_z3_to_z4", "carry_z3_to_z5",
            "actions_in_z3", "z3_actions",
        }

        team_match_metrics = {
            "team_score", "opponent_score", "assists", "xg_total", "progressive_passes",
            "key_passes", "touches_in_box", "aerial_duels_won", "recoveries",
            "interceptions", "clearances", "fouls_committed", "fouls_suffered",
            "actions_z1", "actions_z2", "actions_z3", "actions_z4", "actions_z5",
            "pass_z2_to_z4", "pass_z2_to_z5", "pass_z3_to_z4", "pass_z3_to_z5",
            "carry_z2_to_z4", "carry_z2_to_z5", "carry_z3_to_z4", "carry_z3_to_z5",
            "points", "wins", "goal_difference", "actions_in_z3", "z3_actions",
        }

        # Strong override when question implies match context
        if has_match_context:
            if metric in player_match_metrics:
                return "player_match"

            if metric in player_event_metrics:
                return "player_match_event"

            if metric in team_match_metrics:
                return "team_match"

        # If existing scope is already valid and no strong override is needed
        if current_scope in self.allowed_scopes:
            return current_scope

        # Fallback by metric
        if metric in self.metric_catalog.get("players_summary", []):
            return "players_summary"
        if metric in self.metric_catalog.get("teams_summary", []):
            return "teams_summary"
        if metric in player_match_metrics:
            return "player_match"
        if metric in player_event_metrics:
            return "player_match_event"
        if metric in team_match_metrics:
            return "team_match"

        return current_scope

    def __init__(self):
        self.client = get_llm_client()
        self.model = get_model()

        self.players_df = pl.read_parquet(PLAYER_DATA_PATH)
        self.teams_df = pl.read_parquet(TEAM_DATA_PATH)

        self.prompt = self._load_prompt("resolve_query_intent")

        self.allowed_scopes = set(self.prompt["available_values"]["table_scope"])
        self.allowed_entity_types = set(self.prompt["available_values"]["entity_type"])
        self.allowed_aggregations = set(self.prompt["available_values"]["aggregation"])
        self.allowed_ranking_modes = set(self.prompt["available_values"]["ranking_mode"])
        self.metric_catalog: dict[str, list[str]] = self.prompt["metric_catalog"]

        self.player_names = self._load_player_names()
        self.team_names = self._load_team_names()

    def _load_prompt(self, name: str) -> dict:
        return yaml.safe_load((PROMPTS_DIR / f"{name}.yaml").read_text(encoding="utf8"))

    def _load_player_names(self) -> list[str]:
        if "short_name" not in self.players_df.columns:
            return []
        return (
            self.players_df
            .select("short_name")
            .drop_nulls()
            .unique()
            .to_series()
            .to_list()
        )

    def _load_team_names(self) -> list[str]:
        if "team_name" not in self.teams_df.columns:
            return []
        return (
            self.teams_df
            .select("team_name")
            .drop_nulls()
            .unique()
            .to_series()
            .to_list()
        )

    def _extract_opponent_team_hint(self, question: str) -> str | None:
        q = _normalize_text(question)

        patterns = [
            r"\bagainst\s+(.+?)(?:\s+this season|\s+between|\s+away|\s+at home|$)",
            r"\bvs\.?\s+(.+?)(?:\s+this season|\s+between|\s+away|\s+at home|$)",
            r"\bversus\s+(.+?)(?:\s+this season|\s+between|\s+away|\s+at home|$)",
            r"\bcontra\s+(.+?)(?:\s+esta temporada|\s+entre|\s+fuera de casa|\s+en casa|$)",
        ]

        for pattern in patterns:
            m = re.search(pattern, q)
            if not m:
                continue

            chunk = m.group(1).strip()
            for team in sorted(self.team_names, key=len, reverse=True):
                if _normalize_text(team) in chunk:
                    return team

        return None

    def _extract_own_team_hint(self, question: str) -> str | None:
        q = _normalize_text(question)

        patterns = [
            r"\bwhich\s+(.+?)\s+player\b",
            r"\bwhat\s+(.+?)\s+player\b",
            r"\bque\s+jugador\s+del\s+(.+?)\b",
            r"\bqué\s+jugador\s+del\s+(.+?)\b",
        ]

        for pattern in patterns:
            m = re.search(pattern, q)
            if not m:
                continue

            chunk = m.group(1).strip()
            for team in sorted(self.team_names, key=len, reverse=True):
                if _normalize_text(team) in chunk:
                    return team

        return None

    def _match_known_name(self, question: str, candidates: list[str]) -> str | None:
        q = _normalize_text(question)
        for candidate in sorted(candidates, key=len, reverse=True):
            cand_norm = _normalize_text(candidate)
            if cand_norm and cand_norm in q:
                return candidate
        return None

    def _infer_position_hint(self, question: str) -> str | None:
        q = _normalize_text(question)
        for canonical, hints in self.POSITION_HINTS.items():
            if any(h in q for h in hints):
                return canonical
        return None

    def _call_llm_for_plan(self, question: str) -> dict:
        response = self.client.chat.completions.create(
            model=self.model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": self.prompt["system"]},
                {"role": "user", "content": question},
            ],
        )
        content = response.choices[0].message.content
        return json.loads(content)

    def _validate_scope_and_metric(self, plan: QueryPlan) -> None:
        if plan.table_scope not in self.allowed_scopes:
            raise ValueError(f"Invalid table_scope: {plan.table_scope}")

        if plan.entity_type not in self.allowed_entity_types:
            raise ValueError(f"Invalid entity_type: {plan.entity_type}")

        if plan.aggregation not in self.allowed_aggregations:
            raise ValueError(f"Invalid aggregation: {plan.aggregation}")

        if plan.ranking.mode not in self.allowed_ranking_modes:
            raise ValueError(f"Invalid ranking.mode: {plan.ranking.mode}")

        allowed_metrics = self.metric_catalog.get(plan.table_scope, [])
        if plan.metric not in allowed_metrics:
            raise ValueError(
                f"Metric '{plan.metric}' is not allowed for scope '{plan.table_scope}'. "
                f"Allowed metrics: {allowed_metrics}"
            )

    def _canonicalize_raw_plan(self, question: str, raw_plan: dict) -> dict:
        q = _normalize_text(question)
        plan = dict(raw_plan)

        matched_player = self._match_known_name(question, self.player_names)
        matched_team = self._match_known_name(question, self.team_names)

        # --- normalize top-level key names ---
        if "table_scope" not in plan:
            if "table" in plan:
                plan["table_scope"] = plan.pop("table")
            elif "scope" in plan:
                plan["table_scope"] = plan.pop("scope")

        if "table_scope" not in plan or plan.get("table_scope") is None:
            metric_guess = plan.get("metric")

            if metric_guess in self.metric_catalog.get("players_summary", []):
                plan["table_scope"] = "players_summary"
            elif metric_guess in self.metric_catalog.get("teams_summary", []):
                plan["table_scope"] = "teams_summary"

        # --- normalize scope aliases ---
        scope = plan.get("table_scope")
        if isinstance(scope, str):
            plan["table_scope"] = self.SCOPE_ALIASES.get(scope, scope)

        # --- normalize filters ---
        filters = plan.get("filters")

        if filters is None:
            filters = self._default_filters_dict()

        elif isinstance(filters, list):
            fixed_filters = self._default_filters_dict()
            for item in filters:
                if isinstance(item, dict):
                    field = item.get("field")
                    value = item.get("value")
                    if field in fixed_filters:
                        fixed_filters[field] = value
            filters = fixed_filters

        elif isinstance(filters, dict):
            fixed_filters = self._default_filters_dict()
            fixed_filters.update(filters)
            filters = fixed_filters

        else:
            filters = self._default_filters_dict()

        plan["filters"] = filters

        if isinstance(plan["filters"].get("position"), str):
            plan["filters"]["position"] = _normalize_text(plan["filters"]["position"])

        # --- deterministic basic filters from question ---
        if plan["filters"]["position"] is None:
            inferred_position = self._infer_position_hint(question)
            if inferred_position:
                plan["filters"]["position"] = inferred_position

        if plan["filters"]["age_lt"] is None:
            for pattern in [
                r"\bunder\s+(\d+)\b",
                r"\byounger than\s+(\d+)\b",
                r"\bmenor(?:es)? de\s+(\d+)\b",
                r"\bsub[\-\s]?(\d+)\b",
            ]:
                m = re.search(pattern, q)
                if m:
                    plan["filters"]["age_lt"] = int(m.group(1))
                    break

        if plan["filters"]["min_minutes"] is None:
            for pattern in [
                r"\bwith at least\s+(\d+)\s+minutes\b",
                r"\bmore than\s+(\d+)\s+minutes\b",
                r"\bal menos\s+(\d+)\s+minutos\b",
                r"\bcon al menos\s+(\d+)\s+minutos\b",
            ]:
                m = re.search(pattern, q)
                if m:
                    plan["filters"]["min_minutes"] = int(m.group(1))
                    break

        if plan["filters"]["min_matches"] is None:
            for pattern in [
                r"\bminimum\s+(\d+)\s+(?:appearances|matches|games)\b",
                r"\bat least\s+(\d+)\s+(?:appearances|matches|games)\b",
                r"\bal menos\s+(\d+)\s+(?:partidos|apariciones)\b",
                r"\bminimo\s+(\d+)\s+(?:partidos|apariciones)\b",
                r"\bmínimo\s+(\d+)\s+(?:partidos|apariciones)\b",
            ]:
                m = re.search(pattern, q)
                if m:
                    plan["filters"]["min_matches"] = int(m.group(1))
                    break

        # --- normalize ranking ---
        ranking = plan.get("ranking")
        if ranking is None or not isinstance(ranking, dict):
            ranking = self._default_ranking_dict()
        else:
            fixed_ranking = self._default_ranking_dict()
            fixed_ranking.update(ranking)
            ranking = fixed_ranking

        plan["ranking"] = ranking

        # --- normalize match conditions ---
        match_conditions = plan.get("match_conditions")
        allowed_ops = {">", ">=", "<", "<=", "=", "!="}

        if match_conditions is None:
            plan["match_conditions"] = None

        elif isinstance(match_conditions, list):
            fixed_conditions = []

            for item in match_conditions:
                if not isinstance(item, dict):
                    continue

                metric = item.get("metric")
                operator = item.get("operator")
                value = item.get("value")

                if metric is None or operator not in allowed_ops:
                    continue

                if isinstance(value, str):
                    try:
                        value = float(value) if "." in value else int(value)
                    except Exception:
                        continue

                if not isinstance(value, (int, float)):
                    continue

                fixed_conditions.append({
                    "metric": metric,
                    "operator": operator,
                    "value": value,
                })

            plan["match_conditions"] = fixed_conditions or None

        else:
            plan["match_conditions"] = None

        # --- strong deterministic overrides for common contextual questions ---
        # Sprint 2 - derived player match questions
        if (
            "matches with both a goal and an assist" in q
            or "games with both a goal and an assist" in q
            or "most matches with a goal and an assist" in q
            or "most games with a goal and an assist" in q
            or "partidos con gol y asistencia" in q
        ):
            plan["table_scope"] = "player_match"
            plan["entity_type"] = "player"
            plan["metric"] = "goals"
            plan["aggregation"] = "count_matches_positive"
            plan["ranking"] = {"mode": "top_n", "n": 1, "ordinal": None}
            plan["match_conditions"] = [
                {"metric": "goals", "operator": ">", "value": 0},
                {"metric": "assists", "operator": ">", "value": 0},
            ]

        elif (
            "matches with 2 or more goals" in q
            or "games with 2 or more goals" in q
            or "matches with two or more goals" in q
            or "most matches with 2 or more goals" in q
            or "most games with 2 or more goals" in q
            or "partidos con 2 o mas goles" in q
            or "partidos con dos o mas goles" in q
        ):
            plan["table_scope"] = "player_match"
            plan["entity_type"] = "player"
            plan["metric"] = "goals"
            plan["aggregation"] = "count_matches_positive"
            plan["ranking"] = {"mode": "top_n", "n": 1, "ordinal": None}
            plan["match_conditions"] = [
                {"metric": "goals", "operator": ">=", "value": 2},
            ]

        # Sprint 3 - player goals by opponent/home-away
        elif (
            "goals against top-6" in q
            or "goals against top 6" in q
            or "scored against top-6" in q
            or "scored against top 6" in q
        ):
            plan["table_scope"] = "player_match"
            plan["entity_type"] = "player"
            plan["metric"] = "goals"
            plan["aggregation"] = "sum"
            plan["filters"]["opponent_rank_lte"] = 6

        elif (
            "away goals" in q
            or "goles fuera de casa" in q
        ):
            if _targets_team_subject(q):
                plan["table_scope"] = "team_match"
                plan["entity_type"] = "team"
                plan["metric"] = "team_score"
                plan["aggregation"] = "sum"
                plan["filters"]["is_home"] = False
            else:
                plan["table_scope"] = "player_match"
                plan["entity_type"] = "player"
                plan["metric"] = "goals"
                plan["aggregation"] = "sum"
                plan["filters"]["is_home"] = False

        # Sprint 4 - player match event context
        elif (
            "progressive passes" in q
            and ("against top-6" in q or "against top 6" in q)
        ):
            plan["table_scope"] = "player_match_event"
            plan["entity_type"] = "player"
            plan["metric"] = "progressive_passes"
            plan["aggregation"] = "sum"
            plan["filters"]["opponent_rank_lte"] = 6

        elif (
            "key passes" in q
            and (
                "between matchdays" in q
                or "between gameweeks" in q
                or "entre jornadas" in q
            )
        ):
            plan["table_scope"] = "player_match_event"
            plan["entity_type"] = "player"
            plan["metric"] = "key_passes"
            plan["aggregation"] = "sum"

        elif (
            "shot assists" in q
            and (
                "big six" in q
                or "big6" in q
                or "big 6" in q
            )
        ):
            plan["table_scope"] = "player_match_event"
            plan["entity_type"] = "player"
            plan["metric"] = "shot_assists"
            plan["aggregation"] = "sum"
            plan["filters"]["opponent_is_big6"] = True

        # Sprint 5 - team match context
        elif (
            ("points" in q or "puntos" in q)
            and ("big six" in q or "big6" in q or "big 6" in q)
        ):
            plan["table_scope"] = "team_match"
            plan["entity_type"] = "team"
            plan["metric"] = "team_score"
            plan["aggregation"] = "points"
            plan["filters"]["opponent_is_big6"] = True

        elif (
            ("away wins" in q or "victorias fuera de casa" in q)
        ):
            plan["table_scope"] = "team_match"
            plan["entity_type"] = "team"
            plan["metric"] = "team_score"
            plan["aggregation"] = "wins"
            plan["filters"]["is_home"] = False

        elif (
            ("actions in z3" in q or "acciones en z3" in q or "actions_z3" in q)
        ):
            if any(tok in q for tok in ["team", "teams", "club", "side", "equipo", "equipos"]):
                plan["table_scope"] = "team_match"
                plan["entity_type"] = "team"
                plan["metric"] = "actions_z3"
                plan["aggregation"] = "sum"
        
        if plan["filters"].get("player_name") is not None:
            plan["entity_type"] = "player"
            if plan["table_scope"] == "team_match":
                if plan["metric"] in self.metric_catalog.get("player_match_event", []):
                    plan["table_scope"] = "player_match_event"
                else:
                    plan["table_scope"] = "player_match"

        if plan["filters"].get("team_name") is not None and plan["entity_type"] == "team":
            if _has_match_like_question(q):
                plan["table_scope"] = "team_match"
        
        # --- normalize aggregation ---
        metric = plan.get("metric")
        aggregation = plan.get("aggregation")

        if plan.get("aggregation") == "count":
            plan["aggregation"] = "count_matches_positive"

        if (
            aggregation is None
            or aggregation == "sum"
        ):
            if (
                "won the most points" in q
                or "most points against" in q
                or "mas puntos" in q
                or "más puntos" in q
            ):
                plan["aggregation"] = "points"
            elif (
                "won the most matches" in q
                or "most wins" in q
                or "mas victorias" in q
                or "más victorias" in q
            ):
                plan["aggregation"] = "wins"
            elif "goal difference" in q or "diferencia de goles" in q:
                plan["aggregation"] = "goal_difference"
            elif metric in {"points"}:
                plan["aggregation"] = "points"
            else:
                plan["aggregation"] = "sum"

        # --- normalize metric aliases depending on scope ---
        scope = plan.get("table_scope")
        metric = plan.get("metric")

        if isinstance(metric, str) and metric in self.METRIC_ALIASES:
            scoped_alias = self.METRIC_ALIASES[metric]
            if isinstance(scoped_alias, dict) and scope in scoped_alias:
                plan["metric"] = scoped_alias[scope]

        if plan.get("table_scope") is None:
            plan["table_scope"] = None

        scope = plan.get("table_scope")
        metric = plan.get("metric")

        plan["table_scope"] = self._infer_scope_from_question(
            question=question,
            current_scope=scope,
            metric=metric,
        )

        metric = plan.get("metric")

        if metric in {
            "matches_with_two_or_more_goals",
            "two_goal_matches",
            "matches_with_2_or_more_goals",
        }:
            plan["metric"] = "goals"
            plan["table_scope"] = "player_match"
            plan["entity_type"] = "player"
            plan["aggregation"] = "count_matches_positive"
            plan["match_conditions"] = [
                {"metric": "goals", "operator": ">=", "value": 2},
            ]

        if metric in {
            "matches_with_goal_and_assist",
            "matches_scored_and_assisted",
            "goal_and_assist_matches",
        }:
            plan["metric"] = "goals"
            plan["table_scope"] = "player_match"
            plan["entity_type"] = "player"
            plan["aggregation"] = "count_matches_positive"
            plan["match_conditions"] = [
                {"metric": "goals", "operator": ">", "value": 0},
                {"metric": "assists", "operator": ">", "value": 0},
            ]

        scope = plan.get("table_scope")
        metric = plan.get("metric")

        # --- strong entity type correction from wording ---
        # --- subject-aware entity correction ---
        if matched_player is not None:
            plan["entity_type"] = "player"
        elif plan["filters"].get("position") is not None:
            plan["entity_type"] = "player"
        elif _targets_player_subject(q):
            plan["entity_type"] = "player"
        elif _targets_team_subject(q):
            plan["entity_type"] = "team"

        # --- detect whether question has real match/event context ---
        has_context = any([
            plan["filters"]["is_home"] is not None,
            plan["filters"]["opponent_rank_lte"] is not None,
            plan["filters"]["opponent_rank_gte"] is not None,
            plan["filters"]["opponent_rank_between"] is not None,
            plan["filters"]["opponent_is_big6"] is not None,
            plan["filters"]["matchday_start"] is not None,
            plan["filters"]["matchday_end"] is not None,
            plan["filters"]["opponent_team_name"] is not None,
        ])

        if scope == "player_match" and metric == "total_goals":
            plan["metric"] = "goals"

        if scope == "player_match" and metric == "total_assists":
            plan["metric"] = "assists"

        if scope == "player_match" and metric == "total_minutes":
            plan["metric"] = "minutes_played"
        
        if scope == "team_match" and metric == "goals":
            plan["metric"] = "team_score"

        if scope == "team_match" and metric == "total_goals":
            plan["metric"] = "team_score"

        if scope == "team_match" and metric == "total_goals_against":
            plan["metric"] = "opponent_score"

        if scope == "team_match" and metric == "points":
            plan["metric"] = "team_score"

        if scope == "team_match" and metric == "wins":
            plan["metric"] = "team_score"

        if scope == "team_match" and metric == "goal_difference":
            plan["metric"] = "team_score"

        if scope == "team_match" and metric in {"actions_in_z3", "z3_actions"}:
            plan["metric"] = "actions_z3"
        
        if scope == "player_match" and metric == "away_goals":
            plan["metric"] = "goals"

        if scope == "team_match" and metric == "away_goals":
            plan["metric"] = "team_score"

        if metric in {"away_goals", "away_goal"}:
            if "team" in q or "equipo" in q or "club" in q or "side" in q:
                plan["metric"] = "team_score"
                plan["table_scope"] = "team_match"
                plan["entity_type"] = "team"
            else:
                plan["metric"] = "goals"
                plan["table_scope"] = "player_match"
                plan["entity_type"] = "player"

        if metric in {"total_wins", "wins_total", "away_wins"}:
            plan["metric"] = "team_score"
            plan["table_scope"] = "team_match"
            plan["entity_type"] = "team"
            if "away" in q or "fuera de casa" in q:
                plan["filters"]["is_home"] = False
            plan["aggregation"] = "wins"

        if metric in {"actions", "z3_actions", "actions_in_z3"}:
            if "z3" in q:
                plan["metric"] = "actions_z3"
                if "team" in q or "equipo" in q or "club" in q or "side" in q:
                    plan["table_scope"] = "team_match"
                    plan["entity_type"] = "team"
                else:
                    plan["table_scope"] = "player_match_event"
                    plan["entity_type"] = "player"

        # --- ranking repair from question ---
        ordinal = _extract_numeric_ordinal(q)
        if ordinal is not None:
            plan["ranking"]["mode"] = "ordinal"
            plan["ranking"]["ordinal"] = ordinal
            plan["ranking"]["n"] = None

        if plan["ranking"]["mode"] == "top_n" and plan["ranking"]["n"] is None:
            plan["ranking"]["n"] = 1

        # --- some deterministic semantic repairs ---
        if "away" in q or "fuera de casa" in q:
            if plan["filters"]["is_home"] is None:
                plan["filters"]["is_home"] = False

        if "at home" in q or "home " in q or "en casa" in q:
            if plan["filters"]["is_home"] is None:
                plan["filters"]["is_home"] = True

        if "top-6" in q or "top 6" in q:
            plan["filters"]["opponent_rank_lte"] = 6
            plan["filters"]["opponent_is_big6"] = None

        elif "big six" in q or "big6" in q or "big 6" in q:
            plan["filters"]["opponent_is_big6"] = True

        m = re.search(r"\bbetween matchdays?\s+(\d+)\s+and\s+(\d+)\b", q)
        if m:
            a, b = int(m.group(1)), int(m.group(2))
            plan["filters"]["matchday_start"] = min(a, b)
            plan["filters"]["matchday_end"] = max(a, b)

        m = re.search(r"\bentre jornadas?\s+(\d+)\s+y\s+(\d+)\b", q)
        if m:
            a, b = int(m.group(1)), int(m.group(2))
            plan["filters"]["matchday_start"] = min(a, b)
            plan["filters"]["matchday_end"] = max(a, b)
        
        # Strong scope corrections from obvious context
        has_context = any([
            plan["filters"]["is_home"] is not None,
            plan["filters"]["opponent_rank_lte"] is not None,
            plan["filters"]["opponent_rank_gte"] is not None,
            plan["filters"]["opponent_rank_between"] is not None,
            plan["filters"]["opponent_is_big6"] is not None,
            plan["filters"]["matchday_start"] is not None,
            plan["filters"]["matchday_end"] is not None,
            plan["filters"]["opponent_team_name"] is not None,
        ])

        if has_context:
            if plan["entity_type"] == "player":
                if plan["metric"] in {
                    "goals", "assists", "own_goals", "yellow_card", "red_card", "minutes_played"
                }:
                    plan["table_scope"] = "player_match"
                elif plan["metric"] in self.metric_catalog["player_match_event"]:
                    plan["table_scope"] = "player_match_event"

            if plan["entity_type"] == "team":
                plan["table_scope"] = "team_match"
        
        

        if plan["entity_type"] == "team" and plan["table_scope"] == "players_summary":
            if has_context:
                plan["table_scope"] = "team_match"
            else:
                plan["table_scope"] = "teams_summary"

        # --- deterministic match-level derived conditions ---
        if plan["table_scope"] == "player_match":
            if plan["match_conditions"] is None:
                if (
                    "matches with both a goal and an assist" in q
                    or "games with both a goal and an assist" in q
                    or "partidos con gol y asistencia" in q
                ):
                    plan["aggregation"] = "count_matches_positive"
                    plan["metric"] = "goals"
                    plan["match_conditions"] = [
                        {"metric": "goals", "operator": ">", "value": 0},
                        {"metric": "assists", "operator": ">", "value": 0},
                    ]

                elif (
                    "matches with 2 or more goals" in q
                    or "games with 2 or more goals" in q
                    or "matches with two or more goals" in q
                    or "partidos con 2 o mas goles" in q
                    or "partidos con dos o mas goles" in q
                ):
                    plan["aggregation"] = "count_matches_positive"
                    plan["metric"] = "goals"
                    plan["match_conditions"] = [
                        {"metric": "goals", "operator": ">=", "value": 2},
                    ]

        if plan["entity_type"] == "player" and plan["table_scope"] == "teams_summary":
            if has_context:
                if plan["metric"] in self.metric_catalog["player_match_event"]:
                    plan["table_scope"] = "player_match_event"
                else:
                    plan["table_scope"] = "player_match"
            else:
                plan["table_scope"] = "players_summary"

        return plan

    def _post_process_plan(self, question: str, raw_plan: dict) -> QueryPlan:
        q = _normalize_text(question)

        # Build / validate with pydantic first
        plan = QueryPlan(**raw_plan)

        # Name enrichment from known entities in the dataset
        matched_player = self._match_known_name(question, self.player_names)
        matched_team = self._match_known_name(question, self.team_names)

        own_team_hint = self._extract_own_team_hint(question)
        opponent_team_hint = self._extract_opponent_team_hint(question)

        if matched_player and not plan.filters.player_name:
            plan.filters.player_name = matched_player

        # Prefer explicit own-team hint when present
        if own_team_hint and not plan.filters.team_name:
            plan.filters.team_name = own_team_hint

        # Prefer explicit opponent-team hint when present
        if opponent_team_hint and not plan.filters.opponent_team_name:
            plan.filters.opponent_team_name = opponent_team_hint

        # Fallback: only assign matched team if still unassigned and context is safe
        if matched_team:
            if not plan.filters.team_name and not plan.filters.opponent_team_name:
                if plan.entity_type == "team" and "against" not in q and "vs" not in q and "versus" not in q and "contra" not in q:
                    plan.filters.team_name = matched_team

        # Position hint repair
        inferred_position = self._infer_position_hint(question)
        if inferred_position and not plan.filters.position and plan.entity_type == "player":
            plan.filters.position = inferred_position

        # Ordinal repair
        ordinal = _extract_numeric_ordinal(q)
        if ordinal is not None and plan.ranking.mode != "entity_value":
            plan.ranking.mode = "ordinal"
            plan.ranking.ordinal = ordinal
            plan.ranking.n = None

        # Top-N / default ranking repair
        if plan.ranking.mode == "top_n" and plan.ranking.n is None:
            plan.ranking.n = 1

        if plan.ranking.mode == "ordinal" and plan.ranking.ordinal is None:
            extracted = _extract_numeric_ordinal(q)
            if extracted is not None:
                plan.ranking.ordinal = extracted

        # Normalize opponent rank between
        if plan.filters.opponent_rank_between and len(plan.filters.opponent_rank_between) == 2:
            a, b = plan.filters.opponent_rank_between
            plan.filters.opponent_rank_between = [min(a, b), max(a, b)]

        # Coherence guards
        if plan.entity_type == "team" and plan.filters.position is not None:
            plan.filters.position = None

        # If question explicitly says "against X", that team should not also become team_name
        if plan.filters.team_name and plan.filters.opponent_team_name:
            if plan.filters.team_name == plan.filters.opponent_team_name:
                plan.filters.team_name = None

        self._validate_scope_and_metric(plan)
        return plan

    def resolve(self, question: str) -> QueryPlan:
        raw_plan = self._call_llm_for_plan(question)
        canonical_plan = self._canonicalize_raw_plan(question, raw_plan)
        return self._post_process_plan(question, canonical_plan)

    def to_debug_dict(self, plan: QueryPlan) -> dict[str, Any]:
        return plan.model_dump()

    def build_execution_payload(self, plan: QueryPlan) -> dict[str, Any]:
        """
        Convert the validated plan into a simple execution payload that a query runner
        or duckdb manager can consume.

        This keeps the LLM out of SQL generation.
        """
        payload = {
            "table_scope": plan.table_scope,
            "entity_type": plan.entity_type,
            "metric": plan.metric,
            "aggregation": plan.aggregation,
            "filters": plan.filters.model_dump(),
            "ranking": plan.ranking.model_dump(),
            "match_conditions": [mc.model_dump() for mc in plan.match_conditions] if plan.match_conditions else None,
        }

        # convenience translation for bottom-N questions
        filters = payload["filters"]
        if (
            filters.get("opponent_rank_gte") is None
            and filters.get("opponent_rank_between") is None
            and filters.get("opponent_rank_lte") is None
            and plan.ranking.mode in {"top_n", "ordinal", "entity_value"}
        ):
            pass

        return payload


if __name__ == "__main__":
    planner = QueryPlanner()

    sample_questions = [
        "How many goals has E. Haaland scored against top-6 teams this season?",
        "Which player has scored the most away goals this season?",
        "Which midfielder has played the most progressive passes against top-6 teams this season?",
        "Which team won the most points against Big Six teams this season?",
    ]

    for q in sample_questions:
        print("=" * 80)
        print(q)
        try:
            plan = planner.resolve(q)
            print(json.dumps(planner.to_debug_dict(plan), indent=2, ensure_ascii=False))
        except ValidationError as e:
            print("ValidationError:", e)
        except Exception as e:
            print("Error:", e)