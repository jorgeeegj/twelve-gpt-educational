"""
LLMQueryEngine v2 — planner-first + generic DuckDB dispatch.

Flow:
1. QueryPlanner resolves the question into a structured plan
2. Engine dispatches by table_scope
3. DuckDBManager runs a generic query for that scope
4. LLM verbalizes grounded rows

This version keeps only a small summary fallback path for robustness.
"""

import json
import re
import unicodedata

import polars as pl
import yaml

from utils.basic_stats.core.config import (
    PLAYER_DATA_PATH,
    TEAM_DATA_PATH,
    PROMPTS_DIR,
    get_llm_client,
    get_model,
)
from utils.basic_stats.core.duckdb_manager import DuckDBManager
from utils.basic_stats.core.models import MetricResolution, QueryResult
from utils.basic_stats.core.query_planner import QueryPlanner, _detect_dual_bucket_comparison, _classify_all_buckets


NEGATIVE_METRICS = {
    "ball_losses",
    "fouls_committed",
    "total_yellow_cards",
    "total_red_cards",
    "offsides",
    "total_goals_against",
    "shots_against",
}

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

ORDINAL_WORDS_EN = {
    "first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5,
    "sixth": 6, "seventh": 7, "eighth": 8, "ninth": 9, "tenth": 10,
    "eleventh": 11, "twelfth": 12, "thirteenth": 13, "fourteenth": 14,
    "fifteenth": 15, "sixteenth": 16, "seventeenth": 17, "eighteenth": 18,
    "nineteenth": 19, "twentieth": 20,
}

ORDINAL_WORDS_ES = {
    "primero": 1, "segunda": 2, "segundo": 2, "tercero": 3, "tercera": 3,
    "cuarto": 4, "cuarta": 4, "quinto": 5, "quinta": 5, "sexto": 6, "sexta": 6,
    "septimo": 7, "septima": 7, "séptimo": 7, "séptima": 7,
    "octavo": 8, "octava": 8, "noveno": 9, "novena": 9,
    "decimo": 10, "decima": 10, "décimo": 10, "décima": 10,
}

TOP_PATTERNS = [
    r"\btop\s+(\d+)\b",
    r"\bbest\s+(\d+)\b",
    r"\bhighest\s+(\d+)\b",
    r"\b(\d+)\s+(?:teams|players)\b",
    r"\blos\s+(\d+)\s+mejores\b",
    r"\blos\s+top\s+(\d+)\b",
    r"\btop\s+(\d+)\s+(?:jugadores|equipos)\b",
]


def _load_prompt(name: str) -> dict:
    return yaml.safe_load((PROMPTS_DIR / f"{name}.yaml").read_text(encoding="utf8"))


def _normalize_text(text: str) -> str:
    text = text.strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", text)

def _detect_subject_entity(question: str) -> str | None:
    q = _normalize_text(question)

    player_patterns = [
        r"^\s*which player\b",
        r"^\s*what player\b",
        r"^\s*who\b",
        r"^\s*how many\b.*\bhas\b",
        r"^\s*que jugador\b",
        r"^\s*qué jugador\b",
    ]
    if any(re.search(p, q) for p in player_patterns):
        return "player"

    team_patterns = [
        r"^\s*which team\b",
        r"^\s*what team\b",
        r"^\s*which club\b",
        r"^\s*which side\b",
        r"^\s*que equipo\b",
        r"^\s*qué equipo\b",
    ]
    if any(re.search(p, q) for p in team_patterns):
        return "team"

    return None

def _extract(pattern: str, text: str) -> int | None:
    m = re.search(pattern, text)
    return int(m.group(1)) if m else None


def _extract_top_n(q: str) -> int:
    for pattern in TOP_PATTERNS:
        m = re.search(pattern, q)
        if m:
            return int(m.group(1))
    return 1

def _detect_true_tie(rows: list[dict], metric: str, ranking: dict | None) -> bool:
    if not rows or len(rows) <= 1:
        return False

    ranking = ranking or {}
    mode = ranking.get("mode")
    n = ranking.get("n")

    # Solo hay empate "real" si la consulta pedía un único líder
    if mode == "top_n" and (n is not None and n > 1):
        return False

    if mode in {"ordinal", "entity_value"}:
        return False

    values = []
    for row in rows:
        val = row.get(metric)
        if isinstance(val, (int, float)):
            values.append(float(val))

    if len(values) <= 1:
        return False

    best = values[0]
    tied_count = sum(1 for v in values if v == best)

    return tied_count > 1



def _extract_rank_position(q: str) -> int | None:
    patterns = [
        r"\b(\d+)(?:st|nd|rd|th)\b",
        r"\b(\d+)[ºª]\b",
        r"\bposition\s+(\d+)\b",
        r"\bpuesto\s+(\d+)\b",
        r"\bposicion\s+(\d+)\b",
    ]
    for pattern in patterns:
        m = re.search(pattern, q)
        if m:
            return int(m.group(1))

    for word, value in ORDINAL_WORDS_EN.items():
        if re.search(rf"\b{re.escape(word)}\b", q):
            return value

    for word, value in ORDINAL_WORDS_ES.items():
        if re.search(rf"\b{re.escape(word)}\b", q):
            return value

    return None


def _is_ordinal_query(q: str) -> bool:
    ordinal_markers = [
        r"\b\d+(?:st|nd|rd|th)\b",
        r"\b\d+[ºª]\b",
        r"\bfirst\b", r"\bsecond\b", r"\bthird\b", r"\bfourth\b", r"\bfifth\b",
        r"\bseventh\b", r"\btenth\b",
        r"\bprimero\b", r"\bsegundo\b", r"\btercero\b", r"\bquinto\b", r"\bdecimo\b", r"\bdécimo\b",
        r"\bposition\b", r"\bpuesto\b", r"\bposicion\b",
    ]
    return any(re.search(pattern, q) for pattern in ordinal_markers)


def _player_tiebreak_desc_for_minutes(metric: str, descending: bool) -> bool:
    if metric in NEGATIVE_METRICS:
        return not descending
    return False

def _slug_metric_suffix(text: str) -> str:
    text = _normalize_text(text)
    text = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    return text

def _has_match_context_filters(filters: dict) -> bool:
    context_keys = [
        "opponent_team_name",
        "is_home",
        "opponent_rank_lte",
        "opponent_rank_gte",
        "opponent_rank_between",
        "opponent_is_big6",
        "matchday_start",
        "matchday_end",
    ]
    return any(filters.get(k) is not None for k in context_keys)

def _has_match_level_logic(plan) -> bool:
    if getattr(plan, "match_conditions", None):
        return True

    if plan.table_scope in {"player_match", "player_match_event", "team_match"}:
        if plan.aggregation in {"count_matches_positive", "points", "wins", "goal_difference"}:
            return True

    return False


def _bucket_label(bucket: dict) -> str:
    """Return a short human-readable label for an opponent-bucket filter dict."""
    if "opponent_rank_lte" in bucket:
        return f"top {bucket['opponent_rank_lte']} teams"
    if "opponent_rank_gte" in bucket:
        bottom_n = 21 - bucket["opponent_rank_gte"]
        return f"bottom {bottom_n} teams"
    if "opponent_rank_between" in bucket:
        lo, hi = bucket["opponent_rank_between"]
        return f"mid-table teams (positions {lo}–{hi})"
    if bucket.get("opponent_is_big6"):
        return "Big Six teams"
    return "that group"


def _compute_p90(val: float, denominator: int | None, is_player: bool) -> float | None:
    """
    Compute per-90 rate for a subset.
    Player: val / minutes * 90.  Team: val / match_count (standard 90-min-per-match).
    Returns None when denominator is absent or zero.
    """
    if not denominator:
        return None
    if is_player:
        return round(float(val) / denominator * 90, 2)
    return round(float(val) / denominator, 2)


