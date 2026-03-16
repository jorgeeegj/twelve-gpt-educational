from utils.basic_stats.core.knowledge_base import KnowledgeBase
from utils.basic_stats.core.llm_query_engine_v2 import LLMQueryEngineV2


class BasicStatsAgent:
    def __init__(self):
        self.kb = KnowledgeBase()
        self.engine = LLMQueryEngineV2()

    def ask(self, question: str) -> dict:
        answer = self.kb.find_answer(question)
        if answer:
            return {
                "type": "text",
                "content": answer,
                "debug": {
                    "engine": "knowledge_base",
                    "table": None,
                    "metric": None,
                    "descending": None,
                    "filters": {},
                    "rows": [],
                    "source": "verbal_model_qa.csv",
                },
            }

        return self.engine.ask(question)