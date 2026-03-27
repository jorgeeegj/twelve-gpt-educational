import json

from utils.basic_stats.core.query_planner import QueryPlanner


TEST_CASES = [
    {
        "id": "P01",
        "question": "Who has scored the most goals this season?",
        "expected": {
            "table_scope": "players_summary",
            "entity_type": "player",
            "metric": "total_goals",
            "aggregation": "sum",
            "ranking_mode": "top_n",
        },
    },
    {
        "id": "P02",
        "question": "Which team has conceded the fewest goals?",
        "expected": {
            "table_scope": "teams_summary",
            "entity_type": "team",
            "metric": "total_goals_against",
            "aggregation": "sum",
            "ranking_mode": "top_n",
        },
    },
    {
        "id": "P03",
        "question": "Who is 7th for total minutes played this season?",
        "expected": {
            "table_scope": "players_summary",
            "entity_type": "player",
            "metric": "total_minutes",
            "aggregation": "sum",
            "ranking_mode": "ordinal",
            "ordinal": 7,
        },
    },
    {
        "id": "P04",
        "question": "Which Liverpool player scored the most goals between matchdays 25 and 30?",
        "expected": {
            "table_scope": "player_match",
            "entity_type": "player",
            "metric": "goals",
            "aggregation": "sum",
            "team_name": "Liverpool",
            "matchday_start": 25,
            "matchday_end": 30,
            "ranking_mode": "top_n",
        },
    },
    {
        "id": "P05",
        "question": "How many goals has E. Haaland scored against top-6 teams this season?",
        "expected": {
            "table_scope": "player_match",
            "entity_type": "player",
            "metric": "goals",
            "aggregation": "sum",
            "player_name": "E. Haaland",
            "opponent_rank_lte": 6,
            "ranking_mode": "entity_value",
        },
    },
    {
        "id": "P06",
        "question": "Which player has scored the most away goals this season?",
        "expected": {
            "table_scope": "player_match",
            "entity_type": "player",
            "metric": "goals",
            "aggregation": "sum",
            "is_home": False,
            "ranking_mode": "top_n",
        },
    },
    {
        "id": "P07",
        "question": "Which midfielder has played the most progressive passes against top-6 teams this season?",
        "expected": {
            "table_scope": "player_match_event",
            "entity_type": "player",
            "metric": "progressive_passes",
            "aggregation": "sum",
            "position": "midfielder",
            "opponent_rank_lte": 6,
            "ranking_mode": "top_n",
        },
    },
    {
        "id": "P08",
        "question": "Which player has the most shot assists against Big Six teams?",
        "expected": {
            "table_scope": "player_match_event",
            "entity_type": "player",
            "metric": "shot_assists",
            "aggregation": "sum",
            "opponent_is_big6": True,
            "ranking_mode": "top_n",
        },
    },
    {
        "id": "P09",
        "question": "Which team won the most points against Big Six teams this season?",
        "expected": {
            "table_scope": "team_match",
            "entity_type": "team",
            "metric": "team_score",
            "aggregation": "points",
            "opponent_is_big6": True,
            "ranking_mode": "top_n",
        },
    },
    {
        "id": "P10",
        "question": "Which team had the most actions in z3 against Manchester City this season?",
        "expected": {
            "table_scope": "team_match",
            "entity_type": "team",
            "metric": "actions_z3",
            "aggregation": "sum",
            "opponent_team_name": "Manchester City",
            "ranking_mode": "top_n",
        },
    },
    {
        "id": "P11",
        "question": "Which player under 23 has scored the most goals?",
        "expected": {
            "table_scope": "players_summary",
            "entity_type": "player",
            "metric": "total_goals",
            "aggregation": "sum",
            "age_lt": 23,
            "ranking_mode": "top_n",
        },
    },
    {
        "id": "P12",
        "question": "Which team scored the most away goals against top-6 teams this season?",
        "expected": {
            "table_scope": "team_match",
            "entity_type": "team",
            "metric": "team_score",
            "aggregation": "sum",
            "is_home": False,
            "opponent_rank_lte": 6,
            "ranking_mode": "top_n",
        },
    },
]


def check_expected(plan_dict: dict, expected: dict) -> list[str]:
    errors = []

    if "table_scope" in expected and plan_dict["table_scope"] != expected["table_scope"]:
        errors.append(f"table_scope -> expected {expected['table_scope']}, got {plan_dict['table_scope']}")

    if "entity_type" in expected and plan_dict["entity_type"] != expected["entity_type"]:
        errors.append(f"entity_type -> expected {expected['entity_type']}, got {plan_dict['entity_type']}")

    if "metric" in expected and plan_dict["metric"] != expected["metric"]:
        errors.append(f"metric -> expected {expected['metric']}, got {plan_dict['metric']}")

    if "aggregation" in expected and plan_dict["aggregation"] != expected["aggregation"]:
        errors.append(f"aggregation -> expected {expected['aggregation']}, got {plan_dict['aggregation']}")

    filters = plan_dict.get("filters", {})
    ranking = plan_dict.get("ranking", {})

    for key in ["team_name", "player_name", "opponent_team_name", "position", "is_home", "opponent_rank_lte", "opponent_is_big6", "matchday_start", "matchday_end", "age_lt"]:
        if key in expected and filters.get(key) != expected[key]:
            errors.append(f"filters.{key} -> expected {expected[key]}, got {filters.get(key)}")

    if "ranking_mode" in expected and ranking.get("mode") != expected["ranking_mode"]:
        errors.append(f"ranking.mode -> expected {expected['ranking_mode']}, got {ranking.get('mode')}")

    if "ordinal" in expected and ranking.get("ordinal") != expected["ordinal"]:
        errors.append(f"ranking.ordinal -> expected {expected['ordinal']}, got {ranking.get('ordinal')}")

    return errors