_PLAYER_P90_MAP: dict[str, str] = {
    "goals":               "total_goals_p90",
    "assists":             "total_assists_p90",
    "shot_assists":        "shot_assists_p90",
    "key_passes":          "key_passes_p90",
    "progressive_passes":  "progressive_passes_p90",
    "passes_to_box":       "passes_to_box_p90",
    "crosses":             "crosses_p90",
    "forward_passes":      "forward_passes_p90",
    "smart_passes":        "smart_passes_p90",
    "through_passes":      "through_passes_p90",
}

_TEAM_P90_MAP: dict[str, str] = {
    "team_score":     "total_goals_p90",
    "opponent_score": "total_goals_against_p90",
}


def _detect_home_away_comparison(q: str) -> tuple[dict, dict] | None:
    """
    Detect a home-vs-away comparison intent.

    Returns ({"is_home": False}, {"is_home": True}) when:
    - question contains both 'home' and 'away'
    - question contains 'or'
    - question does NOT contain opponent-rank bucket language
      (to avoid colliding with dual-bucket detection)

    Returns None otherwise.
    """
    ql = q.lower()
    if "home" not in ql or "away" not in ql:
        return None
    if not re.search(r"\bor\b", ql):
        return None
    # Exclude questions that also have rank buckets — those belong to dual-bucket path
    rank_patterns = [
        r"\btop[-\s]?\d+\b",
        r"\bbottom[-\s]?\d+\b",
        r"\bmid.?table\b",
        r"\bbig.?six\b",
        r"\bbig\s*6\b",
    ]
    for pat in rank_patterns:
        if re.search(pat, ql):
            return None
    return ({"is_home": False}, {"is_home": True})


# ── metric-derived opponent bucket ────────────────────────────────────────────

_METRIC_BUCKET_RE = re.compile(
    r"\bthe\s+(\d+)\s+teams?\s+that\s+"
    r"(?:have\s+)?"
    r"(score[ds]?|concede[ds]?|take[ns]?|took|attempt(?:s|ed)?|allow(?:s|ed)?|face[ds]?)"
    r"\s+the\s+(most|fewest)"
    r"(?:\s+(goals?|shots?))?",
    re.IGNORECASE,
)

# verbs that pair naturally only with shots; default trailing noun is "shots" for these
_SHOTS_ONLY_VERBS = frozenset({
    "take", "takes", "taken", "took",
    "attempt", "attempts", "attempted",
    "allow", "allows", "allowed",
    "face", "faces", "faced",
})

# keyed by (verb, trailing_noun) — trailing noun defaults to "goals" or "shots" by verb family
_BUCKET_VERB_METRIC: dict[tuple[str, str], str] = {
    ("score",     "goals"): "total_goals",
    ("scores",    "goals"): "total_goals",
    ("scored",    "goals"): "total_goals",
    ("concede",   "goals"): "total_goals_against",
    ("concedes",  "goals"): "total_goals_against",
    ("conceded",  "goals"): "total_goals_against",
    # score/concede + shots
    ("concede",   "shots"): "shots_against",
    ("concedes",  "shots"): "shots_against",
    ("conceded",  "shots"): "shots_against",
    ("score",     "shots"): "shots",
    ("scores",    "shots"): "shots",
    ("scored",    "shots"): "shots",
    # take/attempt → shots (offensive)
    ("take",      "shots"): "shots",
    ("takes",     "shots"): "shots",
    ("taken",     "shots"): "shots",
    ("took",      "shots"): "shots",
    ("attempt",   "shots"): "shots",
    ("attempts",  "shots"): "shots",
    ("attempted", "shots"): "shots",
    # allow/face → shots_against (defensive)
    ("allow",     "shots"): "shots_against",
    ("allows",    "shots"): "shots_against",
    ("allowed",   "shots"): "shots_against",
    ("face",      "shots"): "shots_against",
    ("faces",     "shots"): "shots_against",
    ("faced",     "shots"): "shots_against",
}

# canonical human-readable label for each (bucket_metric, descending) combo
_BUCKET_METRIC_LABEL: dict[tuple[str, bool], str] = {
    ("total_goals",         True):  "have scored the most goals",
    ("total_goals",         False): "have scored the fewest goals",
    ("total_goals_against", True):  "have conceded the most goals",
    ("total_goals_against", False): "have conceded the fewest goals",
    ("shots_against",       True):  "concede the most shots",
    ("shots_against",       False): "concede the fewest shots",
    ("shots",               True):  "take the most shots",
    ("shots",               False): "take the fewest shots",
}


def _detect_metric_derived_bucket(q: str) -> dict | None:
    """
    Detect a metric-derived opponent bucket intent.

    Matches: "the N teams that [have] score[d]/concede[d] the most/fewest [goals|shots]"
    Returns a spec dict or None.

    Guard: if any fixed rank bucket (top-N, bottom-N, big-six, mid-table) is
    already present in q, returns None and lets existing paths handle the question.
    """
    if _classify_all_buckets(q):
        return None

    m = _METRIC_BUCKET_RE.search(q)
    if not m:
        return None

    n = int(m.group(1))
    verb = m.group(2).lower()
    direction = m.group(3).lower()
    trailing = m.group(4).lower().rstrip("s") + "s" if m.group(4) else ("shots" if verb in _SHOTS_ONLY_VERBS else "goals")

    bucket_metric = _BUCKET_VERB_METRIC.get((verb, trailing))
    if not bucket_metric:
        return None

    descending = direction == "most"
    label = _BUCKET_METRIC_LABEL.get((bucket_metric, descending), "")

    return {
        "n": n,
        "bucket_metric": bucket_metric,
        "descending": descending,
        "label": label,
    }


def _derive_teams_for_bucket(
    teams_df: "pl.DataFrame", n: int, bucket_metric: str, descending: bool
) -> list[str]:
    """Return N team names sorted by bucket_metric (descending=True for 'most')."""
    if bucket_metric not in teams_df.columns:
        return []
    return (
        teams_df
        .select(["team_name", bucket_metric])
        .sort(bucket_metric, descending=descending)
        .head(n)["team_name"]
        .to_list()
    )


