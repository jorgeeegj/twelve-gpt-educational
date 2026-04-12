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
                    "description": (
                        "Player or team name as it appears in English football "
                        "(e.g. 'E. Haaland', 'Manchester City')."
                    ),
                },
                "metric": {
                    "type": "string",
                    "description": (
                        "The stat to retrieve (e.g. 'goals', 'assists', 'xg', "
                        "'progressive_passes', 'tackles_won')."
                    ),
                },
                "aggregation": {
                    "type": "string",
                    "enum": [
                        "sum",
                        "avg",
                        "count_matches_positive",
                        "points",
                        "wins",
                        "goal_difference",
                    ],
                    "description": (
                        "How to aggregate the metric. Use 'sum' for totals, "
                        "'avg' for per-game averages."
                    ),
                },
                "opponent_team": {
                    "type": "string",
                    "description": "Filter to matches against this specific team (e.g. 'Arsenal').",
                },
                "is_home": {
                    "type": "boolean",
                    "description": (
                        "True = home matches only, False = away matches only, omit for all matches."
                    ),
                },
                "opponent_rank_lte": {
                    "type": "integer",
                    "description": (
                        "Filter to matches against teams ranked N or better (top-N teams). "
                        "E.g. 6 = top 6 teams."
                    ),
                },
                "opponent_rank_gte": {
                    "type": "integer",
                    "description": (
                        "Filter to matches against teams ranked N or worse (bottom teams). "
                        "E.g. 16 = bottom 5 of 20."
                    ),
                },
                "opponent_rank_between": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": (
                        "Filter to matches against teams with rank in [lo, hi]. "
                        "E.g. [7, 14] = mid-table."
                    ),
                },
                "opponent_is_big6": {
                    "type": "boolean",
                    "description": (
                        "True = filter to Big Six opponents "
                        "(Arsenal, Chelsea, Liverpool, Man City, Man Utd, Spurs)."
                    ),
                },
                "matchday_start": {
                    "type": "integer",
                    "description": "First matchday of the window (inclusive).",
                },
                "matchday_end": {
                    "type": "integer",
                    "description": "Last matchday of the window (inclusive).",
                },
                "position": {
                    "type": "string",
                    "description": (
                        "Player position filter "
                        "(e.g. 'forward', 'midfielder', 'defender', 'goalkeeper')."
                    ),
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
            "Use for 'or' questions like "
            "'Has Haaland scored more against top 5 or bottom 5 teams?'"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "entity_type": {"type": "string", "enum": ["player", "team"]},
                "entity_name": {"type": "string"},
                "metric": {"type": "string"},
                "aggregation": {
                    "type": "string",
                    "enum": [
                        "sum",
                        "avg",
                        "count_matches_positive",
                        "points",
                        "wins",
                        "goal_difference",
                    ],
                },
                "bucket_a": {
                    "type": "object",
                    "description": "First opponent group filter.",
                    "properties": {
                        "opponent_rank_lte": {"type": "integer"},
                        "opponent_rank_gte": {"type": "integer"},
                        "opponent_rank_between": {
                            "type": "array",
                            "items": {"type": "integer"},
                        },
                        "opponent_is_big6": {"type": "boolean"},
                    },
                },
                "bucket_b": {
                    "type": "object",
                    "description": "Second opponent group filter.",
                    "properties": {
                        "opponent_rank_lte": {"type": "integer"},
                        "opponent_rank_gte": {"type": "integer"},
                        "opponent_rank_between": {
                            "type": "array",
                            "items": {"type": "integer"},
                        },
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
                    "enum": [
                        "sum",
                        "avg",
                        "count_matches_positive",
                        "points",
                        "wins",
                        "goal_difference",
                    ],
                },
                "ranking_mode": {
                    "type": "string",
                    "enum": ["top_n", "ordinal"],
                    "description": (
                        "'top_n' returns the top N entities, "
                        "'ordinal' finds the entity at position N."
                    ),
                },
                "n": {
                    "type": "integer",
                    "description": (
                        "Number of entities to return (top_n mode), "
                        "or rank position (ordinal mode)."
                    ),
                },
                "descending": {
                    "type": "boolean",
                    "description": (
                        "True = highest first (most/best), False = lowest first (fewest/worst)."
                    ),
                },
                "position": {"type": "string"},
                "team_name": {
                    "type": "string",
                    "description": "Filter to players from this team.",
                },
                "opponent_rank_lte": {"type": "integer"},
                "opponent_rank_gte": {"type": "integer"},
                "opponent_rank_between": {
                    "type": "array",
                    "items": {"type": "integer"},
                },
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
            "Use for questions like "
            "'How many goals has Haaland scored in the last 5 gameweeks?'"
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
