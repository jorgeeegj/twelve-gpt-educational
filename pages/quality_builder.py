import os
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

from utils.page_components import add_common_page_elements

sidebar_container = add_common_page_elements()
page_container = st.sidebar.container()
sidebar_container = st.sidebar.container()

st.divider()

st.header("Quality Builder")

st.markdown(
    """
    <style>
    /* Multiselect text color */
    div[data-baseweb="select"] > div {
        color: black !important;
    }

    /* Text input */
    input {
        color: black !important;
    }

    /* Placeholder text */
    input::placeholder {
        color: #dddddd !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.write("Create a custom player quality by selecting metrics and assigning weights.")

# -------------------------
# LOAD DATA
# -------------------------


@st.cache_data
def load_data():

    data_path = Path("output") / "player_full_stats.parquet"

    df = pd.read_parquet(data_path)

    return df


df = load_data()

# -------------------------
# SELECT METRICS
# -------------------------

st.header("Step 1: Select metrics")

st.info(
    """
Metrics must be z-scores (`*_score`).  
All metrics are oriented so **higher = better**.
"""
)

score_columns = [col for col in df.columns if col.endswith("_zscore") and df[col].notna().sum() > 0]
score_columns = sorted(score_columns)

available_metrics = len(score_columns)
available_qualities = len([c for c in df.columns if c.startswith("q_") and c.endswith("_zscore")])

st.caption(f"Available metrics: {available_metrics} | Available qualities: {available_qualities}")

selected_metrics = st.multiselect(
    "Choose z-score metrics",
    score_columns,
    max_selections=10,
    placeholder="Select 3–10 metrics to build the quality",
)

st.write(f"Selected metrics: {len(selected_metrics)}")
# -------------------------
# CORRELATION MATRIX
# -------------------------

if len(selected_metrics) < 2:
    st.info("Select at least 2 metrics to compute correlation.")
else:
    corr = df[selected_metrics].corr()

    fig, ax = plt.subplots(figsize=(6, 5))

    im = ax.imshow(corr, cmap="RdYlGn")

    # labels
    ax.set_xticks(range(len(corr.columns)))
    ax.set_xticklabels(corr.columns, rotation=45, ha="right")

    ax.set_yticks(range(len(corr.columns)))
    ax.set_yticklabels(corr.columns)

    # values inside cells
    for i in range(len(corr.columns)):
        for j in range(len(corr.columns)):
            text = ax.text(j, i, f"{corr.iloc[i, j]:.2f}", ha="center", va="center", color="black")

    fig.colorbar(im)

    st.pyplot(fig)

# -------------------------
# WEIGHTS
# -------------------------

st.header("Step 2: Set metric weights")

weights = {}

for metric in selected_metrics:
    weights[metric] = st.slider(metric, min_value=0.0, max_value=1.0, value=0.2, step=0.05)

# -------------------------
# POSITION FILTER
# -------------------------

st.header("Position filter (for validation)")

positions = sorted(df["main_position"].dropna().unique())

selected_positions = st.multiselect("Filter positions", positions, default=positions)


# -------------------------
# MINUTES FILTER
# -------------------------
st.header("Minutes filter (for validation)")

min_minutes = int(df["total_minutes"].min())
max_minutes = int(df["total_minutes"].max())

minutes_threshold = st.slider(
    "Minimum minutes played", min_value=min_minutes, max_value=max_minutes, value=600, step=50
)


# -------------------------
# QUALITY NAME
# -------------------------

quality_name = st.text_input("Quality name")

compute_quality = st.button("Compute Quality")

# -------------------------
# COMPUTE QUALITY
# -------------------------

if compute_quality:
    if quality_name == "":
        st.error("Please give a name to the quality")
        st.stop()

    if len(weights) == 0:
        st.error("Select metrics first")
        st.stop()

    total_weight = sum(weights.values())

    normalized_weights = {k: v / total_weight for k, v in weights.items()}

    score = 0

    for metric, weight in normalized_weights.items():
        score += df[metric] * weight

    df_preview = df.copy()

    df_preview["preview_quality"] = score

    if selected_positions:
        df_preview = df_preview[df_preview["main_position"].isin(selected_positions)]

    df_preview = df_preview[df_preview["total_minutes"] >= minutes_threshold]

    st.caption(
        f"{len(df_preview)} players after filters (positions + minutes ≥ {minutes_threshold})"
    )

    top_players = df_preview.sort_values("preview_quality", ascending=False).head(25)

    st.subheader("Top 25 players (preview)")

    base_cols = ["short_name", "team_name", "main_position", "preview_quality"]

    metric_cols = selected_metrics

    cols = base_cols + metric_cols

    cols = [c for c in cols if c in df_preview.columns]

    st.dataframe(top_players[cols].sort_values("preview_quality", ascending=False))
# -------------------------
# CREATE QUALITY
# -------------------------

create_quality = st.button("Create Quality")

if create_quality:
    quality_name = quality_name.strip().lower().replace(" ", "_")
    quality_name = f"q_{quality_name}_score"

    df[quality_name] = score

    # -------------------------
    # SAVE YAML
    # -------------------------

    os.makedirs("qualities", exist_ok=True)

    yaml_path = f"qualities/{quality_name}.yaml"

    yaml_content = f"name: {quality_name}\n"
    yaml_content += "normalization: already_zscore\n"
    yaml_content += "metrics:\n"

    for metric, weight in normalized_weights.items():
        yaml_content += f"  {metric}: {weight:.4f}\n"

    with open(yaml_path, "w") as f:
        f.write(yaml_content)

    st.success(f"Saved to {yaml_path}")
