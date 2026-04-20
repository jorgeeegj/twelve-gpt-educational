"""
agent_prompt.py — system prompt builder for the Phase 5 agent.

Loads the static template from prompts/agent_system.yaml and interpolates
live DB values (player names, teams, positions, max gameweek) once at
agent init time. No runtime discovery tools needed — the PL 2024-25
schema is static.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from src.basic_stats.duckdb_manager import DuckDBManager

_PROMPTS_DIR = Path(__file__).parent / "prompts"


def build_system_prompt(duck: DuckDBManager) -> str:
    """Build the full system prompt by interpolating live DB values into the YAML template."""
    template_text = (_PROMPTS_DIR / "agent_system.yaml").read_text(encoding="utf-8")
    template: str = yaml.safe_load(template_text)["system"]

    player_count_row = duck.query_dicts(
        "SELECT COUNT(DISTINCT short_name) AS c FROM players_summary"
    )
    player_count = player_count_row[0]["c"] if player_count_row else 0

    team_rows = duck.query_dicts(
        "SELECT DISTINCT team_name FROM players_summary ORDER BY team_name"
    )
    team_names = [r["team_name"] for r in team_rows]

    pos_rows = duck.query_dicts(
        "SELECT DISTINCT main_position FROM players_summary ORDER BY main_position"
    )
    positions = [r["main_position"] for r in pos_rows]

    gw_rows = duck.query_dicts("SELECT MAX(gameweek) AS max_gw FROM player_match_stats")
    max_gw = gw_rows[0]["max_gw"] if gw_rows else 38

    return template.format(
        max_gw=max_gw,
        team_count=len(team_names),
        team_names=", ".join(team_names),
        positions=", ".join(positions),
        player_count=player_count,
    )
