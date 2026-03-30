import json

from utils.basic_stats.core.query_planner import QueryPlanner, _detect_dual_bucket_comparison
from utils.basic_stats.core.llm_query_engine_v2 import _bucket_label, _detect_home_away_comparison, _detect_metric_derived_bucket


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
    # mid-table bucket: opponent_rank_between must be set to [7, 14]
    {"id": "C12", "question": "How many goals has E. Haaland scored against mid-table teams?", "plan": {"metric": "goals", "table_scope": "player_match", "aggregation": "sum", "entity_type": "player"}, "expect_opponent_rank_between": [7, 14]},
    {"id": "C13", "question": "Who scored the most goals against mid table teams?", "plan": {"metric": "goals", "table_scope": "player_match", "aggregation": "sum", "entity_type": "player"}, "expect_opponent_rank_between": [7, 14]},
    # Issue A: "last N gameweeks" must NOT be misread as a bottom-N opponent bucket
    {"id": "C14", "question": "How many goals has Haaland scored in the last 5 gameweeks?", "plan": {"metric": "goals", "table_scope": "player_match", "aggregation": "sum", "entity_type": "player"}, "expect_opponent_rank_gte": None},
    {"id": "C15", "question": "How many goals has E. Haaland scored in the last 3 rounds?", "plan": {"metric": "goals", "table_scope": "player_match", "aggregation": "sum", "entity_type": "player"}, "expect_opponent_rank_gte": None},
    # Temporal window: "last N gameweeks" → concrete matchday_start / matchday_end
    # max_matchday=38, so last 5 → start=34, end=38; last 3 rounds → start=36, end=38
    {"id": "C16", "question": "How many goals has Haaland scored in the last 5 gameweeks?", "plan": {"metric": "goals", "table_scope": "player_match", "aggregation": "sum", "entity_type": "player"}, "expect_matchday_start": 34, "expect_matchday_end": 38, "expect_opponent_rank_gte": None},
    {"id": "C17", "question": "How many goals has Bruno Fernandes scored in the last 3 rounds?", "plan": {"metric": "goals", "table_scope": "player_match", "aggregation": "sum", "entity_type": "player"}, "expect_matchday_start": 36, "expect_matchday_end": 38, "expect_opponent_rank_gte": None},
]


def run_canonicalize_tests():
    planner = QueryPlanner()
    passed = 0

    print("\n" + "=" * 100)
    print("CANONICALIZE UNIT TESTS (no LLM)")
    print("=" * 100)

    for case in CANONICALIZE_CASES:
        plan_in = dict(case["plan"])
        question = case.get("question", "")
        try:
            result = planner._canonicalize_raw_plan(question=question, raw_plan=plan_in)
            ok = True
            errors = []
            if "expect_metric" in case and result.get("metric") != case["expect_metric"]:
                ok = False
                errors.append(f"metric -> expected {case['expect_metric']}, got {result.get('metric')}")
            if "expect_aggregation" in case and result.get("aggregation") != case["expect_aggregation"]:
                ok = False
                errors.append(f"aggregation -> expected {case['expect_aggregation']}, got {result.get('aggregation')}")
            if "expect_opponent_rank_between" in case:
                got = result.get("filters", {}).get("opponent_rank_between")
                if got != case["expect_opponent_rank_between"]:
                    ok = False
                    errors.append(f"filters.opponent_rank_between -> expected {case['expect_opponent_rank_between']}, got {got}")
            if "expect_opponent_rank_gte" in case:
                got = result.get("filters", {}).get("opponent_rank_gte")
                if got != case["expect_opponent_rank_gte"]:
                    ok = False
                    errors.append(f"filters.opponent_rank_gte -> expected {case['expect_opponent_rank_gte']}, got {got}")
            if "expect_matchday_start" in case:
                got = result.get("filters", {}).get("matchday_start")
                if got != case["expect_matchday_start"]:
                    ok = False
                    errors.append(f"filters.matchday_start -> expected {case['expect_matchday_start']}, got {got}")
            if "expect_matchday_end" in case:
                got = result.get("filters", {}).get("matchday_end")
                if got != case["expect_matchday_end"]:
                    ok = False
                    errors.append(f"filters.matchday_end -> expected {case['expect_matchday_end']}, got {got}")

            if ok:
                passed += 1
                print(f"{case['id']}: PASS")
            else:
                print(f"{case['id']}: FAIL - {'; '.join(errors)}")
        except Exception as e:
            print(f"{case['id']}: ERROR - {repr(e)}")

    print(f"\nCANONICALIZE SCORE: {passed}/{len(CANONICALIZE_CASES)}")
    return passed == len(CANONICALIZE_CASES)


