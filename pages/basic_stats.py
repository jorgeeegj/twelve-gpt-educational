import json
from pathlib import Path

import pandas as pd
import streamlit as st

from src.basic_stats.agent import BasicStatsAgent
from utils.page_components import add_common_page_elements

sidebar_container = add_common_page_elements()

st.header("Basic Stats Analyst")

st.write(
    """
Ask factual football questions about players, teams, rankings and contextual statistics.
"""
)

st.markdown(
    """
**Examples**

**Season summary**
- Who has scored the most goals this season?
- Which team has conceded the fewest goals?
- Who is 7th for total minutes played this season?

**Player contextual**
- How many goals has E. Haaland scored against top-6 teams this season?
- Which player has scored the most away goals this season?
- Which Liverpool player scored the most goals between matchdays 25 and 30?

**Event-level**
- Which player made the most key passes between matchdays 25 and 30?
- Which midfielder has played the most progressive passes against top-6 teams this season?
- Which player has the most shot assists against Big Six teams?

**Team contextual**
- Which team won the most points against Big Six teams this season?
- Which team scored the most away goals against top-6 teams this season?
- Which team had the most actions in z3 against Manchester City this season?

**Top N**
- Top 5 players with the most away goals
- Top 4 forwards with the most passes to the box
"""
)

# ── Benchmark status ──────────────────────────────────────────────
eval_candidates = [
    Path("docs/evals/latest_eval_results_v4.json"),
    Path("docs/evals/latest_eval_results.json"),
]

for eval_path in eval_candidates:
    if eval_path.exists():
        try:
            eval_data = json.loads(eval_path.read_text(encoding="utf8"))
            summary = eval_data.get("summary", eval_data.get("SUMMARY", {}))
            score = summary.get("score", "unknown")
            st.caption(f"Benchmark status: {score}")
            break
        except Exception:
            st.caption("Benchmark status: unavailable")
            break

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
            # Mostrar aviso de empate solo si el backend lo marca explícitamente
            if debug.get("is_tie") is True:
                st.info("Tie detected: multiple rows matched the same top value.")

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
                    descending = debug.get("descending")
                    if descending is None:
                        st.write("n/a")
                    else:
                        st.write("descending" if descending else "ascending")

                    st.markdown("**Filters**")
                    st.json(debug.get("filters", {}))

                    st.markdown("**Rows**")
                    st.json(rows)

                    error = debug.get("error")
                    if error:
                        st.markdown("**Error**")
                        st.code(error)

# ── Chat input ────────────────────────────────────────────────────
question = st.chat_input("Ask a question")

if question:
    st.session_state[CHAT_KEY].append(
        {
            "role": "user",
            "content": question,
        }
    )

    try:
        with st.spinner("Analysing..."):
            result = agent.ask(question)

        st.session_state[CHAT_KEY].append(
            {
                "role": "assistant",
                "content": result["content"],
                "debug": result.get("debug", {}),
            }
        )

        st.rerun()

    except Exception as e:
        st.session_state[CHAT_KEY].append(
            {
                "role": "assistant",
                "content": "Sorry, I couldn't answer that question. Enable debug info for details.",
                "debug": {"error": repr(e)},
            }
        )
        st.rerun()
