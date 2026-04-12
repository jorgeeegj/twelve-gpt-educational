"""
benchmark_runner.py — parallel benchmark runner for evals/questions_benchmark.json

Drop-in replacement for eval_runner.py with concurrent execution via ThreadPoolExecutor.
Each worker thread owns its own LLMQueryEngineV2 instance (and therefore its own
DuckDB connection + OpenAI client), so there is no shared mutable state.

Reuses all evaluation logic from eval_runner (evaluate_question, summarize_bucket,
save_results, STAGE_NAMES) — no duplication.

Usage:
    python evals/benchmark_runner.py                     # default 5 workers
    python evals/benchmark_runner.py --workers 8
    python evals/benchmark_runner.py --workers 1         # sequential (same as eval_runner)
    python evals/benchmark_runner.py --label my_run
"""

import argparse
import json
import sys
import threading
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, ".")

from evals.eval_runner import (
    BENCHMARK_PATH,
    OUTPUT_DIR,
    STAGE_NAMES,
    evaluate_question,
    save_results,
    summarize_bucket,
)
from src.basic_stats.llm_query_engine_v2 import LLMQueryEngineV2

# One engine per thread — avoids DuckDB connection sharing
_thread_local = threading.local()


def _get_engine() -> LLMQueryEngineV2:
    if not hasattr(_thread_local, "engine"):
        # in_memory=True avoids DuckDB write-write conflicts across threads
        # (views are registered on parquet files, not persisted anyway)
        _thread_local.engine = LLMQueryEngineV2(in_memory=True)
    return _thread_local.engine


def _run_one(entry: dict) -> dict:
    """Run a single benchmark entry. Called from a worker thread."""
    engine = _get_engine()
    result = engine.ask(entry["question"])
    passed, meta = evaluate_question(result, entry)
    debug = result.get("debug", {})
    stage = entry.get("expected_stage", "unspecified")
    return {
        "id": entry["id"],
        "category": entry.get("category", "uncategorized"),
        "expected_stage": stage,
        "expected_stage_name": STAGE_NAMES.get(stage, stage),
        "question": entry["question"],
        "expected": entry.get("answer"),
        "debug_expected": entry.get("debug_expected"),
        "agent_text": result["content"],
        "debug": debug,
        "passed": passed,
        "eval_meta": meta,
    }


def run_benchmark(benchmark_path: str, workers: int) -> dict:
    with open(benchmark_path, encoding="utf8") as f:
        benchmark = json.load(f)

    print(f"Running {len(benchmark)} questions with {workers} workers...\n")

    rows: list[dict] = [None] * len(benchmark)
    index = {entry["id"]: i for i, entry in enumerate(benchmark)}

    score_by_category = defaultdict(lambda: {"passed": 0, "total": 0})
    score_by_stage = defaultdict(lambda: {"passed": 0, "total": 0})
    total_passed = 0

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_run_one, entry): entry for entry in benchmark}
        for future in as_completed(futures):
            row = future.result()
            rows[index[row["id"]]] = row

            # Thread-safe: defaultdict operations on simple ints are GIL-protected
            score_by_category[row["category"]]["total"] += 1
            score_by_stage[row["expected_stage"]]["total"] += 1
            if row["passed"]:
                score_by_category[row["category"]]["passed"] += 1
                score_by_stage[row["expected_stage"]]["passed"] += 1
                total_passed += 1

            _print_row(row)

    summary = {
        "benchmark_path": benchmark_path,
        "workers": workers,
        "total_passed": total_passed,
        "total_questions": len(benchmark),
        "score": f"{total_passed}/{len(benchmark)}",
        "by_category": {c: summarize_bucket(b) for c, b in dict(score_by_category).items()},
        "by_expected_stage": {
            s: {**summarize_bucket(b), "stage_name": STAGE_NAMES.get(s, s)}
            for s, b in dict(score_by_stage).items()
        },
    }

    print(f"\n{'#' * 100}")
    print("SUMMARY")
    print(json.dumps(summary, indent=2, ensure_ascii=False))

    return {"summary": summary, "results": rows}


def _print_row(row: dict) -> None:
    debug = row["debug"]
    print(f"\n{'=' * 100}")
    print(f"{row['id']} | {row['category']} | {row['expected_stage_name']}")
    print(f"QUESTION : {row['question']}")
    if row["debug_expected"]:
        print(f"EXPECTED : [debug] {row['debug_expected']}")
    else:
        print(f"EXPECTED : {row['expected']}")
    print(f"AGENT    : {row['agent_text']}")
    print(
        f"DEBUG    : engine={debug.get('engine')} | "
        f"table={debug.get('table')} | "
        f"metric={debug.get('metric')}"
    )
    print(f"PASS     : {row['passed']}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Parallel benchmark runner")
    parser.add_argument("--benchmark", default=BENCHMARK_PATH)
    parser.add_argument(
        "--workers", type=int, default=5, help="Parallel worker threads (default: 5)"
    )
    parser.add_argument("--label", default=None, help="Optional run label")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = run_benchmark(args.benchmark, args.workers)
    save_results(payload, args.label)


if __name__ == "__main__":
    main()
