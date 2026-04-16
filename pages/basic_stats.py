from pathlib import Path

import streamlit as st

from utils.page_components import add_common_page_elements

sidebar_container = add_common_page_elements()

st.header("Basic Stats Analyst")

st.write("Ask factual football questions about players, teams, rankings and contextual statistics.")

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
- Which midfielder has played the most progressive passes against top-6 teams?
- Which player has the most shot assists against Big Six teams?

**Team contextual**
- Which team won the most points against Big Six teams this season?
- Which team scored the most away goals against top-6 teams this season?

**Comparison**
- Has Haaland scored more goals against top-5 or bottom-5 teams?
- Compare Salah and Haaland's goals at home this season
"""
)

from src.basic_stats.agent import BasicStatsAgent


@st.cache_resource
def _get_agent() -> BasicStatsAgent:
    return BasicStatsAgent()


_agent = _get_agent()


def _ask(question: str) -> str:
    return _agent.ask(question)


# ── Benchmark status ──────────────────────────────────────────────
_runs_dir = Path("evals/runs")
if _runs_dir.exists():
    _agent_runs = sorted(
        [d for d in _runs_dir.iterdir() if d.is_dir() and "agent" in d.name],
        reverse=True,
    )
    if _agent_runs:
        import json

        try:
            _summary = json.loads((_agent_runs[0] / "summary.json").read_text(encoding="utf-8"))
            _gates = _summary.get("gates", {})
            _faith = _gates.get("faithfulness", {}).get("score", "?")
            st.caption(
                f"Agent benchmark — faithfulness: {_faith} | run: {_agent_runs[0].name[:19]}"
            )
        except Exception:
            pass

CHAT_KEY = "basic_stats_messages"
if CHAT_KEY not in st.session_state:
    st.session_state[CHAT_KEY] = []

if st.button("Clear chat"):
    st.session_state[CHAT_KEY] = []
    _agent.reset()
    st.rerun()

# ── Render chat history ───────────────────────────────────────────
for message in st.session_state[CHAT_KEY]:
    with st.chat_message(message["role"]):
        st.write(message["content"])

# ── Chat input ────────────────────────────────────────────────────
question = st.chat_input("Ask a question about PL 2024-25")

if question:
    st.session_state[CHAT_KEY].append({"role": "user", "content": question})

    try:
        with st.spinner("Analysing..."):
            answer = _ask(question)

        st.session_state[CHAT_KEY].append({"role": "assistant", "content": answer})
        st.rerun()

    except Exception as e:
        st.session_state[CHAT_KEY].append(
            {
                "role": "assistant",
                "content": f"Sorry, I couldn't answer that. ({type(e).__name__}: {e})",
            }
        )
        st.rerun()
