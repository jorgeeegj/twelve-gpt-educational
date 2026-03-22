import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
import re
sys.path.insert(0, ".")

from utils.basic_stats.core.llm_query_engine_v2 import LLMQueryEngineV2

# Aqui cambiamos a v5 que es el último, el anterior de 40 es v4
BENCHMARK_PATH = "questions_benchmark_v5.json"
OUTPUT_DIR = Path("docs/evals")

STAGE_NAMES = {
    "baseline": "Baseline regression",
    "sprint_1": "Sprint 1 - Robust NL + Ordinal Ranking",
    "sprint_2": "Sprint 2 - Match-level tables (minutes + matches)",
    "sprint_3": "Sprint 3 - Opponent and home/away context",
    "sprint_4": "Sprint 4 - Event-level match context",
}


def normalize_value(v):
    if isinstance(v, float):
        return round(v, 2)
    return v


def row_matches_expected(row: dict, expected: dict) -> bool:
    for key, expected_value in expected.items():
        if key not in row:
            return False

        row_value = normalize_value(row[key])
        expected_value = normalize_value(expected_value)

        if row_value != expected_value:
            return False

    return True


def evaluate_question(result: dict, expected: dict) -> tuple[bool, dict]:
    debug = result.get("debug", {})
    rows = debug.get("rows", []) or []

    if not rows:
        return False, {"reason": "no_rows", "matched_row": None}

    for row in rows:
        if row_matches_expected(row, expected):
            return True, {"reason": "matched", "matched_row": row}

    return False, {"reason": "no_matching_row", "matched_row": None}


def summarize_bucket(bucket: dict) -> dict:
    return {
        "passed": bucket["passed"],
        "total": bucket["total"],
        "score": f"{bucket['passed']}/{bucket['total']}",
    }


def run_benchmark(benchmark_path: str) -> dict:
    engine = LLMQueryEngineV2()

    with open(benchmark_path, encoding="utf8") as f:
        benchmark = json.load(f)

    results = []
    score_by_category = defaultdict(lambda: {"passed": 0, "total": 0})
    score_by_stage = defaultdict(lambda: {"passed": 0, "total": 0})
    total_passed = 0

    for q in benchmark:
        result = engine.ask(q["question"])
        passed, meta = evaluate_question(result, q["answer"])

        category = q.get("category", "uncategorized")
        stage = q.get("expected_stage", "unspecified")

        score_by_category[category]["total"] += 1
        score_by_stage[stage]["total"] += 1

        if passed:
            score_by_category[category]["passed"] += 1
            score_by_stage[stage]["passed"] += 1
            total_passed += 1

        debug = result.get("debug", {})

        results.append({
            "id": q["id"],
            "category": category,
            "expected_stage": stage,
            "expected_stage_name": STAGE_NAMES.get(stage, stage),
            "question": q["question"],
            "expected": q["answer"],
            "agent_text": result["content"],
            "debug": debug,
            "passed": passed,
            "eval_meta": meta,
        })

        print(f"\n{'=' * 100}")
        print(f"{q['id']} | {category} | {STAGE_NAMES.get(stage, stage)}")
        print(f"QUESTION : {q['question']}")
        print(f"EXPECTED : {q['answer']}")
        print(f"AGENT    : {result['content']}")
        print(
            f"DEBUG    : table={debug.get('table')} | "
            f"metric={debug.get('metric')} | "
            f"filters={debug.get('filters')}"
        )
        print(f"PASS     : {passed}")

    summary = {
        "benchmark_path": benchmark_path,
        "total_passed": total_passed,
        "total_questions": len(benchmark),
        "score": f"{total_passed}/{len(benchmark)}",
        "by_category": {
            category: summarize_bucket(bucket)
            for category, bucket in dict(score_by_category).items()
        },
        "by_expected_stage": {
            stage: {
                **summarize_bucket(bucket),
                "stage_name": STAGE_NAMES.get(stage, stage),
            }
            for stage, bucket in dict(score_by_stage).items()
        },
    }

    print(f"\n{'#' * 100}")
    print("SUMMARY")
    print(json.dumps(summary, indent=2, ensure_ascii=False))

    return {
        "summary": summary,
        "results": results,
    }


def save_results(payload: dict, run_label: str | None = None) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    latest_path = OUTPUT_DIR / "latest_eval_results_v4.json"
    dated_path = OUTPUT_DIR / f"{timestamp}_eval_results_v4.json"

    json_payload = json.dumps(payload, indent=2, ensure_ascii=False)

    latest_path.write_text(json_payload, encoding="utf8")
    dated_path.write_text(json_payload, encoding="utf8")

    print(f"\nSaved: {latest_path}")
    print(f"Saved: {dated_path}")

    if run_label:
        safe_label = re.sub(r'[^a-zA-Z0-9._-]+', "_", run_label.strip().lower())
        label_path = OUTPUT_DIR / f"{timestamp}__{safe_label}.json"
        label_path.write_text(json_payload, encoding="utf8")
        print(f"Saved: {label_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Basic Stats benchmark v4")
    parser.add_argument(
        "--benchmark",
        default=BENCHMARK_PATH,
        help="Path to the benchmark JSON file",
    )
    parser.add_argument(
        "--label",
        default=None,
        help="Optional run label, e.g. 'baseline_v4' or 'Sprint 1 - Ordinal Ranking'",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    payload = run_benchmark(args.benchmark)
    save_results(payload, args.label)


if __name__ == "__main__":
    main()
