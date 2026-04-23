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
    get_stat_vs_opponent_group,
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

    def test_p90_with_big6_filter_is_not_raw_count(self, duck):
        """total_goals_p90 vs Big6 should be a ratio, not the raw goals sum."""
        result_p90 = get_player_stat(
            duck, "E. Haaland", "total_goals_p90", {"opponent_is_big6": True}
        )
        result_raw = get_player_stat(
            duck, "E. Haaland", "goals", {"opponent_is_big6": True}
        )
        assert result_p90["rows"], "Expected p90 result for Haaland vs Big6"
        p90_val = result_p90["rows"][0]["metric_value"]
        raw_val = result_raw["rows"][0]["metric_value"]
        assert p90_val != raw_val, (
            f"p90={p90_val} equals raw count={raw_val} — likely falling back to goals sum"
        )
        assert 0 < p90_val < 5.0

    def test_p90_without_match_context_uses_summary(self, duck):
        """total_goals_p90 without filters routes to summary (season total)."""
        result = get_player_stat(duck, "E. Haaland", "total_goals_p90")
        assert len(result["rows"]) == 1
        assert result["rows"][0]["metric_value"] > 0

    def test_p90_with_matchday_filter(self, duck):
        """total_goals_p90 with matchday window computes a ratio, not raw count."""
        result_p90 = get_player_stat(
            duck, "E. Haaland", "total_goals_p90", {"matchday_start": 1, "matchday_end": 20}
        )
        result_raw = get_player_stat(
            duck, "E. Haaland", "goals", {"matchday_start": 1, "matchday_end": 20}
        )
        if result_p90["rows"] and result_raw["rows"]:
            p90_val = result_p90["rows"][0]["metric_value"]
            raw_val = result_raw["rows"][0]["metric_value"]
            assert p90_val != raw_val


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

    def test_rank_by_p90_with_big6_filter(self, duck):
        """Ranking by total_goals_p90 vs Big6 should return ratio values, not raw goals."""
        result_p90 = rank_players(
            duck, "total_goals_p90", filters={"opponent_is_big6": True}, limit=3
        )
        result_raw = rank_players(
            duck, "goals", filters={"opponent_is_big6": True}, limit=3
        )
        assert result_p90["rows"], "Expected at least one player with Big6 goals"
        top_p90 = result_p90["rows"][0]["metric_value"]
        top_raw = result_raw["rows"][0]["metric_value"]
        assert top_p90 != top_raw
        assert 0 < top_p90 < 5.0


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


# ---------------------------------------------------------------------------
# Truthfulness — match-context responses must include appearances + total_minutes
# ---------------------------------------------------------------------------


class TestMatchContextGrounding:
    """Verify that query_player_match_context returns appearances and total_minutes
    so the LLM cannot invent those values when answering contextual questions."""

    def test_haaland_vs_big6_appearances_and_minutes(self, duck):
        """Ground truth: Haaland vs Big Six = 8 appearances, 720 minutes, 5 goals."""
        result = get_player_stat(
            duck, "E. Haaland", "goals", {"opponent_is_big6": True}
        )
        assert result["rows"], "Expected at least one row for Haaland vs Big Six"
        row = result["rows"][0]
        assert row["metric_value"] == 5, f"Expected 5 goals, got {row['metric_value']}"
        assert row["appearances"] == 8, f"Expected 8 appearances, got {row['appearances']}"
        assert row["total_minutes"] == 720, f"Expected 720 minutes, got {row['total_minutes']}"


# ---------------------------------------------------------------------------
# Subject Exclusion — WI-1
# ---------------------------------------------------------------------------


