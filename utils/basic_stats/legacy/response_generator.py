import streamlit as st
from openai import AzureOpenAI
import polars as pl

class ResponseGenerator:
    def __init__(self):
        self.client = AzureOpenAI(
            api_key=st.secrets["GPT_KEY"],
            api_version=st.secrets["GPT_VERSION"],
            azure_endpoint="https://twelve-courses.openai.azure.com",
        )
        self.model = st.secrets["GPT_CHAT_MODEL"]

    def verbalize_query_result(self, question: str, query_result: dict) -> str:
        result_df = query_result["result_df"]
        result_df = result_df.with_columns([
        pl.col(c).round(2)
        for c, t in zip(result_df.columns, result_df.dtypes)
        if t in (pl.Float64, pl.Float32)
            ])
        rows = result_df.to_dicts()

        if not rows:
            return "I couldn't find any matching results in the data."

        prompt = f"""
You are a football data analyst.

Answer the user's question using ONLY the provided structured result.
Do not invent numbers.
Do not mention players or teams not present in the result.
Use the exact values from the table.
Round decimals to a maximum of 2 decimal places.
Do not use bullet points.

Formatting rules:
- If the result is about one player, mention the player name, team, metric value, and if available say "in X appearances" rather than "played X matches".
- If the result is about one team, mention the team name and metric value, but do not mention matches played unless explicitly useful.
- If there are multiple rows, write one natural sentence listing them in order.
- Keep the answer concise but complete.

User question:
{question}

Metric used:
{query_result.get("metric")}

Structured result:
{rows}
"""

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You must answer strictly from the provided structured result. "
                        "Never invent facts. Always include the relevant numeric value."
                    )
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )

        return response.choices[0].message.content.strip()