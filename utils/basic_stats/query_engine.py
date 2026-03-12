import polars as pl
from pathlib import Path
import re

BASE = Path(__file__).resolve().parents[2]

DATA_PATH = BASE / "output" / "player_full_stats.parquet"


class QueryEngine:

    def __init__(self):
        self.df = pl.read_parquet(DATA_PATH)

    def top_players_by_metric(self, metric, n=10):

        metric = self.resolve_metric(metric)

        if metric is None:
            return None

        result = (
            self.df
            .sort(metric, descending=True)
            .select([
                "short_name",
                "team_name",
                "main_position",
                metric
            ])
            .head(n)
        )

        return result

    def resolve_metric(self, metric_name):

        cols = self.df.columns

        metric_name = metric_name.lower().replace(" ", "_")

        candidates = []

        for col in cols:

            col_lower = col.lower()

            if metric_name in col_lower:
                candidates.append(col)

        if not candidates:
            return None
        ''' Asi podría ser en un determinado momento aunque sería para sacar esos outstanding y que se active cuando se pida la posición
        
        # Prioridad
        for c in candidates:
            if c.endswith("_p90_zscore"):
                return c

        for c in candidates:
            if c.endswith("_p90"):
                return c

        return candidates[0]

        De momento solo la raw metric
        '''
        
        return candidates[0]

    def best_midfielders_u23_progression(self, n=10):

        df = self.df

        if "age" not in df.columns:
            return None

        metric = None

        for col in df.columns:
            if "progressive" in col and "zscore" in col:
                metric = col
                break

        if metric is None:
            return None

        result = (
            df
            .filter(pl.col("main_position").str.contains("Mid"))
            .filter(pl.col("age") < 23)
            .sort(metric, descending=True)
            .select([
                "short_name",
                "team_name",
                "main_position",
                metric
            ])
            .head(n)
        )

        return result

    def detect_top_query(self, question):

        pattern = r"top\s*(\d+)?\s*players?\s*by\s*([a-zA-Z0-9_]+)"

        match = re.search(pattern, question.lower())

        if match:

            n = match.group(1)
            metric = match.group(2)

            if n is None:
                n = 10
            else:
                n = int(n)

            return metric, n

        return None