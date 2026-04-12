"""
agent_tool_schemas.py — OpenAI tool schemas for the Phase 5 agent.

All schemas use strict=True and additionalProperties=false.
The filters object is flat (OpenAI best-practice for LLM reasoning).
Stat vocabulary goes in descriptions, not enums (too many values).
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Shared filters sub-schema (inlined into each tool)
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
                "Filter to matches against teams ranked N or worse. E.g. 16 = bottom 5 of 20 teams. Null = no filter."
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
                "'Striker', 'Winger', 'Midfielder', 'Defender', 'Goalkeeper'. Null = no filter."
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

# ---------------------------------------------------------------------------
# Tool schemas
# ---------------------------------------------------------------------------

GET_PLAYER_STAT_SCHEMA: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "get_player_stat",
        "strict": True,
        "description": (
            "Look up an aggregated stat for a single named player. "
            "Use for questions like 'How many goals has Haaland scored?' or "
            "'How many assists has Salah made against top-6 teams?'"
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
                "stat": {"type": "string", "description": _STAT_DESCRIPTION},
                "filters": _FILTERS_SCHEMA,
            },
            "required": ["player_name", "stat", "filters"],
            "additionalProperties": False,
        },
    },
}

GET_TEAM_STAT_SCHEMA: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "get_team_stat",
        "strict": True,
        "description": (
            "Look up an aggregated stat for a single named team. "
            "Use for questions like 'How many goals has Arsenal scored at home?' or "
            "'How many points has Liverpool earned against Big Six teams?'"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "team_name": {
                    "type": "string",
                    "description": "Team name as used in the DB (e.g. 'Arsenal', 'Manchester City').",
                },
                "stat": {"type": "string", "description": _STAT_DESCRIPTION},
                "filters": _FILTERS_SCHEMA,
            },
            "required": ["team_name", "stat", "filters"],
            "additionalProperties": False,
        },
    },
}

_MATCH_CONDITIONS_SCHEMA: dict = {
    "type": ["array", "null"],
    "description": (
        "Optional list of per-match conditions that must ALL be true. "
        "When set, rank_players counts the number of matches where ALL conditions hold "
        "(e.g. goals>=1 AND assists>=1). Use this for questions like "
        "'Which player has the most matches with both a goal and an assist?' or "
        "'Which player has the most matches with 2+ goals?'. "
        "When null, rank by the stat sum/total. "
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

RANK_PLAYERS_SCHEMA: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "rank_players",
        "strict": True,
        "description": (
            "Rank all players by a stat and return the top/bottom N. "
            "Use for questions like 'Which player has scored the most goals?' or "
            "'Which midfielder has the most progressive passes against top-6 teams?'. "
            "For 'which player has the most matches with X' questions, set "
            "match_conditions instead of stat."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "stat": {"type": ["string", "null"], "description": _STAT_DESCRIPTION},
                "filters": _FILTERS_SCHEMA,
                "limit": {
                    "type": "integer",
                    "description": "Number of players to return (1–20). Default 1 for 'which player has the most'.",
                },
                "descending": {
                    "type": "boolean",
                    "description": "true = highest first (most/best), false = lowest first (fewest/worst).",
                },
                "match_conditions": _MATCH_CONDITIONS_SCHEMA,
            },
            "required": ["stat", "filters", "limit", "descending", "match_conditions"],
            "additionalProperties": False,
        },
    },
}

RANK_TEAMS_SCHEMA: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "rank_teams",
        "strict": True,
        "description": (
            "Rank all teams by a stat and return the top/bottom N. "
            "Use for questions like 'Which team has scored the most goals?' or "
            "'Which team has the best goal difference away from home?'"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "stat": {"type": "string", "description": _STAT_DESCRIPTION},
                "filters": _FILTERS_SCHEMA,
                "limit": {
                    "type": "integer",
                    "description": "Number of teams to return (1–20).",
                },
                "descending": {
                    "type": "boolean",
                    "description": "true = highest first, false = lowest first.",
                },
            },
            "required": ["stat", "filters", "limit", "descending"],
            "additionalProperties": False,
        },
    },
}

COMPARE_ENTITIES_SCHEMA: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "compare_entities",
        "strict": True,
        "description": (
            "Compare a stat across a list of named players or teams. "
            "Use for questions like 'Has Haaland scored more goals against top-5 or bottom-5 teams?' "
            "or 'Compare Arsenal and Liverpool's goals scored at home.'"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "entity_type": {
                    "type": "string",
                    "enum": ["player", "team"],
                    "description": "Whether the entities are players or teams.",
                },
                "entities": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of player or team names to compare.",
                },
                "stat": {"type": "string", "description": _STAT_DESCRIPTION},
                "filters": _FILTERS_SCHEMA,
            },
            "required": ["entity_type", "entities", "stat", "filters"],
            "additionalProperties": False,
        },
    },
}

COUNT_MATCHES_WHERE_SCHEMA: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "count_matches_where",
        "strict": True,
        "description": (
            "Count the number of matches where a player/team met all given conditions. "
            "Use for questions like 'How many matches has Haaland scored AND assisted in?' or "
            "'In how many matches has Salah scored 2 or more goals?'"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "entity_type": {
                    "type": "string",
                    "enum": ["player", "team"],
                },
                "entity_name": {
                    "type": "string",
                    "description": "Player or team name.",
                },
                "conditions": {
                    "type": "array",
                    "description": (
                        "List of match-level conditions that must ALL be true. "
                        "Each condition: {metric, operator, value}. "
                        "Operators: '>', '>=', '<', '<=', '='. "
                        "Player metrics: goals, assists, minutes_played, yellow_card, red_card. "
                        'Example: [{"metric": "goals", "operator": ">=", "value": 1}, '
                        '{"metric": "assists", "operator": ">=", "value": 1}]'
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
                },
                "filters": _FILTERS_SCHEMA,
            },
            "required": ["entity_type", "entity_name", "conditions", "filters"],
            "additionalProperties": False,
        },
    },
}

GET_STAT_OVER_WINDOW_SCHEMA: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "get_stat_over_window",
        "strict": True,
        "description": (
            "Return a stat for the most recent N gameweeks. "
            "Use for questions like 'How many goals has Haaland scored in the last 5 gameweeks?'"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "entity_type": {
                    "type": "string",
                    "enum": ["player", "team"],
                },
                "entity_name": {
                    "type": "string",
                    "description": "Player or team name.",
                },
                "stat": {"type": "string", "description": _STAT_DESCRIPTION},
                "last_n_gameweeks": {
                    "type": "integer",
                    "description": "Number of most recent gameweeks to include (e.g. 5).",
                },
                "filters": _FILTERS_SCHEMA,
            },
            "required": ["entity_type", "entity_name", "stat", "last_n_gameweeks", "filters"],
            "additionalProperties": False,
        },
    },
}

GET_LEAGUE_STANDINGS_SCHEMA: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "get_league_standings",
        "strict": True,
        "description": (
            "Return the current Premier League 2024-25 standings table with position, team, "
            "points, goal difference, wins, draws, losses. "
            "Use when the question is about league position, promotion, relegation, "
            "or you need to know who the top/bottom N teams are."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False,
        },
    },
}

GET_STAT_VS_OPPONENT_GROUP_SCHEMA: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "get_stat_vs_opponent_group",
        "strict": True,
        "description": (
            "Return a player's or team's aggregated stat across a specific list of opponents. "
            "Use this for two-step questions like 'How many goals has Salah scored against the "
            "3 teams that have conceded the fewest goals?'. "
            "Step 1: call rank_teams to find which teams form the group. "
            "Step 2: call this tool with those team names to aggregate the stat."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "entity_type": {
                    "type": "string",
                    "enum": ["player", "team"],
                },
                "entity_name": {
                    "type": "string",
                    "description": "Player or team name to aggregate stats for.",
                },
                "stat": {"type": "string", "description": _STAT_DESCRIPTION},
                "opponent_teams": {
                    "type": "array",
                    "description": "List of opponent team names to aggregate against.",
                    "items": {"type": "string"},
                },
            },
            "required": ["entity_type", "entity_name", "stat", "opponent_teams"],
            "additionalProperties": False,
        },
    },
}

ALL_AGENT_TOOLS: list[dict[str, Any]] = [
    GET_PLAYER_STAT_SCHEMA,
    GET_TEAM_STAT_SCHEMA,
    RANK_PLAYERS_SCHEMA,
    RANK_TEAMS_SCHEMA,
    COMPARE_ENTITIES_SCHEMA,
    COUNT_MATCHES_WHERE_SCHEMA,
    GET_STAT_OVER_WINDOW_SCHEMA,
    GET_LEAGUE_STANDINGS_SCHEMA,
    GET_STAT_VS_OPPONENT_GROUP_SCHEMA,
]