DUAL_BUCKET_CASES = [
    # Two-bucket OR: top-N + mid-table
    {
        "id": "D01",
        "question": "Who scored more goals against top 6 teams or mid-table teams?",
        "expect_buckets": [{"opponent_rank_lte": 6}, {"opponent_rank_between": [7, 14]}],
    },
    # Two-bucket OR: mid-table + bottom-N
    {
        "id": "D02",
        "question": "Which player had more assists against mid-table or bottom 5 teams?",
        "expect_buckets": [{"opponent_rank_gte": 16}, {"opponent_rank_between": [7, 14]}],
    },
    # Two-bucket OR: big-six + bottom-N
    {
        "id": "D03",
        "question": "Who scored more against big six or bottom 6 teams?",
        "expect_buckets": [{"opponent_rank_gte": 15}, {"opponent_is_big6": True}],
    },
    # Single bucket — must return None (no comparison)
    {
        "id": "D04",
        "question": "Who scored the most goals against top 6 teams?",
        "expect_buckets": None,
    },
    # No bucket at all — must return None
    {
        "id": "D05",
        "question": "Who scored more goals or assists this season?",
        "expect_buckets": None,
    },
    # top-N + bottom-N
    {
        "id": "D06",
        "question": "Which team won more points against top 4 or bottom 4 teams?",
        "expect_buckets": [{"opponent_rank_lte": 4}, {"opponent_rank_gte": 17}],
    },
]


def run_dual_bucket_tests():
    passed = 0

    print("\n" + "=" * 100)
    print("DUAL-BUCKET DETECTION UNIT TESTS (no LLM)")
    print("=" * 100)

    for case in DUAL_BUCKET_CASES:
        q = case["question"]
        expected = case["expect_buckets"]
        try:
            result = _detect_dual_bucket_comparison(q)
            if expected is None:
                ok = result is None
                err = f"expected None, got {result}" if not ok else ""
            else:
                if result is None:
                    ok = False
                    err = f"expected {expected}, got None"
                else:
                    got_list = list(result)
                    # order-insensitive comparison: each expected bucket must appear in got
                    missing = [b for b in expected if b not in got_list]
                    extra = [b for b in got_list if b not in expected]
                    ok = not missing and not extra
                    err = ""
                    if missing:
                        err += f"missing {missing} "
                    if extra:
                        err += f"unexpected {extra}"

            if ok:
                passed += 1
                print(f"{case['id']}: PASS")
            else:
                print(f"{case['id']}: FAIL - {err.strip()}")
        except Exception as e:
            print(f"{case['id']}: ERROR - {repr(e)}")

    print(f"\nDUAL-BUCKET SCORE: {passed}/{len(DUAL_BUCKET_CASES)}")
    return passed == len(DUAL_BUCKET_CASES)


BUCKET_LABEL_CASES = [
    ({"opponent_rank_lte": 5},  "top 5 teams"),
    ({"opponent_rank_lte": 6},  "top 6 teams"),
    ({"opponent_rank_gte": 16}, "bottom 5 teams"),
    ({"opponent_rank_gte": 11}, "bottom 10 teams"),
    ({"opponent_rank_between": [7, 14]}, "mid-table teams (positions 7–14)"),
    ({"opponent_is_big6": True}, "Big Six teams"),
    ({}, "that group"),
]


