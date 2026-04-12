"""
agent_tools.py — thin data-layer tool functions for the Phase 5 agent.

Each function:
  1. Takes typed args (LLM-supplied, already validated by the tool schema)
  2. Decides which DuckDB table/method to hit based on which filters are set
  3. Returns a dict with {"rows": [...], "note": str | None}

No heuristics. No regex on question text. No metric renames.
The LLM supplies canonical column names; these functions pass them straight through.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.basic_stats.duckdb_manager import (
    PLAYER_MATCH_ALLOWED_METRICS,
    PLAYER_MATCH_EVENT_ALLOWED_METRICS,
    TEAM_MATCH_ALLOWED_METRICS,
    DuckDBManager,
)

# ---------------------------------------------------------------------------
# Shared types
# ---------------------------------------------------------------------------


@dataclass
class Filters:
    opponent_team: str | None = None
    is_home: bool | None = None
    opponent_rank_max: int | None = None  # top-N opponents (rank <= N)
    opponent_rank_min: int | None = None  # bottom-N opponents (rank >= N)
    matchday_start: int | None = None
    matchday_end: int | None = None
    min_minutes: int | None = None
    min_matches: int | None = None
    age_max: int | None = None
    position: str | None = None
    opponent_is_big6: bool | None = None  # filter by Big Six club identity
    player_team: str | None = None  # filter to players from this team

    @classmethod
    def from_dict(cls, d: dict | None) -> "Filters":
        if not d:
            return cls()
        return cls(
            opponent_team=d.get("opponent_team"),
            is_home=d.get("is_home"),
            opponent_rank_max=d.get("opponent_rank_max"),
            opponent_rank_min=d.get("opponent_rank_min"),
            matchday_start=d.get("matchday_start"),
            matchday_end=d.get("matchday_end"),
            min_minutes=d.get("min_minutes"),
            min_matches=d.get("min_matches"),
            age_max=d.get("age_max"),
            position=d.get("position"),
            opponent_is_big6=d.get("opponent_is_big6"),
            player_team=d.get("player_team"),
        )

    def has_match_context(self) -> bool:
        return any(
            v is not None
            for v in [
                self.opponent_team,
                self.is_home,
                self.opponent_rank_max,
                self.opponent_rank_min,
                self.opponent_is_big6,
                self.matchday_start,
                self.matchday_end,
            ]
        )


@dataclass
class ToolResult:
    rows: list[dict] = field(default_factory=list)
    note: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"rows": self.rows, "note": self.note}


class ToolError(Exception):
    """Raised when a tool call fails with a user-readable message the LLM can act on."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_PLAYER_SUMMARY_METRICS: set[str] = set()  # populated lazily on first call


def _is_player_summary_metric(metric: str) -> bool:
    # Summary metrics are anything NOT in the match/event sets.
    # We don't maintain a separate allow-list for summary — the DB validates at query time.
    return (
        metric not in PLAYER_MATCH_ALLOWED_METRICS
        and metric not in PLAYER_MATCH_EVENT_ALLOWED_METRICS
    )


def _is_team_match_metric(metric: str) -> bool:
    return metric in TEAM_MATCH_ALLOWED_METRICS


def _is_player_match_event_metric(metric: str) -> bool:
    return metric in PLAYER_MATCH_EVENT_ALLOWED_METRICS


# ---------------------------------------------------------------------------
# Tool 1 — get_player_stat
# ---------------------------------------------------------------------------


def get_player_stat(
    duck: DuckDBManager,
    player_name: str,
    stat: str,
    filters: dict | None = None,
) -> dict:
    """
    Return the aggregated stat for a single named player.
    Automatically picks the right table based on which filters are set and which
    metric is requested.
    """
    f = Filters.from_dict(filters)

    # player_match_event metrics (progressive_passes, touches_in_box, etc.)
    if _is_player_match_event_metric(stat):
        rows = duck.query_player_match_event_context(
            metric=stat,
            agg="sum",
            player_name=player_name,
            is_home=f.is_home,
            opponent_team_name=f.opponent_team,
            opponent_rank_lte=f.opponent_rank_max,
            opponent_rank_gte=f.opponent_rank_min,
            opponent_is_big6=f.opponent_is_big6,
            matchday_start=f.matchday_start,
            matchday_end=f.matchday_end,
            limit=1,
        )
        return ToolResult(rows=rows).to_dict()

    # player_match metrics (goals, assists, minutes_played, yellow_card, red_card)
    if stat in PLAYER_MATCH_ALLOWED_METRICS or f.has_match_context():
        rows = duck.query_player_match_context(
            metric=stat if stat in PLAYER_MATCH_ALLOWED_METRICS else "goals",
            agg="sum",
            player_name=player_name,
            is_home=f.is_home,
            opponent_team_name=f.opponent_team,
            opponent_rank_lte=f.opponent_rank_max,
            opponent_rank_gte=f.opponent_rank_min,
            opponent_is_big6=f.opponent_is_big6,
            matchday_start=f.matchday_start,
            matchday_end=f.matchday_end,
            limit=1,
        )
        return ToolResult(rows=rows).to_dict()

    # players_summary (totals, p90 rates, etc.)
    rows = duck.query_summary_context(
        scope="players_summary",
        metric=stat,
        descending=True,
        player_name=player_name,
        min_minutes=f.min_minutes,
        min_matches=f.min_matches,
        age_lt=f.age_max,
        top_n=1,
    )
    return ToolResult(rows=rows).to_dict()