class TestSubjectExclusion:
    def test_get_stat_vs_opponent_group_excludes_own_team(self, duck):
        """Salah (Liverpool) queried vs ["Arsenal", "Liverpool", "Chelsea"]:
        Liverpool must be excluded from the IN clause and the note must say so."""
        result = get_stat_vs_opponent_group(
            duck,
            entity_type="player",
            entity_name="M. Salah",
            stat="goals",
            opponent_teams=["Arsenal", "Liverpool", "Chelsea"],
        )
        note = (result.get("note") or "").lower()
        assert "liverpool" in note, f"Note should mention Liverpool: {note!r}"
        assert "exclud" in note, f"Note should signal exclusion: {note!r}"

    def test_get_player_stat_own_team_as_opponent_returns_semantic_note(self, duck):
        """Salah (Liverpool) queried with opponent_team=Liverpool:
        rows must be empty and note must explain the player plays for that club."""
        result = get_player_stat(
            duck,
            "M. Salah",
            "total_goals",
            filters={"opponent_team": "Liverpool"},
        )
        assert result["rows"] == [], f"Expected empty rows, got: {result['rows']}"
        note = (result.get("note") or "").lower()
        assert "liverpool" in note, f"Note should mention Liverpool: {note!r}"
        assert any(
            phrase in note for phrase in ("plays for", "own club", "own team")
        ), f"Note should semantically explain why: {note!r}"

    # ------------------------------------------------------------------
    # WI-1 postfix: backfill + metric routing (QV6_56, QV6_57)
    # ------------------------------------------------------------------

    def test_get_stat_vs_opponent_group_backfills_everton(self, duck):
        """QV6_56 proxy: Salah vs ['Arsenal','Liverpool','Chelsea'] with fill_stat.
        Liverpool is excluded; Everton (next fewest GA, tied with Man City but E < M) fills in.
        Uses canonical name 'Mohamed Salah' so the DB SQL resolves correctly in test env."""
        result = get_stat_vs_opponent_group(
            duck,
            entity_type="player",
            entity_name="Mohamed Salah",
            stat="goals",
            opponent_teams=["Arsenal", "Liverpool", "Chelsea"],
            fill_stat="total_goals_against",
            fill_descending=False,
        )
        rows = result.get("rows", [])
        note = (result.get("note") or "").lower()
        assert rows, f"Expected at least one row: {result!r}"
        assert rows[0]["metric_value"] == 3, (
            f"Expected 3 goals (Arsenal+Chelsea+Everton), got {rows[0]['metric_value']!r}. "
            f"Note: {note!r}"
        )
        assert "everton" in note, f"Everton must appear in note as replacement: {note!r}"

    def test_get_team_stat_total_goals_against_routes_to_conceded(self, duck):
        """QV6_57 proxy: get_team_stat with stat='total_goals_against' + opponent filter
        must return goals CONCEDED (opponent_score), not goals scored (team_score)."""
        result = get_team_stat(
            duck, "Brentford", "total_goals_against",
            filters={"opponent_team": "Liverpool"},
        )
        rows = result.get("rows", [])
        assert rows, f"Expected at least one row"
        assert rows[0]["metric_value"] == 4, (
            f"Expected 4 (Brentford conceded 4 vs Liverpool), got {rows[0]['metric_value']!r}. "
            f"If got 0, team_score (goals scored) is being returned instead of opponent_score."
        )

    def test_get_team_stat_own_team_opponent_returns_semantic_note(self, duck):
        """Fix B for teams: Brentford with opponent_team=Brentford must return
        empty rows and a semantic note — never a fake zero."""
        result = get_team_stat(
            duck, "Brentford", "total_goals_against",
            filters={"opponent_team": "Brentford"},
        )
        assert result["rows"] == [], f"Expected empty rows, got: {result['rows']}"
        note = (result.get("note") or "").lower()
        assert "brentford" in note, f"Note should mention Brentford: {note!r}"
        assert any(
            phrase in note for phrase in ("cannot", "own opponent", "themselves", "own team")
        ), f"Note should semantically explain why: {note!r}"

    def test_get_stat_vs_opponent_group_excludes_team_entity(self, duck):
        """Defense-in-depth: entity_type='team' exclusion.
        Brentford queried vs ['Liverpool','Manchester City','Brentford','Chelsea']:
        Brentford must be excluded and note must signal it."""
        result = get_stat_vs_opponent_group(
            duck,
            entity_type="team",
            entity_name="Brentford",
            stat="opponent_score",
            opponent_teams=["Liverpool", "Manchester City", "Brentford", "Chelsea"],
        )
        note = (result.get("note") or "").lower()
        assert "brentford" in note, f"Note should mention Brentford: {note!r}"
        assert "exclud" in note, f"Note should signal exclusion: {note!r}"

    def test_rank_teams_exclude_returns_everton_as_third(self, duck):
        """rank_teams with exclude_teams=['Liverpool'] must return 3 valid teams
        where Everton fills in as the 3rd fewest-GA rival (Arsenal=34, Chelsea=43, Everton=44)."""
        result = rank_teams(
            duck, stat="total_goals_against", descending=False, limit=3,
            exclude_teams=["Liverpool"],
        )
        team_names = [r["team_name"] for r in result["rows"]]
        assert len(team_names) == 3, f"Expected 3 teams, got {team_names!r}"
        assert "Liverpool" not in team_names, f"Liverpool must be excluded: {team_names!r}"
        assert "Everton" in team_names, f"Everton must fill in: {team_names!r}"


# ---------------------------------------------------------------------------
# Event Stat p90 in Match Context — WI-2
# ---------------------------------------------------------------------------


class TestEventStatP90:
    """WI-2: event stat *_p90 with a match-context filter must return a per-90
    ratio, not the raw sum. Tests use Haaland vs Big Six as the probe case."""

    @pytest.mark.parametrize("stat_p90,base_stat", [
        ("shots_p90", "shots"),
        ("xg_total_p90", "xg_total"),
        ("key_passes_p90", "key_passes"),
    ])
    def test_event_stat_p90_vs_big6_is_ratio(self, duck, stat_p90, base_stat):
        """p90 event stat with Big Six context must differ from the raw sum."""
        result_p90 = get_player_stat(
            duck, "E. Haaland", stat_p90, {"opponent_is_big6": True}
        )
        result_raw = get_player_stat(
            duck, "E. Haaland", base_stat, {"opponent_is_big6": True}
        )
        assert result_p90["rows"], f"Expected p90 rows for {stat_p90} vs Big6"
        p90_val = result_p90["rows"][0]["metric_value"]
        raw_val = result_raw["rows"][0]["metric_value"] if result_raw["rows"] else 0
        assert p90_val != raw_val, (
            f"{stat_p90}={p90_val} equals raw {base_stat}={raw_val} — "
            "likely returning raw sum instead of per-90 ratio"
        )
        assert 0 < p90_val < 20.0, f"{stat_p90} value {p90_val} is outside plausible p90 range"

    def test_event_stat_p90_ranking_vs_big6(self, duck):
        """rank_players with shots_p90 + Big6 context must return ratio values."""
        result_p90 = rank_players(
            duck, "shots_p90", filters={"opponent_is_big6": True}, limit=3
        )
        result_raw = rank_players(
            duck, "shots", filters={"opponent_is_big6": True}, limit=3
        )
        assert result_p90["rows"], "Expected p90 ranking rows"
        top_p90 = result_p90["rows"][0]["metric_value"]
        top_raw = result_raw["rows"][0]["metric_value"] if result_raw["rows"] else 0
        assert top_p90 != top_raw, (
            f"shots_p90 top={top_p90} equals raw shots top={top_raw} — not a ratio"
        )
        assert 0 < top_p90 < 20.0