class LLMQueryEngineV2:
    def __init__(self):
        self.players_df = pl.read_parquet(PLAYER_DATA_PATH)
        self.teams_df = pl.read_parquet(TEAM_DATA_PATH)

        if "goal_contributions" not in self.players_df.columns:
            self.players_df = self.players_df.with_columns(
                (pl.col("total_goals") + pl.col("total_assists")).alias("goal_contributions")
            )

        self.client = get_llm_client()
        self.model = get_model()

        self._player_enum = [c for c in PLAYER_COLS if c in self.players_df.columns]
        self._team_enum = [c for c in TEAM_COLS if c in self.teams_df.columns]

        self._resolve_prompt = _load_prompt("resolve_metric")
        self._verbalize_prompt = _load_prompt("verbalize")

        self.duck = DuckDBManager()
        self.planner = QueryPlanner()

    def _metric_description(self, metric: str) -> str:
        col_descriptions = self._resolve_prompt.get("column_descriptions", {})
        col_aliases = self._resolve_prompt.get("column_aliases", {})

        desc = col_descriptions.get(metric, metric)
        aliases = col_aliases.get(metric, [])

        if aliases:
            return f"{metric}: {desc}. Aliases/examples: {', '.join(aliases)}"
        return f"{metric}: {desc}"

    def _resolve_fast_path(self, q: str) -> MetricResolution | None:
        is_team_query = any(tok in q for tok in [" team ", " teams ", "equipo", "equipos"])

        if any(p in q for p in [
            "most goals", "top scorer", "scored the most goals",
            "ha marcado mas goles", "ha metido mas goles", "lidera la liga en goles",
            "maximo goleador", "maximos goleadores"
        ]):
            return MetricResolution(
                metric="total_goals",
                descending=True,
                table="teams" if is_team_query else "players"
            )

        if any(p in q for p in [
            "most assists", "highest assists",
            "mas asistencias", "tiene mas asistencias", "lidera la liga en asistencias"
        ]):
            return MetricResolution(metric="total_assists", descending=True, table="players")

        if any(p in q for p in [
            "most minutes", "played the most minutes", "most total minutes",
            "mas minutos", "ha jugado mas minutos"
        ]):
            return MetricResolution(metric="total_minutes", descending=True, table="players")

        if any(p in q for p in [
            "most yellow cards", "received the most yellow cards",
            "mas tarjetas amarillas", "ha visto mas amarillas"
        ]):
            return MetricResolution(metric="total_yellow_cards", descending=True, table="players")

        if any(p in q for p in [
            "fewest goals conceded", "conceded the fewest", "fewest conceded goals",
            "menos goles encajados", "ha encajado menos goles"
        ]):
            return MetricResolution(metric="total_goals_against", descending=False, table="teams")

        if any(p in q for p in [
            "most accurate passing", "best pass accuracy",
            "mayor precision de pase", "mejor precision de pase", "mejor porcentaje de pase"
        ]):
            return MetricResolution(
                metric="pass_accuracy_pct",
                descending=True,
                table="teams" if is_team_query else "players"
            )

        if any(p in q for p in [
            "provokes the most offsides", "most offsides",
            "provoca mas fueras de juego", "mas fueras de juego"
        ]):
            return MetricResolution(metric="offsides", descending=True, table="teams")

        return None

    def _result_metric_name_from_plan(self, plan, filters: dict) -> str:
        if plan.table_scope in {"players_summary", "teams_summary"}:
            return plan.metric

        if plan.table_scope == "player_match":

            if plan.match_conditions:
                if len(plan.match_conditions) == 2:
                    cond_metrics = sorted([mc.metric for mc in plan.match_conditions])
                    if cond_metrics == ["assists", "goals"]:
                        return "matches_scored_and_assisted"

                if len(plan.match_conditions) == 1:
                    mc = plan.match_conditions[0]
                    if mc.metric == "goals" and mc.operator == ">=" and float(mc.value) == 2:
                        return "two_goal_matches"
            
            if plan.metric == "goals" and filters.get("team_name") and filters.get("matchday_start") and filters.get("matchday_end"):
                return f"goals_gw_{filters['matchday_start']}_{filters['matchday_end']}"

            if plan.metric == "goals" and filters.get("opponent_rank_lte") is not None:
                return f"goals_vs_top{filters['opponent_rank_lte']}"

            if plan.metric == "goals" and filters.get("is_home") is False:
                return "away_goals"

            if plan.metric == "goals":
                if filters.get("team_name") and filters.get("matchday_start") and filters.get("matchday_end"):
                    return f"goals_gw_{filters['matchday_start']}_{filters['matchday_end']}"
                if filters.get("opponent_is_big6") is True:
                    return "goals_vs_big6"
                if filters.get("opponent_rank_lte") is not None:
                    return f"goals_vs_top{filters['opponent_rank_lte']}"
                if filters.get("opponent_rank_gte") is not None:
                    bottom_n = 21 - filters["opponent_rank_gte"]
                    return f"goals_vs_bottom{bottom_n}"
                if filters.get("is_home") is False:
                    return "away_goals"

            return plan.metric

        if plan.table_scope == "player_match_event":
            if plan.metric == "progressive_passes" and filters.get("opponent_rank_lte") is not None:
                return f"progressive_passes_vs_top{filters['opponent_rank_lte']}"
            if plan.metric == "touches_in_box" and filters.get("is_home") is False:
                return "touches_in_box_away"
            if plan.metric == "key_passes" and filters.get("matchday_start") and filters.get("matchday_end"):
                return f"key_passes_gw_{filters['matchday_start']}_{filters['matchday_end']}"
            if plan.metric == "shot_assists" and filters.get("opponent_is_big6") is True:
                return "shot_assists_vs_big6"
            return plan.metric

        if plan.table_scope == "team_match":
            if plan.aggregation == "points" and filters.get("opponent_is_big6") is True:
                return "points_vs_big6"

            if plan.aggregation == "wins" and filters.get("is_home") is False:
                return "away_wins"

            if plan.aggregation == "goal_difference" and filters.get("matchday_start") and filters.get("matchday_end"):
                return f"goal_difference_gw_{filters['matchday_start']}_{filters['matchday_end']}"

            if (
                plan.metric == "team_score"
                and filters.get("is_home") is False
                and filters.get("opponent_rank_lte") is None
                and filters.get("opponent_is_big6") is None
            ):
                return "away_goals"

            if plan.metric == "team_score" and filters.get("is_home") is False and filters.get("opponent_rank_lte") is not None:
                return f"away_goals_vs_top{filters['opponent_rank_lte']}"
            if plan.metric.startswith("actions_z") and filters.get("opponent_team_name"):
                suffix = _slug_metric_suffix(filters["opponent_team_name"])
                return f"{plan.metric}_vs_{suffix}"
            return plan.metric

        return plan.metric

    def _is_contextual_question(self, question: str) -> bool:
        q = _normalize_text(question)

        patterns = [
            "between matchdays",
            "between gameweeks",
            "entre jornadas",
            "against top-",
            "against top ",
            "against bottom",
            "contra top",
            "contra equipos del top",
            "against big six",
            "against big 6",
            "against big6",
            "contra equipos del big six",
            "away from home",
            "away goals",
            "away wins",
            "fuera de casa",
            "at home",
            "en casa",
            "against ",
            "versus ",
            "vs ",
            "contra ",
            "matches with",
            "partidos con",
            "actions in z3",
            "acciones en z3",
        ]
        return any(p in q for p in patterns)

    def _resolve_metric(self, question: str) -> MetricResolution:
        q_norm = f" {_normalize_text(question)} "

        fast = self._resolve_fast_path(q_norm)
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
                                    self._metric_description(c) for c in enum
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
                {"role": "user", "content": question},
            ],
            tools=tools,
            tool_choice="required",
        )

        call = response.choices[0].message.tool_calls[0]
        args = json.loads(call.function.arguments)
        table = "players" if call.function.name == "query_players" else "teams"
        return MetricResolution(metric=args["metric"], descending=args["descending"], table=table)

    def _answer_type_from_result(self, result: QueryResult) -> str:
        filters = result.filters_applied or {}
        ranking = filters.get("ranking", {})

        if ranking:
            mode = ranking.get("mode")
            n = ranking.get("n")

            if mode == "entity_value":
                return "entity_value"
            if mode == "ordinal":
                return "ordinal"
            if mode == "top_n":
                return "top_n" if (n or 1) > 1 else "top_1"

        # summary fallback path
        if "rank_position" in filters:
            return "ordinal"
        if filters.get("top_n", 1) > 1:
            return "top_n"
        return "top_1"


    def _metric_label(self, metric: str) -> str:
        labels = {
            "total_goals": "goals",
            "total_assists": "assists",
            "total_minutes": "minutes",
            "total_yellow_cards": "yellow cards",
            "total_goals_against": "goals conceded",
            "pass_accuracy_pct": "pass accuracy",
            "offsides": "offsides",
            "goals_vs_top6": "goals against top-6 teams",
            "goals_vs_big6": "goals against Big Six teams",
            "away_goals": "away goals",
            "progressive_passes_vs_top6": "progressive passes against top-6 teams",
            "touches_in_box_away": "touches in the box away from home",
            "key_passes_gw_25_30": "key passes between matchdays 25 and 30",
            "shot_assists_vs_big6": "shot assists against Big Six teams",
            "points_vs_big6": "points against Big Six teams",
            "away_goals_vs_top6": "away goals against top-6 teams",
            "goal_difference_gw_25_30": "goal difference between matchdays 25 and 30",
            "away_wins": "away wins",
            "actions_z3_vs_manchester_city": "actions in z3 against Manchester City",
            "passes_to_box": "passes to the box",
        }
        return labels.get(metric, metric.replace("_", " "))


    def _context_label_from_result(self, result: QueryResult) -> str:
        filters = result.filters_applied or {}
        parts = []

        if filters.get("matchday_start") and filters.get("matchday_end"):
            parts.append(f"between matchdays {filters['matchday_start']} and {filters['matchday_end']}")

        if filters.get("opponent_team_name"):
            parts.append(f"against {filters['opponent_team_name']}")

        if filters.get("opponent_is_big6") is True:
            parts.append("against Big Six teams")

        if filters.get("opponent_rank_lte") is not None:
            parts.append(f"against top-{filters['opponent_rank_lte']} teams")

        if filters.get("is_home") is False:
            parts.append("away from home")
        elif filters.get("is_home") is True:
            parts.append("at home")

        if not parts:
            parts.append("this season")

        return ", ".join(parts)

    def _execute_summary(self, question: str, resolution: MetricResolution) -> QueryResult:
        df = self.players_df if resolution.table == "players" else self.teams_df
        q = _normalize_text(question)
        filters = {}

        if resolution.table == "players":
            for key, pattern in POSITION_MAP.items():
                if key in q:
                    df = df.filter(pl.col("main_position").str.to_lowercase().str.contains(pattern))
                    filters["position"] = key
                    break

            age_lt = (
                _extract(r"\bunder\s+(\d+)\b", q)
                or _extract(r"\byounger than\s+(\d+)\b", q)
                or _extract(r"\bmenor(?:es)? de\s+(\d+)\b", q)
                or _extract(r"\bsub[\-\s]?(\d+)\b", q)
            )
            if age_lt and "birth_date" in df.columns:
                df = df.with_columns(
                    ((pl.lit(20240801) - pl.col("birth_date").str.replace_all("-", "").cast(pl.Int64)) / 10000)
                    .cast(pl.Int64)
                    .alias("age")
                ).filter(pl.col("age") < age_lt)
                filters["age_lt"] = age_lt

            min_min = (
                _extract(r"\bwith at least\s+(\d+)\s+minutes\b", q)
                or _extract(r"\bmore than\s+(\d+)\s+minutes\b", q)
                or _extract(r"\bal menos\s+(\d+)\s+minutos\b", q)
                or _extract(r"\bcon al menos\s+(\d+)\s+minutos\b", q)
            )
            if min_min:
                df = df.filter(pl.col("total_minutes") >= min_min)
                filters["min_minutes"] = min_min

            min_apps = (
                _extract(r"\bminimum\s+(\d+)\s+(?:appearances|matches|games)\b", q)
                or _extract(r"\bat least\s+(\d+)\s+(?:appearances|matches|games)\b", q)
                or _extract(r"\bal menos\s+(\d+)\s+(?:partidos|apariciones)\b", q)
                or _extract(r"\bminimo\s+(\d+)\s+(?:partidos|apariciones)\b", q)
            )
            if min_apps:
                df = df.filter(pl.col("matches_played") >= min_apps)
                filters["min_matches"] = min_apps

        if resolution.table == "players":
            sort_cols = [resolution.metric]
            descending_flags = [resolution.descending]

            if "total_minutes" in df.columns and resolution.metric != "total_minutes":
                sort_cols.append("total_minutes")
                descending_flags.append(
                    _player_tiebreak_desc_for_minutes(
                        resolution.metric,
                        resolution.descending,
                    )
                )

            if "short_name" in df.columns:
                sort_cols.append("short_name")
                descending_flags.append(False)

            sorted_df = df.sort(by=sort_cols, descending=descending_flags, nulls_last=True)
        else:
            sort_cols = [resolution.metric]
            descending_flags = [resolution.descending]

            if "team_name" in df.columns:
                sort_cols.append("team_name")
                descending_flags.append(False)

            sorted_df = df.sort(by=sort_cols, descending=descending_flags, nulls_last=True)

        rank_position = _extract_rank_position(q) if _is_ordinal_query(q) else None
        top_n = _extract_top_n(q)

        if rank_position is not None:
            if rank_position < 1 or rank_position > sorted_df.height:
                result_df = sorted_df.head(0)
            else:
                result_df = sorted_df.slice(rank_position - 1, 1)
            filters["rank_position"] = rank_position
        else:
            result_df = sorted_df.head(top_n)
            filters["top_n"] = top_n

            if top_n == 1 and result_df.height > 0:
                boundary = result_df[resolution.metric][0]
                result_df = sorted_df.filter(pl.col(resolution.metric) == boundary)

        display = (
            ["short_name", "team_name", "main_position", "age", resolution.metric, "matches_played", "total_minutes"]
            if resolution.table == "players"
            else ["team_name", resolution.metric, "total_goals", "total_goals_against"]
        )
        display = list(dict.fromkeys(c for c in display if c in result_df.columns))

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

    def _execute_planned_query(self, question: str) -> QueryResult | None:
        
        try:
            plan = self.planner.resolve(question)
        except Exception as e:
            print(f"[PLANNER ERROR] {question} -> {repr(e)}")
            return None

        if not self._should_use_planner_result(question, plan):
            return None

        filters = plan.filters.model_dump()
        ranking = plan.ranking.model_dump()

        if plan.table_scope == "players_summary":
            rows = self.duck.query_summary_context(
                scope="players_summary",
                metric=plan.metric,
                descending=(ranking["mode"] != "entity_value"),
                entity_type=plan.entity_type,
                player_name=filters.get("player_name"),
                team_name=filters.get("team_name"),
                position=filters.get("position"),
                age_lt=filters.get("age_lt"),
                min_minutes=filters.get("min_minutes"),
                min_matches=filters.get("min_matches"),
                rank_position=ranking.get("ordinal") if ranking.get("mode") == "ordinal" else None,
                top_n=ranking.get("n") or 1,
            )
            result_metric, rows = self._shape_rows_for_result(plan, rows, filters)
            return QueryResult(
                table="players_summary",
                metric=result_metric,
                rows=rows,
                filters_applied=filters | {"ranking": ranking},
            )

        if plan.table_scope == "teams_summary":
            descending = True
            if plan.metric == "total_goals_against":
                descending = False

            rows = self.duck.query_summary_context(
                scope="teams_summary",
                metric=plan.metric,
                descending=descending,
                entity_type=plan.entity_type,
                team_name=filters.get("team_name"),
                rank_position=ranking.get("ordinal") if ranking.get("mode") == "ordinal" else None,
                top_n=ranking.get("n") or 1,
            )
            result_metric, rows = self._shape_rows_for_result(plan, rows, filters)
            return QueryResult(
                table="teams_summary",
                metric=result_metric,
                rows=rows,
                filters_applied=filters | {"ranking": ranking},
            )

        if plan.table_scope == "player_match":
            rows = self.duck.query_player_match_context(
                metric=plan.metric,
                agg=plan.aggregation,
                player_name=filters.get("player_name"),
                team_name=filters.get("team_name"),
                is_home=filters.get("is_home"),
                opponent_team_name=filters.get("opponent_team_name"),
                opponent_rank_lte=filters.get("opponent_rank_lte"),
                opponent_rank_gte=filters.get("opponent_rank_gte"),
                opponent_rank_between=tuple(filters["opponent_rank_between"]) if filters.get("opponent_rank_between") else None,
                opponent_is_big6=filters.get("opponent_is_big6"),
                matchday_start=filters.get("matchday_start"),
                matchday_end=filters.get("matchday_end"),
                match_conditions=(
                    [mc.model_dump() for mc in plan.match_conditions]
                    if plan.match_conditions else None
                ),
                limit=ranking.get("n") or 1,
            )
            result_metric, rows = self._shape_rows_for_result(plan, rows, filters)
            return QueryResult(
                table="player_match_stats",
                metric=result_metric,
                rows=rows,
                filters_applied=filters | {"ranking": ranking},
            )

        if plan.table_scope == "player_match_event":
            rows = self.duck.query_player_match_event_context(
                metric=plan.metric,
                agg=plan.aggregation,
                player_name=filters.get("player_name"),
                team_name=filters.get("team_name"),
                position=filters.get("position"),
                is_home=filters.get("is_home"),
                opponent_team_name=filters.get("opponent_team_name"),
                opponent_rank_lte=filters.get("opponent_rank_lte"),
                opponent_rank_gte=filters.get("opponent_rank_gte"),
                opponent_rank_between=tuple(filters["opponent_rank_between"]) if filters.get("opponent_rank_between") else None,
                opponent_is_big6=filters.get("opponent_is_big6"),
                matchday_start=filters.get("matchday_start"),
                matchday_end=filters.get("matchday_end"),
                limit=ranking.get("n") or 1,
            )
            result_metric, rows = self._shape_rows_for_result(plan, rows, filters)
            return QueryResult(
                table="player_match_event_stats",
                metric=result_metric,
                rows=rows,
                filters_applied=filters | {"ranking": ranking, "aggregation": plan.aggregation},
            )

        if plan.table_scope == "team_match":
            rows = self.duck.query_team_match_context(
                metric=plan.metric,
                agg=plan.aggregation,
                team_name=filters.get("team_name"),
                is_home=filters.get("is_home"),
                opponent_team_name=filters.get("opponent_team_name"),
                opponent_rank_lte=filters.get("opponent_rank_lte"),
                opponent_rank_gte=filters.get("opponent_rank_gte"),
                opponent_rank_between=tuple(filters["opponent_rank_between"]) if filters.get("opponent_rank_between") else None,
                opponent_is_big6=filters.get("opponent_is_big6"),
                matchday_start=filters.get("matchday_start"),
                matchday_end=filters.get("matchday_end"),
                limit=ranking.get("n") or 1,
            )
            result_metric, rows = self._shape_rows_for_result(plan, rows, filters)
            return QueryResult(
                table="team_match_stats",
                metric=result_metric,
                rows=rows,
                filters_applied=filters | {"ranking": ranking, "aggregation": plan.aggregation},
            )

        return None

    def _shape_rows_for_result(self, plan, rows: list[dict], filters: dict) -> tuple[str, list[dict]]:
        result_metric = self._result_metric_name_from_plan(plan, filters)

        shaped = []
        for row in rows:
            new_row = dict(row)
            if "metric_value" in new_row:
                new_row[result_metric] = new_row.pop("metric_value")
            shaped.append(new_row)

        return result_metric, shaped

    def _should_use_planner_result(self, question: str, plan) -> bool:
        q = _normalize_text(question)
        filters = plan.filters.model_dump()

        subject_entity = _detect_subject_entity(question)
        has_context = _has_match_context_filters(filters)
        has_match_logic = _has_match_level_logic(plan)
        is_contextual = self._is_contextual_question(question)

        # Solo rechazar si el SUJETO de la pregunta contradice claramente el plan.
        if subject_entity == "team" and plan.entity_type == "player":
            return False

        if subject_entity == "player" and plan.entity_type == "team":
            return False

        # Si la pregunta es contextual, debe resolverse en scopes contextuales
        if is_contextual:
            if not has_context and not has_match_logic:
                return False

            if plan.table_scope in {"players_summary", "teams_summary"}:
                return False

        # Si NO es contextual, no debería ir a match scopes salvo que haya lógica real de partido
        if not has_context and not has_match_logic and plan.table_scope in {
            "player_match", "player_match_event", "team_match"
        }:
            return False

        return True

    def _verbalize(self, question: str, result: QueryResult) -> str:
        p = self._verbalize_prompt

        filters = result.filters_applied or {}
        ranking = filters.get("ranking", {}) or {}

        answer_type = self._answer_type_from_result(result)
        metric_label = self._metric_label(result.metric)
        context_label = self._context_label_from_result(result)

        ordinal_position = None
        requested_top_n = 1

        if ranking:
            ordinal_position = ranking.get("ordinal")
            requested_top_n = ranking.get("n") or 1
        else:
            ordinal_position = filters.get("rank_position")
            requested_top_n = filters.get("top_n", 1)

        prompt = p["user"].format(
            question=question,
            metric=result.metric,
            rows=result.rows,
            answer_type=answer_type,
            metric_label=metric_label,
            context_label=context_label,
            ordinal_position=ordinal_position,
            requested_top_n=requested_top_n,
        )

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": p["system"]},
                {"role": "user", "content": prompt},
            ],
        )
        return response.choices[0].message.content.strip()

    def _run_bucket_sub_query(
        self, plan, bucket: dict
    ) -> tuple[float | int | None, list[dict]]:
        """
        Run one duck sub-query for a single opponent bucket.
        Clears all opponent-rank fields from plan.filters, then applies `bucket`.
        Returns (numeric_value_or_None, rows).
        """
        filters = plan.filters.model_dump()
        for key in ("opponent_rank_lte", "opponent_rank_gte", "opponent_rank_between", "opponent_is_big6"):
            filters[key] = None
        filters.update(bucket)

        try:
            if plan.table_scope == "player_match":
                rows = self.duck.query_player_match_context(
                    metric=plan.metric,
                    agg=plan.aggregation,
                    player_name=filters.get("player_name"),
                    team_name=filters.get("team_name"),
                    is_home=filters.get("is_home"),
                    opponent_team_name=filters.get("opponent_team_name"),
                    opponent_rank_lte=filters.get("opponent_rank_lte"),
                    opponent_rank_gte=filters.get("opponent_rank_gte"),
                    opponent_rank_between=(
                        tuple(filters["opponent_rank_between"])
                        if filters.get("opponent_rank_between") else None
                    ),
                    opponent_is_big6=filters.get("opponent_is_big6"),
                    matchday_start=filters.get("matchday_start"),
                    matchday_end=filters.get("matchday_end"),
                    match_conditions=None,
                    limit=1,
                )
            elif plan.table_scope == "team_match":
                rows = self.duck.query_team_match_context(
                    metric=plan.metric,
                    agg=plan.aggregation,
                    team_name=filters.get("team_name"),
                    is_home=filters.get("is_home"),
                    opponent_team_name=filters.get("opponent_team_name"),
                    opponent_rank_lte=filters.get("opponent_rank_lte"),
                    opponent_rank_gte=filters.get("opponent_rank_gte"),
                    opponent_rank_between=(
                        tuple(filters["opponent_rank_between"])
                        if filters.get("opponent_rank_between") else None
                    ),
                    opponent_is_big6=filters.get("opponent_is_big6"),
                    matchday_start=filters.get("matchday_start"),
                    matchday_end=filters.get("matchday_end"),
                    limit=1,
                )
            else:
                return None, []
        except Exception as e:
            print(f"[DUAL-BUCKET SUB-QUERY ERROR] bucket={bucket} -> {repr(e)}")
            return None, []

        if not rows:
            # Return None (not 0) so the caller can distinguish "no data" from a
            # grounded zero value.  An unknown player or a player with no games
            # in this bucket both produce empty rows; we cannot tell them apart,
            # so the safe choice is to signal "untrustworthy" and fall through.
            return None, []

        val = rows[0].get("metric_value")
        if isinstance(val, (int, float)):
            return val, rows
        return None, rows

    def _fetch_subset_denominator(self, plan, bucket: dict) -> int | None:
        """
        Fetch the subset denominator for per-90 enrichment, mirroring the filter
        logic of _run_bucket_sub_query without touching duckdb_manager.py.

        player_match scope  → SUM(pms.minutes)
        team_match scope    → COUNT(*) (match count, standard 90-min-per-match)

        Returns None on any failure (enrichment is always best-effort).
        """
        filters = plan.filters.model_dump()
        for key in ("opponent_rank_lte", "opponent_rank_gte",
                    "opponent_rank_between", "opponent_is_big6"):
            filters[key] = None
        filters.update(bucket)

        where: list[str] = []
        params: list = []
        need_rank_join = False

        def _add_rank_filters(alias: str) -> None:
            nonlocal need_rank_join
            rank_lte = filters.get("opponent_rank_lte")
            rank_gte = filters.get("opponent_rank_gte")
            rank_between = filters.get("opponent_rank_between")
            is_big6 = filters.get("opponent_is_big6")
            if rank_lte is not None:
                where.append(f"{alias}.final_rank <= ?")
                params.append(rank_lte)
                need_rank_join = True
            if rank_gte is not None:
                where.append(f"{alias}.final_rank >= ?")
                params.append(rank_gte)
                need_rank_join = True
            if rank_between is not None:
                a, b = rank_between
                lo, hi = min(a, b), max(a, b)
                where.append(f"{alias}.final_rank BETWEEN ? AND ?")
                params.extend([lo, hi])
                need_rank_join = True
            if is_big6 is not None:
                where.append(f"{alias}.is_big6 = ?")
                params.append(is_big6)
                need_rank_join = True

        try:
            if plan.table_scope == "player_match":
                player_name = filters.get("player_name")
                if player_name:
                    where.append("lower(pms.short_name) = lower(?)")
                    params.append(player_name)
                is_home = filters.get("is_home")
                if is_home is not None:
                    where.append("pms.is_home = ?")
                    params.append(is_home)
                _add_rank_filters("opp")
                ms = filters.get("matchday_start")
                me = filters.get("matchday_end")
                if ms is not None:
                    where.append("pms.gameweek >= ?")
                    params.append(ms)
                if me is not None:
                    where.append("pms.gameweek <= ?")
                    params.append(me)
                join_sql = (
                    "LEFT JOIN league_table opp ON pms.opponent_team_id = opp.team_id"
                    if need_rank_join else ""
                )
                where_sql = ("WHERE " + " AND ".join(where)) if where else ""
                sql = (
                    f"SELECT SUM(pms.minutes) AS denom "
                    f"FROM player_match_stats pms {join_sql} {where_sql}"
                )

            elif plan.table_scope == "team_match":
                team_name = filters.get("team_name")
                if team_name:
                    where.append("lower(tms.team_name) = lower(?)")
                    params.append(team_name)
                is_home = filters.get("is_home")
                if is_home is not None:
                    where.append("tms.is_home = ?")
                    params.append(is_home)
                _add_rank_filters("opp")
                ms = filters.get("matchday_start")
                me = filters.get("matchday_end")
                if ms is not None:
                    where.append("tms.gameweek >= ?")
                    params.append(ms)
                if me is not None:
                    where.append("tms.gameweek <= ?")
                    params.append(me)
                join_sql = (
                    "LEFT JOIN league_table opp ON tms.opponent_team_id = opp.team_id"
                    if need_rank_join else ""
                )
                where_sql = ("WHERE " + " AND ".join(where)) if where else ""
                sql = (
                    f"SELECT COUNT(*) AS denom "
                    f"FROM team_match_stats tms {join_sql} {where_sql}"
                )

            else:
                return None

            rows = self.duck.query_dicts(sql, params)
            if rows and rows[0].get("denom") is not None:
                return int(rows[0]["denom"])
        except Exception:
            pass
        return None

    def _fetch_temporal_denominator(
        self,
        table: str,
        player_name: str | None,
        team_name: str | None,
        matchday_start: int | None,
        matchday_end: int | None,
    ) -> int | None:
        """
        Fetch per-90 denominator for a temporal entity-value query.

        Player tables  → SUM(minutes) from player_match_stats (includes player_match_event).
        Team table     → COUNT(*) from team_match_stats (standard 90-min-per-match).
        Returns None on any failure; enrichment is always best-effort.
        """
        try:
            where: list[str] = []
            params: list = []
            if table in ("player_match_stats", "player_match_event_stats"):
                if player_name:
                    where.append("lower(pms.short_name) = lower(?)")
                    params.append(player_name)
                if matchday_start is not None:
                    where.append("pms.gameweek >= ?")
                    params.append(matchday_start)
                if matchday_end is not None:
                    where.append("pms.gameweek <= ?")
                    params.append(matchday_end)
                where_sql = ("WHERE " + " AND ".join(where)) if where else ""
                sql = f"SELECT SUM(pms.minutes) AS denom FROM player_match_stats pms {where_sql}"
            elif table == "team_match_stats":
                if team_name:
                    where.append("lower(tms.team_name) = lower(?)")
                    params.append(team_name)
                if matchday_start is not None:
                    where.append("tms.gameweek >= ?")
                    params.append(matchday_start)
                if matchday_end is not None:
                    where.append("tms.gameweek <= ?")
                    params.append(matchday_end)
                where_sql = ("WHERE " + " AND ".join(where)) if where else ""
                sql = f"SELECT COUNT(*) AS denom FROM team_match_stats tms {where_sql}"
            else:
                return None
            rows = self.duck.query_dicts(sql, params)
            if rows and rows[0].get("denom") is not None:
                return int(rows[0]["denom"])
        except Exception:
            pass
        return None

    def _append_temporal_p90_enrichment(self, answer: str, result) -> str:
        """
        Append per-90 contextual enrichment to a temporal entity-value answer.
        Enrichment is appended only when both subset p90 and season p90 are available.
        Returns answer unmodified on any failure.
        """
        filters = result.filters_applied or {}
        player_name = filters.get("player_name")
        team_name = filters.get("team_name")
        ms = filters.get("matchday_start")
        me = filters.get("matchday_end")
        metric = result.metric

        if not result.rows:
            return answer
        val = result.rows[0].get(metric)
        if val is None or not isinstance(val, (int, float)):
            return answer

        is_player = player_name is not None
        denom = self._fetch_temporal_denominator(result.table, player_name, team_name, ms, me)
        subset_p90 = _compute_p90(float(val), denom, is_player)
        if subset_p90 is None:
            return answer

        season_p90 = None
        if is_player:
            p90_col = _PLAYER_P90_MAP.get(metric)
            if p90_col:
                p_row = self.players_df.filter(
                    pl.col("short_name").str.to_lowercase() == player_name.lower()
                )
                if p_row.height > 0 and p90_col in p_row.columns:
                    season_p90 = round(float(p_row[p90_col][0]), 2)
        elif team_name:
            p90_col = _TEAM_P90_MAP.get(metric)
            if p90_col:
                t_row = self.teams_df.filter(
                    pl.col("team_name").str.to_lowercase() == team_name.lower()
                )
                if t_row.height > 0 and p90_col in t_row.columns:
                    season_p90 = round(float(t_row[p90_col][0]), 2)

        if season_p90 is not None:
            answer += (
                f" That is {subset_p90:.2f} per 90 in this subset, "
                f"compared with {season_p90:.2f} per 90 across the full season."
            )
        return answer

    def _execute_dual_bucket_comparison(
        self, question: str, dual: tuple[dict, dict]
    ) -> dict | None:
        """
        Execute a two-bucket comparison for a named subject + single metric.
        Returns a structured answer dict, or None to fall through to normal path.
        """
        try:
            plan = self.planner.resolve(question)
        except Exception as e:
            print(f"[DUAL-BUCKET PLANNER ERROR] {question} -> {repr(e)}")
            return None

        # LLM-independent subject extraction — don't rely solely on what the LLM
        # put in filters; the LLM may have returned player_name=null.
        resolved_player = self.planner._match_known_name(question, self.planner.player_names)
        if not resolved_player:
            for word in question.split():
                candidate = word.strip("?.,!'\"")
                if len(candidate) >= 4:
                    resolved_player = self.planner._resolve_player_suffix(candidate)
                    if resolved_player:
                        break

        if resolved_player:
            plan.table_scope = "player_match"
            plan.filters.player_name = resolved_player
            # summary-scope metric names are invalid in player_match context
            if plan.metric == "total_goals":
                plan.metric = "goals"
            elif plan.metric == "total_assists":
                plan.metric = "assists"
        elif plan.table_scope not in {"player_match", "team_match"}:
            return None

        filters = plan.filters.model_dump()
        subject = filters.get("player_name") or filters.get("team_name")
        if not subject:
            return None

        bucket_a, bucket_b = dual
        val_a, _ = self._run_bucket_sub_query(plan, bucket_a)
        val_b, _ = self._run_bucket_sub_query(plan, bucket_b)

        if val_a is None or val_b is None:
            return None

        label_a = _bucket_label(bucket_a)
        label_b = _bucket_label(bucket_b)

        # Metric base noun and action verb (with team_score normalisation)
        _METRIC_BASE = {"goals": "goals", "team_score": "goals", "assists": "assists"}
        _METRIC_ACTION_VERB = {"goals": "scored", "team_score": "scored", "assists": "made"}
        metric_base = _METRIC_BASE.get(plan.metric, plan.metric.replace("_", " "))
        action_verb = _METRIC_ACTION_VERB.get(plan.metric, "scored")

        # Carry is_home modifier when baked into the plan (e.g. "away goals against top 6")
        if plan.filters.is_home is False:
            metric_label = f"away {metric_base}"
        elif plan.filters.is_home is True:
            metric_label = f"home {metric_base}"
        else:
            metric_label = metric_base

        def _fmt(v: float) -> str:
            return str(int(v)) if v == int(v) else str(round(v, 2))

        def _val_label(v: float) -> str:
            # Singularize "goals" → "goal", "assists" → "assist" when value is 1
            if v == 1 and metric_label.endswith(("goals", "assists")):
                return f"{_fmt(v)} {metric_label[:-1]}"
            return f"{_fmt(v)} {metric_label}"

        # "has" for named players, "have" for teams
        verb = "has" if plan.filters.player_name is not None else "have"

        if val_a > val_b:
            conclusion = f"so {subject} {verb} {action_verb} more {metric_label} against the {label_a}"
        elif val_b > val_a:
            conclusion = f"so {subject} {verb} {action_verb} more {metric_label} against the {label_b}"
        else:
            conclusion = "so it is equal against both"

        answer = (
            f"{subject} {verb} {action_verb} {_val_label(val_a)} against the {label_a} and "
            f"{_val_label(val_b)} against the {label_b}, {conclusion}."
        )

        # Per-90 enrichment (best-effort)
        is_player = plan.filters.player_name is not None
        p90_a = p90_b = None
        try:
            denom_a = self._fetch_subset_denominator(plan, bucket_a)
            denom_b = self._fetch_subset_denominator(plan, bucket_b)
            p90_a = _compute_p90(val_a, denom_a, is_player)
            p90_b = _compute_p90(val_b, denom_b, is_player)
            if p90_a is not None and p90_b is not None:
                answer += (
                    f" That is {p90_a:.2f} per 90 against the {label_a} "
                    f"and {p90_b:.2f} per 90 against the {label_b}."
                )
        except Exception:
            pass

        return {
            "type": "text",
            "content": answer,
            "debug": {
                "engine": "dual_bucket_comparison",
                "table": plan.table_scope,
                "metric": plan.metric,
                "subject": subject,
                "bucket_a": {"filters": bucket_a, "value": val_a, "p90": p90_a},
                "bucket_b": {"filters": bucket_b, "value": val_b, "p90": p90_b},
            },
        }

    def _execute_home_away_comparison(
        self, question: str, sides: tuple[dict, dict]
    ) -> dict | None:
        """
        Execute a home-vs-away comparison for a named subject + single metric.
        sides = ({"is_home": False}, {"is_home": True})
        Returns a structured answer dict, or None to fall through to normal path.
        """
        try:
            plan = self.planner.resolve(question)
        except Exception as e:
            print(f"[HOME-AWAY PLANNER ERROR] {question} -> {repr(e)}")
            return None

        # LLM-independent subject extraction (same pattern as dual-bucket)
        resolved_player = self.planner._match_known_name(question, self.planner.player_names)
        if not resolved_player:
            for word in question.split():
                candidate = word.strip("?.,!'\"")
                if len(candidate) >= 4:
                    resolved_player = self.planner._resolve_player_suffix(candidate)
                    if resolved_player:
                        break

        if resolved_player:
            plan.table_scope = "player_match"
            plan.filters.player_name = resolved_player
            if plan.metric == "total_goals":
                plan.metric = "goals"
            elif plan.metric == "total_assists":
                plan.metric = "assists"
        elif plan.table_scope not in {"player_match", "team_match"}:
            return None

        # Clear is_home so each sub-query sets its own side
        plan.filters.is_home = None

        filters = plan.filters.model_dump()
        subject = filters.get("player_name") or filters.get("team_name")
        if not subject:
            return None

        away_side, home_side = sides
        val_away, _ = self._run_bucket_sub_query(plan, away_side)
        val_home, _ = self._run_bucket_sub_query(plan, home_side)

        if val_away is None or val_home is None:
            return None

        # Metric-to-noun: explicit mapping for currently supported metrics
        _METRIC_NOUN = {
            "goals": "goals",
            "team_score": "goals",
        }
        metric_noun = _METRIC_NOUN.get(plan.metric, plan.metric.replace("_", " "))

        def _fmt(v: float) -> str:
            return str(int(v)) if v == int(v) else str(round(v, 2))

        def _sng(v: float, noun: str) -> str:
            """Singularize 'goals'/'assists' when value is 1."""
            if v == 1 and noun in ("goals", "assists"):
                return noun[:-1]
            return noun

        # "has" for players, "have" for teams
        verb = "has" if plan.filters.player_name is not None else "have"

        if val_away > val_home:
            conclusion = f"so {subject} {verb} scored more away {metric_noun}"
        elif val_home > val_away:
            conclusion = f"so {subject} {verb} scored more {metric_noun} at home"
        else:
            conclusion = "so the totals are equal"

        answer = (
            f"{subject} {verb} scored {_fmt(val_away)} away {_sng(val_away, metric_noun)} and "
            f"{_fmt(val_home)} home {_sng(val_home, metric_noun)}, {conclusion}."
        )

        # Per-90 enrichment (best-effort)
        is_player = plan.filters.player_name is not None
        p90_away = p90_home = None
        try:
            denom_away = self._fetch_subset_denominator(plan, away_side)
            denom_home = self._fetch_subset_denominator(plan, home_side)
            p90_away = _compute_p90(val_away, denom_away, is_player)
            p90_home = _compute_p90(val_home, denom_home, is_player)
            if p90_away is not None and p90_home is not None:
                answer += (
                    f" That is {p90_away:.2f} per 90 away "
                    f"and {p90_home:.2f} per 90 at home."
                )
        except Exception:
            pass

        return {
            "type": "text",
            "content": answer,
            "debug": {
                "engine": "home_away_comparison",
                "table": plan.table_scope,
                "metric": plan.metric,
                "subject": subject,
                "away": val_away,
                "home": val_home,
                "p90_away": p90_away,
                "p90_home": p90_home,
            },
        }

    def _execute_metric_derived_bucket(
        self, question: str, bucket_spec: dict
    ) -> dict | None:
        """
        Execute a metric-derived opponent bucket query.
        Derives opponent team set from teams_df, then runs a grounded SQL query.
        Returns a structured answer dict, or None to fall through to normal path.
        """
        ql = question.lower()
        n = bucket_spec["n"]

        # 1. identify subject first (needed to exclude subject team from derived bucket)
        player_name = self.planner._match_known_name(question, self.planner.player_names)
        team_name = None
        if not player_name:
            team_name = self.planner._match_known_name(question, self.planner.team_names)
        if not player_name and not team_name:
            for word in question.split():
                candidate = word.strip("?.,!'\"")
                if len(candidate) >= 4:
                    player_name = self.planner._resolve_player_suffix(candidate)
                    if player_name:
                        break
        if not player_name and not team_name:
            return None

        # 2. determine subject team name for exclusion from derived bucket
        subject_team_lower = None
        if team_name:
            subject_team_lower = team_name.lower()
        elif player_name and "team_name" in self.players_df.columns:
            rows_p = self.players_df.filter(
                pl.col("short_name").str.to_lowercase() == player_name.lower()
            )
            if rows_p.height > 0:
                subject_team_lower = rows_p["team_name"][0].lower()

        # 3. derive opponent team names (n+1 to allow one exclusion slot)
        team_names_raw = _derive_teams_for_bucket(
            self.teams_df,
            n + 1,
            bucket_spec["bucket_metric"],
            bucket_spec["descending"],
        )
        if subject_team_lower:
            team_names = [t for t in team_names_raw if t.lower() != subject_team_lower][:n]
        else:
            team_names = team_names_raw[:n]
        if not team_names:
            return None

        # 3. resolve final answer metric; fall through if unsupported
        if player_name:
            if "shot assist" in ql:
                # player_match_stats has no match-level shot_assists — not supported
                return None
            elif "assist" in ql:
                final_col, action, metric_singular = "assists", "made", "assist"
            elif "goal" in ql or "scored" in ql or "conceded" in ql:
                final_col, action, metric_singular = "goals", "scored", "goal"
            else:
                return None
        else:
            if "conceded" in ql or "concede" in ql or "concedes" in ql:
                final_col, action, metric_singular = "opponent_score", "conceded", "goal"
            elif "goal" in ql or "scored" in ql:
                final_col, action, metric_singular = "team_score", "scored", "goal"
            else:
                return None

        lower_names = [t.lower() for t in team_names]
        placeholders = ", ".join(["?" for _ in team_names])

        if player_name:
            sql = (
                f"SELECT SUM(pms.{final_col}) AS metric_value, "
                f"SUM(pms.minutes) AS subset_minutes "
                f"FROM player_match_stats pms "
                f"WHERE lower(pms.short_name) = lower(?) "
                f"AND lower(pms.opponent_team_name) IN ({placeholders})"
            )
            params = [player_name] + lower_names
            subject = player_name
            verb = "has"
        else:
            sql = (
                f"SELECT SUM(tms.{final_col}) AS metric_value, "
                f"COUNT(*) AS subset_matches "
                f"FROM team_match_stats tms "
                f"WHERE lower(tms.team_name) = lower(?) "
                f"AND lower(tms.opponent_team_name) IN ({placeholders})"
            )
            params = [team_name] + lower_names
            subject = team_name
            verb = "have"

        # 4. execute
        try:
            rows = self.duck.query_dicts(sql, params)
        except Exception as e:
            print(f"[METRIC-BUCKET QUERY ERROR] {question!r} -> {repr(e)}")
            return None

        if not rows:
            return None
        val = rows[0].get("metric_value")
        if val is None:
            return None
        val = int(val) if isinstance(val, float) and val == int(val) else val

        # 5. compose answer
        metric_word = metric_singular if val == 1 else metric_singular + "s"
        n = bucket_spec["n"]
        label = bucket_spec["label"]
        if n == 1:
            teams_str = team_names[0]
        elif n == 2:
            teams_str = f"{team_names[0]} and {team_names[1]}"
        else:
            teams_str = ", ".join(team_names[:-1]) + f" and {team_names[-1]}"

        answer = (
            f"{subject} {verb} {action} {val} {metric_word} against the {n} teams that "
            f"{label}: {teams_str}."
        )

        # 6. per-90 enrichment (best-effort; skipped silently on missing data)
        subset_p90 = None
        season_p90 = None
        p90_context = None

        try:
            if player_name:
                subset_minutes = rows[0].get("subset_minutes")
                if subset_minutes and float(subset_minutes) > 0:
                    subset_p90 = round(float(val) / float(subset_minutes) * 90, 2)
                # season baseline from player_full_stats (already loaded)
                p_row = self.players_df.filter(
                    pl.col("short_name").str.to_lowercase() == player_name.lower()
                )
                if p_row.height > 0:
                    p90_col = "total_goals_p90" if final_col == "goals" else "total_assists_p90"
                    if p90_col in p_row.columns:
                        season_p90 = round(float(p_row[p90_col][0]), 2)
            else:
                subset_matches = rows[0].get("subset_matches")
                if subset_matches and int(subset_matches) > 0:
                    subset_p90 = round(float(val) / int(subset_matches), 2)
                # season baseline from team_full_stats (already loaded)
                t_row = self.teams_df.filter(
                    pl.col("team_name").str.to_lowercase() == team_name.lower()
                )
                if t_row.height > 0:
                    p90_col = "total_goals_p90" if final_col == "team_score" else "total_goals_against_p90"
                    if p90_col in t_row.columns:
                        season_p90 = round(float(t_row[p90_col][0]), 2)

            if subset_p90 is not None and season_p90 is not None:
                p90_context = (
                    f" That is {subset_p90:.2f} per 90 in this subset, "
                    f"compared with {season_p90:.2f} per 90 across the full season."
                )
        except Exception:
            pass  # enrichment failure must not affect the main answer

        if p90_context:
            answer = answer + p90_context

        return {
            "type": "text",
            "content": answer,
            "debug": {
                "engine": "metric_derived_bucket",
                "table": "player_match_stats" if player_name else "team_match_stats",
                "metric": final_col,
                "descending": bucket_spec["descending"],
                "bucket_spec": bucket_spec,
                "team_names": team_names,
                "subject": subject,
                "value": val,
                "subset_p90": subset_p90,
                "season_p90": season_p90,
            },
        }

    def ask(self, question: str) -> dict:
        dual = _detect_dual_bucket_comparison(question)
        if dual is not None:
            comparison_result = self._execute_dual_bucket_comparison(question, dual)
            if comparison_result is not None:
                return comparison_result

        home_away = _detect_home_away_comparison(question)
        if home_away is not None:
            comparison_result = self._execute_home_away_comparison(question, home_away)
            if comparison_result is not None:
                return comparison_result

        metric_bucket = _detect_metric_derived_bucket(question)
        if metric_bucket is not None:
            bucket_result = self._execute_metric_derived_bucket(question, metric_bucket)
            if bucket_result is not None:
                return bucket_result

        is_contextual = self._is_contextual_question(question)

        planned_result = self._execute_planned_query(question)

        if planned_result is not None:
            ranking = (planned_result.filters_applied or {}).get("ranking", {}) or {}
            is_tie = _detect_true_tie(
                planned_result.rows,
                planned_result.metric,
                ranking,
            )

            answer = self._verbalize(question, planned_result)

            # Temporal entity-value enrichment: only for named-entity value queries
            # with a real temporal subset (matchday_start or matchday_end set).
            if ranking.get("mode") == "entity_value":
                filters_ = planned_result.filters_applied or {}
                if (filters_.get("matchday_start") is not None
                        or filters_.get("matchday_end") is not None):
                    try:
                        answer = self._append_temporal_p90_enrichment(answer, planned_result)
                    except Exception:
                        pass

            return {
                "type": "text",
                "content": answer,
                "debug": {
                    "engine": "planner_duckdb",
                    "table": planned_result.table,
                    "metric": planned_result.metric,
                    "descending": None,
                    "filters": planned_result.filters_applied,
                    "rows": planned_result.rows,
                    "is_tie": is_tie,
                    "ranking_mode": ranking.get("mode"),
                    "ranking_n": ranking.get("n"),
                },
            }

        # if the question is contextual, do NOT silently fall back to legacy summary logic
        if is_contextual:
            return {
                "type": "text",
                "content": "I could not resolve that contextual query with the current planner.",
                "debug": {
                    "engine": "planner_duckdb_failed",
                    "table": None,
                    "metric": None,
                    "descending": None,
                    "filters": {},
                    "rows": [],
                    "is_tie": False,
                    "ranking_mode": None,
                    "ranking_n": None,
                },
            }

        resolution = self._resolve_metric(question)
        result = self._execute_summary(question, resolution)

        ranking = (result.filters_applied or {})
        is_tie = _detect_true_tie(
            result.rows,
            result.metric,
            {
                "mode": "top_n" if ranking.get("top_n", 1) >= 1 else None,
                "n": ranking.get("top_n", 1),
            },
        )

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
                "is_tie": is_tie,
                "ranking_mode": "ordinal" if "rank_position" in result.filters_applied else "top_n",
                "ranking_n": result.filters_applied.get("top_n", 1),
            },
        }

    def __del__(self):
        try:
            if hasattr(self, "duck"):
                self.duck.close()
        except Exception:
            pass