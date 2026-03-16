import re
import polars as pl
from pathlib import Path

from utils.basic_stats.metric_resolver import MetricResolver


BASE = Path(__file__).resolve().parents[2]
PLAYER_DATA_PATH = BASE / "output" / "player_full_stats.parquet"
TEAM_DATA_PATH = BASE / "output" / "team_full_stats.parquet"


class QueryEngine:
    def __init__(self):
        self.players_df = pl.read_parquet(PLAYER_DATA_PATH)
        self.teams_df = pl.read_parquet(TEAM_DATA_PATH)

        # Derived columns
        if "goal_contributions" not in self.players_df.columns:
            if {"total_goals", "total_assists"}.issubset(set(self.players_df.columns)):
                self.players_df = self.players_df.with_columns(
                    (pl.col("total_goals") + pl.col("total_assists")).alias("goal_contributions")
                )

        if "goal_contributions" not in self.teams_df.columns:
            if {"total_goals", "total_assists"}.issubset(set(self.teams_df.columns)):
                self.teams_df = self.teams_df.with_columns(
                    (pl.col("total_goals") + pl.col("total_assists")).alias("goal_contributions")
                )

        self.metric_resolver = MetricResolver(
            player_columns=self.players_df.columns,
            team_columns=self.teams_df.columns,
        )

    def run_top_player_metric_query(self, question: str, descending: bool = True) -> dict | None:
        metric = self.metric_resolver.resolve(question, source="players")
        if metric is None:
            return None

        n = self._extract_top_n(question, default=1)

        sorted_df = self.players_df.sort(metric, descending=descending, nulls_last=True)
        top_n_df = sorted_df.head(n)
        boundary_val = top_n_df[metric][-1]
        result_df = sorted_df.filter(pl.col(metric) == boundary_val).select(self._safe_player_columns(metric)) if n == 1 else top_n_df.select(self._safe_player_columns(metric))

        return {
            "source": "players",
            "metric": metric,
            "result_df": result_df,
            "question": question,
        }

    def run_top_team_metric_query(self, question: str, descending: bool = True) -> dict | None:
        metric = self.metric_resolver.resolve(question, source="teams")
        if metric is None:
            return None

        n = self._extract_top_n(question, default=1)

        result_df = (
            self.teams_df
            .sort(metric, descending=descending, nulls_last=True)
            .select(self._safe_team_columns(metric))
            .head(n)
        )

        return {
            "source": "teams",
            "metric": metric,
            "result_df": result_df,
            "question": question,
        }

    def run_filtered_player_query(self, question: str) -> dict | None:
        metric = self.metric_resolver.resolve(question, source="players")
        if metric is None:
            return None

        df = self.players_df

        position_value = self._extract_position(question)
        if position_value:
            df = df.filter(pl.col("main_position").str.to_lowercase().str.contains(position_value))

        age_lt = self._extract_under_age(question)
        if age_lt is not None:
            if "birth_date" not in df.columns:
                return None
            df = df.with_columns(
                ((pl.lit(20240801) - pl.col("birth_date").str.replace_all("-", "").cast(pl.Int64)) / 10000)
                .cast(pl.Int64).alias("_age")
            ).filter(pl.col("_age") < age_lt)

        min_minutes = self._extract_min_minutes(question)
        if min_minutes is not None and "total_minutes" in df.columns:
            df = df.filter(pl.col("total_minutes") >= min_minutes)

        n = self._extract_top_n(question, default=5)

        selected_cols = self._safe_player_columns(metric)
        if "_age" in df.columns and "_age" not in selected_cols:
            selected_cols.insert(3, "_age")

        result_df = (
            df
            .sort(metric, descending=True, nulls_last=True)
            .select(selected_cols)
            .head(n)
        )

        return {
            "source": "players",
            "metric": metric,
            "result_df": result_df,
            "question": question,
            "filters": {
                "position": position_value,
                "age_lt": age_lt,
                "min_minutes": min_minutes,
            },
        }

    def _extract_top_n(self, question: str, default: int = 1) -> int:
        q = question.lower()

        patterns = [
            r"\btop\s+(\d+)\b",
            r"\bbest\s+(\d+)\b",
            r"\bthe\s+(\d+)\s+teams\b",
            r"\bthe\s+(\d+)\s+players\b",
            r"\b(\d+)\s+teams\b",
            r"\b(\d+)\s+players\b",
        ]

        for pattern in patterns:
            m = re.search(pattern, q)
            if m:
                return int(m.group(1))

        return default

    def _extract_under_age(self, question: str) -> int | None:
        q = question.lower()

        m = re.search(r"\bunder\s+(\d+)\b", q)
        if m:
            return int(m.group(1))

        m = re.search(r"\byounger than\s+(\d+)\b", q)
        if m:
            return int(m.group(1))

        return None

    def _extract_min_minutes(self, question: str) -> int | None:
        q = question.lower()

        m = re.search(r"\bwith at least\s+(\d+)\s+minutes\b", q)
        if m:
            return int(m.group(1))

        m = re.search(r"\bmore than\s+(\d+)\s+minutes\b", q)
        if m:
            return int(m.group(1))

        return None

    def _extract_position(self, question: str) -> str | None:
        q = question.lower()

        mapping = {
            "attacking midfielder": "attacking midfielder|am|cam",
            "central defender":     "central defender|cb",
            "goalkeepers":          "goalkeeper|gk",
            "goalkeeper":           "goalkeeper|gk",
            "midfielders":          "midfielder|cm|dm|am",
            "midfielder":           "midfielder|cm|dm|am",
            "defenders":            "central defender|full back|cb|lb|rb|wb|back|def",
            "defender":             "central defender|full back|cb|lb|rb|wb|back|def",
            "full back":            "full back|lb|rb|wb",
            "forwards":             "striker|winger|cf|st|lw|rw|forward",
            "forward":              "striker|winger|cf|st|lw|rw|forward",
            "strikers":             "striker|cf|st|forward",
            "striker":              "striker|cf|st|forward",
            "wingers":              "winger|lw|rw",
            "winger":               "winger|lw|rw",
        }

        for key, value in mapping.items():
            if key in q:
                return value

        return None

    def _unique_preserve_order(self, cols: list[str]) -> list[str]:
        seen = set()
        out = []
        for c in cols:
            if c not in seen:
                seen.add(c)
                out.append(c)
        return out

    def _safe_team_columns(self, metric: str) -> list[str]:
        cols = [
            "team_name",
            metric,
            "total_goals",
            "total_goals_against",
        ]
        cols = [c for c in cols if c in self.teams_df.columns]
        return self._unique_preserve_order(cols)

    def _safe_player_columns(self, metric: str) -> list[str]:
        cols = [
            "short_name",
            "team_name",
            "main_position",
            metric,
            "matches_played",
            "total_minutes",
        ]
        cols = [c for c in cols if c in self.players_df.columns]
        return self._unique_preserve_order(cols)