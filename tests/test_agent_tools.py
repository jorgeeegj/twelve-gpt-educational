# NOTE: These tests require DuckDB data files in output/ but NO LLM credentials.
# Run manually: python -m pytest tests/test_agent_tools.py -v

import pytest

from src.basic_stats.agent_tools import (
    ToolError,
    compare_entities,
    count_matches_where,
    get_league_standings,
    get_player_stat,
    get_stat_over_window,
    get_team_stat,
    rank_players,
    rank_teams,
)
from src.basic_stats.duckdb_manager import DuckDBManager


@pytest.fixture(scope="module")
def duck():
    return DuckDBManager()


# ---------------------------------------------------------------------------
# get_player_stat
# ---------------------------------------------------------------------------


class TestGetPlayerStat:
    def test_happy_path_no_filters(self, duck):
        result = get_player_stat(duck, "E. Haaland", "total_goals")
        assert "rows" in result
        assert len(result["rows"]) == 1
        row = result["rows"][0]
        assert "metric_value" in row
        assert row["metric_value"] > 0

    def test_with_match_filter(self, duck):
        # Goals against top-6 opponents
        result = get_player_stat(
            duck,
            "E. Haaland",
            "goals",
            {"opponent_rank_max": 6},
        )
        assert "rows" in result
        assert len(result["rows"]) <= 1  # may be 0 if no matches vs top-6

    def test_unknown_player_returns_empty(self, duck):
        result = get_player_stat(duck, "Nonexistent Player", "total_goals")
        assert result["rows"] == []

    def test_match_event_metric_routes_correctly(self, duck):
        result = get_player_stat(duck, "K. De Bruyne", "progressive_passes")
        assert "rows" in result
        # progressive_passes is a match-event metric — should return data

    def test_away_goals(self, duck):
        result = get_player_stat(duck, "M. Salah", "goals", {"is_home": False})
        assert "rows" in result


# ---------------------------------------------------------------------------
# get_team_stat
# ---------------------------------------------------------------------------


class TestGetTeamStat:
    def test_summary_stat(self, duck):
        result = get_team_stat(duck, "Arsenal", "total_goals")
        assert len(result["rows"]) == 1
        assert result["rows"][0]["metric_value"] > 0

    def test_match_stat_with_home_filter(self, duck):
        result = get_team_stat(duck, "Liverpool", "team_score", {"is_home": True})
        assert "rows" in result

    def test_unknown_team_returns_empty(self, duck):
        result = get_team_stat(duck, "Nonexistent FC", "total_goals")
        assert result["rows"] == []

    def test_points_agg(self, duck):
        result = get_team_stat(
            duck,
            "Arsenal",
            "points",
            {"opponent_rank_max": 6},
        )
        assert "rows" in result


# ---------------------------------------------------------------------------
# rank_players
# ---------------------------------------------------------------------------


class TestRankPlayers:
    def test_top1_no_filters(self, duck):
        result = rank_players(duck, "total_goals", limit=1)
        assert len(result["rows"]) == 1

    def test_top5(self, duck):
        result = rank_players(duck, "total_goals", limit=5)
        assert len(result["rows"]) == 5

    def test_with_opponent_filter(self, duck):
        result = rank_players(duck, "goals", {"opponent_rank_max": 6}, limit=3)
        assert "rows" in result
        assert len(result["rows"]) <= 3

    def test_limit_capped_at_20(self, duck):
        result = rank_players(duck, "total_goals", limit=100)
        assert len(result["rows"]) <= 20

    def test_position_filter(self, duck):
        result = rank_players(
            duck,
            "progressive_passes",
            {"position": "Midfielder"},
            limit=3,
        )
        assert "rows" in result


# ---------------------------------------------------------------------------
# rank_teams
# ---------------------------------------------------------------------------


class TestRankTeams:
    def test_top1(self, duck):
        result = rank_teams(duck, "total_goals", limit=1)
        assert len(result["rows"]) == 1

    def test_with_home_filter(self, duck):
        result = rank_teams(duck, "team_score", {"is_home": True}, limit=3)
        assert len(result["rows"]) <= 3

    def test_points_vs_big6(self, duck):
        result = rank_teams(
            duck,
            "points",
            {"opponent_rank_max": 6},
            limit=1,
        )
        assert "rows" in result


