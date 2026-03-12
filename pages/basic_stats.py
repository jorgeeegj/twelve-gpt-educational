import streamlit as st

from utils.page_components import add_common_page_elements
from utils.basic_stats.agent import BasicStatsAgent


sidebar_container = add_common_page_elements()

st.header("Basic Cuñao Analyst")

st.write(
"""
Ask questions about the dataset.

Examples:

- What is Breaking the Lines?
- Top 10 players by progressive_passes_p90
- Who are the best midfielders under 23 with progressive passing?
"""
)

agent = BasicStatsAgent()

question = st.text_input("Ask a question")

if st.button("Ask"):

    if question:

        with st.spinner("Analysing..."):

            result = agent.ask(question)

        if result["type"] == "text":

            st.write(result["content"])

        if result["type"] == "table":

            st.dataframe(result["content"].to_pandas())