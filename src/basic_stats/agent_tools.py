"""
agent_tools.py — tool functions for the BasicStatsAgent (Responses API).

Each function receives args as plain dicts (parsed from JSON by the agent loop),
queries DuckDB, and returns {"rows": [...], "note": str | None}.

No dataclasses. No heuristics. No metric renames.
The LLM supplies canonical column names; these functions pass them straight through.
"""

from __future__ import annotations

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


class ToolError(Exception):
    """Raised when a tool call fails with a user-readable message the LLM can act on."""


# Default minutes cutoff applied to p90 rankings when the LLM omits min_minutes.
# 600 min ≈ 6.7 full matches — the floor below which per-90 rates are small-sample
# artefacts. Users who want to include cameos must pass min_minutes=0 explicitly.
_P90_MIN_MINUTES_DEFAULT = 600

# Maps summary *_p90 stat names → their base column in player_match_stats.
# Only covers metrics whose base is in PLAYER_MATCH_ALLOWED_METRICS.
# Event-table p90s (xg_p90, shots_p90, …) are handled separately.
_PLAYER_MATCH_P90_MAP: dict[str, str] = {
    "total_goals_p90": "goals",
    "assists_p90": "assists",
}


def _r(result: list[dict], note: str | None = None) -> dict[str, Any]:
    """Wrap DuckDB rows into the standard tool response format."""
    return {"rows": result, "note": note}


def _f(filters: dict | None, key: str):
    """Extract a filter value safely from the filters dict."""
    if not filters:
        return None
    return filters.get(key)


def _lookup_player_teams(duck: DuckDBManager, player_name: str) -> set[str]:
    """Return all team names the player appears for in player_match_stats.

    Tries an exact match on short_name first. If that yields nothing (e.g. input
    is an abbreviated form like "M. Salah" while the DB stores "Mohamed Salah"),
    falls back to resolving via the last-name token against entity_embeddings —
    this path works without an embedding client, so it covers the test environment.
    """
    rows = duck.query_dicts(
        "SELECT DISTINCT team_name FROM player_match_stats WHERE lower(short_name) = lower(?)",
        [player_name],
    )
    if rows:
        return {r["team_name"] for r in rows}

    # Abbreviated-name fallback: extract last-name token and find the unique
    # canonical_name in entity_embeddings that contains it, then re-query.
    parts = player_name.replace(".", " ").split()
    if len(parts) < 2:
        return set()
    last_name = parts[-1]
    canonical_rows = duck.query_dicts(
        "SELECT DISTINCT canonical_name FROM entity_embeddings "
        "WHERE entity_type = 'player' AND lower(canonical_name) LIKE '%' || lower(?) || '%'",
        [last_name],
    )
    if len(canonical_rows) != 1:
        return set()  # ambiguous or not found — conservative, no false exclusions
    canonical = canonical_rows[0]["canonical_name"]
    rows = duck.query_dicts(
        "SELECT DISTINCT team_name FROM player_match_stats WHERE lower(short_name) = lower(?)",
        [canonical],
    )
    return {r["team_name"] for r in rows}


def _same_team(a: str, b: str) -> bool:
    return (a or "").strip().lower() == (b or "").strip().lower()


def _resolve_team_filters(
    duck: DuckDBManager, filters: dict | None
) -> tuple[dict | None, list[dict]]:
    """Apply fuzzy_resolve_entity to team-valued filter fields when present.

    Mirrors the resolution already done for primary entity names (player_name,
    team_name) so that team filters inside rankings don't silently bypass the
    DB canonical name — e.g. "Nottingham Forest" inside rank_players(filters).
    Returns (resolved_filters, resolution_log). Original filters dict is not mutated.
    resolution_log is a list of {field, input, canonical, similarity, resolved} dicts
    for every filter field that went through fuzzy resolution.
    """
    if not filters:
        return filters, []
    resolved = dict(filters)
    log: list[dict] = []
    for key in ("player_team", "opponent_team"):
        val = resolved.get(key)
        if isinstance(val, str) and val:
            meta = duck.fuzzy_resolve_entity_verbose(val, "team")
            resolved[key] = meta["canonical"]
            log.append({"field": key, **meta})
    return resolved, log


