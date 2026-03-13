import re


class IntentRouter:
    def route(self, question: str) -> dict:
        q = question.strip().lower()

        if self._is_definition(q):
            return {"intent": "definition"}

        if self._is_team_query(q):
            if self._is_bottom_query(q):
                return {"intent": "bottom_team_metric"}
            return {"intent": "top_team_metric"}

        if self._is_filtered_player_query(q):
            return {"intent": "filtered_player_metric"}

        if self._is_player_query(q):
            if self._is_bottom_query(q):
                return {"intent": "bottom_player_metric"}
            return {"intent": "top_player_metric"}

        return {"intent": "unknown"}

    def _is_definition(self, q: str) -> bool:
        prefixes = (
            "what is ",
            "how is ",
            "how do you ",
            "what does it mean",
            "why is ",
            "why are ",
            "is ",
        )
        return q.startswith(prefixes)

    def _is_team_query(self, q: str) -> bool:
        team_words = ("team", "teams", "club", "clubs")
        ranking_words = (
            "most", "highest", "best", "top", "lead", "leads",
            "lowest", "fewest", "worst", "least", "concedes",
            "conceded", "concede"
        )
        return any(w in q for w in team_words) and any(w in q for w in ranking_words)

    def _is_player_query(self, q: str) -> bool:
        player_words = ("player", "players", "who is the player", "who scored", "who has")
        ranking_words = (
            "most", "highest", "best", "top", "lead", "leads",
            "lowest", "fewest", "worst", "least", "commit",
            "commits", "played", "play more"
        )
        return any(w in q for w in player_words) or (
            not self._is_team_query(q) and any(w in q for w in ranking_words)
        )

    def _is_filtered_player_query(self, q: str) -> bool:
        filter_markers = (
            "under ",
            "older than ",
            "younger than ",
            "midfielder",
            "midfielders",
            "defender",
            "defenders",
            "forward",
            "forwards",
            "goalkeeper",
            "goalkeepers",
            "with at least ",
            "more than ",
            "less than ",
            "minutes",
        )
        ranking_words = ("best", "top", "highest", "most", "lead", "leads")
        return any(f in q for f in filter_markers) and any(r in q for r in ranking_words)

    def _is_bottom_query(self, q: str) -> bool:
        return any(w in q for w in ("lowest", "fewest", "least", "worst"))