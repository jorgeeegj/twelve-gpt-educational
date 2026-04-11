import argparse
import json
import re
import sys
from collections import defaultdict
from copy import deepcopy
from datetime import datetime
from pathlib import Path

sys.path.insert(0, ".")

from utils.basic_stats.core.llm_query_engine_v2 import (
    LLMQueryEngineV2,
    _has_match_context_filters,
    _has_match_level_logic,
    _question_subject_entity,
)

BENCHMARK_PATH = "questions_benchmark_v5.json"
OUTPUT_DIR = Path("docs/evals")

FOCUS_IDS_DEFAULT = [
    "QV4_16",  # under-23 top scorer (fixed)
    "QV4_37",  # most goals vs top-6 (still failing)
    "QV4_38",  # Haaland goals vs top-6 (still failing)
    "QV5_41",  # progressive passes vs top-6 (still failing)
    "QV5_44",  # shot assists vs Big Six EN (fixed)
    "QV5_45",  # shot assists vs Big Six ES (still failing)
    "QV5_47",  # away goals vs top-6 (fixed)
    "QV5_50",  # actions_z3 vs Man City (fixed)
]

STAGE_NAMES = {
    "baseline": "Baseline regression",
    "sprint_1": "Sprint 1 - Robust NL + Ordinal Ranking",
    "sprint_2": "Sprint 2 - Match-level tables (minutes + matches)",
    "sprint_3": "Sprint 3 - Opponent and home/away context",
    "sprint_4": "Sprint 4 - Event-level match context",
    "sprint_5": "Sprint 5 - Team match context",
}


def normalize_value(v):
    if isinstance(v, float):
        return round(v, 2)
    return v


def row_matches_expected(row: dict, expected: dict) -> bool:
    for key, expected_value in expected.items():
        if key not in row:
            return False
        if normalize_value(row[key]) != normalize_value(expected_value):
            return False
    return True


def evaluate_rows(rows: list[dict], expected: dict) -> tuple[bool, dict]:
    if not rows:
        return False, {"reason": "no_rows", "matched_row": None}

    for row in rows:
        if row_matches_expected(row, expected):
            return True, {"reason": "matched", "matched_row": row}

    return False, {"reason": "no_matching_row", "matched_row": None}


def explain_should_use(engine: LLMQueryEngineV2, question: str, plan) -> dict:
    subject_entity = _question_subject_entity(question)
    filters = plan.filters.model_dump()

    has_context = _has_match_context_filters(filters)
    has_match_logic = _has_match_level_logic(plan)
    is_contextual = engine._is_contextual_question(question)

    reasons = []
    should_use = True

    if subject_entity == "team" and plan.entity_type == "player":
        should_use = False
        reasons.append("subject_entity_team_but_plan_entity_is_player")

    if subject_entity == "player" and plan.entity_type == "team":
        should_use = False
        reasons.append("subject_entity_player_but_plan_entity_is_team")

    if is_contextual:
        if not has_context and not has_match_logic:
            should_use = False
            reasons.append("contextual_question_but_plan_has_no_context_filters_or_match_logic")

        if plan.table_scope in {"players_summary", "teams_summary"}:
            should_use = False
            reasons.append("contextual_question_but_plan_scope_is_summary")

    if (
        not has_context
        and not has_match_logic
        and plan.table_scope in {"player_match", "player_match_event", "team_match"}
    ):
        should_use = False
        reasons.append("non_contextual_question_but_plan_scope_is_match_level_without_context")

    return {
        "should_use": should_use,
        "reasons": reasons,
        "signals": {
            "subject_entity": subject_entity,
            "has_context_filters": has_context,
            "has_match_logic": has_match_logic,
            "is_contextual_question": is_contextual,
        },
    }


def try_debug_question(engine: LLMQueryEngineV2, qitem: dict) -> dict:
    question = qitem["question"]
    expected = qitem["answer"]
    planner = engine.planner

    debug = {
        "question": question,
        "expected": expected,
        "raw_llm_plan": None,
        "canonical_plan": None,
        "post_processed_plan": None,
        "planner_error": None,
        "should_use_planner": None,
        "planned_query_result": None,
        "planned_eval": None,
        "agent_result": None,
        "agent_eval": None,
    }

    raw_plan = None
    canonical_plan = None
    final_plan = None

    try:
        raw_plan = planner._call_llm_for_plan(question)
        debug["raw_llm_plan"] = raw_plan
    except Exception as e:
        debug["planner_error"] = {"stage": "raw_llm_plan", "error": repr(e)}

    if raw_plan is not None:
        try:
            canonical_plan = planner._canonicalize_raw_plan(question, deepcopy(raw_plan))
            debug["canonical_plan"] = canonical_plan
        except Exception as e:
            debug["planner_error"] = {"stage": "canonicalize_raw_plan", "error": repr(e)}

    if canonical_plan is not None:
        try:
            final_plan = planner._post_process_plan(question, deepcopy(canonical_plan))
            debug["post_processed_plan"] = final_plan.model_dump()
            debug["should_use_planner"] = explain_should_use(engine, question, final_plan)
        except Exception as e:
            debug["planner_error"] = {
                "stage": "post_process_plan",
                "error": repr(e),
                "canonical_plan_before_failure": canonical_plan,
            }

    if final_plan is not None and debug["should_use_planner"]["should_use"]:
        try:
            planned_result = engine._execute_planned_query(question)
            if planned_result is not None:
                planned_rows = planned_result.rows or []
                planned_passed, planned_meta = evaluate_rows(planned_rows, expected)
                debug["planned_query_result"] = {
                    "table": planned_result.table,
                    "metric": planned_result.metric,
                    "filters_applied": planned_result.filters_applied,
                    "rows": planned_rows,
                }
                debug["planned_eval"] = {
                    "passed": planned_passed,
                    **planned_meta,
                }
            else:
                debug["planned_query_result"] = None
                debug["planned_eval"] = {
                    "passed": False,
                    "reason": "engine_execute_planned_query_returned_none",
                }
        except Exception as e:
            debug["planned_eval"] = {
                "passed": False,
                "reason": "planned_query_exception",
                "error": repr(e),
            }

    agent_result = engine.ask(question)
    agent_rows = (agent_result.get("debug") or {}).get("rows") or []
    agent_passed, agent_meta = evaluate_rows(agent_rows, expected)
    debug["agent_result"] = agent_result
    debug["agent_eval"] = {"passed": agent_passed, **agent_meta}

    return debug