# ---------------------------------------------------------------------------
# Tool 2 — get_team_stat
# ---------------------------------------------------------------------------


def get_team_stat(
    duck: DuckDBManager,
    team_name: str,
    stat: str,
    filters: dict | None = None,
) -> dict:
    """Return the aggregated stat for a single named team."""
    f = Filters.from_dict(filters)

    if _is_team_match_metric(stat) or f.has_match_context():
        effective_stat = stat if _is_team_match_metric(stat) else "team_score"
        rows = duck.query_team_match_context(
            metric=effective_stat,
            agg="sum",
            team_name=team_name,
            is_home=f.is_home,
            opponent_team_name=f.opponent_team,
            opponent_rank_lte=f.opponent_rank_max,
            opponent_rank_gte=f.opponent_rank_min,
            opponent_is_big6=f.opponent_is_big6,
            matchday_start=f.matchday_start,
            matchday_end=f.matchday_end,
            limit=1,
        )
        return ToolResult(rows=rows).to_dict()

    rows = duck.query_summary_context(
        scope="teams_summary",
        metric=stat,
        descending=True,
        team_name=team_name,
        top_n=1,
    )
    return ToolResult(rows=rows).to_dict()


# ---------------------------------------------------------------------------
# Tool 3 — rank_players
# ---------------------------------------------------------------------------


def rank_players(
    duck: DuckDBManager,
    stat: str | None = None,
    filters: dict | None = None,
    limit: int = 1,
    descending: bool = True,
    match_conditions: list[dict] | None = None,
) -> dict:
    """Return top/bottom N players ranked by a stat or by a match-condition count."""
    f = Filters.from_dict(filters)
    limit = max(1, min(limit, 20))

    # match_conditions mode: count matches where all conditions hold
    if match_conditions:
        rows = duck.query_player_match_context(
            metric="goals",  # base metric; match_conditions do the actual filtering
            agg="count_matches_positive",
            team_name=f.player_team,
            is_home=f.is_home,
            opponent_team_name=f.opponent_team,
            opponent_rank_lte=f.opponent_rank_max,
            opponent_rank_gte=f.opponent_rank_min,
            opponent_is_big6=f.opponent_is_big6,
            matchday_start=f.matchday_start,
            matchday_end=f.matchday_end,
            match_conditions=match_conditions,
            limit=limit,
        )
        return ToolResult(rows=rows).to_dict()

    if stat is None:
        raise ToolError("rank_players requires either stat or match_conditions")

    if _is_player_match_event_metric(stat):
        rows = duck.query_player_match_event_context(
            metric=stat,
            agg="sum",
            position=f.position,
            team_name=f.player_team,
            is_home=f.is_home,
            opponent_team_name=f.opponent_team,
            opponent_rank_lte=f.opponent_rank_max,
            opponent_rank_gte=f.opponent_rank_min,
            opponent_is_big6=f.opponent_is_big6,
            matchday_start=f.matchday_start,
            matchday_end=f.matchday_end,
            limit=limit,
        )
        return ToolResult(rows=rows).to_dict()

    if stat in PLAYER_MATCH_ALLOWED_METRICS or f.has_match_context():
        effective_stat = stat if stat in PLAYER_MATCH_ALLOWED_METRICS else "goals"
        rows = duck.query_player_match_context(
            metric=effective_stat,
            agg="sum",
            team_name=f.player_team,
            is_home=f.is_home,
            opponent_team_name=f.opponent_team,
            opponent_rank_lte=f.opponent_rank_max,
            opponent_rank_gte=f.opponent_rank_min,
            opponent_is_big6=f.opponent_is_big6,
            matchday_start=f.matchday_start,
            matchday_end=f.matchday_end,
            limit=limit,
        )
        return ToolResult(rows=rows).to_dict()

    rows = duck.query_summary_context(
        scope="players_summary",
        metric=stat,
        descending=descending,
        position=f.position,
        min_minutes=f.min_minutes,
        min_matches=f.min_matches,
        age_lt=f.age_max,
        top_n=limit,
    )
    return ToolResult(rows=rows).to_dict()


