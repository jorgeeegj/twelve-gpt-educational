import json
from pathlib import Path

import pandas as pd
import streamlit as st

from utils.page_components import add_common_page_elements
from utils.basic_stats.core.agent import BasicStatsAgent


sidebar_container = add_common_page_elements()

st.header("Basic Stats Analyst")

st.write(
    """
Ask factual questions about players, teams, metrics and qualities.
"""
)

st.markdown(
    """
**Examples**

**Definitions**
- What is Breaking the Lines?

**Players**
- Who scored the most goals?
- Which player has played the most minutes?
- Which midfielder has the most progressive passes per 90?

**Teams**
- Which team has scored the most goals?
- Which team wins the most aerial duels?
- Which team has the most accurate passing?

**Filtered**
- Who are the best midfielders under 23 with progressive passing?
- Which player under 23 has scored the most goals?
"""
)

# ── Benchmark status ──────────────────────────────────────────────
eval_path = Path("docs/evals/latest_eval_results.json")
if eval_path.exists():
    try:
        eval_data = json.loads(eval_path.read_text(encoding="utf8"))
        summary = eval_data.get("summary", {})
        score = summary.get("score", "unknown")
        st.caption(f"Benchmark status: {score}")
    except Exception:
        st.caption("Benchmark status: unavailable")

agent = BasicStatsAgent()

CHAT_KEY = "basic_stats_messages"

if CHAT_KEY not in st.session_state:
    st.session_state[CHAT_KEY] = []

col1, col2, col3 = st.columns([1, 1, 1])

with col1:
    show_debug = st.checkbox("Show debug info", value=False)
with col2:
    show_rows_table = st.checkbox("Show result rows table", value=True)
with col3:
    if st.button("Clear chat"):
        st.session_state[CHAT_KEY] = []
        st.rerun()

# ── Render chat history ───────────────────────────────────────────
for message in st.session_state[CHAT_KEY]:
    with st.chat_message(message["role"]):
        st.write(message["content"])

        debug = message.get("debug", {}) or {}
        rows = debug.get("rows", []) or []

        if message["role"] == "assistant":
            if len(rows) > 1:
                st.info("Tie detected: multiple top rows matched the same best value.")

            if show_rows_table and rows:
                st.dataframe(pd.DataFrame(rows), use_container_width=True)

            if show_debug:
                with st.expander("Debug info", expanded=False):
                    st.markdown("**Engine**")
                    st.write(debug.get("engine"))

                    st.markdown("**Resolved source**")
                    st.write(debug.get("table"))

                    st.markdown("**Resolved metric**")
                    st.write(debug.get("metric"))

                    st.markdown("**Sort direction**")
                    st.write("descending" if debug.get("descending") else "ascending")

                    st.markdown("**Filters**")
                    st.json(debug.get("filters", {}))

                    st.markdown("**Rows**")
                    st.json(rows)

# ── Chat input ────────────────────────────────────────────────────
question = st.chat_input("Ask a question")

if question:
    st.session_state[CHAT_KEY].append({
        "role": "user",
        "content": question,
    })

    try:
        with st.spinner("Analysing..."):
            result = agent.ask(question)

        st.session_state[CHAT_KEY].append({
            "role": "assistant",
            "content": result["content"],
            "debug": result.get("debug", {}),
        })

        st.rerun()

    except Exception as e:
        st.session_state[CHAT_KEY].append({
            "role": "assistant",
            "content": f"Something went wrong: {e}",
            "debug": {"error": repr(e)},
        })
        st.rerun()