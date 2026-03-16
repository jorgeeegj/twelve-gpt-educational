import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, ".")

from utils.basic_stats.core.llm_query_engine_v2 import LLMQueryEngineV2


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


def run_benchmark() -> dict:
    engine = LLMQueryEngineV2()

    with open("questions_benchmark_raw.json", encoding="utf8") as f:
        benchmark = json.load(f)

    results = []
    score_by_category = defaultdict(lambda: {"passed": 0, "total": 0})
    total_passed = 0

    for q in benchmark:
        result = engine.ask(q["question"])
        passed, meta = evaluate_question(result, q["answer"])

        score_by_category[q["category"]]["total"] += 1
        if passed:
            score_by_category[q["category"]]["passed"] += 1
            total_passed += 1

        debug = result.get("debug", {})

        results.append({
            "id": q["id"],
            "category": q["category"],
            "question": q["question"],
            "expected": q["answer"],
            "agent_text": result["content"],
            "debug": debug,
            "passed": passed,
            "eval_meta": meta,
        })

        print(f"\n{'=' * 80}")
        print(f"{q['id']} | {q['category']}")
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
        "total_passed": total_passed,
        "total_questions": len(benchmark),
        "score": f"{total_passed}/{len(benchmark)}",
        "by_category": dict(score_by_category),
    }

    print(f"\n{'#' * 80}")
    print("SUMMARY")
    print(json.dumps(summary, indent=2, ensure_ascii=False))

    return {
        "summary": summary,
        "results": results,
    }


def save_results(payload: dict) -> None:
    output_dir = Path("docs/evals")
    output_dir.mkdir(parents=True, exist_ok=True)

    latest_path = output_dir / "latest_eval_results.json"
    dated_path = output_dir / f"{datetime.now().strftime('%Y-%m-%d')}_eval_results.json"

    json_payload = json.dumps(payload, indent=2, ensure_ascii=False)

    latest_path.write_text(json_payload, encoding="utf8")
    dated_path.write_text(json_payload, encoding="utf8")

    print(f"\nSaved: {latest_path}")
    print(f"Saved: {dated_path}")


def main():
    payload = run_benchmark()
    save_results(payload)


if __name__ == "__main__":
    main()