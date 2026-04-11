import re


class MetricResolver:
    def __init__(self, player_columns: list[str], team_columns: list[str]):
        self.player_columns = player_columns
        self.team_columns = team_columns

        self.aliases = {
            # GOALS & ASSISTS (longest first)
            "goal contributions": "goal_contributions",
            "goal scorer": "total_goals",
            "top scorer": "total_goals",
            "goals from events": "goals_from_events",
            "assists from events": "assists_from_events",
            "second assists": "second_assists",
            "third assists": "third_assists",
            "goals": "total_goals",
            "scored": "total_goals",
            "assists": "total_assists",
            "own goals received": "total_own_goals",
            "own goals": "total_own_goals",
            # DISCIPLINE
            "yellow cards": "total_yellow_cards",
            "bookings": "total_yellow_cards",
            "red cards": "total_red_cards",
            "sent off": "total_red_cards",
            # TIME PLAYED
            "minutes played": "total_minutes",
            "minutes": "total_minutes",
            "appearances": "matches_played",
            "games played": "matches_played",
            "matches played": "matches_played",
            # PASSING — accuracy (longest first)
            "greatest percentage of successful passes": "pass_accuracy_pct",
            "highest percentage of successful passes": "pass_accuracy_pct",
            "percentage of successful passes": "pass_accuracy_pct",
            "successful passes percentage": "pass_accuracy_pct",
            "pass completion percentage": "pass_accuracy_pct",
            "most accurate passing": "pass_accuracy_pct",
            "successful passes": "pass_accuracy_pct",
            "pass completion": "pass_accuracy_pct",
            "passing accuracy": "pass_accuracy_pct",
            "accurate passing": "pass_accuracy_pct",
            "accurate passes": "pass_accuracy_pct",
            "pass accuracy": "pass_accuracy_pct",
            "average pass length": "avg_pass_length",
            "avg pass length": "avg_pass_length",
            # PASSING — direction & type
            "passes attempted": "passes_attempted",
            "passes accurate": "passes_accurate",
            "passes under pressure": "passes_under_pressure",
            "passes into final third": "passes_to_final_third",
            "passes to final third": "passes_to_final_third",
            "final third passes": "passes_to_final_third",
            "passes into the box": "passes_to_box",
            "passes to box": "passes_to_box",
            "forward passes": "forward_passes",
            "play more backwards": "back_passes",
            "backwards passes": "back_passes",
            "more backwards": "back_passes",
            "back passes": "back_passes",
            "long passes": "long_passes",
            "through passes": "through_passes",
            "smart passes": "smart_passes",
            "chance creation": "key_passes",
            "key passes": "key_passes",
            "crosses": "crosses",
            # PROGRESSIVE PASSING
            "progressive passing": "progressive_passes",
            "progressive passers": "progressive_passes",
            "progressive passes": "progressive_passes",
            # SHOTS
            "shots on target": "shots_on_target",
            "shots on goal": "shots_on_target",
            "on target": "shots_on_target",
            "expected goals": "xg_total",
            "xgoals": "xg_total",
            "shots": "shots",
            "xg": "xg_total",
            # GOALKEEPERS
            "reflex saves": "reflex_saves",
            "shot stopping": "saves",
            "shots against": "shots_against",
            "shots faced": "shots_against",
            "goalkeeper exits": "goalkeeper_exits",
            "sweeper keeper": "goalkeeper_exits",
            "goals let in": "conceded_goals_from_gk_events",
            "save percentage": "saves",
            "saves": "saves",
            # DUELS (longest first)
            "defensive duel win percentage": "defensive_duel_won_pct",
            "offensive duel win percentage": "offensive_duel_won_pct",
            "defensive duel win rate": "defensive_duel_won_pct",
            "offensive duel win rate": "offensive_duel_won_pct",
            "aerial duel win percentage": "aerial_duel_won_pct",
            "aerial duel win rate": "aerial_duel_won_pct",
            "defensive duels won": "defensive_duels_won",
            "offensive duels won": "offensive_duels_won",
            "aerial battles won": "aerial_duels_won",
            "aerial duels won": "aerial_duels_won",
            "headers won": "aerial_duels_won",
            "wins in the air": "aerial_duels_won",
            "aerial battles": "aerial_duels",
            "defensive duels": "defensive_duels",
            "offensive duels": "offensive_duels",
            "aerial duels": "aerial_duels",
            "headers": "aerial_duels",
            "duels": "duels",
            # DRIBBLES
            "dribbles attempted": "dribbles_attempted",
            "dribbles completed": "dribbles_won",
            "dribbles won": "dribbles_won",
            "dribbling success rate": "dribble_success_pct",
            "dribbling success": "dribble_success_pct",
            "dribble success rate": "dribble_success_pct",
            "dribble success": "dribble_success_pct",
            "dribble accuracy": "dribble_success_pct",
            "dribbled past": "dribbled_past_attempts",
            "dribbles": "dribbles_attempted",
            # CARRYING
            "progressive carries": "progressive_carries",
            "carry meters gained": "carry_meters_gained",
            "meters carried": "carry_meters_gained",
            "distance carried": "carry_meters_gained",
            "carry meters": "carry_meters_gained",
            "progressive runs": "progressive_runs",
            "forward runs": "progressive_runs",
            "carries": "carries",
            # RECOVERIES & PRESSING
            "ball recoveries": "recoveries",
            "interceptions": "interceptions",
            "clearances": "clearances",
            "sliding tackles": "sliding_tackles",
            "tackles": "sliding_tackles",
            "recoveries": "recoveries",
            # ATTACKING ACTIONS
            "pre-shot assists": "shot_assists",
            "shot assists": "shot_assists",
            "touches in the box": "touches_in_box",
            "penalty area touches": "touches_in_box",
            "touches in box": "touches_in_box",
            "box touches": "touches_in_box",
            # FOULS
            "fouls committed": "fouls_committed",
            "commit more fouls": "fouls_committed",
            "commits more fouls": "fouls_committed",
            "fouls suffered": "fouls_suffered",
            "fouls won": "fouls_suffered",
            "fouled": "fouls_suffered",
            "fouls": "fouls_committed",
            # LOSSES & OFFSIDE
            "possession lost": "ball_losses",
            "ball losses": "ball_losses",
            "turnovers": "ball_losses",
            "offside traps": "offsides",
            "offsides": "offsides",
            # GOALS CONCEDED (TEAMS — longest first)
            "goals conceded by team": "total_goals_against",
            "concedes the fewest goals": "total_goals_against",
            "concedes the most goals": "total_goals_against",
            "fewest goals conceded": "total_goals_against",
            "best defence": "total_goals_against",
            "goals conceded": "total_goals_against",
            "conceded goals": "total_goals_against",
            "goals against": "total_goals_against",
            # TEAM SPECIFIC
            "shots on target percentage": "shots_on_target_pct",
            "shot accuracy": "shots_on_target_pct",
        }

    def resolve(self, question: str, source: str = "players") -> str | None:
        columns = self.player_columns if source == "players" else self.team_columns
        q = question.lower()
        per_90 = "per 90" in q or "per90" in q or "p90" in q

        if source == "teams":
            if ("concede" in q or "concedes" in q or "conceded" in q) and "goal" in q:
                return "total_goals_against"

        if "successful passes" in q or "pass completion" in q or "pass accuracy" in q:
            return "pass_accuracy_pct"

        if "shots on target" in q:
            col = "shots_on_target_p90" if per_90 else "shots_on_target"
            return col if col in columns else "shots_on_target"

        if "backwards" in q or "back passes" in q:
            return "back_passes"

        if "commit" in q and "foul" in q:
            return "fouls_committed"

        concept = self._find_concept(q)
        if concept is None:
            return None

        if per_90:
            p90_col = f"{concept}_p90"
            if p90_col in columns:
                return p90_col

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
        zscore_candidates = [
            c for c in columns if c == f"{concept}_zscore" or c == f"{concept}_p90_zscore"
        ]

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
