from utils.basic_stats.core.duckdb_manager import DuckDBManager

db = DuckDBManager()

print(db.table_counts())

print("TEAM MATCH: most points vs Big Six")
print(
    db.query_team_match_context(
        metric="points",
        agg="points",
        opponent_is_big6=True,
        limit=1,
    )
)

print("TEAM MATCH: most away goals vs top 6")
print(
    db.query_team_match_context(
        metric="team_score",
        agg="sum",
        is_home=False,
        opponent_rank_lte=6,
        limit=1,
    )
)

print("TEAM MATCH: best goal difference between GW25-30")
print(
    db.query_team_match_context(
        metric="goal_difference",
        agg="goal_difference",
        matchday_start=25,
        matchday_end=30,
        limit=1,
    )
)

print("TEAM MATCH: most away wins")
print(
    db.query_team_match_context(
        metric="team_score",
        agg="wins",
        is_home=False,
        limit=1,
    )
)

print("TEAM MATCH: most actions_z3 against Manchester City")
print(
    db.query_team_match_context(
        metric="actions_z3",
        agg="sum",
        opponent_team_name="Manchester City",
        limit=1,
    )
)

db.close()