def main():
    planner = QueryPlanner()
    passed = 0

    for case in TEST_CASES:
        print("=" * 100)
        print(case["id"])
        print(case["question"])

        try:
            plan = planner.resolve(case["question"])
            plan_dict = planner.to_debug_dict(plan)
            print(json.dumps(plan_dict, indent=2, ensure_ascii=False))

            errors = check_expected(plan_dict, case["expected"])
            ok = len(errors) == 0

            if ok:
                passed += 1
                print("PASS: True")
            else:
                print("PASS: False")
                for err in errors:
                    print(" -", err)

        except Exception as e:
            print("PASS: False")
            print("ERROR:", repr(e))

    print("\n" + "#" * 100)
    print(f"PLANNER SCORE: {passed}/{len(TEST_CASES)}")


CANONICALIZE_CASES = [
    # metric alias normalization (no LLM)
    {"id": "C01", "plan": {"metric": "yellow_cards", "table_scope": "players_summary", "aggregation": "sum", "entity_type": "player"}, "expect_metric": "total_yellow_cards"},
    {"id": "C02", "plan": {"metric": "yellow_card", "table_scope": "players_summary", "aggregation": "sum", "entity_type": "player"}, "expect_metric": "total_yellow_cards"},
    {"id": "C03", "plan": {"metric": "goals_per_90", "table_scope": "players_summary", "aggregation": "sum", "entity_type": "player"}, "expect_metric": "total_goals_p90"},
    {"id": "C04", "plan": {"metric": "progressive_passes_per_90", "table_scope": "players_summary", "aggregation": "sum", "entity_type": "player"}, "expect_metric": "progressive_passes_p90"},
    {"id": "C05", "plan": {"metric": "passing_accuracy", "table_scope": "players_summary", "aggregation": "sum", "entity_type": "player"}, "expect_metric": "pass_accuracy_pct"},
    {"id": "C06", "plan": {"metric": "offsides_drawn", "table_scope": "teams_summary", "aggregation": "sum", "entity_type": "team"}, "expect_metric": "offsides"},
    {"id": "C07", "plan": {"metric": "team_score", "table_scope": "teams_summary", "aggregation": "sum", "entity_type": "team"}, "expect_metric": "total_goals"},
    # aggregation canonicalization
    {"id": "C08", "plan": {"metric": "total_goals", "table_scope": "players_summary", "aggregation": "mean", "entity_type": "player"}, "expect_aggregation": "avg"},
    {"id": "C09", "plan": {"metric": "total_goals", "table_scope": "players_summary", "aggregation": "average", "entity_type": "player"}, "expect_aggregation": "avg"},
    # per_90 aggregation: must NOT be converted (leave for legacy fallback)
    {"id": "C10", "plan": {"metric": "recoveries", "table_scope": "players_summary", "aggregation": "per_90", "entity_type": "player"}, "expect_aggregation": "per_90"},
    # scope guard: total_goals must NOT become team_score in teams_summary
    {"id": "C11", "plan": {"metric": "total_goals", "table_scope": "teams_summary", "aggregation": "sum", "entity_type": "team"}, "expect_metric": "total_goals"},
]


def run_canonicalize_tests():
    planner = QueryPlanner()
    passed = 0

    print("\n" + "=" * 100)
    print("CANONICALIZE UNIT TESTS (no LLM)")
    print("=" * 100)

    for case in CANONICALIZE_CASES:
        plan_in = dict(case["plan"])
        try:
            result = planner._canonicalize_raw_plan(question="", raw_plan=plan_in)
            ok = True
            errors = []
            if "expect_metric" in case and result.get("metric") != case["expect_metric"]:
                ok = False
                errors.append(f"metric -> expected {case['expect_metric']}, got {result.get('metric')}")
            if "expect_aggregation" in case and result.get("aggregation") != case["expect_aggregation"]:
                ok = False
                errors.append(f"aggregation -> expected {case['expect_aggregation']}, got {result.get('aggregation')}")

            if ok:
                passed += 1
                print(f"{case['id']}: PASS")
            else:
                print(f"{case['id']}: FAIL - {'; '.join(errors)}")
        except Exception as e:
            print(f"{case['id']}: ERROR - {repr(e)}")

    print(f"\nCANONICALIZE SCORE: {passed}/{len(CANONICALIZE_CASES)}")
    return passed == len(CANONICALIZE_CASES)


if __name__ == "__main__":
    all_ok = run_canonicalize_tests()
    print()
    main()