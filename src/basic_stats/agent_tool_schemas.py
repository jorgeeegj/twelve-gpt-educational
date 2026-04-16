"""
agent_tool_schemas.py — OpenAI Responses API tool schemas (4 mother tools).

Flat format required by client.responses.create:
  {"type": "function", "name": "...", "description": "...", "parameters": {...}}

No "function": {} wrapper. No "strict": True (invalid in Responses API).
The filters object is flat (OpenAI best-practice for LLM reasoning).
Stat vocabulary goes in descriptions, not enums (too many values).
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Shared sub-schemas (reused across tools)
# ---------------------------------------------------------------------------

_FILTERS_SCHEMA: dict = {
    "type": "object",
    "description": (
        "Match-level filters. Set unused fields to null to use season totals. "
        "Set only the fields relevant to the question — leave others as null."
    ),
    "properties": {
        "opponent_team": {
            "type": ["string", "null"],
            "description": "Filter to matches against this specific team (e.g. 'Arsenal'). Null = no filter.",
        },
        "is_home": {
            "type": ["boolean", "null"],
            "description": "true = home matches only, false = away matches only, null = all.",
        },
        "opponent_rank_max": {
            "type": ["integer", "null"],
            "description": (
                "Filter to matches against teams ranked N or better. "
                "E.g. 6 = top 6 teams, 4 = top 4 teams. Null = no filter."
            ),
        },
        "opponent_rank_min": {
            "type": ["integer", "null"],
            "description": (
                "Filter to matches against teams ranked N or worse. "
                "E.g. 16 = bottom 5 of 20 teams. Null = no filter."
            ),
        },
        "matchday_start": {
            "type": ["integer", "null"],
            "description": "First gameweek of the window, inclusive (1–38). Null = no filter.",
        },
        "matchday_end": {
            "type": ["integer", "null"],
            "description": "Last gameweek of the window, inclusive (1–38). Null = no filter.",
        },
        "min_minutes": {
            "type": ["integer", "null"],
            "description": "Only include players with at least this many minutes played. Null = no filter.",
        },
        "min_matches": {
            "type": ["integer", "null"],
            "description": "Only include players who appeared in at least this many matches. Null = no filter.",
        },
        "age_max": {
            "type": ["integer", "null"],
            "description": "Only include players younger than this age (exclusive). Null = no filter.",
        },
        "position": {
            "type": ["string", "null"],
            "description": (
                "Filter by playing position. Use exact DB values: "
                "'Striker', 'Winger', 'Midfielder', 'Central Defender', 'Full Back', 'Goalkeeper'. "
                "Map user aliases: 'CB'/'centre-back' → 'Central Defender', "
                "'LB'/'RB'/'full-back' → 'Full Back', 'GK'/'keeper' → 'Goalkeeper', "
                "'CM'/'DM'/'AM' → 'Midfielder', 'CF'/'forward' → 'Striker', "
                "'winger'/'LW'/'RW' → 'Winger'. Null = no filter."
            ),
        },
        "player_team": {
            "type": ["string", "null"],
            "description": (
                "Filter to players belonging to this team (e.g. 'Liverpool'). "
                "Use when the question asks for the top scorer within a specific club. Null = no filter."
            ),
        },
        "opponent_is_big6": {
            "type": ["boolean", "null"],
            "description": (
                "true = only matches against Big Six clubs (Arsenal, Chelsea, Liverpool, "
                "Manchester City, Manchester United, Tottenham Hotspur). "
                "Use this instead of opponent_rank_max=6 when the question mentions "
                "'Big Six' or 'top 6 teams' — the Big Six is defined by club identity, "
                "not final league position. Null = no filter."
            ),
        },
    },
    "required": [
        "opponent_team",
        "is_home",
        "opponent_rank_max",
        "opponent_rank_min",
        "matchday_start",
        "matchday_end",
        "min_minutes",
        "min_matches",
        "age_max",
        "position",
        "player_team",
        "opponent_is_big6",
    ],
    "additionalProperties": False,
}

_STAT_DESCRIPTION = (
    "The stat column to retrieve. Use the exact DB column name. Examples:\n"
    "Player summary stats: total_goals, total_assists, xg_total, total_minutes, "
    "matches_played, pass_accuracy_pct, progressive_passes, dribbles_won, "
    "dribble_success_pct, aerial_duels_won, recoveries, interceptions, "
    "touches_in_box, shot_assists, total_goals_p90, total_assists_p90, "
    "xg_total_p90, recoveries_p90, progressive_passes_p90.\n"
    "Player match stats (per-game): goals, assists, minutes_played, yellow_card, red_card.\n"
    "Player match event stats: progressive_passes, key_passes, crosses, shots, "
    "shots_on_target, xg_total, dribbles_won, touches_in_box, shot_assists, "
    "recoveries, interceptions, clearances, fouls_committed, aerial_duels_won, "
    "actions_z3.\n"
    "Team summary stats: total_goals, total_goals_against, pass_accuracy_pct, "
    "progressive_passes, shots_on_target, aerial_duels_won.\n"
    "Team match stats: team_score, opponent_score, points, goal_difference, "
    "assists, progressive_passes, touches_in_box, actions_z3."
)

_MATCH_CONDITIONS_SCHEMA: dict = {
    "type": ["array", "null"],
    "description": (
        "Optional list of per-match conditions that must ALL be true. "
        "When set, counts the number of matches where ALL conditions hold "
        "(e.g. goals>=1 AND assists>=1). Use for questions like "
        "'Which player has the most matches with both a goal and an assist?' or "
        "'Which player has the most matches with 2+ goals?'. "
        "Set null to rank by stat total instead. "
        "Player match metrics: goals, assists, minutes_played, yellow_card, red_card."
    ),
    "items": {
        "type": "object",
        "properties": {
            "metric": {"type": "string"},
            "operator": {
                "type": "string",
                "enum": [">", ">=", "<", "<=", "=", "!="],
            },
            "value": {"type": "number"},
        },
        "required": ["metric", "operator", "value"],
        "additionalProperties": False,
    },
}

# ---------------------------------------------------------------------------
# Tool 1 — query_player_stats
# Absorbs: get_player_stat, count_matches_where (player),
#          get_stat_over_window (player), get_stat_vs_opponent_group (player)
# ---------------------------------------------------------------------------

QUERY_PLAYER_STATS_SCHEMA: dict[str, Any] = {
    "type": "function",
    "name": "query_player_stats",
    "description": (
        "Look up, count, or aggregate a stat for a single named player.\n\n"
        "Use for:\n"
        "- Season totals: 'How many goals has Haaland scored?'\n"
        "- With filters: 'How many goals has Salah scored against Big Six teams?'\n"
        "- Match counts: 'How many matches has Haaland scored AND assisted?' "
        "→ set match_conditions, leave stat null\n"
        "- Gameweek window: 'How many goals in the last 5 gameweeks?' "
        "→ set last_n_gameweeks=5\n"
        "- Against opponent list: 'Goals vs the 3 teams with fewest goals conceded?' "
        "→ first call query_ranking to get team names, then set opponent_teams"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "player_name": {
                "type": "string",
                "description": (
                    "Player short name as used in the DB "
                    "(e.g. 'E. Haaland', 'M. Salah', 'K. De Bruyne')."
                ),
            },
            "stat": {
                "type": ["string", "null"],
                "description": _STAT_DESCRIPTION + "\nSet null only when match_conditions is set.",
            },
            "filters": _FILTERS_SCHEMA,
            "match_conditions": _MATCH_CONDITIONS_SCHEMA,
            "last_n_gameweeks": {
                "type": ["integer", "null"],
                "description": (
                    "When set, restricts the query to the N most recent gameweeks. "
                    "The start/end gameweek is resolved automatically from the DB. "
                    "null = no window filter."
                ),
            },
            "opponent_teams": {
                "type": ["array", "null"],
                "description": (
                    "When set, aggregates the stat only across matches against these specific "
                    "opponent teams. Use after query_ranking to form the list. "
                    "null = no opponent-list filter."
                ),
                "items": {"type": "string"},
            },
        },
        "required": [
            "player_name",
            "stat",
            "filters",
            "match_conditions",
            "last_n_gameweeks",
            "opponent_teams",
        ],
        "additionalProperties": False,
    },
}

# ---------------------------------------------------------------------------
# Tool 2 — query_team_stats
# Absorbs: get_team_stat, rank_teams, get_stat_over_window (team)
# ---------------------------------------------------------------------------

QUERY_TEAM_STATS_SCHEMA: dict[str, Any] = {
    "type": "function",
    "name": "query_team_stats",
    "description": (
        "Look up or rank a stat for one or all teams.\n\n"
        "Use for:\n"
        "- Single team lookup: 'How many goals has Arsenal scored at home?' "
        "→ set team_name, rank_mode=false\n"
        "- Team ranking: 'Which team has conceded the fewest goals?' "
        "→ set rank_mode=true, descending=false\n"
        "- Top N teams: 'Top 5 teams by progressive passes' "
        "→ rank_mode=true, limit=5\n"
        "- Gameweek window: 'Liverpool goals in the last 5 gameweeks' "
        "→ set team_name, last_n_gameweeks=5"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "team_name": {
                "type": ["string", "null"],
                "description": (
                    "Team name for single-team lookup (e.g. 'Arsenal', 'Manchester City'). "
                    "Set null when rank_mode=true."
                ),
            },
            "stat": {
                "type": "string",
                "description": _STAT_DESCRIPTION,
            },
            "filters": _FILTERS_SCHEMA,
            "rank_mode": {
                "type": "boolean",
                "description": (
                    "true = rank all teams by stat and return top/bottom limit. "
                    "false = look up a single named team."
                ),
            },
            "limit": {
                "type": "integer",
                "description": "Number of teams to return when rank_mode=true (1–20). Default 1.",
            },
            "descending": {
                "type": "boolean",
                "description": "true = highest first (most goals), false = lowest first (fewest goals conceded).",
            },
            "last_n_gameweeks": {
                "type": ["integer", "null"],
                "description": (
                    "When set, restricts the query to the N most recent gameweeks. "
                    "Cannot be combined with rank_mode=true. null = no window filter."
                ),
            },
        },
        "required": [
            "team_name",
            "stat",
            "filters",
            "rank_mode",
            "limit",
            "descending",
            "last_n_gameweeks",
        ],
        "additionalProperties": False,
    },
}

# ---------------------------------------------------------------------------
# Tool 3 — query_ranking
# Absorbs: rank_players, compare_entities
# ---------------------------------------------------------------------------

QUERY_RANKING_SCHEMA: dict[str, Any] = {
    "type": "function",
    "name": "query_ranking",
    "description": (
        "Rank players by a stat, or compare a stat across named players/teams side-by-side.\n\n"
        "Use for:\n"
        "- Ranking: 'Which player has scored the most goals?' "
        "→ entity_type=player, rank_mode=true, limit=1\n"
        "- Position filter: 'Which midfielder has the most progressive passes?' "
        "→ rank_mode=true, filters.position='Midfielder'\n"
        "- Match conditions: 'Which player has the most matches with goal+assist?' "
        "→ rank_mode=true, match_conditions set\n"
        "- Comparison: 'Compare Salah and Haaland goals at home' "
        "→ rank_mode=false, entities=['M. Salah', 'E. Haaland']\n"
        "- Bucket split: 'Has Haaland scored more vs top-5 or bottom-5?' "
        "→ call query_player_stats twice with different filters and compare"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "entity_type": {
                "type": "string",
                "enum": ["player", "team"],
                "description": "Whether ranking/comparing players or teams.",
            },
            "rank_mode": {
                "type": "boolean",
                "description": (
                    "true = rank all entities by stat, return top/bottom limit. "
                    "false = compare a named list of entities side-by-side."
                ),
            },
            "entities": {
                "type": ["array", "null"],
                "description": (
                    "List of player or team names for side-by-side comparison. "
                    "Required when rank_mode=false. Set null when rank_mode=true."
                ),
                "items": {"type": "string"},
            },
            "stat": {
                "type": ["string", "null"],
                "description": _STAT_DESCRIPTION + "\nSet null only when match_conditions is set.",
            },
            "filters": _FILTERS_SCHEMA,
            "limit": {
                "type": "integer",
                "description": "Number of results to return when rank_mode=true (1–20). Default 1.",
            },
            "descending": {
                "type": "boolean",
                "description": "true = highest first, false = lowest first.",
            },
            "match_conditions": _MATCH_CONDITIONS_SCHEMA,
        },
        "required": [
            "entity_type",
            "rank_mode",
            "entities",
            "stat",
            "filters",
            "limit",
            "descending",
            "match_conditions",
        ],
        "additionalProperties": False,
    },
}

# ---------------------------------------------------------------------------
# Tool 4 — get_league_standings (unchanged logic, updated format)
# ---------------------------------------------------------------------------

GET_LEAGUE_STANDINGS_SCHEMA: dict[str, Any] = {
    "type": "function",
    "name": "get_league_standings",
    "description": (
        "Return the current Premier League 2024-25 standings table with position, "
        "team name, wins, draws, losses, goals for/against, goal difference, and points. "
        "Use when the question is about league position, promotion, relegation, "
        "Champions League spots, or when you need to identify the top/bottom N teams "
        "by actual league standing."
    ),
    "parameters": {
        "type": "object",
        "properties": {},
        "required": [],
        "additionalProperties": False,
    },
}

# ---------------------------------------------------------------------------
# Exported list — passed as tools= to client.responses.create
# ---------------------------------------------------------------------------

ALL_AGENT_TOOLS: list[dict[str, Any]] = [
    QUERY_PLAYER_STATS_SCHEMA,
    QUERY_TEAM_STATS_SCHEMA,
    QUERY_RANKING_SCHEMA,
    GET_LEAGUE_STANDINGS_SCHEMA,
]