# ---------------------------------------------------------------------------
# Tool 4 — rank_teams
# ---------------------------------------------------------------------------


def rank_teams(
    duck: DuckDBManager,
    stat: str,
    filters: dict | None = None,
    limit: int = 1,
    descending: bool = True,
) -> dict:
    """Return top/bottom N teams ranked by a stat."""
    f = Filters.from_dict(filters)
    limit = max(1, min(limit, 20))

    if _is_team_match_metric(stat) or f.has_match_context():
        effective_stat = stat if _is_team_match_metric(stat) else "team_score"
        agg = stat if stat in {"points", "wins", "goal_difference"} else "sum"
        rows = duck.query_team_match_context(
            metric=effective_stat,
            agg=agg,
            is_home=f.is_home,
            opponent_team_name=f.opponent_team,
            opponent_rank_lte=f.opponent_rank_max,
            opponent_rank_gte=f.opponent_rank_min,
            opponent_is_big6=f.opponent_is_big6,
            matchday_start=f.matchday_start,
            matchday_end=f.matchday_end,
            limit=limit,
        )
        return ToolResult(rows=rows).to_dict()

    rows = duck.query_summary_context(
        scope="teams_summary",
        metric=stat,
        descending=descending,
        top_n=limit,
    )
    return ToolResult(rows=rows).to_dict()


# ---------------------------------------------------------------------------
# Tool 5 — compare_entities
# ---------------------------------------------------------------------------


def compare_entities(
    duck: DuckDBManager,
    entity_type: str,
    entities: list[str],
    stat: str,
    filters: dict | None = None,
) -> dict:
    """
    Return one row per entity with the aggregated stat, for side-by-side comparison.
    entity_type: "player" | "team"
    entities: list of player or team names
    """
    if entity_type not in {"player", "team"}:
        raise ToolError(f"entity_type must be 'player' or 'team', got '{entity_type}'")

    rows = []
    for name in entities:
        if entity_type == "player":
            result = get_player_stat(duck, name, stat, filters)
        else:
            result = get_team_stat(duck, name, stat, filters)

        entity_rows = result.get("rows", [])
        if entity_rows:
            rows.append({"entity": name, **entity_rows[0]})
        else:
            rows.append({"entity": name, "metric_value": None, "note": "no data"})

    return ToolResult(rows=rows).to_dict()


# ---------------------------------------------------------------------------
# Tool 6 — count_matches_where
# ---------------------------------------------------------------------------


def count_matches_where(
    duck: DuckDBManager,
    entity_type: str,
    entity_name: str,
    conditions: list[dict],
    filters: dict | None = None,
) -> dict:
    """
    Count matches where a player/team meets all given conditions.
    conditions: list of {"metric": str, "operator": str, "value": number}
    Example: [{"metric": "goals", "operator": ">=", "value": 1},
               {"metric": "assists", "operator": ">=", "value": 1}]
    """
    if entity_type not in {"player", "team"}:
        raise ToolError(f"entity_type must be 'player' or 'team', got '{entity_type}'")

    f = Filters.from_dict(filters)

    if entity_type == "player":
        rows = duck.query_player_match_context(
            metric="goals",  # base metric; match_conditions do the real filtering
            agg="count_matches_positive",
            player_name=entity_name,
            is_home=f.is_home,
            opponent_team_name=f.opponent_team,
            opponent_rank_lte=f.opponent_rank_max,
            opponent_rank_gte=f.opponent_rank_min,
            opponent_is_big6=f.opponent_is_big6,
            matchday_start=f.matchday_start,
            matchday_end=f.matchday_end,
            match_conditions=conditions,
            limit=1,
        )
    else:
        # For teams, we count matches via team_match_context using the first condition metric
        if not conditions:
            raise ToolError("conditions list cannot be empty for count_matches_where")
        first = conditions[0]
        effective_metric = (
            first["metric"] if _is_team_match_metric(first["metric"]) else "team_score"
        )
        rows = duck.query_team_match_context(
            metric=effective_metric,
            agg="count_matches_positive",
            team_name=entity_name,
            is_home=f.is_home,
            opponent_team_name=f.opponent_team,
            opponent_rank_lte=f.opponent_rank_max,
            opponent_rank_gte=f.opponent_rank_min,
            opponent_is_big6=f.opponent_is_big6,
            matchday_start=f.matchday_start,
            matchday_end=f.matchday_end,
            limit=1,
        )

    return ToolResult(rows=rows).to_dict()


