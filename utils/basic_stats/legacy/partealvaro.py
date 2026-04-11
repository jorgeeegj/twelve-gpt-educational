import json
from datetime import datetime

import numpy as np
import pandas as pd

players = pd.read_parquet("output/player_full_stats.parquet")
teams = pd.read_parquet("output/team_full_stats.parquet")

# Calcular edad desde birth_date
SEASON_START = datetime(2024, 8, 1)
players["age"] = players["birth_date"].apply(
    lambda x: (SEASON_START - pd.to_datetime(x)).days // 365 if pd.notnull(x) else None
)

# Filtros reutilizables
p10 = players[players["matches_played"] >= 10]
mids = players[players["main_position"].str.contains("mid|CM|DM|AM", case=False, na=False)]
fwds = players[
    players["main_position"].str.contains("FW|ST|CF|LW|RW|Winger|Forward", case=False, na=False)
]
defs = players[players["main_position"].str.contains("CB|LB|RB|WB|Back|Def", case=False, na=False)]
u23 = players[(players["age"].notnull()) & (players["age"] < 23) & (players["matches_played"] >= 5)]


def top_player(df, metric, cols=None):
    cols = cols or ["short_name", "team_name", metric]
    row = df.nlargest(1, metric)[cols].iloc[0]
    return {
        c: (round(float(row[c]), 2) if isinstance(row[c], (float, np.floating)) else row[c])
        for c in cols
    }


def top_team(df, metric, cols=None):
    cols = cols or ["team_name", metric]
    row = df.nlargest(1, metric)[cols].iloc[0]
    return {
        c: (round(float(row[c]), 2) if isinstance(row[c], (float, np.floating)) else row[c])
        for c in cols
    }


def bot_team(df, metric, cols=None):
    cols = cols or ["team_name", metric]
    row = df.nsmallest(1, metric)[cols].iloc[0]
    return {
        c: (round(float(row[c]), 2) if isinstance(row[c], (float, np.floating)) else row[c])
        for c in cols
    }


benchmark = [
    # ── JUGADORES BÁSICO ──────────────────────────────────────
    {
        "id": "Q01",
        "category": "player_basic",
        "question": "Who has scored the most goals this season?",
        "answer": top_player(players, "total_goals"),
    },
    {
        "id": "Q02",
        "category": "player_basic",
        "question": "Who has the most assists this season?",
        "answer": top_player(players, "total_assists"),
    },
    {
        "id": "Q03",
        "category": "player_basic",
        "question": "Which player has played the most minutes?",
        "answer": top_player(players, "total_minutes"),
    },
    {
        "id": "Q04",
        "category": "player_basic",
        "question": "Who has received the most yellow cards?",
        "answer": top_player(players, "total_yellow_cards"),
    },
    {
        "id": "Q05",
        "category": "player_basic",
        "question": "Which player has the best goals per 90 minutes (minimum 10 appearances)?",
        "answer": top_player(p10, "total_goals_p90"),
    },
    # ── EQUIPOS BÁSICO ────────────────────────────────────────
    {
        "id": "Q06",
        "category": "team_basic",
        "question": "Which team has scored the most goals?",
        "answer": top_team(teams, "total_goals"),
    },
    {
        "id": "Q07",
        "category": "team_basic",
        "question": "Which team has conceded the fewest goals?",
        "answer": bot_team(teams, "total_goals_against"),
    },
    {
        "id": "Q08",
        "category": "team_basic",
        "question": "Which team wins the most aerial duels?",
        "answer": top_team(teams, "aerial_duels_won"),
    },
    {
        "id": "Q09",
        "category": "team_basic",
        "question": "Which team has the most accurate passing?",
        "answer": top_team(teams, "pass_accuracy_pct"),
    },
    {
        "id": "Q10",
        "category": "team_basic",
        "question": "Which team provokes the most offsides?",
        "answer": top_team(teams, "offsides"),
    },
    # ── JUGADORES AVANZADO ────────────────────────────────────
    {
        "id": "Q11",
        "category": "player_advanced",
        "question": "Which midfielder has the most progressive passes per 90?",
        "answer": top_player(mids, "progressive_passes_p90"),
    },
    {
        "id": "Q12",
        "category": "player_advanced",
        "question": "Which player has the highest dribble success rate (minimum 10 appearances)?",
        "answer": top_player(p10, "dribble_success_pct"),
    },
    {
        "id": "Q13",
        "category": "player_advanced",
        "question": "Which forward has the most shots on target per 90?",
        "answer": top_player(fwds, "shots_on_target_p90"),
    },
    {
        "id": "Q14",
        "category": "player_advanced",
        "question": "Which player makes the most recoveries per 90?",
        "answer": top_player(players, "recoveries_p90"),
    },
    {
        "id": "Q15",
        "category": "player_advanced",
        "question": "Which defender wins the most aerial duels per 90?",
        "answer": top_player(defs, "aerial_duels_won_p90"),
    },
    # ── FILTRADAS ─────────────────────────────────────────────
    {
        "id": "Q16",
        "category": "player_filtered",
        "question": "Which player under 23 has scored the most goals?",
        "answer": top_player(u23, "total_goals", ["short_name", "team_name", "age", "total_goals"]),
    },
    {
        "id": "Q17",
        "category": "player_filtered",
        "question": "Which midfielder has the best pass accuracy?",
        "answer": top_player(mids, "pass_accuracy_pct"),
    },
    {
        "id": "Q18",
        "category": "player_filtered",
        "question": "Which forward has the most touches in the box per 90?",
        "answer": top_player(fwds, "touches_in_box_p90"),
    },
    # ── EQUIPOS AVANZADO ──────────────────────────────────────
    {
        "id": "Q19",
        "category": "team_advanced",
        "question": "Which team has the most progressive passes per 90?",
        "answer": top_team(teams, "progressive_passes_p90"),
    },
    {
        "id": "Q20",
        "category": "team_advanced",
        "question": "Which team has the most key passes per 90?",
        "answer": top_team(teams, "key_passes_p90"),
    },
]


# Encoder para tipos numpy
class NpEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return round(float(obj), 2)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super().default(obj)


with open("questions_benchmark_raw.json", "w", encoding="utf-8") as f:
    json.dump(benchmark, f, indent=2, ensure_ascii=False, cls=NpEncoder)

print(f"✅ questions_benchmark.json generado — {len(benchmark)} preguntas\n")
for q in benchmark:
    print(f"{q['id']} [{q['category']}]")
    print(f"  Q: {q['question']}")
    print(f"  A: {q['answer']}")
    print()
