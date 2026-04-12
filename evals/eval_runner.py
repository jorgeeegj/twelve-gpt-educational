"""
eval_runner.py — benchmark runner for evals/questions_benchmark.json

Extends eval_runner_v4 with support for Phase 3 early-return paths
(dual_bucket, home_away, metric_derived_bucket) via an optional
`debug_expected` field in the benchmark entry.

Schema change (backward-compatible):
  - If `debug_expected` is present in a benchmark entry, the question is
    validated by matching those key-value pairs directly against the engine's
    `result["debug"]` dict.  Dotted-path keys are supported:
    e.g. `"bucket_a.value": 4` looks up `debug["bucket_a"]["value"]`.
  - If `debug_expected` is absent, the existing rows-based check is used
    (matches `answer` against any row in `debug["rows"]`).

A question PASSES if its active check (debug_expected or rows) succeeds.
"""

import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, ".")

from src.basic_stats.llm_query_engine_v2 import LLMQueryEngineV2

BENCHMARK_PATH = str(Path(__file__).parent / "questions_benchmark.json")
OUTPUT_DIR = Path("docs/evals")

STAGE_NAMES = {
    "baseline": "Baseline regression",
    "sprint_1": "Sprint 1 - Robust NL + Ordinal Ranking",
    "sprint_2": "Sprint 2 - Match-level tables (minutes + matches)",
    "sprint_3": "Sprint 3 - Opponent and home/away context",
    "sprint_4": "Sprint 4 - Event-level match context",
    "sprint_5": "Sprint 5 - Team match context",
    "sprint_6": "Sprint 6 - Planner robustness + mid-table bucket",
    "sprint_7": "Sprint 7 - Dual-bucket comparison",
    "sprint_8": "Sprint 8 - Home-away comparison",
    "sprint_9": "Sprint 9 - Metric-derived bucket",
    "sprint_10": "Sprint 10 - Temporal entity-value",
}

_SENTINEL = object()


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


def get_nested(d: dict, dotted_key: str):
    """
    Resolve a dot-separated key path into a nested dict.
    Returns _SENTINEL if any key in the path is missing.
    Example: get_nested(d, "bucket_a.value") => d["bucket_a"]["value"]
    """
    val = d
    for part in dotted_key.split("."):
        if not isinstance(val, dict) or part not in val:
            return _SENTINEL
        val = val[part]
    return val


def debug_matches_expected(debug: dict, debug_expected: dict) -> bool:
    """
    Validate that all key-value pairs in debug_expected appear in debug.
    Supports dot-separated keys for nested access.
    Values are normalized (floats rounded to 2dp) before comparison.
    """
    for key, expected_val in debug_expected.items():
        actual = get_nested(debug, key)
        if actual is _SENTINEL:
            return False
        if normalize_value(actual) != normalize_value(expected_val):
            return False
    return True


def evaluate_question(result: dict, entry: dict) -> tuple[bool, dict]:
    """
    Evaluate one benchmark entry against the engine result.

    If `debug_expected` is present in the entry: validate against debug dict.
    Otherwise: validate `answer` against debug["rows"] (original v4 path).
    """
    debug_expected = entry.get("debug_expected")

    if debug_expected is not None:
        debug = result.get("debug", {})
        passed = debug_matches_expected(debug, debug_expected)
        return passed, {
            "reason": "debug_matched" if passed else "debug_no_match",
            "debug_expected": debug_expected,
            "debug_engine": debug.get("engine"),
        }

    # Original rows-based path (backward compatible with v4/v5 entries)
    expected = entry.get("answer", {})
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
        passed, meta = evaluate_question(result, q)

        category = q.get("category", "uncategorized")
        stage = q.get("expected_stage", "unspecified")

        score_by_category[category]["total"] += 1
        score_by_stage[stage]["total"] += 1

        if passed:
            score_by_category[category]["passed"] += 1
            score_by_stage[stage]["passed"] += 1
            total_passed += 1

        debug = result.get("debug", {})

        results.append(
            {
                "id": q["id"],
                "category": category,
                "expected_stage": stage,
                "expected_stage_name": STAGE_NAMES.get(stage, stage),
                "question": q["question"],
                "expected": q.get("answer"),
                "debug_expected": q.get("debug_expected"),
                "agent_text": result["content"],
                "debug": debug,
                "passed": passed,
                "eval_meta": meta,
            }
        )

        print(f"\n{'=' * 100}")
        print(f"{q['id']} | {category} | {STAGE_NAMES.get(stage, stage)}")
        print(f"QUESTION : {q['question']}")
        if q.get("debug_expected"):
            print(f"EXPECTED : [debug] {q['debug_expected']}")
        else:
            print(f"EXPECTED : {q.get('answer')}")
        print(f"AGENT    : {result['content']}")
        print(
            f"DEBUG    : engine={debug.get('engine')} | "
            f"table={debug.get('table')} | "
            f"metric={debug.get('metric')}"
        )
        print(f"PASS     : {passed}")

    summary = {
        "benchmark_path": benchmark_path,
        "total_passed": total_passed,
        "total_questions": len(benchmark),
        "score": f"{total_passed}/{len(benchmark)}",
        "by_category": {cat: summarize_bucket(b) for cat, b in dict(score_by_category).items()},
        "by_expected_stage": {
            stage: {
                **summarize_bucket(b),
                "stage_name": STAGE_NAMES.get(stage, stage),
            }
            for stage, b in dict(score_by_stage).items()
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
    latest_path = OUTPUT_DIR / "latest_eval_results.json"
    dated_path = OUTPUT_DIR / f"{timestamp}_eval_results.json"

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
    parser = argparse.ArgumentParser(description="Run Basic Stats benchmark v6")
    parser.add_argument(
        "--benchmark",
        default=BENCHMARK_PATH,
        help="Path to the benchmark JSON file",
    )
    parser.add_argument(
        "--label",
        default=None,
        help="Optional run label, e.g. 'Phase3_enrichment_v6'",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    payload = run_benchmark(args.benchmark)
    save_results(payload, args.label)


if __name__ == "__main__":
    main()