def summarize_focus(results: list[dict]) -> dict:
    by_status = defaultdict(int)
    by_stage = defaultdict(lambda: {"passed": 0, "total": 0})

    for item in results:
        passed = item["agent_eval"]["passed"]
        by_status["passed" if passed else "failed"] += 1
        stage = item["expected_stage"]
        by_stage[stage]["total"] += 1
        if passed:
            by_stage[stage]["passed"] += 1

    return {
        "total": len(results),
        "passed": by_status["passed"],
        "failed": by_status["failed"],
        "score": f"{by_status['passed']}/{len(results)}",
        "by_expected_stage": {
            stage: {
                "passed": bucket["passed"],
                "total": bucket["total"],
                "score": f"{bucket['passed']}/{bucket['total']}",
                "stage_name": STAGE_NAMES.get(stage, stage),
            }
            for stage, bucket in by_stage.items()
        },
    }


def print_case_report(item: dict) -> None:
    print("\n" + "=" * 120)
    print(
        f"{item['id']} | {item['category']} | {STAGE_NAMES.get(item['expected_stage'], item['expected_stage'])}"
    )
    print(f"QUESTION : {item['question']}")
    print(f"EXPECTED : {item['expected']}")

    if item["planner_error"]:
        print(f"PLANNER ERROR: {item['planner_error']}")
    else:
        print("RAW PLAN:")
        print(json.dumps(item["raw_llm_plan"], indent=2, ensure_ascii=False))
        print("CANONICAL PLAN:")
        print(json.dumps(item["canonical_plan"], indent=2, ensure_ascii=False))
        print("FINAL PLAN:")
        print(json.dumps(item["post_processed_plan"], indent=2, ensure_ascii=False))
        print("SHOULD USE PLANNER:")
        print(json.dumps(item["should_use_planner"], indent=2, ensure_ascii=False))

    print("PLANNED QUERY RESULT:")
    print(json.dumps(item["planned_query_result"], indent=2, ensure_ascii=False))
    print("PLANNED EVAL:")
    print(json.dumps(item["planned_eval"], indent=2, ensure_ascii=False))

    print("AGENT RESULT:")
    print(f"CONTENT  : {item['agent_result']['content']}")
    print("DEBUG:")
    print(json.dumps(item["agent_result"].get("debug", {}), indent=2, ensure_ascii=False))
    print("AGENT EVAL:")
    print(json.dumps(item["agent_eval"], indent=2, ensure_ascii=False))


def load_focus_questions(benchmark_path: str, focus_ids: list[str]) -> list[dict]:
    with open(benchmark_path, encoding="utf8") as f:
        benchmark = json.load(f)

    wanted = set(focus_ids)
    selected = [q for q in benchmark if q["id"] in wanted]
    selected.sort(key=lambda q: focus_ids.index(q["id"]))
    return selected


def save_results(payload: dict, run_label: str | None = None) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    latest_path = OUTPUT_DIR / "latest_eval_results_v5_focus.json"
    dated_path = OUTPUT_DIR / f"{timestamp}_eval_results_v5_focus.json"

    json_payload = json.dumps(payload, indent=2, ensure_ascii=False)
    latest_path.write_text(json_payload, encoding="utf8")
    dated_path.write_text(json_payload, encoding="utf8")

    print(f"\nSaved: {latest_path}")
    print(f"Saved: {dated_path}")

    if run_label:
        safe_label = re.sub(r"[^a-zA-Z0-9._-]+", "_", run_label.strip().lower())
        label_path = OUTPUT_DIR / f"{timestamp}__{safe_label}.json"
        label_path.write_text(json_payload, encoding="utf8")
        print(f"Saved: {label_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run focused Basic Stats benchmark v5 with deep planner debug"
    )
    parser.add_argument("--benchmark", default=BENCHMARK_PATH, help="Path to benchmark JSON")
    parser.add_argument(
        "--ids",
        nargs="*",
        default=FOCUS_IDS_DEFAULT,
        help="Benchmark ids to run. Default: the original 7 failures plus the ones already fixed.",
    )
    parser.add_argument("--label", default=None, help="Optional run label")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    focus_questions = load_focus_questions(args.benchmark, args.ids)
    if not focus_questions:
        raise SystemExit("No focus questions found for the provided ids.")

    engine = LLMQueryEngineV2()
    results = []

    for qitem in focus_questions:
        debug = try_debug_question(engine, qitem)
        item = {
            "id": qitem["id"],
            "category": qitem.get("category", "uncategorized"),
            "expected_stage": qitem.get("expected_stage", "unspecified"),
            **debug,
        }
        results.append(item)
        print_case_report(item)

    summary = summarize_focus(results)
    payload = {
        "benchmark_path": args.benchmark,
        "focus_ids": args.ids,
        "summary": summary,
        "results": results,
    }

    print("\n" + "#" * 120)
    print("FOCUS SUMMARY")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    save_results(payload, args.label)


if __name__ == "__main__":
    main()
