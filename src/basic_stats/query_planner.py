import json
import re
import unicodedata
from pathlib import Path
from typing import Any

import polars as pl
import yaml
from pydantic import BaseModel, Field, ValidationError

from src.basic_stats.config import (
    PLAYER_DATA_PATH,
    PROMPTS_DIR,
    TEAM_DATA_PATH,
    get_llm_client,
    get_model,
)


def _normalize_text(text: str) -> str:
    text = text.strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[\u2018\u2019\u02bc]", "'", text)  # smart quotes → ASCII apostrophe
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


def _extract_top_rank_bucket(q: str) -> int | None:
    patterns = [
        r"\bagainst\s+top[-\s]?(\d+)\b",
        r"\bvs\.?\s+top[-\s]?(\d+)\b",
        r"\bversus\s+top[-\s]?(\d+)\b",
        r"\bcontra\s+top[-\s]?(\d+)\b",
        r"\bagainst\s+top\s+(\d+)\s+teams\b",
        r"\bvs\.?\s+top\s+(\d+)\s+teams\b",
        r"\bversus\s+top\s+(\d+)\s+teams\b",
        r"\bcontra\s+equipos?\s+del\s+top[-\s]?(\d+)\b",
        r"\bequipos?\s+del\s+top[-\s]?(\d+)\b",
    ]
    for pattern in patterns:
        m = re.search(pattern, q)
        if m:
            return int(m.group(1))
    return None


def _extract_bottom_rank_bucket(q: str) -> int | None:
    patterns = [
        r"\bbottom[-\s]?(\d+)\b",
        r"\blast[-\s]?(\d+)\s+teams?\b",  # "last N teams" only — NOT "last N gameweeks/rounds/weeks"
        r"\bultimos?\s+(\d+)\b",
        r"\búltimos?\s+(\d+)\b",
    ]
    for pattern in patterns:
        m = re.search(pattern, q)
        if m:
            return int(m.group(1))
    return None


# Mid-table bucket: positions 7–14 in a 20-team Premier League season.
# Simple stable rule: middle 8 teams by final standings rank.
MID_TABLE_RANGE: tuple[int, int] = (7, 14)


def _extract_recent_window(q: str) -> int | None:
    """Extract N from 'last N gameweeks/rounds/matchdays/weeks/jornadas'.
    Returns the integer window size, or None if not detected.
    Only matches patterns with an explicit numeric N followed by a time-unit word."""
    patterns = [
        r"\blast\s+(\d+)\s+(?:gameweeks?|game\s*weeks?|rounds?|matchdays?|jornadas?|weeks?)\b",
        r"\b[uú]ltimas?\s+(\d+)\s+(?:jornadas?|semanas?|gameweeks?|rondas?)\b",
    ]
    for pattern in patterns:
        m = re.search(pattern, q)
        if m:
            return int(m.group(1))
    return None


def _extract_mid_table_bucket(q: str) -> bool:
    patterns = [
        r"\bmid[-\s]?table\b",
        r"\bmidtable\b",
        r"\bmiddle\s+of\s+the\s+table\b",
        r"\bmiddle\s+teams\b",
        r"\bmedia\s+tabla\b",
    ]
    return any(re.search(p, q) for p in patterns)


def _classify_all_buckets(q: str) -> list[dict]:
    """
    Return one filter-dict per opponent bucket detected in q.
    Recognises: top-N, bottom-N, mid-table, big-six.
    Order matches detection order; at most one entry per bucket type.
    """
    buckets: list[dict] = []

    top_n = _extract_top_rank_bucket(q)
    if top_n is not None:
        buckets.append({"opponent_rank_lte": top_n})

    bottom_n = _extract_bottom_rank_bucket(q)
    if bottom_n is not None:
        buckets.append({"opponent_rank_gte": max(1, 21 - bottom_n)})

    if _extract_mid_table_bucket(q):
        lo, hi = MID_TABLE_RANGE
        buckets.append({"opponent_rank_between": [lo, hi]})

    if re.search(r"\bbig\s*s?ix\b|\bbig\s*6\b", q, re.IGNORECASE):
        buckets.append({"opponent_is_big6": True})

    return buckets


