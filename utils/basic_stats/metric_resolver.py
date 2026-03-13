import re


class MetricResolver:
    def __init__(self, player_columns: list[str], team_columns: list[str]):
        self.player_columns = player_columns
        self.team_columns = team_columns

        self.aliases = {
            "goals": "total_goals",
            "assists": "total_assists",
            "own goals": "total_own_goals",
            "own goals received": "total_own_goals",
            "yellow cards": "total_yellow_cards",
            "red cards": "total_red_cards",
            "goal contributions": "goal_contributions",
            "minutes": "total_minutes",

            "progressive passes": "progressive_passes",
            "progressive passing": "progressive_passes",
            "progressive passers": "progressive_passes",

            "progressive carries": "progressive_carries",
            "carry meters": "carry_meters_gained",
            "carry meters gained": "carry_meters_gained",

            "long passes": "long_passes",
            "forward passes": "forward_passes",
            "back passes": "back_passes",
            "backwards passes": "back_passes",
            "play more backwards": "back_passes",
            "more backwards": "back_passes",

            "through passes": "through_passes",
            "smart passes": "smart_passes",
            "passes to final third": "passes_to_final_third",
            "final third passes": "passes_to_final_third",
            "passes to box": "passes_to_box",
            "key passes": "key_passes",
            "crosses": "crosses",
            "passes under pressure": "passes_under_pressure",

            "shots": "shots",
            "shots on target": "shots_on_target",
            "xg": "xg_total",

            "interceptions": "interceptions",
            "recoveries": "recoveries",

            "fouls committed": "fouls_committed",
            "commit more fouls": "fouls_committed",
            "commits more fouls": "fouls_committed",
            "fouls suffered": "fouls_suffered",

            "ball losses": "ball_losses",

            "duels": "duels",
            "defensive duels": "defensive_duels",
            "offensive duels": "offensive_duels",
            "aerial duels": "aerial_duels",
            "aerial duels won": "aerial_duels_won",
            "aerial duel win percentage": "aerial_duel_won_pct",

            "dribbles": "dribbles_attempted",
            "dribbles attempted": "dribbles_attempted",
            "dribbles won": "dribbles_won",
            "dribble success": "dribble_success_pct",

            "progressive runs": "progressive_runs",
            "shot assists": "shot_assists",
            "touches in box": "touches_in_box",
            "offsides": "offsides",
            "clearances": "clearances",
            "goalkeeper exits": "goalkeeper_exits",
            "shots against": "shots_against",
            "saves": "saves",
            "reflex saves": "reflex_saves",

            "goals against": "total_goals_against",
            "goals conceded": "total_goals_against",
            "conceded goals": "total_goals_against",
            "concedes the most goals": "total_goals_against",
            "concedes the fewest goals": "total_goals_against",

            "successful passes percentage": "pass_accuracy_pct",
            "percentage of successful passes": "pass_accuracy_pct",
            "greatest percentage of successful passes": "pass_accuracy_pct",
            "highest percentage of successful passes": "pass_accuracy_pct",
            "successful passes": "pass_accuracy_pct",
            "pass completion": "pass_accuracy_pct",
            "pass completion percentage": "pass_accuracy_pct",
            "pass accuracy": "pass_accuracy_pct",

            "average pass length": "avg_pass_length",
        }

    def resolve(self, question: str, source: str = "players") -> str | None:
        columns = self.player_columns if source == "players" else self.team_columns
        q = question.lower()

        if source == "teams":
            if ("concede" in q or "concedes" in q or "conceded" in q) and "goal" in q:
                return "total_goals_against"

        if "successful passes" in q or "pass completion" in q or "pass accuracy" in q:
            return "pass_accuracy_pct"

        if "shots on target" in q:
            return "shots_on_target"

        if "backwards" in q or "back passes" in q:
            return "back_passes"

        if "commit" in q and "foul" in q:
            return "fouls_committed"

        concept = self._find_concept(q)
        if concept is None:
            return None

        return self._resolve_column_from_concept(concept, columns)

    def _find_concept(self, q: str) -> str | None:
        for alias, concept in sorted(self.aliases.items(), key=lambda x: len(x[0]), reverse=True):
            if alias in q:
                return concept
        return None

    def _resolve_column_from_concept(self, concept: str, columns: list[str]) -> str | None:
        if concept in columns:
            return concept

        raw_candidates = [c for c in columns if c == concept or c.startswith(f"{concept}_")]
        p90_candidates = [c for c in columns if c == f"{concept}_p90"]
        zscore_candidates = [c for c in columns if c == f"{concept}_zscore" or c == f"{concept}_p90_zscore"]

        if raw_candidates:
            exact = [c for c in raw_candidates if c == concept]
            if exact:
                return exact[0]
            return raw_candidates[0]

        if p90_candidates:
            return p90_candidates[0]

        if zscore_candidates:
            return zscore_candidates[0]

        fuzzy = [c for c in columns if concept in c]
        if fuzzy:
            return fuzzy[0]

        return None