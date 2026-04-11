from pathlib import Path

import polars as pl

BASE = Path(__file__).resolve().parents[3]
QA_PATH = BASE / "data" / "verbal_model_qa.csv"


class KnowledgeBase:
    def __init__(self):
        self.qa = pl.read_csv(QA_PATH)

    def find_exact_answer(self, question: str) -> str | None:
        q = question.strip().lower()

        for row in self.qa.iter_rows(named=True):
            candidate = str(row["question"]).strip().lower()
            if q == candidate:
                return row["answer"]

        return None

    def find_contained_answer(self, question: str) -> str | None:
        q = question.strip().lower()

        for row in self.qa.iter_rows(named=True):
            candidate = str(row["question"]).strip().lower()
            if candidate in q or q in candidate:
                return row["answer"]

        return None

    def find_answer(self, question: str) -> str | None:
        exact = self.find_exact_answer(question)
        if exact:
            return exact

        return self.find_contained_answer(question)
