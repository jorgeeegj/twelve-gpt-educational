import streamlit as st

from utils.page_components import add_common_page_elements
from utils.basic_stats.agent import BasicStatsAgent


sidebar_container = add_common_page_elements()

st.header("Basic Stats Analyst")

st.write(
"""
Ask factual questions about players, teams, metrics and qualities.

Examples:
- What is Breaking the Lines?
- Who scored the most goals?
- Which team has scored the most goals?
- Who are the best midfielders under 23 with progressive passing?
- Which team wins the most aerial duels?
"""
)

agent = BasicStatsAgent()

show_debug = st.checkbox("Show debug info", value=False)

question = st.text_input("Ask a question")

if st.button("Ask") and question:
    with st.spinner("Analysing..."):
        result = agent.ask(question)

    st.write(result["content"])

    if show_debug:
        with st.expander("Debug info", expanded=False):
            st.json(result.get("debug", {}))