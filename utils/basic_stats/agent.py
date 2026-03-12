import streamlit as st
from openai import AzureOpenAI

from utils.basic_stats.query_engine import QueryEngine
from utils.basic_stats.verbal_model import VerbalModel


class BasicStatsAgent:

    def __init__(self):

        self.query_engine = QueryEngine()
        self.verbal_model = VerbalModel()

        self.client = AzureOpenAI(
            api_key=st.secrets["GPT_KEY"],
            api_version=st.secrets["GPT_VERSION"],
            azure_endpoint="https://twelve-courses.openai.azure.com"
        )

        self.model = st.secrets["GPT_CHAT_MODEL"]

    def ask(self, question):

        # 1️⃣ Definitional questions

        definition = self.verbal_model.search_definition(question)

        if definition:
            return {"type": "text", "content": definition}

        # 2️⃣ Detect top queries

        top_query = self.query_engine.detect_top_query(question)

        if top_query:

            metric, n = top_query

            result = self.query_engine.top_players_by_metric(metric, n)

            if result is not None:
                return {"type": "table", "content": result}

        # 3️⃣ Example special query

        if "midfield" in question.lower() and "23" in question:

            result = self.query_engine.best_midfielders_u23_progression()

            if result is not None:
                return {"type": "table", "content": result}

        # 4️⃣ Fallback to LLM

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": "You are a football data analyst. Be concise and explain insights clearly."
                },
                {
                    "role": "user",
                    "content": question
                }
            ]
        )

        answer = response.choices[0].message.content

        return {"type": "text", "content": answer}