def _detect_dual_bucket_comparison(q: str) -> tuple[dict, dict] | None:
    """
    Detect a two-bucket comparison intent.

    Returns (filters_a, filters_b) when:
    - the question contains 'or' (conjunction between two opponent groups), AND
    - exactly two distinct opponent buckets are found via _classify_all_buckets.

    Returns None for single-bucket questions, zero-bucket questions,
    and three-or-more-bucket questions (ambiguous).
    No plan dict is modified; this is detection only.
    """
    if not re.search(r"\bor\b", q, re.IGNORECASE):
        return None
    buckets = _classify_all_buckets(q)
    if len(buckets) == 2:
        return (buckets[0], buckets[1])
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


def _normalize_metric_key(metric: str) -> str:
    metric = metric.strip().lower()
    metric = metric.replace("-", "_")
    metric = metric.replace(" ", "_")
    metric = re.sub(r"_+", "_", metric)
    return metric


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
    return any(
        [
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
            _extract_top_rank_bucket(q) is not None,
            _extract_bottom_rank_bucket(q) is not None,
            _extract_mid_table_bucket(q),
        ]
    )


PLAYER_MATCH_CONDITION_ALLOWED_METRICS = {
    "goals",
    "assists",
    "minutes_played",
    "own_goals",
    "red_card",
    "yellow_card",
}

