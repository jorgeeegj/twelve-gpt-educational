from pathlib import Path

import streamlit as st
from openai import AzureOpenAI

BASE = Path(__file__).resolve().parents[2]
PLAYER_DATA_PATH = BASE / "output" / "player_full_stats.parquet"
TEAM_DATA_PATH = BASE / "output" / "team_full_stats.parquet"
PROMPTS_DIR = BASE / "src" / "basic_stats" / "prompts"


def get_llm_client() -> AzureOpenAI:
    return AzureOpenAI(
        api_key=st.secrets["GPT_KEY"],
        api_version=st.secrets["GPT_VERSION"],
        azure_endpoint="https://twelve-courses.openai.azure.com",
    )


def get_model() -> str:
    return st.secrets["GPT_CHAT_MODEL"]