# ---------------------------------------------------------------------------
# compare_entities
# ---------------------------------------------------------------------------


class TestCompareEntities:
    def test_compare_two_players(self, duck):
        result = compare_entities(
            duck,
            entity_type="player",
            entities=["E. Haaland", "M. Salah"],
            stat="total_goals",
        )
        assert len(result["rows"]) == 2
        names = {r["entity"] for r in result["rows"]}
        assert "E. Haaland" in names
        assert "M. Salah" in names

    def test_compare_with_filter(self, duck):
        result = compare_entities(
            duck,
            entity_type="player",
            entities=["E. Haaland"],
            stat="goals",
            filters={"opponent_rank_max": 5},
        )
        assert len(result["rows"]) == 1

    def test_invalid_entity_type_raises(self, duck):
        with pytest.raises(ToolError):
            compare_entities(duck, entity_type="coach", entities=["Guardiola"], stat="goals")

    def test_compare_two_teams(self, duck):
        result = compare_entities(
            duck,
            entity_type="team",
            entities=["Arsenal", "Chelsea"],
            stat="total_goals",
        )
        assert len(result["rows"]) == 2


# ---------------------------------------------------------------------------
# count_matches_where
# ---------------------------------------------------------------------------


class TestCountMatchesWhere:
    def test_matches_with_goal(self, duck):
        result = count_matches_where(
            duck,
            entity_type="player",
            entity_name="E. Haaland",
            conditions=[{"metric": "goals", "operator": ">=", "value": 1}],
        )
        assert "rows" in result
        assert len(result["rows"]) <= 1

    def test_matches_with_goal_and_assist(self, duck):
        result = count_matches_where(
            duck,
            entity_type="player",
            entity_name="M. Salah",
            conditions=[
                {"metric": "goals", "operator": ">=", "value": 1},
                {"metric": "assists", "operator": ">=", "value": 1},
            ],
        )
        assert "rows" in result

    def test_invalid_entity_type_raises(self, duck):
        with pytest.raises(ToolError):
            count_matches_where(
                duck,
                entity_type="coach",
                entity_name="Arteta",
                conditions=[{"metric": "goals", "operator": ">=", "value": 1}],
            )


# ---------------------------------------------------------------------------
# get_stat_over_window
# ---------------------------------------------------------------------------


class TestGetStatOverWindow:
    def test_last_5_gameweeks_player(self, duck):
        result = get_stat_over_window(
            duck,
            entity_type="player",
            entity_name="E. Haaland",
            stat="goals",
            last_n_gameweeks=5,
        )
        assert "rows" in result

    def test_last_5_gameweeks_team(self, duck):
        result = get_stat_over_window(
            duck,
            entity_type="team",
            entity_name="Arsenal",
            stat="team_score",
            last_n_gameweeks=5,
        )
        assert "rows" in result

    def test_invalid_entity_type_raises(self, duck):
        with pytest.raises(ToolError):
            get_stat_over_window(
                duck,
                entity_type="referee",
                entity_name="Mike Dean",
                stat="goals",
                last_n_gameweeks=5,
            )


# ---------------------------------------------------------------------------
# get_league_standings
# ---------------------------------------------------------------------------


class TestGetLeagueStandings:
    def test_returns_20_teams(self, duck):
        result = get_league_standings(duck)
        assert len(result["rows"]) == 20

    def test_first_row_has_position_1(self, duck):
        result = get_league_standings(duck)
        assert result["rows"][0]["position"] == 1

    def test_has_expected_columns(self, duck):
        result = get_league_standings(duck)
        row = result["rows"][0]
        for col in ("team_name", "points", "wins", "goal_difference", "is_big6"):
            assert col in row, f"Missing column: {col}"

    def test_big6_flag(self, duck):
        result = get_league_standings(duck)
        big6_teams = {r["team_name"] for r in result["rows"] if r["is_big6"]}
        assert "Arsenal" in big6_teams
        assert "Liverpool" in big6_teams
        assert len(big6_teams) == 6