FILTER_LIKE_MATCH_CONDITION_MAP = {
    "opponent_is_big6": "opponent_is_big6",
    "is_home": "is_home",
    "player_name": "player_name",
    "team_name": "team_name",
    "opponent_team_name": "opponent_team_name",
    "position": "position",
    "matchday_start": "matchday_start",
    "matchday_end": "matchday_end",
    "min_minutes": "min_minutes",
    "min_matches": "min_matches",
    "age_lt": "age_lt",
}


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
        "passes_to_box": {
            "players_summary": "passes_to_box",
        },
        "passes_into_box": {
            "players_summary": "passes_to_box",
        },
        "yellow_cards": {"players_summary": "total_yellow_cards"},
        "yellow_card": {"players_summary": "total_yellow_cards"},
        "goals_per_90": {"players_summary": "total_goals_p90", "teams_summary": "total_goals_p90"},
        "progressive_passes_per_90": {
            "players_summary": "progressive_passes_p90",
            "teams_summary": "progressive_passes_p90",
        },
        "passing_accuracy": {
            "players_summary": "pass_accuracy_pct",
            "teams_summary": "pass_accuracy_pct",
        },
        "offsides_drawn": {"teams_summary": "offsides"},
        "team_score": {"players_summary": "total_goals", "teams_summary": "total_goals"},
    }

    def _sanitize_match_conditions(self, plan: QueryPlan) -> QueryPlan:
        """
        match_conditions solo deben usarse para lógica derivada a nivel player_match,
        y solo con métricas válidas del scope.

        Si el LLM mete cosas como opponent_is_big6 ahí, las movemos a filters
        o las descartamos.
        """
        if not plan.match_conditions:
            return plan

        # Fuera de player_match, no queremos match_conditions
        if plan.table_scope != "player_match":
            plan.match_conditions = None
            return plan

        sanitized = []

        for cond in plan.match_conditions:
            metric = cond.metric

            # Si es realmente un filtro contextual, no debe vivir en match_conditions
            if metric in FILTER_LIKE_MATCH_CONDITION_MAP:
                filter_name = FILTER_LIKE_MATCH_CONDITION_MAP[metric]

                # movemos solo si tiene sentido
                if metric == "opponent_is_big6":
                    # solo aceptar boolean true/false
                    if cond.value in [True, False]:
                        setattr(plan.filters, filter_name, bool(cond.value))
                elif metric == "is_home":
                    if cond.value in [True, False]:
                        setattr(plan.filters, filter_name, bool(cond.value))
                elif metric in {
                    "matchday_start",
                    "matchday_end",
                    "min_minutes",
                    "min_matches",
                    "age_lt",
                }:
                    try:
                        setattr(plan.filters, filter_name, int(cond.value))
                    except Exception:
                        pass
                elif metric in {"player_name", "team_name", "opponent_team_name", "position"}:
                    if cond.value is not None:
                        setattr(plan.filters, filter_name, str(cond.value))

                continue

            # Si no es una métrica válida de match condition, se descarta
            if metric not in PLAYER_MATCH_CONDITION_ALLOWED_METRICS:
                continue

            sanitized.append(cond)

        plan.match_conditions = sanitized or None
        return plan

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

    def _infer_scope_from_question(
        self, question: str, current_scope: str | None, metric: str | None
    ) -> str | None:
        q = _normalize_text(question)

        has_match_context = any(
            [
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
                _extract_top_rank_bucket(q) is not None,
                _extract_bottom_rank_bucket(q) is not None,
                _extract_mid_table_bucket(q),
            ]
        )

        player_match_metrics = {
            "goals",
            "assists",
            "own_goals",
            "yellow_card",
            "red_card",
            "minutes_played",
            "total_goals",
            "total_assists",
            "total_minutes",
        }

        player_event_metrics = {
            "passes_attempted",
            "passes_accurate",
            "progressive_passes",
            "forward_passes",
            "back_passes",
            "long_passes",
            "key_passes",
            "crosses",
            "passes_to_final_third",
            "passes_to_box",
            "through_passes",
            "smart_passes",
            "shots",
            "shots_on_target",
            "xg_total",
            "aerial_duels",
            "aerial_duels_won",
            "defensive_duels",
            "defensive_duels_won",
            "offensive_duels",
            "offensive_duels_won",
            "dribbles_attempted",
            "dribbles_won",
            "recoveries",
            "interceptions",
            "clearances",
            "sliding_tackles",
            "fouls_committed",
            "fouls_suffered",
            "progressive_carries",
            "carry_meters_gained",
            "progressive_runs",
            "touches_in_box",
            "shot_assists",
            "ball_losses",
            "goalkeeper_exits",
            "shots_against",
            "saves",
            "reflex_saves",
            "actions_z1",
            "actions_z2",
            "actions_z3",
            "actions_z4",
            "actions_z5",
            "pass_z2_to_z4",
            "pass_z2_to_z5",
            "pass_z3_to_z4",
            "pass_z3_to_z5",
            "carry_z2_to_z4",
            "carry_z2_to_z5",
            "carry_z3_to_z4",
            "carry_z3_to_z5",
            "actions_in_z3",
            "z3_actions",
        }

        team_match_metrics = {
            "team_score",
            "opponent_score",
            "assists",
            "xg_total",
            "progressive_passes",
            "key_passes",
            "touches_in_box",
            "aerial_duels_won",
            "recoveries",
            "interceptions",
            "clearances",
            "fouls_committed",
            "fouls_suffered",
            "actions_z1",
            "actions_z2",
            "actions_z3",
            "actions_z4",
            "actions_z5",
            "pass_z2_to_z4",
            "pass_z2_to_z5",
            "pass_z3_to_z4",
            "pass_z3_to_z5",
            "carry_z2_to_z4",
            "carry_z2_to_z5",
            "carry_z3_to_z4",
            "carry_z3_to_z5",
            "points",
            "wins",
            "goal_difference",
            "actions_in_z3",
            "z3_actions",
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
        self.max_matchday = self._load_max_matchday()
        self._player_alias_map = self._build_player_alias_map()

    def _load_prompt(self, name: str) -> dict:
        return yaml.safe_load((PROMPTS_DIR / f"{name}.yaml").read_text(encoding="utf8"))

    def _load_player_names(self) -> list[str]:
        if "short_name" not in self.players_df.columns:
            return []
        return self.players_df.select("short_name").drop_nulls().unique().to_series().to_list()

    def _load_team_names(self) -> list[str]:
        if "team_name" not in self.teams_df.columns:
            return []
        return self.teams_df.select("team_name").drop_nulls().unique().to_series().to_list()

    def _load_max_matchday(self) -> int:
        """Load the highest gameweek number present in the player match stats parquet.
        Used to translate 'last N gameweeks' into a concrete matchday_start."""
        match_path = PLAYER_DATA_PATH.parent / "player_match_stats.parquet"
        try:
            df = pl.read_parquet(match_path, columns=["gameweek"])
            return int(df["gameweek"].max())
        except Exception:
            return 38  # safe default for a standard 38-matchday season

    def _build_player_alias_map(self) -> dict[str, str]:
        """
        Build a normalized alias → canonical short_name map from first_name / last_name columns.

        Aliases added per player:
          1. first_name + " " + last_name        (e.g. "erling braut haaland" → "E. Haaland")
          2. first_name + " " + last_word_of_ln   (e.g. "erling haaland"       → "E. Haaland")
             — only added when last_word differs from last_name (multi-word last name)
          3. last_word_of_last_name               (e.g. "haaland"              → "E. Haaland")
             — only added when the alias maps to exactly one player (unique surname)

        All keys are _normalize_text normalized. Returns {} if columns are absent.
        """
        required = {"short_name", "first_name", "last_name"}
        if not required.issubset(self.players_df.columns):
            return {}

        alias_map: dict[str, str] = {}
        last_word_seen: dict[str, list[str]] = {}  # lw_norm → [canonical short_names]

        for row in (
            self.players_df.select(["short_name", "first_name", "last_name"])
            .drop_nulls()
            .iter_rows(named=True)
        ):
            sn = row["short_name"]
            fn = (row["first_name"] or "").strip()
            ln = (row["last_name"] or "").strip()
            if not sn or not fn or not ln:
                continue

            ln_words = ln.split()
            last_word = ln_words[-1] if ln_words else ""

            # Alias 1: full first + last name
            alias_map[_normalize_text(fn + " " + ln)] = sn

            # Alias 2: first_name + last_word (only meaningful when ln is multi-word)
            if last_word and last_word.lower() != ln.lower():
                alias_map[_normalize_text(fn + " " + last_word)] = sn

            # Collect last_word candidates for uniqueness check
            if last_word and len(last_word) >= 4:
                lw_norm = _normalize_text(last_word)
                if lw_norm not in last_word_seen:
                    last_word_seen[lw_norm] = []
                if sn not in last_word_seen[lw_norm]:
                    last_word_seen[lw_norm].append(sn)

        # Alias 3: unique last_word surnames
        for lw_norm, sns in last_word_seen.items():
            if len(sns) == 1 and lw_norm not in alias_map:
                alias_map[lw_norm] = sns[0]

        return alias_map

    def _match_player_alias(self, question: str) -> str | None:
        """
        Match a player name from the question using the alias map built from
        first_name / last_name columns.  Checks aliases longest-first so that
        "erling haaland" is preferred over the standalone "haaland" alias.
        Returns the canonical short_name or None.
        """
        q = _normalize_text(question)
        for alias_norm in sorted(self._player_alias_map, key=len, reverse=True):
            if alias_norm and alias_norm in q:
                return self._player_alias_map[alias_norm]
        return None

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

    def _resolve_player_suffix(self, name: str) -> str | None:
        """Resolve a partial or full player name to the canonical DB form.
        Tries:
          1. Exact or suffix match on the whole name (e.g. 'Haaland' → 'E. Haaland')
          2. Suffix match on the last word of a multi-word name
             (e.g. 'Bruno Fernandes' → last word 'fernandes' → 'B. Fernandes')
        """
        name_norm = _normalize_text(name)
        # Pass 1: full-name exact or suffix match
        for candidate in sorted(self.player_names, key=len, reverse=True):
            cand_norm = _normalize_text(candidate)
            if cand_norm == name_norm or cand_norm.endswith(" " + name_norm):
                return candidate
        # Pass 2: last-word surname suffix (for names like "Bruno Fernandes")
        words = name_norm.split()
        if len(words) >= 2:
            last_word = words[-1]
            if len(last_word) >= 4:
                for candidate in sorted(self.player_names, key=len, reverse=True):
                    cand_norm = _normalize_text(candidate)
                    if cand_norm.endswith(" " + last_word):
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

        top_rank_bucket = _extract_top_rank_bucket(q)
        bottom_rank_bucket = _extract_bottom_rank_bucket(q)

        if top_rank_bucket is not None:
            plan["filters"]["opponent_rank_lte"] = top_rank_bucket
            plan["filters"]["opponent_is_big6"] = None

        if bottom_rank_bucket is not None:
            plan["filters"]["opponent_rank_gte"] = max(1, 21 - bottom_rank_bucket)
            plan["filters"]["opponent_is_big6"] = None

        if _extract_mid_table_bucket(q):
            lo, hi = MID_TABLE_RANGE
            plan["filters"]["opponent_rank_between"] = [lo, hi]
            plan["filters"]["opponent_rank_lte"] = None
            plan["filters"]["opponent_rank_gte"] = None
            plan["filters"]["opponent_is_big6"] = None

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

                fixed_conditions.append(
                    {
                        "metric": metric,
                        "operator": operator,
                        "value": value,
                    }
                )

            plan["match_conditions"] = fixed_conditions or None

        else:
            plan["match_conditions"] = None

        has_rank_bucket = top_rank_bucket is not None or bottom_rank_bucket is not None
        mentions_big_six = any(
            tok in q for tok in ["big six", "big6", "big 6", "equipos del big six", "del big six"]
        )
        mentions_progressive_passes = "progressive passes" in q or "pases progresivos" in q
        mentions_shot_assists = "shot assists" in q
        mentions_actions_z3 = any(
            tok in q for tok in ["actions in z3", "actions_z3", "acciones en z3"]
        )
        mentions_goals = "goals" in q or "goles" in q
        mentions_away_goals = "away goals" in q or "goles fuera de casa" in q

        # generic contextual repairs: prefer broad, reusable rules over benchmark-only rules
        if (
            mentions_goals
            and (has_rank_bucket or mentions_big_six)
            and (
                matched_player is not None
                or _targets_player_subject(q)
                or plan["filters"].get("player_name") is not None
            )
        ):
            plan["table_scope"] = "player_match"
            plan["entity_type"] = "player"
            plan["metric"] = "goals"
            plan["aggregation"] = "sum"

        if (
            mentions_progressive_passes
            and has_rank_bucket
            and (
                plan["filters"].get("position") is not None
                or matched_player is not None
                or _targets_player_subject(q)
            )
        ):
            plan["table_scope"] = "player_match_event"
            plan["entity_type"] = "player"
            plan["metric"] = "progressive_passes"
            plan["aggregation"] = "sum"

        if mentions_shot_assists and mentions_big_six:
            plan["table_scope"] = "player_match_event"
            plan["entity_type"] = "player"
            plan["metric"] = "shot_assists"
            plan["aggregation"] = "sum"
            plan["filters"]["opponent_is_big6"] = True

        if mentions_away_goals and _targets_team_subject(q):
            plan["table_scope"] = "team_match"
            plan["entity_type"] = "team"
            plan["metric"] = "team_score"
            plan["aggregation"] = "sum"
            plan["filters"]["is_home"] = False
        elif mentions_away_goals:
            plan["table_scope"] = "player_match"
            plan["entity_type"] = "player"
            plan["metric"] = "goals"
            plan["aggregation"] = "sum"
            plan["filters"]["is_home"] = False

        if (
            mentions_actions_z3
            and (plan["filters"].get("opponent_team_name") is not None or matched_team is not None)
            and _targets_team_subject(q)
        ):
            plan["table_scope"] = "team_match"
            plan["entity_type"] = "team"
            plan["metric"] = "actions_z3"
            plan["aggregation"] = "sum"

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

        elif "away goals" in q or "goles fuera de casa" in q:
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
        elif "progressive passes" in q and ("against top-6" in q or "against top 6" in q):
            plan["table_scope"] = "player_match_event"
            plan["entity_type"] = "player"
            plan["metric"] = "progressive_passes"
            plan["aggregation"] = "sum"
            plan["filters"]["opponent_rank_lte"] = 6

        elif "key passes" in q and (
            "between matchdays" in q or "between gameweeks" in q or "entre jornadas" in q
        ):
            plan["table_scope"] = "player_match_event"
            plan["entity_type"] = "player"
            plan["metric"] = "key_passes"
            plan["aggregation"] = "sum"

        elif "shot assists" in q and ("big six" in q or "big6" in q or "big 6" in q):
            plan["table_scope"] = "player_match_event"
            plan["entity_type"] = "player"
            plan["metric"] = "shot_assists"
            plan["aggregation"] = "sum"
            plan["filters"]["opponent_is_big6"] = True

        # Sprint 5 - team match context
        elif ("points" in q or "puntos" in q) and ("big six" in q or "big6" in q or "big 6" in q):
            plan["table_scope"] = "team_match"
            plan["entity_type"] = "team"
            plan["metric"] = "team_score"
            plan["aggregation"] = "points"
            plan["filters"]["opponent_is_big6"] = True

        elif "away wins" in q or "victorias fuera de casa" in q:
            plan["table_scope"] = "team_match"
            plan["entity_type"] = "team"
            plan["metric"] = "team_score"
            plan["aggregation"] = "wins"
            plan["filters"]["is_home"] = False

        elif "actions in z3" in q or "acciones en z3" in q or "actions_z3" in q:
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

        if plan.get("aggregation") in {"mean", "average"}:
            plan["aggregation"] = "avg"
        # per_90/per90 aggregations are intentionally left as-is here so they fail
        # _validate_scope_and_metric and fall back to the legacy _resolve_metric path,
        # which handles per-90 queries correctly for all position filters.

        if aggregation is None or aggregation == "sum":
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
        metric = _normalize_metric_key(metric)
        if isinstance(metric, str):
            plan["metric"] = metric

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
        has_context = any(
            [
                plan["filters"]["is_home"] is not None,
                plan["filters"]["opponent_rank_lte"] is not None,
                plan["filters"]["opponent_rank_gte"] is not None,
                plan["filters"]["opponent_rank_between"] is not None,
                plan["filters"]["opponent_is_big6"] is not None,
                plan["filters"]["matchday_start"] is not None,
                plan["filters"]["matchday_end"] is not None,
                plan["filters"]["opponent_team_name"] is not None,
            ]
        )

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

        top_rank_bucket = _extract_top_rank_bucket(q)
        bottom_rank_bucket = _extract_bottom_rank_bucket(q)

        if _extract_mid_table_bucket(q):
            lo, hi = MID_TABLE_RANGE
            plan["filters"]["opponent_rank_between"] = [lo, hi]
            plan["filters"]["opponent_rank_lte"] = None
            plan["filters"]["opponent_rank_gte"] = None
            plan["filters"]["opponent_is_big6"] = None

        elif top_rank_bucket is not None:
            plan["filters"]["opponent_rank_lte"] = top_rank_bucket
            plan["filters"]["opponent_is_big6"] = None

        elif bottom_rank_bucket is not None:
            plan["filters"]["opponent_rank_gte"] = max(1, 21 - bottom_rank_bucket)
            plan["filters"]["opponent_is_big6"] = None

        elif (
            "big six" in q
            or "big6" in q
            or "big 6" in q
            or "equipos del big six" in q
            or "del big six" in q
        ):
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

        # "last N gameweeks/rounds" → concrete matchday window
        # Only fires when no explicit matchday range is already set.
        if plan["filters"]["matchday_start"] is None:
            recent_n = _extract_recent_window(q)
            if recent_n is not None:
                end_gw = self.max_matchday
                plan["filters"]["matchday_end"] = end_gw
                plan["filters"]["matchday_start"] = max(1, end_gw - recent_n + 1)

        # Strong scope corrections from obvious context
        has_context = any(
            [
                plan["filters"]["is_home"] is not None,
                plan["filters"]["opponent_rank_lte"] is not None,
                plan["filters"]["opponent_rank_gte"] is not None,
                plan["filters"]["opponent_rank_between"] is not None,
                plan["filters"]["opponent_is_big6"] is not None,
                plan["filters"]["matchday_start"] is not None,
                plan["filters"]["matchday_end"] is not None,
                plan["filters"]["opponent_team_name"] is not None,
            ]
        )

        if has_context:
            if plan["entity_type"] == "player":
                # LLM may return summary-scope names; convert to match-level equivalents
                if plan["metric"] == "total_goals":
                    plan["metric"] = "goals"
                elif plan["metric"] == "total_assists":
                    plan["metric"] = "assists"
                if plan["metric"] in {
                    "goals",
                    "assists",
                    "own_goals",
                    "yellow_card",
                    "red_card",
                    "minutes_played",
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
        if not matched_player:
            matched_player = self._match_player_alias(question)
        matched_team = self._match_known_name(question, self.team_names)

        own_team_hint = self._extract_own_team_hint(question)
        opponent_team_hint = self._extract_opponent_team_hint(question)

        # Deterministic question-scan result always overrides LLM-extracted name
        # because the alias map gives the canonical DB form (e.g. "Erling Haaland" → "E. Haaland").
        if matched_player:
            plan.filters.player_name = matched_player
        elif plan.filters.player_name:
            # Resolve partial player names (e.g. LLM returns "Haaland", DB has "E. Haaland")
            resolved = self._resolve_player_suffix(plan.filters.player_name)
            if resolved:
                plan.filters.player_name = resolved

        # Temporal-window fallback: when the question has a 'last N gameweeks' window but
        # neither the LLM nor _match_known_name found a player, scan the question word-by-word.
        # Gated on matchday_start being set so this only fires for temporal-window queries.
        if (
            not plan.filters.player_name
            and not matched_player
            and plan.filters.matchday_start is not None
        ):
            for word in question.split():
                candidate = word.strip("?.,!'\"")
                if len(candidate) >= 4:
                    resolved = self._resolve_player_suffix(candidate)
                    if resolved:
                        plan.filters.player_name = resolved
                        plan.entity_type = "player"
                        break

        # Prefer explicit own-team hint when present
        if own_team_hint and not plan.filters.team_name:
            plan.filters.team_name = own_team_hint

        # Prefer explicit opponent-team hint when present
        if opponent_team_hint and not plan.filters.opponent_team_name:
            plan.filters.opponent_team_name = opponent_team_hint

        # Fallback: only assign matched team if still unassigned and context is safe
        if matched_team:
            if not plan.filters.team_name and not plan.filters.opponent_team_name:
                if (
                    plan.entity_type == "team"
                    and "against" not in q
                    and "vs" not in q
                    and "versus" not in q
                    and "contra" not in q
                ):
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

        # Final deterministic entity/scope guards
        if matched_player:
            plan.entity_type = "player"
        elif plan.filters.position is not None or _targets_player_subject(q):
            plan.entity_type = "player"
        elif _targets_team_subject(q):
            plan.entity_type = "team"

        if plan.filters.player_name:
            plan.entity_type = "player"
        if plan.filters.team_name and _targets_team_subject(q):
            plan.entity_type = "team"

        has_context = any(
            [
                plan.filters.is_home is not None,
                plan.filters.opponent_rank_lte is not None,
                plan.filters.opponent_rank_gte is not None,
                plan.filters.opponent_rank_between is not None,
                plan.filters.opponent_is_big6 is not None,
                plan.filters.matchday_start is not None,
                plan.filters.matchday_end is not None,
                plan.filters.opponent_team_name is not None,
            ]
        )

        if (
            plan.metric in {"actions_z3", "actions_in_z3", "z3_actions"}
            and plan.filters.opponent_team_name
            and plan.entity_type == "team"
        ):
            plan.metric = "actions_z3"
            plan.table_scope = "team_match"
            plan.aggregation = "sum"

        if plan.metric == "goals" and has_context and plan.entity_type == "player":
            plan.table_scope = "player_match"

        if (
            plan.metric in {"progressive_passes", "shot_assists", "key_passes", "touches_in_box"}
            and has_context
            and plan.entity_type == "player"
        ):
            plan.table_scope = "player_match_event"

        if (
            plan.entity_type == "team"
            and plan.metric in {"goals", "total_goals", "away_goals"}
            and plan.table_scope == "team_match"
        ):
            plan.metric = "team_score"

        if plan.metric == "team_score" and has_context and plan.entity_type == "team":
            plan.table_scope = "team_match"

        if plan.entity_type == "team" and plan.table_scope == "player_match_event":
            plan.table_scope = "team_match"

        if plan.entity_type == "team" and plan.table_scope == "player_match":
            plan.table_scope = "team_match"
            if plan.metric == "goals":
                plan.metric = "team_score"

        if plan.entity_type == "player" and plan.table_scope == "teams_summary" and not has_context:
            plan.table_scope = "players_summary"

        # If question explicitly says "against X", that team should not also become team_name
        if plan.filters.team_name and plan.filters.opponent_team_name:
            if plan.filters.team_name == plan.filters.opponent_team_name:
                plan.filters.team_name = None

        plan = self._sanitize_match_conditions(plan)

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
            "match_conditions": [mc.model_dump() for mc in plan.match_conditions]
            if plan.match_conditions
            else None,
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