def _fuzzy_primary(
    duck: DuckDBManager, name: str, entity_type: str, field: str
) -> tuple[str, dict]:
    """Fuzzy-resolve a primary entity name and return (canonical, resolution_entry)."""
    meta = duck.fuzzy_resolve_entity_verbose(name, entity_type)
    entry = {"field": field, **meta}
    return meta["canonical"], entry


def _has_match_context(filters: dict | None) -> bool:
    """True if any match-level filter is set (triggers match table instead of summary)."""
    if not filters:
        return False
    return any(
        filters.get(k) is not None
        for k in [
            "opponent_team",
            "is_home",
            "opponent_rank_max",
            "opponent_rank_min",
            "opponent_is_big6",
            "matchday_start",
            "matchday_end",
        ]
    )


# ---------------------------------------------------------------------------
# Metric routing helpers
# ---------------------------------------------------------------------------


def _is_player_match_event_metric(metric: str) -> bool:
    return metric in PLAYER_MATCH_EVENT_ALLOWED_METRICS


def _is_team_match_metric(metric: str) -> bool:
    return metric in TEAM_MATCH_ALLOWED_METRICS


# ---------------------------------------------------------------------------
# Tool 1 — get_player_stat
# ---------------------------------------------------------------------------


def get_player_stat(
    duck: DuckDBManager,
    player_name: str,
    stat: str,
    filters: dict | None = None,
) -> dict:
    """Return the aggregated stat for a single named player."""
    player_name = duck.fuzzy_resolve_entity(player_name, "player")
    if filters and filters.get("opponent_team"):
        own_teams = _lookup_player_teams(duck, player_name)
        if any(_same_team(filters["opponent_team"], t) for t in own_teams):
            own_label = next(t for t in own_teams if _same_team(filters["opponent_team"], t))
            return _r(
                [],
                note=f"{player_name} plays for {own_label}; no matches exist against their own club.",
            )
    if _is_player_match_event_metric(stat):
        rows = duck.query_player_match_event_context(
            metric=stat,
            agg="sum",
            player_name=player_name,
            is_home=_f(filters, "is_home"),
            opponent_team_name=_f(filters, "opponent_team"),
            opponent_rank_lte=_f(filters, "opponent_rank_max"),
            opponent_rank_gte=_f(filters, "opponent_rank_min"),
            opponent_is_big6=_f(filters, "opponent_is_big6"),
            matchday_start=_f(filters, "matchday_start"),
            matchday_end=_f(filters, "matchday_end"),
            limit=1,
        )
        return _r(rows)

    if stat in _PLAYER_MATCH_P90_MAP and _has_match_context(filters):
        rows = duck.query_player_match_context(
            metric=_PLAYER_MATCH_P90_MAP[stat],
            agg="p90",
            player_name=player_name,
            is_home=_f(filters, "is_home"),
            opponent_team_name=_f(filters, "opponent_team"),
            opponent_rank_lte=_f(filters, "opponent_rank_max"),
            opponent_rank_gte=_f(filters, "opponent_rank_min"),
            opponent_is_big6=_f(filters, "opponent_is_big6"),
            matchday_start=_f(filters, "matchday_start"),
            matchday_end=_f(filters, "matchday_end"),
            limit=1,
        )
        return _r(rows)

    if stat in PLAYER_MATCH_ALLOWED_METRICS or _has_match_context(filters):
        rows = duck.query_player_match_context(
            metric=stat if stat in PLAYER_MATCH_ALLOWED_METRICS else "goals",
            agg="sum",
            player_name=player_name,
            is_home=_f(filters, "is_home"),
            opponent_team_name=_f(filters, "opponent_team"),
            opponent_rank_lte=_f(filters, "opponent_rank_max"),
            opponent_rank_gte=_f(filters, "opponent_rank_min"),
            opponent_is_big6=_f(filters, "opponent_is_big6"),
            matchday_start=_f(filters, "matchday_start"),
            matchday_end=_f(filters, "matchday_end"),
            limit=1,
        )
        return _r(rows)

    rows = duck.query_summary_context(
        scope="players_summary",
        metric=stat,
        descending=True,
        player_name=player_name,
        min_minutes=_f(filters, "min_minutes"),
        min_matches=_f(filters, "min_matches"),
        age_lt=_f(filters, "age_max"),
        top_n=1,
    )
    return _r(rows)


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
    team_name = duck.fuzzy_resolve_entity(team_name, "team")
    if _is_team_match_metric(stat) or _has_match_context(filters):
        effective_stat = stat if _is_team_match_metric(stat) else "team_score"
        rows = duck.query_team_match_context(
            metric=effective_stat,
            agg="sum",
            team_name=team_name,
            is_home=_f(filters, "is_home"),
            opponent_team_name=_f(filters, "opponent_team"),
            opponent_rank_lte=_f(filters, "opponent_rank_max"),
            opponent_rank_gte=_f(filters, "opponent_rank_min"),
            opponent_is_big6=_f(filters, "opponent_is_big6"),
            matchday_start=_f(filters, "matchday_start"),
            matchday_end=_f(filters, "matchday_end"),
            limit=1,
        )
        return _r(rows)

    rows = duck.query_summary_context(
        scope="teams_summary",
        metric=stat,
        descending=True,
        team_name=team_name,
        top_n=1,
    )
    return _r(rows)


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
    limit = max(1, min(limit, 20))

    if match_conditions:
        rows = duck.query_player_match_context(
            metric="goals",
            agg="count_matches_positive",
            team_name=_f(filters, "player_team"),
            is_home=_f(filters, "is_home"),
            opponent_team_name=_f(filters, "opponent_team"),
            opponent_rank_lte=_f(filters, "opponent_rank_max"),
            opponent_rank_gte=_f(filters, "opponent_rank_min"),
            opponent_is_big6=_f(filters, "opponent_is_big6"),
            matchday_start=_f(filters, "matchday_start"),
            matchday_end=_f(filters, "matchday_end"),
            match_conditions=match_conditions,
            limit=limit,
        )
        return _r(rows)

    if stat is None:
        raise ToolError("rank_players requires either stat or match_conditions")

    if _is_player_match_event_metric(stat):
        rows = duck.query_player_match_event_context(
            metric=stat,
            agg="sum",
            position=_f(filters, "position"),
            team_name=_f(filters, "player_team"),
            is_home=_f(filters, "is_home"),
            opponent_team_name=_f(filters, "opponent_team"),
            opponent_rank_lte=_f(filters, "opponent_rank_max"),
            opponent_rank_gte=_f(filters, "opponent_rank_min"),
            opponent_is_big6=_f(filters, "opponent_is_big6"),
            matchday_start=_f(filters, "matchday_start"),
            matchday_end=_f(filters, "matchday_end"),
            limit=limit,
        )
        return _r(rows)

    if stat in _PLAYER_MATCH_P90_MAP and _has_match_context(filters):
        min_minutes = _f(filters, "min_minutes")
        note: str | None = None
        if min_minutes is None:
            min_minutes = _P90_MIN_MINUTES_DEFAULT
            note = (
                f"Applied default min_minutes={_P90_MIN_MINUTES_DEFAULT} for per-90 ranking. "
                "Pass min_minutes=0 to include all players."
            )
        rows = duck.query_player_match_context(
            metric=_PLAYER_MATCH_P90_MAP[stat],
            agg="p90",
            team_name=_f(filters, "player_team"),
            is_home=_f(filters, "is_home"),
            opponent_team_name=_f(filters, "opponent_team"),
            opponent_rank_lte=_f(filters, "opponent_rank_max"),
            opponent_rank_gte=_f(filters, "opponent_rank_min"),
            opponent_is_big6=_f(filters, "opponent_is_big6"),
            matchday_start=_f(filters, "matchday_start"),
            matchday_end=_f(filters, "matchday_end"),
            limit=limit,
        )
        return _r(rows, note=note)

    if stat in PLAYER_MATCH_ALLOWED_METRICS or _has_match_context(filters):
        rows = duck.query_player_match_context(
            metric=stat if stat in PLAYER_MATCH_ALLOWED_METRICS else "goals",
            agg="sum",
            team_name=_f(filters, "player_team"),
            is_home=_f(filters, "is_home"),
            opponent_team_name=_f(filters, "opponent_team"),
            opponent_rank_lte=_f(filters, "opponent_rank_max"),
            opponent_rank_gte=_f(filters, "opponent_rank_min"),
            opponent_is_big6=_f(filters, "opponent_is_big6"),
            matchday_start=_f(filters, "matchday_start"),
            matchday_end=_f(filters, "matchday_end"),
            limit=limit,
        )
        return _r(rows)

    min_minutes = _f(filters, "min_minutes")
    note: str | None = None
    if stat.endswith("_p90") and min_minutes is None:
        min_minutes = _P90_MIN_MINUTES_DEFAULT
        note = (
            f"Applied default min_minutes={_P90_MIN_MINUTES_DEFAULT} to avoid small-sample "
            "artefacts in per-90 ranking. Pass min_minutes=0 to include all players."
        )

    rows = duck.query_summary_context(
        scope="players_summary",
        metric=stat,
        descending=descending,
        position=_f(filters, "position"),
        team_name=_f(filters, "player_team"),
        min_minutes=min_minutes,
        min_matches=_f(filters, "min_matches"),
        age_lt=_f(filters, "age_max"),
        top_n=limit,
    )
    return _r(rows, note=note)


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
    limit = max(1, min(limit, 20))

    # Use match context only when there are active match-level filters OR the stat
    # is not available in teams_summary. Checking the schema avoids a hardcoded list.
    in_summary = duck.column_exists("teams_summary", stat)
    needs_match = _has_match_context(filters) or not in_summary
    if needs_match:
        effective_stat = stat if _is_team_match_metric(stat) else "team_score"
        agg = stat if stat in {"points", "wins", "goal_difference"} else "sum"
        rows = duck.query_team_match_context(
            metric=effective_stat,
            agg=agg,
            is_home=_f(filters, "is_home"),
            opponent_team_name=_f(filters, "opponent_team"),
            opponent_rank_lte=_f(filters, "opponent_rank_max"),
            opponent_rank_gte=_f(filters, "opponent_rank_min"),
            opponent_is_big6=_f(filters, "opponent_is_big6"),
            matchday_start=_f(filters, "matchday_start"),
            matchday_end=_f(filters, "matchday_end"),
            limit=limit,
        )
        return _r(rows)

    rows = duck.query_summary_context(
        scope="teams_summary",
        metric=stat,
        descending=descending,
        top_n=limit,
    )
    return _r(rows)


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
    """Return one row per entity with the aggregated stat, for side-by-side comparison."""
    if entity_type not in {"player", "team"}:
        raise ToolError(f"entity_type must be 'player' or 'team', got '{entity_type}'")

    rows = []
    for name in entities:
        resolved = duck.fuzzy_resolve_entity(name, entity_type)
        if entity_type == "player":
            result = get_player_stat(duck, resolved, stat, filters)
        else:
            result = get_team_stat(duck, resolved, stat, filters)

        entity_rows = result.get("rows", [])
        if entity_rows:
            rows.append({"entity": name, **entity_rows[0]})
        else:
            rows.append({"entity": name, "metric_value": None, "note": "no data"})

    return _r(rows)


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
    """Count matches where a player/team meets all given conditions."""
    if entity_type not in {"player", "team"}:
        raise ToolError(f"entity_type must be 'player' or 'team', got '{entity_type}'")

    entity_name = duck.fuzzy_resolve_entity(entity_name, entity_type)

    if entity_type == "player":
        rows = duck.query_player_match_context(
            metric="goals",
            agg="count_matches_positive",
            player_name=entity_name,
            is_home=_f(filters, "is_home"),
            opponent_team_name=_f(filters, "opponent_team"),
            opponent_rank_lte=_f(filters, "opponent_rank_max"),
            opponent_rank_gte=_f(filters, "opponent_rank_min"),
            opponent_is_big6=_f(filters, "opponent_is_big6"),
            matchday_start=_f(filters, "matchday_start"),
            matchday_end=_f(filters, "matchday_end"),
            match_conditions=conditions,
            limit=1,
        )
    else:
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
            is_home=_f(filters, "is_home"),
            opponent_team_name=_f(filters, "opponent_team"),
            opponent_rank_lte=_f(filters, "opponent_rank_max"),
            opponent_rank_gte=_f(filters, "opponent_rank_min"),
            opponent_is_big6=_f(filters, "opponent_is_big6"),
            matchday_start=_f(filters, "matchday_start"),
            matchday_end=_f(filters, "matchday_end"),
            limit=1,
        )

    return _r(rows)


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
    """Return a stat for the last N gameweeks. Resolves window from DB max matchday."""
    if entity_type not in {"player", "team"}:
        raise ToolError(f"entity_type must be 'player' or 'team', got '{entity_type}'")

    rows_max = duck.query_dicts("SELECT MAX(gameweek) AS max_gw FROM player_match_stats")
    max_gw = rows_max[0]["max_gw"] if rows_max else 38
    start_gw = max(1, max_gw - last_n_gameweeks + 1)

    window_filters = dict(filters) if filters else {}
    window_filters["matchday_start"] = start_gw
    window_filters["matchday_end"] = max_gw

    if entity_type == "player":
        return get_player_stat(duck, entity_name, stat, window_filters)
    return get_team_stat(duck, entity_name, stat, window_filters)


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
    """Return aggregated stat across a specific list of opponents."""
    if not opponent_teams:
        raise ToolError("opponent_teams list cannot be empty")

    entity_name = duck.fuzzy_resolve_entity(entity_name, entity_type)
    opponent_teams = [duck.fuzzy_resolve_entity(t, "team") for t in opponent_teams]

    excluded_note = None
    if entity_type == "player":
        own_teams = _lookup_player_teams(duck, entity_name)
        if own_teams:
            filtered = [t for t in opponent_teams if not any(_same_team(t, ot) for ot in own_teams)]
            if len(filtered) != len(opponent_teams):
                excluded = [t for t in opponent_teams if t not in filtered]
                excluded_note = (
                    f"Excluded {', '.join(excluded)} from opponent group: "
                    f"{entity_name} plays for {', '.join(own_teams)}."
                )
                opponent_teams = filtered

    if not opponent_teams:
        return _r([], note=excluded_note or "opponent_teams list is empty after subject exclusion.")

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

    agg_note = f"Aggregated {stat} vs opponents: {', '.join(opponent_teams)}"
    final_note = " | ".join(n for n in [excluded_note, agg_note] if n)
    return _r(rows, note=final_note)


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
    return _r(rows)


