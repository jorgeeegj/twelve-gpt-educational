from pathlib import Path
from typing import Any

import duckdb

BASE = Path(__file__).resolve().parents[3]

OUTPUT_DIR = BASE / "output"
DB_DIR = BASE / "db"
DB_DIR.mkdir(exist_ok=True)

DUCKDB_PATH = DB_DIR / "basic_stats.duckdb"

PLAYER_SUMMARY_PATH = OUTPUT_DIR / "player_full_stats.parquet"
TEAM_SUMMARY_PATH = OUTPUT_DIR / "team_full_stats.parquet"
PLAYER_MATCH_PATH = OUTPUT_DIR / "player_match_stats.parquet"
PLAYER_MATCH_EVENT_PATH = OUTPUT_DIR / "player_match_event_stats.parquet"
TEAM_MATCH_PATH = OUTPUT_DIR / "team_match_stats.parquet"

NEGATIVE_METRICS = {
    "ball_losses",
    "fouls_committed",
    "total_yellow_cards",
    "total_red_cards",
    "offsides",
    "total_goals_against",
    "shots_against",
}

PLAYER_MATCH_ALLOWED_METRICS = {
    "goals",
    "assists",
    "own_goals",
    "yellow_card",
    "red_card",
    "minutes_played",
}

PLAYER_MATCH_EVENT_ALLOWED_METRICS = {
    "total_actions",
    "actions_z1",
    "actions_z2",
    "actions_z3",
    "actions_z4",
    "actions_z5",
    "passes_attempted",
    "passes_accurate",
    "progressive_passes",
    "forward_passes",
    "back_passes",
    "long_passes",
    "key_passes",
    "crosses",
    "passes_to_final_third",
    "passes_to_box",
    "through_passes",
    "smart_passes",
    "shots",
    "shots_on_target",
    "xg_total",
    "aerial_duels",
    "aerial_duels_won",
    "defensive_duels",
    "defensive_duels_won",
    "offensive_duels",
    "offensive_duels_won",
    "dribbles_attempted",
    "dribbles_won",
    "recoveries",
    "interceptions",
    "clearances",
    "sliding_tackles",
    "fouls_committed",
    "fouls_suffered",
    "progressive_carries",
    "carry_meters_gained",
    "progressive_runs",
    "touches_in_box",
    "shot_assists",
    "ball_losses",
    "goalkeeper_exits",
    "shots_against",
    "saves",
    "reflex_saves",
    "pass_z2_to_z4",
    "pass_z2_to_z5",
    "pass_z3_to_z4",
    "pass_z3_to_z5",
    "carry_z2_to_z4",
    "carry_z2_to_z5",
    "carry_z3_to_z4",
    "carry_z3_to_z5",
}

TEAM_MATCH_ALLOWED_METRICS = {
    "team_score",
    "opponent_score",
    "points",
    "goal_difference",
    "assists",
    "xg_total",
    "progressive_passes",
    "key_passes",
    "touches_in_box",
    "aerial_duels_won",
    "recoveries",
    "interceptions",
    "clearances",
    "fouls_committed",
    "fouls_suffered",
    "actions_z1",
    "actions_z2",
    "actions_z3",
    "actions_z4",
    "actions_z5",
    "pass_z2_to_z4",
    "pass_z2_to_z5",
    "pass_z3_to_z4",
    "pass_z3_to_z5",
    "carry_z2_to_z4",
    "carry_z2_to_z5",
    "carry_z3_to_z4",
    "carry_z3_to_z5",
}


