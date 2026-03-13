from utils.basic_stats.knowledge_base import KnowledgeBase
from utils.basic_stats.intent_router import IntentRouter
from utils.basic_stats.query_engine import QueryEngine
from utils.basic_stats.response_generator import ResponseGenerator


class BasicStatsAgent:
    def __init__(self):
        self.kb = KnowledgeBase()
        self.router = IntentRouter()
        self.query_engine = QueryEngine()
        self.response_generator = ResponseGenerator()

    def ask(self, question: str) -> dict:
        route = self.router.route(question)
        intent = route["intent"]

        # 1. Definitions / KB
        if intent == "definition":
            answer = self.kb.find_answer(question)
            if answer:
                return {
                    "type": "text",
                    "content": answer,
                    "debug": {"intent": intent, "source": "knowledge_base"}
                }

        # 2. Team factual queries
        if intent == "top_team_metric":
            query_result = self.query_engine.run_top_team_metric_query(question, descending=True)
            if query_result:
                text = self.response_generator.verbalize_query_result(question, query_result)
                return {
                    "type": "text",
                    "content": text,
                    "debug": {
                        "intent": intent,
                        "source": "teams",
                        "metric": query_result["metric"],
                        "rows": query_result["result_df"].to_dicts(),
                    }
                }

        if intent == "bottom_team_metric":
            query_result = self.query_engine.run_top_team_metric_query(question, descending=False)
            if query_result:
                text = self.response_generator.verbalize_query_result(question, query_result)
                return {
                    "type": "text",
                    "content": text,
                    "debug": {
                        "intent": intent,
                        "source": "teams",
                        "metric": query_result["metric"],
                        "rows": query_result["result_df"].to_dicts(),
                    }
                }

        # 3. Filtered player queries
        if intent == "filtered_player_metric":
            query_result = self.query_engine.run_filtered_player_query(question)
            if query_result:
                text = self.response_generator.verbalize_query_result(question, query_result)
                return {
                    "type": "text",
                    "content": text,
                    "debug": {
                        "intent": intent,
                        "source": "players",
                        "metric": query_result["metric"],
                        "filters": query_result.get("filters", {}),
                        "rows": query_result["result_df"].to_dicts(),
                    }
                }

        # 4. Player factual queries
        if intent == "top_player_metric":
            query_result = self.query_engine.run_top_player_metric_query(question, descending=True)
            if query_result:
                text = self.response_generator.verbalize_query_result(question, query_result)
                return {
                    "type": "text",
                    "content": text,
                    "debug": {
                        "intent": intent,
                        "source": "players",
                        "metric": query_result["metric"],
                        "rows": query_result["result_df"].to_dicts(),
                    }
                }

        if intent == "bottom_player_metric":
            query_result = self.query_engine.run_top_player_metric_query(question, descending=False)
            if query_result:
                text = self.response_generator.verbalize_query_result(question, query_result)
                return {
                    "type": "text",
                    "content": text,
                    "debug": {
                        "intent": intent,
                        "source": "players",
                        "metric": query_result["metric"],
                        "rows": query_result["result_df"].to_dicts(),
                    }
                }

        return {
            "type": "text",
            "content": "I couldn't reliably answer that from the current knowledge base or data queries yet.",
            "debug": {"intent": intent, "source": "fallback_none"}
        }