# ---------------------------------------------------------------------------
# Mother tools — Responses API dispatchers
# Delegate to the 9 functions above. Args arrive as plain dicts from json.loads().
# ---------------------------------------------------------------------------


def query_player_stats(
    duck: DuckDBManager,
    player_name: str,
    stat: str | None = None,
    filters: dict | None = None,
    match_conditions: list[dict] | None = None,
    last_n_gameweeks: int | None = None,
    opponent_teams: list[str] | None = None,
) -> dict:
    """Mother tool: look up, count, or aggregate a stat for a single named player."""
    resolved_log: list[dict] = []
    player_name, entry = _fuzzy_primary(duck, player_name, "player", "player_name")
    resolved_log.append(entry)
    filters, team_log = _resolve_team_filters(duck, filters)
    resolved_log.extend(team_log)

    if opponent_teams:
        if stat is None:
            raise ToolError("query_player_stats with opponent_teams requires stat")
        result = get_stat_vs_opponent_group(
            duck,
            entity_type="player",
            entity_name=player_name,
            stat=stat,
            opponent_teams=opponent_teams,
        )
    elif last_n_gameweeks is not None:
        if stat is None:
            raise ToolError("query_player_stats with last_n_gameweeks requires stat")
        result = get_stat_over_window(
            duck,
            entity_type="player",
            entity_name=player_name,
            stat=stat,
            last_n_gameweeks=last_n_gameweeks,
            filters=filters,
        )
    elif match_conditions:
        result = count_matches_where(
            duck,
            entity_type="player",
            entity_name=player_name,
            conditions=match_conditions,
            filters=filters,
        )
    elif stat is None:
        raise ToolError(
            "query_player_stats requires stat when match_conditions and opponent_teams are both null"
        )
    else:
        result = get_player_stat(duck, player_name=player_name, stat=stat, filters=filters)

    result["resolved_entities"] = resolved_log
    return result