# ---------------------------------------------------------------------------
# Tool 7 — get_stat_over_window
# ---------------------------------------------------------------------------


def get_stat_over_window(
    duck: DuckDBManager,
    entity_type: str,
    entity_name: str,
    stat: str,
    last_n_gameweeks: int,
    filters: dict | None = None,
) -> dict:
    """
    Return a stat for the last N gameweeks.
    Resolves the gameweek window automatically from the DB's max matchday.
    """
    if entity_type not in {"player", "team"}:
        raise ToolError(f"entity_type must be 'player' or 'team', got '{entity_type}'")

    # Resolve max matchday from DB
    rows_max = duck.query_dicts("SELECT MAX(gameweek) AS max_gw FROM player_match_stats")
    max_gw = rows_max[0]["max_gw"] if rows_max else 38
    start_gw = max(1, max_gw - last_n_gameweeks + 1)

    f = Filters.from_dict(filters)
    f.matchday_start = start_gw
    f.matchday_end = max_gw

    if entity_type == "player":
        return get_player_stat(duck, entity_name, stat, f.__dict__)
    else:
        return get_team_stat(duck, entity_name, stat, f.__dict__)


# ---------------------------------------------------------------------------
# Tool 8 — get_stat_vs_opponent_group
# ---------------------------------------------------------------------------


def get_stat_vs_opponent_group(
    duck: DuckDBManager,
    entity_type: str,
    entity_name: str,
    stat: str,
    opponent_teams: list[str],
) -> dict:
    """
    Return a player's or team's aggregated stat across a specific list of opponents.

    Use this when a question names a derived set of opponents, e.g.:
    "How many goals has Salah scored against the 3 teams that concede the fewest goals?"

    Workflow:
      1. Call rank_teams to find which teams form the group (e.g. fewest goals conceded).
      2. Extract the team names from the result rows.
      3. Call this tool with those names to get the aggregated stat.
    """
    if not opponent_teams:
        raise ToolError("opponent_teams list cannot be empty")

    placeholders = ", ".join("?" for _ in opponent_teams)
    params_lower = [t.lower() for t in opponent_teams]

    if entity_type == "player":
        if stat in PLAYER_MATCH_EVENT_ALLOWED_METRICS:
            sql = f"""
            SELECT pmes.short_name, pmes.team_name,
                   SUM(pmes.{stat}) AS metric_value
            FROM player_match_event_stats pmes
            WHERE lower(pmes.short_name) = lower(?)
              AND lower(pmes.opponent_team_name) IN ({placeholders})
            GROUP BY pmes.short_name, pmes.team_name
            """
        else:
            effective = stat if stat in PLAYER_MATCH_ALLOWED_METRICS else "goals"
            sql = f"""
            SELECT pms.short_name, pms.team_name,
                   SUM(pms.{effective}) AS metric_value
            FROM player_match_stats pms
            WHERE lower(pms.short_name) = lower(?)
              AND lower(pms.opponent_team_name) IN ({placeholders})
            GROUP BY pms.short_name, pms.team_name
            """
        rows = duck.query_dicts(sql, [entity_name.lower()] + params_lower)
    else:
        if stat not in TEAM_MATCH_ALLOWED_METRICS:
            raise ToolError(f"stat '{stat}' is not available in team match data")
        sql = f"""
        SELECT tms.team_name,
               SUM(tms.{stat}) AS metric_value
        FROM team_match_stats tms
        WHERE lower(tms.team_name) = lower(?)
          AND lower(tms.opponent_team_name) IN ({placeholders})
        GROUP BY tms.team_name
        """
        rows = duck.query_dicts(sql, [entity_name.lower()] + params_lower)

    note = f"Aggregated {stat} vs opponents: {', '.join(opponent_teams)}"
    return ToolResult(rows=rows, note=note).to_dict()


# ---------------------------------------------------------------------------
# Tool 9 — get_league_standings
# ---------------------------------------------------------------------------


def get_league_standings(duck: DuckDBManager) -> dict:
    """Return the current Premier League standings table."""
    rows = duck.query_dicts("""
        SELECT
            position,
            team_name,
            matches_played,
            wins,
            draws,
            losses,
            goals_for,
            goals_against,
            goal_difference,
            points,
            is_big6
        FROM league_standings
        ORDER BY position ASC
    """)
    return ToolResult(rows=rows).to_dict()
