"""
eval_runner_async.py — fast parallel benchmark runner

Runs all questions in questions_benchmark.json concurrently using
asyncio + ThreadPoolExecutor (the underlying AzureOpenAI client is sync,
so we wrap each call in run_in_executor rather than using AsyncAzureOpenAI).

Results are saved to evals/runs/<YYYY-MM-DD_HH-MM-SS>/
  - summary.json   overall score + by_category + by_stage
  - results.json   per-question detail

Usage:
    python evals/eval_runner_async.py
    python evals/eval_runner_async.py --benchmark evals/questions_benchmark.json
    python evals/eval_runner_async.py --workers 20 --label phase5_cleanup
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, ".")

from src.basic_stats.llm_query_engine_v2 import LLMQueryEngineV2

BENCHMARK_PATH = Path(__file__).parent / "questions_benchmark.json"
RUNS_DIR = Path(__file__).parent / "runs"

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


# ---------------------------------------------------------------------------
# Evaluation helpers (identical logic to eval_runner.py)
# ---------------------------------------------------------------------------


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
    val = d
    for part in dotted_key.split("."):
        if not isinstance(val, dict) or part not in val:
            return _SENTINEL
        val = val[part]
    return val


def debug_matches_expected(debug: dict, debug_expected: dict) -> bool:
    for key, expected_val in debug_expected.items():
        actual = get_nested(debug, key)
        if actual is _SENTINEL:
            return False
        if normalize_value(actual) != normalize_value(expected_val):
            return False
    return True


def evaluate_question(result: dict, entry: dict) -> tuple[bool, dict]:
    debug_expected = entry.get("debug_expected")

    if debug_expected is not None:
        debug = result.get("debug", {})
        passed = debug_matches_expected(debug, debug_expected)
        return passed, {
            "reason": "debug_matched" if passed else "debug_no_match",
            "debug_expected": debug_expected,
            "debug_engine": debug.get("engine"),
        }

    expected = entry.get("answer", {})
    debug = result.get("debug", {})
    rows = debug.get("rows", []) or []

    if not rows:
        return False, {"reason": "no_rows", "matched_row": None}

    for row in rows:
        if row_matches_expected(row, expected):
            return True, {"reason": "matched", "matched_row": row}

    return False, {"reason": "no_matching_row", "matched_row": None}


# ---------------------------------------------------------------------------
# Async runner
# ---------------------------------------------------------------------------


async def run_one(
    entry: dict,
    engine: LLMQueryEngineV2,
    executor: ThreadPoolExecutor,
    loop: asyncio.AbstractEventLoop,
    counter: list[int],
    total: int,
) -> dict:
    """Run a single benchmark question in the thread pool."""
    try:
        result = await loop.run_in_executor(executor, engine.ask, entry["question"])
    except Exception as exc:
        result = {"content": f"ERROR: {exc}", "debug": {}}

    passed, meta = evaluate_question(result, entry)

    counter[0] += 1
    status = "PASS" if passed else "FAIL"
    print(f"[{counter[0]:>3}/{total}] {status} {entry['id']} — {entry['question'][:70]}")

    debug = result.get("debug", {})
    category = entry.get("category", "uncategorized")
    stage = entry.get("expected_stage", "unspecified")

    return {
        "id": entry["id"],
        "category": category,
        "expected_stage": stage,
        "expected_stage_name": STAGE_NAMES.get(stage, stage),
        "question": entry["question"],
        "expected": entry.get("answer"),
        "debug_expected": entry.get("debug_expected"),
        "agent_text": result.get("content"),
        "debug": debug,
        "passed": passed,
        "eval_meta": meta,
    }


async def run_benchmark_async(
    benchmark_path: Path,
    max_workers: int,
) -> dict:
    with open(benchmark_path, encoding="utf8") as f:
        benchmark: list[dict] = json.load(f)

    total = len(benchmark)
    print(f"Running {total} questions with up to {max_workers} parallel workers…\n")

    engine = LLMQueryEngineV2()
    loop = asyncio.get_event_loop()
    counter = [0]

    t0 = time.perf_counter()

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        tasks = [run_one(entry, engine, executor, loop, counter, total) for entry in benchmark]
        results = await asyncio.gather(*tasks)

    elapsed = time.perf_counter() - t0

    # Sort results back to benchmark order for readability
    id_order = {entry["id"]: i for i, entry in enumerate(benchmark)}
    results = sorted(results, key=lambda r: id_order.get(r["id"], 9999))

    # Aggregate scores
    score_by_category: dict = defaultdict(lambda: {"passed": 0, "total": 0})
    score_by_stage: dict = defaultdict(lambda: {"passed": 0, "total": 0})
    total_passed = 0

    for r in results:
        cat = r["category"]
        stage = r["expected_stage"]
        score_by_category[cat]["total"] += 1
        score_by_stage[stage]["total"] += 1
        if r["passed"]:
            score_by_category[cat]["passed"] += 1
            score_by_stage[stage]["passed"] += 1
            total_passed += 1

    summary = {
        "benchmark_path": str(benchmark_path),
        "total_passed": total_passed,
        "total_questions": total,
        "score": f"{total_passed}/{total}",
        "elapsed_seconds": round(elapsed, 1),
        "max_workers": max_workers,
        "by_category": {
            cat: {
                "passed": b["passed"],
                "total": b["total"],
                "score": f"{b['passed']}/{b['total']}",
            }
            for cat, b in sorted(score_by_category.items())
        },
        "by_expected_stage": {
            stage: {
                "passed": b["passed"],
                "total": b["total"],
                "score": f"{b['passed']}/{b['total']}",
                "stage_name": STAGE_NAMES.get(stage, stage),
            }
            for stage, b in sorted(score_by_stage.items())
        },
    }

    print(f"\n{'#' * 80}")
    print(f"SCORE: {total_passed}/{total}  ({elapsed:.1f}s with {max_workers} workers)")
    print(json.dumps(summary["by_category"], indent=2, ensure_ascii=False))

    return {"summary": summary, "results": results}


# ---------------------------------------------------------------------------
# Save results
# ---------------------------------------------------------------------------


def save_results(payload: dict, run_label: str | None) -> Path:
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    run_name = (
        timestamp
        if not run_label
        else f"{timestamp}__{re.sub(r'[^a-zA-Z0-9._-]+', '_', run_label.strip().lower())}"
    )
    run_dir = RUNS_DIR / run_name
    run_dir.mkdir(parents=True, exist_ok=True)

    summary_path = run_dir / "summary.json"
    results_path = run_dir / "results.json"

    summary_path.write_text(
        json.dumps(payload["summary"], indent=2, ensure_ascii=False), encoding="utf8"
    )
    results_path.write_text(
        json.dumps(payload["results"], indent=2, ensure_ascii=False), encoding="utf8"
    )

    print(f"\nSaved to: {run_dir}")
    print(f"  {summary_path.name}")
    print(f"  {results_path.name}")

    return run_dir


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fast async benchmark runner")
    parser.add_argument(
        "--benchmark",
        default=str(BENCHMARK_PATH),
        help="Path to benchmark JSON (default: evals/questions_benchmark.json)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=15,
        help="Max parallel threads (default: 15). Increase to 20+ if rate limits allow.",
    )
    parser.add_argument(
        "--label",
        default=None,
        help="Optional run label appended to folder name, e.g. 'phase5_cleanup'",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    payload = asyncio.run(
        run_benchmark_async(
            benchmark_path=Path(args.benchmark),
            max_workers=args.workers,
        )
    )
    save_results(payload, args.label)


if __name__ == "__main__":
    main()