def query_team_stats(
    duck: DuckDBManager,
    stat: str,
    team_name: str | None = None,
    filters: dict | None = None,
    rank_mode: bool = False,
    limit: int = 1,
    descending: bool = True,
    last_n_gameweeks: int | None = None,
) -> dict:
    """Mother tool: look up or rank a stat for one or all teams."""
    resolved_log: list[dict] = []
    if team_name is not None:
        team_name, entry = _fuzzy_primary(duck, team_name, "team", "team_name")
        resolved_log.append(entry)
    filters, team_log = _resolve_team_filters(duck, filters)
    resolved_log.extend(team_log)

    if last_n_gameweeks is not None and rank_mode:
        raise ToolError("query_team_stats cannot combine rank_mode=true with last_n_gameweeks")

    if last_n_gameweeks is not None:
        if team_name is None:
            raise ToolError("query_team_stats with last_n_gameweeks requires team_name")
        result = get_stat_over_window(
            duck,
            entity_type="team",
            entity_name=team_name,
            stat=stat,
            last_n_gameweeks=last_n_gameweeks,
            filters=filters,
        )
    elif rank_mode:
        result = rank_teams(duck, stat=stat, filters=filters, limit=limit, descending=descending)
    else:
        if team_name is None:
            raise ToolError("query_team_stats with rank_mode=false requires team_name")
        result = get_team_stat(duck, team_name=team_name, stat=stat, filters=filters)

    result["resolved_entities"] = resolved_log
    return result