def run_bucket_label_tests():
    passed = 0

    print("\n" + "=" * 100)
    print("BUCKET LABEL UNIT TESTS (no LLM)")
    print("=" * 100)

    for bucket, expected in BUCKET_LABEL_CASES:
        result = _bucket_label(bucket)
        ok = result == expected
        if ok:
            passed += 1
            print(f"PASS  {bucket} -> '{result}'")
        else:
            print(f"FAIL  {bucket} -> got '{result}', expected '{expected}'")

    print(f"\nBUCKET LABEL SCORE: {passed}/{len(BUCKET_LABEL_CASES)}")
    return passed == len(BUCKET_LABEL_CASES)


HOME_AWAY_CASES = [
    # Player: away-or-home → both detected
    {
        "id": "H01",
        "question": "Has Mohamed Salah scored more away goals or home goals?",
        "expect": ({"is_home": False}, {"is_home": True}),
    },
    # Team: home-or-away → both detected (order doesn't matter in detection)
    {
        "id": "H02",
        "question": "Has Liverpool scored more goals at home or away?",
        "expect": ({"is_home": False}, {"is_home": True}),
    },
    # Player: reversed phrasing "home or away"
    {
        "id": "H03",
        "question": "Has Bruno scored more away or home goals?",
        "expect": ({"is_home": False}, {"is_home": True}),
    },
    # Single-side: no "or" → must return None
    {
        "id": "H04",
        "question": "How many away goals has Salah scored?",
        "expect": None,
    },
    # No home/away at all → must return None
    {
        "id": "H05",
        "question": "Has Haaland scored more goals against top 5 teams or bottom 5 teams?",
        "expect": None,
    },
    # Rank buckets present alongside home/away → must return None (let dual-bucket handle)
    {
        "id": "H06",
        "question": "Has Haaland scored more away goals against top 6 or bottom 6 teams?",
        "expect": None,
    },
]


def run_home_away_tests():
    passed = 0

    print("\n" + "=" * 100)
    print("HOME-AWAY DETECTION UNIT TESTS (no LLM)")
    print("=" * 100)

    for case in HOME_AWAY_CASES:
        q = case["question"]
        expected = case["expect"]
        try:
            result = _detect_home_away_comparison(q)
            if expected is None:
                ok = result is None
                err = f"expected None, got {result}" if not ok else ""
            else:
                ok = result == expected
                err = f"expected {expected}, got {result}" if not ok else ""

            if ok:
                passed += 1
                print(f"{case['id']}: PASS")
            else:
                print(f"{case['id']}: FAIL - {err}")
        except Exception as e:
            print(f"{case['id']}: ERROR - {repr(e)}")

    print(f"\nHOME-AWAY SCORE: {passed}/{len(HOME_AWAY_CASES)}")
    return passed == len(HOME_AWAY_CASES)