class DuckDBManager:
    def __init__(self, db_path: Path | None = None):
        self.db_path = str(db_path or DUCKDB_PATH)
        self.con = duckdb.connect(self.db_path)
        self._register_base_views()

    def close(self) -> None:
        self.con.close()

    def _register_base_views(self) -> None:
        self.con.execute(f"""
            CREATE OR REPLACE VIEW players_summary AS
            SELECT * FROM read_parquet('{PLAYER_SUMMARY_PATH.as_posix()}')
        """)

        self.con.execute(f"""
            CREATE OR REPLACE VIEW teams_summary AS
            SELECT * FROM read_parquet('{TEAM_SUMMARY_PATH.as_posix()}')
        """)

        self.con.execute(f"""
            CREATE OR REPLACE VIEW player_match_stats AS
            SELECT * FROM read_parquet('{PLAYER_MATCH_PATH.as_posix()}')
        """)

        self.con.execute(f"""
            CREATE OR REPLACE VIEW player_match_event_stats AS
            SELECT * FROM read_parquet('{PLAYER_MATCH_EVENT_PATH.as_posix()}')
        """)

        self.con.execute(f"""
            CREATE OR REPLACE VIEW team_match_stats AS
            SELECT * FROM read_parquet('{TEAM_MATCH_PATH.as_posix()}')
        """)

        self.con.execute("""
            CREATE OR REPLACE VIEW league_table AS
            WITH team_match_base AS (
                SELECT DISTINCT
                    match_id,
                    gameweek,
                    home_team_id,
                    away_team_id,
                    team_name,
                    opponent_team_name,
                    is_home,
                    team_score,
                    opponent_score
                FROM player_match_stats
            ),
            one_row_per_match AS (
                SELECT
                    match_id,
                    MAX(CASE WHEN is_home THEN home_team_id END) AS home_team_id,
                    MAX(CASE WHEN is_home THEN away_team_id END) AS away_team_id,
                    MAX(CASE WHEN is_home THEN team_name END) AS home_team_name,
                    MAX(CASE WHEN is_home THEN opponent_team_name END) AS away_team_name,
                    MAX(CASE WHEN is_home THEN team_score END) AS home_team_score,
                    MAX(CASE WHEN is_home THEN opponent_score END) AS away_team_score
                FROM team_match_base
                GROUP BY match_id
            ),
            match_results AS (
                SELECT
                    home_team_id AS team_id,
                    home_team_name AS team_name,
                    home_team_score AS goals_for,
                    away_team_score AS goals_against,
                    CASE
                        WHEN home_team_score > away_team_score THEN 3
                        WHEN home_team_score = away_team_score THEN 1
                        ELSE 0
                    END AS points
                FROM one_row_per_match

                UNION ALL

                SELECT
                    away_team_id AS team_id,
                    away_team_name AS team_name,
                    away_team_score AS goals_for,
                    home_team_score AS goals_against,
                    CASE
                        WHEN away_team_score > home_team_score THEN 3
                        WHEN away_team_score = home_team_score THEN 1
                        ELSE 0
                    END AS points
                FROM one_row_per_match
            ),
            season_table AS (
                SELECT
                    team_id,
                    team_name,
                    SUM(points) AS points,
                    SUM(goals_for) AS goals_for,
                    SUM(goals_against) AS goals_against,
                    SUM(goals_for) - SUM(goals_against) AS goal_difference
                FROM match_results
                GROUP BY team_id, team_name
            )
            SELECT
                team_id,
                team_name,
                points,
                goals_for,
                goals_against,
                goal_difference,
                ROW_NUMBER() OVER (
                    ORDER BY
                        points DESC,
                        goal_difference DESC,
                        goals_for DESC,
                        team_name ASC
                ) AS final_rank,
                CASE
                    WHEN team_name IN (
                        'Arsenal',
                        'Chelsea',
                        'Liverpool',
                        'Manchester City',
                        'Manchester United',
                        'Tottenham Hotspur'
                    ) THEN TRUE
                    ELSE FALSE
                END AS is_big6
            FROM season_table
        """)

    def query_df(self, sql: str, params: list[Any] | None = None):
        if params is None:
            return self.con.execute(sql).df()
        return self.con.execute(sql, params).df()

    def query_dicts(self, sql: str, params: list[Any] | None = None) -> list[dict]:
        df = self.query_df(sql, params)
        return df.to_dict(orient="records")

    def _validate_metric(self, metric: str, allowed_metrics: set[str]) -> None:
        if metric not in allowed_metrics:
            raise ValueError(
                f"Metric '{metric}' is not allowed for this query. "
                f"Allowed: {sorted(allowed_metrics)}"
            )

    def _build_rank_filters(
        self,
        alias: str,
        params: list[Any],
        opponent_rank_lte: int | None = None,
        opponent_rank_gte: int | None = None,
        opponent_rank_between: tuple[int, int] | None = None,
        opponent_is_big6: bool | None = None,
    ) -> list[str]:
        where = []

        if opponent_rank_lte is not None:
            where.append(f"{alias}.final_rank <= ?")
            params.append(opponent_rank_lte)

        if opponent_rank_gte is not None:
            where.append(f"{alias}.final_rank >= ?")
            params.append(opponent_rank_gte)

        if opponent_rank_between is not None:
            a, b = opponent_rank_between
            lo, hi = min(a, b), max(a, b)
            where.append(f"{alias}.final_rank BETWEEN ? AND ?")
            params.extend([lo, hi])

        if opponent_is_big6 is not None:
            where.append(f"{alias}.is_big6 = ?")
            params.append(opponent_is_big6)

        return where

    def _summary_value_expr(self, metric: str, agg: str, alias: str) -> str:
        if agg == "sum":
            return f"SUM({alias}.{metric})"
        if agg == "avg":
            return f"AVG({alias}.{metric})"
        if agg == "max":
            return f"MAX({alias}.{metric})"
        if agg == "min":
            return f"MIN({alias}.{metric})"
        raise ValueError(f"Unsupported agg '{agg}' for summary scope")

    def _match_value_expr(self, metric: str, agg: str, alias: str) -> str:
        if agg == "sum":
            return f"SUM({alias}.{metric})"
        if agg == "avg":
            return f"AVG({alias}.{metric})"
        if agg == "max":
            return f"MAX({alias}.{metric})"
        if agg == "min":
            return f"MIN({alias}.{metric})"
        if agg == "count_matches_positive":
            return f"SUM(CASE WHEN {alias}.{metric} > 0 THEN 1 ELSE 0 END)"
        if agg == "points":
            return f"SUM({alias}.points)"
        if agg == "wins":
            return f"SUM(CASE WHEN {alias}.is_win THEN 1 ELSE 0 END)"
        if agg == "goal_difference":
            return f"SUM({alias}.goal_difference)"
        raise ValueError(f"Unsupported agg '{agg}'")

    def query_summary_context(
        self,
        scope: str,
        metric: str,
        descending: bool = True,
        entity_type: str | None = None,
        player_name: str | None = None,
        team_name: str | None = None,
        position: str | None = None,
        age_lt: int | None = None,
        min_minutes: int | None = None,
        min_matches: int | None = None,
        rank_position: int | None = None,
        top_n: int = 1,
    ) -> list[dict]:
        if scope not in {"players_summary", "teams_summary"}:
            raise ValueError(f"Unsupported summary scope: {scope}")

        if scope == "players_summary":
            alias = "ps"
            value_expr = self._summary_value_expr(metric, "sum", alias)
            params: list[Any] = []
            where = []

            if player_name is not None:
                where.append("lower(ps.short_name) = lower(?)")
                params.append(player_name)

            if team_name is not None:
                where.append("lower(ps.team_name) = lower(?)")
                params.append(team_name)

            if position is not None:
                where.append("lower(ps.main_position) LIKE lower(?)")
                params.append(f"%{position}%")

            if age_lt is not None:
                where.append("""
                    CAST(((20240801 - CAST(replace(ps.birth_date, '-', '') AS BIGINT)) / 10000) AS BIGINT) < ?
                """)
                params.append(age_lt)

            if min_minutes is not None:
                where.append("ps.total_minutes >= ?")
                params.append(min_minutes)

            if min_matches is not None:
                where.append("ps.matches_played >= ?")
                params.append(min_matches)

            where_sql = ""
            if where:
                where_sql = "WHERE " + " AND ".join(where)

            order_dir = "DESC" if descending else "ASC"

            if metric == "total_minutes":
                minutes_order = "DESC"
            elif metric in NEGATIVE_METRICS:
                minutes_order = "DESC" if descending else "ASC"
            else:
                minutes_order = "ASC" if descending else "DESC"
            sql = f"""
            SELECT
                ps.short_name,
                ps.team_name,
                ps.main_position,
                CAST(((20240801 - CAST(replace(ps.birth_date, '-', '') AS BIGINT)) / 10000) AS BIGINT) AS age,
                ps.total_minutes,
                ps.matches_played,
                {value_expr} AS metric_value
            FROM players_summary ps
            {where_sql}
            GROUP BY
                ps.player_id,
                ps.short_name,
                ps.team_name,
                ps.main_position,
                age,
                ps.total_minutes,
                ps.matches_played
            ORDER BY
                metric_value {order_dir},
                ps.total_minutes {minutes_order},
                ps.short_name ASC
            """
            rows = self.query_dicts(sql, params)

        else:
            alias = "ts"
            value_expr = self._summary_value_expr(metric, "sum", alias)
            params = []
            where = []

            if team_name is not None:
                where.append("lower(ts.team_name) = lower(?)")
                params.append(team_name)

            where_sql = ""
            if where:
                where_sql = "WHERE " + " AND ".join(where)

            order_dir = "DESC" if descending else "ASC"
            sql = f"""
            SELECT
                ts.team_name,
                {value_expr} AS metric_value
            FROM teams_summary ts
            {where_sql}
            GROUP BY
                ts.team_id,
                ts.team_name
            ORDER BY
                metric_value {order_dir},
                ts.team_name ASC
            """
            rows = self.query_dicts(sql, params)

        if rank_position is not None:
            idx = rank_position - 1
            if 0 <= idx < len(rows):
                return [rows[idx]]
            return []

        return rows[:top_n]

    def query_player_match_context(
        self,
        metric: str,
        agg: str = "sum",
        player_name: str | None = None,
        team_name: str | None = None,
        is_home: bool | None = None,
        opponent_team_name: str | None = None,
        opponent_rank_lte: int | None = None,
        opponent_rank_gte: int | None = None,
        opponent_rank_between: tuple[int, int] | None = None,
        opponent_is_big6: bool | None = None,
        matchday_start: int | None = None,
        matchday_end: int | None = None,
        match_conditions: list[dict] | None = None,
        limit: int = 1,
    ) -> list[dict]:
        self._validate_metric(metric, PLAYER_MATCH_ALLOWED_METRICS)

        params: list[Any] = []
        where = []

        if player_name is not None:
            where.append("lower(pms.short_name) = lower(?)")
            params.append(player_name)

        if team_name is not None:
            where.append("lower(pms.team_name) = lower(?)")
            params.append(team_name)

        if is_home is not None:
            where.append("pms.is_home = ?")
            params.append(is_home)

        if opponent_team_name is not None:
            where.append("lower(pms.opponent_team_name) = lower(?)")
            params.append(opponent_team_name)

        where += self._build_rank_filters(
            alias="opp",
            params=params,
            opponent_rank_lte=opponent_rank_lte,
            opponent_rank_gte=opponent_rank_gte,
            opponent_rank_between=opponent_rank_between,
            opponent_is_big6=opponent_is_big6,
        )

        if matchday_start is not None:
            where.append("pms.gameweek >= ?")
            params.append(matchday_start)

        if matchday_end is not None:
            where.append("pms.gameweek <= ?")
            params.append(matchday_end)

        allowed_ops = {">", ">=", "<", "<=", "=", "!="}

        if match_conditions:
            for cond in match_conditions:
                cond_metric = cond["metric"]
                cond_op = cond["operator"]
                cond_value = cond["value"]

                self._validate_metric(cond_metric, PLAYER_MATCH_ALLOWED_METRICS)

                if cond_op not in allowed_ops:
                    raise ValueError(f"Unsupported operator '{cond_op}' in match_conditions")

                where.append(f"pms.{cond_metric} {cond_op} ?")
                params.append(cond_value)

        where_sql = ""
        if where:
            where_sql = "WHERE " + " AND ".join(where)

        value_expr = self._match_value_expr(metric=metric, agg=agg, alias="pms")

        sql = f"""
        SELECT
            pms.short_name,
            pms.team_name,
            {value_expr} AS metric_value
        FROM player_match_stats pms
        LEFT JOIN league_table opp
            ON pms.opponent_team_id = opp.team_id
        {where_sql}
        GROUP BY
            pms.player_id,
            pms.short_name,
            pms.team_name
        ORDER BY
            metric_value DESC,
            pms.short_name ASC
        LIMIT {int(limit)}
        """

        return self.query_dicts(sql, params)

    def query_player_match_event_context(
        self,
        metric: str,
        agg: str = "sum",
        player_name: str | None = None,
        team_name: str | None = None,
        position: str | None = None,
        is_home: bool | None = None,
        opponent_team_name: str | None = None,
        opponent_rank_lte: int | None = None,
        opponent_rank_gte: int | None = None,
        opponent_rank_between: tuple[int, int] | None = None,
        opponent_is_big6: bool | None = None,
        matchday_start: int | None = None,
        matchday_end: int | None = None,
        limit: int = 1,
    ) -> list[dict]:
        self._validate_metric(metric, PLAYER_MATCH_EVENT_ALLOWED_METRICS)

        params: list[Any] = []
        where = []

        if player_name is not None:
            where.append("lower(pmes.short_name) = lower(?)")
            params.append(player_name)

        if team_name is not None:
            where.append("lower(pmes.team_name) = lower(?)")
            params.append(team_name)

        if position is not None:
            where.append("lower(ps.main_position) LIKE lower(?)")
            params.append(f"%{position}%")

        if is_home is not None:
            where.append("pmes.is_home = ?")
            params.append(is_home)

        if opponent_team_name is not None:
            where.append("lower(pmes.opponent_team_name) = lower(?)")
            params.append(opponent_team_name)

        where += self._build_rank_filters(
            alias="opp",
            params=params,
            opponent_rank_lte=opponent_rank_lte,
            opponent_rank_gte=opponent_rank_gte,
            opponent_rank_between=opponent_rank_between,
            opponent_is_big6=opponent_is_big6,
        )

        if matchday_start is not None:
            where.append("pmes.gameweek >= ?")
            params.append(matchday_start)

        if matchday_end is not None:
            where.append("pmes.gameweek <= ?")
            params.append(matchday_end)

        where_sql = ""
        if where:
            where_sql = "WHERE " + " AND ".join(where)

        value_expr = self._match_value_expr(metric=metric, agg=agg, alias="pmes")

        sql = f"""
        SELECT
            pmes.short_name,
            pmes.team_name,
            {value_expr} AS metric_value
        FROM player_match_event_stats pmes
        LEFT JOIN league_table opp
            ON pmes.opponent_team_id = opp.team_id
        LEFT JOIN players_summary ps
            ON pmes.short_name = ps.short_name
           AND pmes.team_name = ps.team_name
        {where_sql}
        GROUP BY
            pmes.player_id,
            pmes.short_name,
            pmes.team_name
        ORDER BY
            metric_value DESC,
            pmes.short_name ASC
        LIMIT {int(limit)}
        """

        return self.query_dicts(sql, params)

    def query_team_match_context(
        self,
        metric: str,
        agg: str = "sum",
        team_name: str | None = None,
        is_home: bool | None = None,
        opponent_team_name: str | None = None,
        opponent_rank_lte: int | None = None,
        opponent_rank_gte: int | None = None,
        opponent_rank_between: tuple[int, int] | None = None,
        opponent_is_big6: bool | None = None,
        matchday_start: int | None = None,
        matchday_end: int | None = None,
        limit: int = 1,
    ) -> list[dict]:
        self._validate_metric(metric, TEAM_MATCH_ALLOWED_METRICS)

        params: list[Any] = []
        where = []

        if team_name is not None:
            where.append("lower(tms.team_name) = lower(?)")
            params.append(team_name)

        if is_home is not None:
            where.append("tms.is_home = ?")
            params.append(is_home)

        if opponent_team_name is not None:
            where.append("lower(tms.opponent_team_name) = lower(?)")
            params.append(opponent_team_name)

        where += self._build_rank_filters(
            alias="opp",
            params=params,
            opponent_rank_lte=opponent_rank_lte,
            opponent_rank_gte=opponent_rank_gte,
            opponent_rank_between=opponent_rank_between,
            opponent_is_big6=opponent_is_big6,
        )

        if matchday_start is not None:
            where.append("tms.gameweek >= ?")
            params.append(matchday_start)

        if matchday_end is not None:
            where.append("tms.gameweek <= ?")
            params.append(matchday_end)

        where_sql = ""
        if where:
            where_sql = "WHERE " + " AND ".join(where)

        value_expr = self._match_value_expr(metric=metric, agg=agg, alias="tms")

        sql = f"""
        SELECT
            tms.team_name,
            {value_expr} AS metric_value
        FROM team_match_stats tms
        LEFT JOIN league_table opp
            ON tms.opponent_team_id = opp.team_id
        {where_sql}
        GROUP BY
            tms.team_id,
            tms.team_name
        ORDER BY
            metric_value DESC,
            tms.team_name ASC
        LIMIT {int(limit)}
        """

        return self.query_dicts(sql, params)

    def table_counts(self) -> dict:
        sql_players_summary = "SELECT COUNT(*) AS n FROM players_summary"
        sql_teams_summary = "SELECT COUNT(*) AS n FROM teams_summary"
        sql_player_match = "SELECT COUNT(*) AS n FROM player_match_stats"
        sql_player_match_event = "SELECT COUNT(*) AS n FROM player_match_event_stats"
        sql_team_match = "SELECT COUNT(*) AS n FROM team_match_stats"

        return {
            "players_summary": self.query_dicts(sql_players_summary)[0]["n"],
            "teams_summary": self.query_dicts(sql_teams_summary)[0]["n"],
            "player_match_stats": self.query_dicts(sql_player_match)[0]["n"],
            "player_match_event_stats": self.query_dicts(sql_player_match_event)[0]["n"],
            "team_match_stats": self.query_dicts(sql_team_match)[0]["n"],
        }
