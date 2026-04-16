"""
Tests for the 3 mother-tool dispatchers in agent_tools.py (Step 4).
Calls real DuckDB — no LLM calls.
Run with: python -m pytest tests/test_agent_tools_mother.py -v
"""

import pytest

from src.basic_stats.agent_tools import (
    ToolError,
    get_league_standings,
    query_player_stats,
    query_ranking,
    query_team_stats,
)
from src.basic_stats.duckdb_manager import DuckDBManager

_DEFAULT_FILTERS = {
    "opponent_team": None,
    "is_home": None,
    "opponent_rank_max": None,
    "opponent_rank_min": None,
    "matchday_start": None,
    "matchday_end": None,
    "min_minutes": None,
    "min_matches": None,
    "age_max": None,
    "position": None,
    "player_team": None,
    "opponent_is_big6": None,
}


@pytest.fixture(scope="module")
def duck():
    return DuckDBManager()


# ---------------------------------------------------------------------------
# query_player_stats
# ---------------------------------------------------------------------------


def test_query_player_stats_basic(duck):
    result = query_player_stats(duck, player_name="E. Haaland", stat="total_goals")
    assert "rows" in result
    assert len(result["rows"]) > 0


def test_query_player_stats_with_match_conditions(duck):
    result = query_player_stats(
        duck,
        player_name="E. Haaland",
        stat=None,
        match_conditions=[{"metric": "goals", "operator": ">=", "value": 1}],
    )
    assert "rows" in result
    assert len(result["rows"]) > 0


def test_query_player_stats_with_last_n_gameweeks(duck):
    result = query_player_stats(
        duck,
        player_name="E. Haaland",
        stat="goals",
        last_n_gameweeks=5,
    )
    assert "rows" in result


def test_query_player_stats_with_opponent_teams(duck):
    result = query_player_stats(
        duck,
        player_name="E. Haaland",
        stat="goals",
        opponent_teams=["Arsenal", "Chelsea"],
    )
    assert "rows" in result


def test_query_player_stats_no_stat_no_conditions_raises(duck):
    with pytest.raises(ToolError):
        query_player_stats(duck, player_name="E. Haaland", stat=None)


def test_query_player_stats_opponent_teams_without_stat_raises(duck):
    with pytest.raises(ToolError):
        query_player_stats(
            duck,
            player_name="E. Haaland",
            stat=None,
            opponent_teams=["Arsenal"],
        )


def test_query_player_stats_last_n_gameweeks_without_stat_raises(duck):
    with pytest.raises(ToolError):
        query_player_stats(
            duck,
            player_name="E. Haaland",
            stat=None,
            last_n_gameweeks=5,
        )


def test_query_player_stats_with_home_filter(duck):
    result = query_player_stats(
        duck,
        player_name="M. Salah",
        stat="goals",
        filters={**_DEFAULT_FILTERS, "is_home": True},
    )
    assert "rows" in result


# ---------------------------------------------------------------------------
# query_team_stats
# ---------------------------------------------------------------------------


def test_query_team_stats_single_team(duck):
    result = query_team_stats(duck, stat="team_score", team_name="Arsenal", rank_mode=False)
    assert "rows" in result
    assert len(result["rows"]) > 0


def test_query_team_stats_rank_mode(duck):
    result = query_team_stats(duck, stat="team_score", rank_mode=True, limit=5, descending=True)
    assert "rows" in result
    assert len(result["rows"]) <= 5


def test_query_team_stats_rank_plus_window_raises(duck):
    with pytest.raises(ToolError):
        query_team_stats(duck, stat="team_score", rank_mode=True, last_n_gameweeks=5)


def test_query_team_stats_no_team_no_rank_raises(duck):
    with pytest.raises(ToolError):
        query_team_stats(duck, stat="team_score", rank_mode=False, team_name=None)


def test_query_team_stats_last_n_gameweeks(duck):
    result = query_team_stats(
        duck,
        stat="team_score",
        team_name="Liverpool",
        rank_mode=False,
        last_n_gameweeks=5,
    )
    assert "rows" in result


def test_query_team_stats_last_n_without_team_raises(duck):
    with pytest.raises(ToolError):
        query_team_stats(
            duck,
            stat="team_score",
            team_name=None,
            rank_mode=False,
            last_n_gameweeks=5,
        )


# ---------------------------------------------------------------------------
# query_ranking
# ---------------------------------------------------------------------------


def test_query_ranking_player_rank(duck):
    result = query_ranking(
        duck,
        entity_type="player",
        rank_mode=True,
        stat="total_goals",
        limit=3,
    )
    assert "rows" in result
    assert len(result["rows"]) <= 3


def test_query_ranking_player_compare(duck):
    result = query_ranking(
        duck,
        entity_type="player",
        rank_mode=False,
        entities=["E. Haaland", "M. Salah"],
        stat="total_goals",
    )
    assert "rows" in result
    assert len(result["rows"]) == 2


def test_query_ranking_no_entities_when_compare_raises(duck):
    with pytest.raises(ToolError):
        query_ranking(
            duck,
            entity_type="player",
            rank_mode=False,
            entities=None,
            stat="total_goals",
        )


def test_query_ranking_compare_no_stat_raises(duck):
    with pytest.raises(ToolError):
        query_ranking(
            duck,
            entity_type="player",
            rank_mode=False,
            entities=["E. Haaland", "M. Salah"],
            stat=None,
        )


def test_query_ranking_team_rank(duck):
    result = query_ranking(
        duck,
        entity_type="team",
        rank_mode=True,
        stat="team_score",
        limit=3,
        descending=True,
    )
    assert "rows" in result
    assert len(result["rows"]) <= 3


def test_query_ranking_team_rank_no_stat_raises(duck):
    with pytest.raises(ToolError):
        query_ranking(
            duck,
            entity_type="team",
            rank_mode=True,
            stat=None,
        )


def test_query_ranking_invalid_entity_type_raises(duck):
    with pytest.raises(ToolError):
        query_ranking(
            duck,
            entity_type="coach",
            rank_mode=True,
            stat="total_goals",
        )


def test_query_ranking_with_match_conditions(duck):
    result = query_ranking(
        duck,
        entity_type="player",
        rank_mode=True,
        stat=None,
        match_conditions=[{"metric": "goals", "operator": ">=", "value": 1}],
        limit=3,
    )
    assert "rows" in result


def test_query_ranking_with_position_filter(duck):
    result = query_ranking(
        duck,
        entity_type="player",
        rank_mode=True,
        stat="total_goals",
        filters={**_DEFAULT_FILTERS, "position": "Striker"},
        limit=5,
    )
    assert "rows" in result


# ---------------------------------------------------------------------------
# get_league_standings (smoke check via mother context)
# ---------------------------------------------------------------------------


def test_get_league_standings_returns_20_teams(duck):
    result = get_league_standings(duck)
    assert "rows" in result
    assert len(result["rows"]) == 20