METRIC_BUCKET_CASES = [
    {
        "id": "M01",
        "question": "How many goals has Salah scored against the 3 teams that have conceded the fewest goals?",
        "expect": {"n": 3, "bucket_metric": "total_goals_against", "descending": False, "label": "have conceded the fewest goals"},
    },
    {
        "id": "M02",
        "question": "How many goals has Liverpool conceded against the 3 teams that score the most?",
        "expect": {"n": 3, "bucket_metric": "total_goals", "descending": True, "label": "score the most goals"},
    },
    {
        "id": "M03",
        "question": "How many goals has Haaland scored against the 5 teams that scored the fewest goals?",
        "expect": {"n": 5, "bucket_metric": "total_goals", "descending": False, "label": "have scored the fewest goals"},
    },
    {
        "id": "M04",
        "question": "How many goals has Arsenal scored against the 4 teams that have conceded the most goals?",
        "expect": {"n": 4, "bucket_metric": "total_goals_against", "descending": True, "label": "have conceded the most goals"},
    },
    {
        "id": "M05",
        "question": "Has Haaland scored against the top 5 teams this season?",
        "expect": None,  # fixed rank bucket → guard returns None
    },
    {
        "id": "M06",
        "question": "How many goals has Salah scored against the bottom 6 teams?",
        "expect": None,  # fixed rank bucket → guard returns None
    },
    # shots bucket
    {
        "id": "M07",
        "question": "How many goals has Salah scored against the 3 teams that concede the most shots?",
        "expect": {"n": 3, "bucket_metric": "shots_against", "descending": True, "label": "concede the most shots"},
    },
    {
        "id": "M08",
        "question": "How many assists has Fernandes made against the 3 teams that concede the fewest shots?",
        "expect": {"n": 3, "bucket_metric": "shots_against", "descending": False, "label": "concede the fewest shots"},
    },
    {
        "id": "M09",
        "question": "How many goals has Liverpool conceded against the 4 teams that scored the most shots?",
        "expect": {"n": 4, "bucket_metric": "shots", "descending": True, "label": "score the most shots"},
    },
    {
        "id": "M10",
        "question": "How many goals has Arsenal scored against the 5 teams that have scored the fewest shots?",
        "expect": {"n": 5, "bucket_metric": "shots", "descending": False, "label": "score the fewest shots"},
    },
    # natural-language phrasing widening — shots bucket via take/attempt/allow/face
    {
        "id": "M11",
        "question": "How many goals has Salah scored against the 3 teams that allow the fewest shots?",
        "expect": {"n": 3, "bucket_metric": "shots_against", "descending": False, "label": "concede the fewest shots"},
    },
    {
        "id": "M12",
        "question": "How many goals has Salah scored against the 3 teams that face the fewest shots?",
        "expect": {"n": 3, "bucket_metric": "shots_against", "descending": False, "label": "concede the fewest shots"},
    },
    {
        "id": "M13",
        "question": "How many goals has Brentford conceded against the 4 teams that take the most shots?",
        "expect": {"n": 4, "bucket_metric": "shots", "descending": True, "label": "score the most shots"},
    },
    {
        "id": "M14",
        "question": "How many goals has Brentford conceded against the 4 teams that attempt the most shots?",
        "expect": {"n": 4, "bucket_metric": "shots", "descending": True, "label": "score the most shots"},
    },
    {
        "id": "M15",
        "question": "How many assists has Fernandes made against the 3 teams that allowed the most shots?",
        "expect": {"n": 3, "bucket_metric": "shots_against", "descending": True, "label": "concede the most shots"},
    },
    {
        "id": "M16",
        "question": "How many goals has Haaland scored against the 5 teams that took the fewest shots?",
        "expect": {"n": 5, "bucket_metric": "shots", "descending": False, "label": "score the fewest shots"},
    },
]


def run_metric_bucket_tests():
    passed = 0

    print("\n" + "=" * 100)
    print("METRIC-DERIVED BUCKET DETECTION UNIT TESTS (no LLM)")
    print("=" * 100)

    for case in METRIC_BUCKET_CASES:
        q = case["question"]
        expected = case["expect"]
        try:
            result = _detect_metric_derived_bucket(q)
            if expected is None:
                ok = result is None
                err = f"expected None, got {result}" if not ok else ""
            else:
                ok = result == expected
                err = f"expected {expected}, got {result}" if not ok else ""

            if ok:
                passed += 1
                print(f"{case['id']}: PASS")
            else:
                print(f"{case['id']}: FAIL - {err}")
        except Exception as e:
            print(f"{case['id']}: ERROR - {repr(e)}")

    print(f"\nMETRIC-BUCKET SCORE: {passed}/{len(METRIC_BUCKET_CASES)}")
    return passed == len(METRIC_BUCKET_CASES)


if __name__ == "__main__":
    run_canonicalize_tests()
    print()
    run_dual_bucket_tests()
    print()
    run_bucket_label_tests()
    print()
    run_home_away_tests()
    print()
    run_metric_bucket_tests()
    print()
    main()