def query_ranking(
    duck: DuckDBManager,
    entity_type: str,
    rank_mode: bool = True,
    entities: list[str] | None = None,
    stat: str | None = None,
    filters: dict | None = None,
    limit: int = 1,
    descending: bool = True,
    match_conditions: list[dict] | None = None,
) -> dict:
    """Mother tool: rank players/teams by a stat, or compare named entities side-by-side."""
    resolved_log: list[dict] = []
    if entities:
        resolved_entities: list[str] = []
        for name in entities:
            canonical, entry = _fuzzy_primary(duck, name, entity_type, "entities[]")
            resolved_entities.append(canonical)
            resolved_log.append(entry)
        entities = resolved_entities
    filters, team_log = _resolve_team_filters(duck, filters)
    resolved_log.extend(team_log)

    if not rank_mode:
        if not entities:
            raise ToolError("query_ranking with rank_mode=false requires entities list")
        if stat is None:
            raise ToolError("query_ranking with rank_mode=false requires stat")
        result = compare_entities(
            duck,
            entity_type=entity_type,
            entities=entities,
            stat=stat,
            filters=filters,
        )
    elif entity_type == "player":
        result = rank_players(
            duck,
            stat=stat,
            filters=filters,
            limit=limit,
            descending=descending,
            match_conditions=match_conditions,
        )
    elif entity_type == "team":
        if stat is None:
            raise ToolError("query_ranking for teams requires stat")
        result = rank_teams(duck, stat=stat, filters=filters, limit=limit, descending=descending)
    else:
        raise ToolError(f"entity_type must be 'player' or 'team', got '{entity_type}'")

    result["resolved_entities"] = resolved_log
    return result
