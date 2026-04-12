"""
agent_benchmark.py — end-to-end benchmark for BasicStatsAgent.

Evaluates answer quality on three dimensions:
  1. Faithfulness  (auto, hard gate >=95%) — numbers in answer match ground truth
  2. Naturalness   (LLM judge, soft gate avg >=4.0) — fluency and analyst voice
  3. Completeness  (LLM judge, soft gate >=90%) — answer addresses the question

Runs questions in parallel using asyncio + ThreadPoolExecutor (same pattern
as eval_runner_async.py). Results saved to evals/runs/<timestamp>__agent/.

Usage:
    python evals/agent_benchmark.py
    python evals/agent_benchmark.py --skip-judges   # faithfulness only, much faster
    python evals/agent_benchmark.py --workers 10 --label phase5_ship
    python evals/agent_benchmark.py --random         # run random_questions.json instead
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

import openai

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, ".")

from evals.judges.faithfulness_judge import judge_faithfulness
from evals.judges.naturalness_judge import judge_naturalness
from src.basic_stats.agent import BasicStatsAgent
from src.basic_stats.config import get_llm_client, get_model

BENCHMARK_PATH = Path(__file__).parent / "questions_benchmark.json"
RANDOM_PATH = Path(__file__).parent / "random_questions.json"
RUNS_DIR = Path(__file__).parent / "runs"

# ---------------------------------------------------------------------------
# Gates
# ---------------------------------------------------------------------------
FAITHFULNESS_GATE = 0.95  # 95% of answers must be faithful
NATURALNESS_GATE = 4.0  # average naturalness score
COMPLETENESS_GATE = 0.90  # 90% of answers must be complete


# ---------------------------------------------------------------------------
# Retry helper
# ---------------------------------------------------------------------------

_MAX_RETRIES = 4
_RETRY_BASE_DELAY = 5.0  # seconds


def _ask_with_retry(agent: "BasicStatsAgent", question: str) -> str:
    """Call agent.ask with exponential backoff on OpenAI 429 rate-limit errors."""
    delay = _RETRY_BASE_DELAY
    for attempt in range(_MAX_RETRIES):
        try:
            return agent.ask(question)
        except openai.RateLimitError:
            if attempt == _MAX_RETRIES - 1:
                return f"ERROR: rate_limit after {_MAX_RETRIES} retries"
            time.sleep(delay)
            delay *= 2
        except Exception as exc:
            return f"ERROR: {exc}"
    return f"ERROR: rate_limit after {_MAX_RETRIES} retries"  # unreachable but satisfies mypy


# ---------------------------------------------------------------------------
# Single question evaluation
# ---------------------------------------------------------------------------


async def evaluate_one(
    entry: dict,
    agent: BasicStatsAgent,
    executor: ThreadPoolExecutor,
    loop: asyncio.AbstractEventLoop,
    judge_client,
    judge_model: str,
    skip_judges: bool,
    counter: list[int],
    total: int,
) -> dict:
    """Run one question through the agent and both judges."""
    question = entry["question"]

    # Agent call (sync wrapped in executor) with exponential backoff on 429
    answer = await loop.run_in_executor(executor, _ask_with_retry, agent, question)

    # Faithfulness (deterministic, no LLM)
    faith = judge_faithfulness(answer, entry)

    # Naturalness + completeness (LLM judge)
    if skip_judges or answer.startswith("ERROR:"):
        nat_score = None
        nat_rationale = "skipped"
        is_complete = None
        completeness_rationale = "skipped"
        nat_error = None
    else:
        try:
            nat = await loop.run_in_executor(
                executor,
                lambda: judge_naturalness(question, answer, judge_client, judge_model),
            )
            nat_score = nat.naturalness_score
            nat_rationale = nat.naturalness_rationale
            is_complete = nat.is_complete
            completeness_rationale = nat.completeness_rationale
            nat_error = nat.error
        except Exception as exc:
            nat_score = None
            nat_rationale = "judge error"
            is_complete = None
            completeness_rationale = "judge error"
            nat_error = str(exc)

    counter[0] += 1
    faith_icon = "F✓" if faith.passed else "F✗"
    nat_icon = f"N{nat_score}" if nat_score is not None else "N-"
    comp_icon = ("C✓" if is_complete else "C✗") if is_complete is not None else "C-"
    print(
        f"[{counter[0]:>3}/{total}] {faith_icon} {nat_icon} {comp_icon} "
        f"{entry['id']} — {question[:60]}"
    )

    return {
        "id": entry["id"],
        "category": entry.get("category", "uncategorized"),
        "question": question,
        "answer": answer,
        "expected": entry.get("answer"),
        "debug_expected": entry.get("debug_expected"),
        # Faithfulness
        "faithfulness_passed": faith.passed,
        "faithfulness_reason": faith.reason,
        "faithfulness_expected": faith.expected_values,
        "faithfulness_missing": faith.missing,
        # Naturalness + completeness
        "naturalness_score": nat_score,
        "naturalness_rationale": nat_rationale,
        "is_complete": is_complete,
        "completeness_rationale": completeness_rationale,
        "judge_error": nat_error,
    }


# ---------------------------------------------------------------------------
# Full benchmark run
# ---------------------------------------------------------------------------


async def run_benchmark_async(
    benchmark_path: Path,
    max_workers: int,
    skip_judges: bool,
) -> dict:
    with open(benchmark_path, encoding="utf-8") as f:
        questions: list[dict] = json.load(f)

    total = len(questions)
    mode = (
        "faithfulness-only" if skip_judges else "full (faithfulness + naturalness + completeness)"
    )
    print(f"\nRunning {total} questions — {mode} — {max_workers} workers\n")

    agent = BasicStatsAgent()
    judge_client = get_llm_client()
    judge_model = get_model()
    loop = asyncio.get_event_loop()
    counter = [0]

    t0 = time.perf_counter()

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        tasks = [
            evaluate_one(
                entry=q,
                agent=agent,
                executor=executor,
                loop=loop,
                judge_client=judge_client,
                judge_model=judge_model,
                skip_judges=skip_judges,
                counter=counter,
                total=total,
            )
            for q in questions
        ]
        results = await asyncio.gather(*tasks)

    elapsed = time.perf_counter() - t0

    # Re-sort to benchmark order
    id_order = {q["id"]: i for i, q in enumerate(questions)}
    results = sorted(results, key=lambda r: id_order.get(r["id"], 9999))

    # Aggregate
    by_category: dict = defaultdict(
        lambda: {"total": 0, "faith_pass": 0, "nat_scores": [], "comp_pass": 0}
    )
    faith_total = faith_pass = 0
    nat_scores: list[float] = []
    comp_total = comp_pass = 0
    error_count = 0

    for r in results:
        cat = r["category"]
        by_category[cat]["total"] += 1

        faith_total += 1
        if r["faithfulness_passed"]:
            faith_pass += 1
            by_category[cat]["faith_pass"] += 1

        if r["answer"].startswith("ERROR:"):
            error_count += 1

        if r["naturalness_score"] is not None:
            nat_scores.append(r["naturalness_score"])
            by_category[cat]["nat_scores"].append(r["naturalness_score"])

        if r["is_complete"] is not None:
            comp_total += 1
            if r["is_complete"]:
                comp_pass += 1
                by_category[cat]["comp_pass"] += 1

    faith_rate = faith_pass / faith_total if faith_total else 0
    nat_avg = sum(nat_scores) / len(nat_scores) if nat_scores else None
    comp_rate = comp_pass / comp_total if comp_total else None

    # Gate checks
    gates = {
        "faithfulness": {
            "value": round(faith_rate, 3),
            "threshold": FAITHFULNESS_GATE,
            "passed": faith_rate >= FAITHFULNESS_GATE,
            "score": f"{faith_pass}/{faith_total}",
        },
    }
    if nat_avg is not None:
        gates["naturalness"] = {
            "value": round(nat_avg, 2),
            "threshold": NATURALNESS_GATE,
            "passed": nat_avg >= NATURALNESS_GATE,
            "score": f"{len(nat_scores)} answers rated",
        }
    if comp_rate is not None:
        gates["completeness"] = {
            "value": round(comp_rate, 3),
            "threshold": COMPLETENESS_GATE,
            "passed": comp_rate >= COMPLETENESS_GATE,
            "score": f"{comp_pass}/{comp_total}",
        }

    all_gates_pass = all(g["passed"] for g in gates.values())

    summary = {
        "benchmark_path": str(benchmark_path),
        "total_questions": total,
        "elapsed_seconds": round(elapsed, 1),
        "max_workers": max_workers,
        "error_count": error_count,
        "gates": gates,
        "all_gates_pass": all_gates_pass,
        "by_category": {
            cat: {
                "total": b["total"],
                "faithfulness": f"{b['faith_pass']}/{b['total']}",
                "naturalness_avg": round(sum(b["nat_scores"]) / len(b["nat_scores"]), 2)
                if b["nat_scores"]
                else None,
            }
            for cat, b in sorted(by_category.items())
        },
    }

    # Print summary
    print(f"\n{'#' * 80}")
    print(f"AGENT BENCHMARK — {total} questions — {elapsed:.1f}s")
    for name, gate in gates.items():
        icon = "PASS" if gate["passed"] else "FAIL"
        print(f"  {icon} {name:15s} {gate['value']} (gate: {gate['threshold']}) — {gate['score']}")
    print(f"\n  {'ALL GATES PASS' if all_gates_pass else 'SOME GATES FAILED'}")

    return {"summary": summary, "results": results}


# ---------------------------------------------------------------------------
# Save
# ---------------------------------------------------------------------------


def save_results(payload: dict, run_label: str | None) -> Path:
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    label = (
        "agent" if not run_label else re.sub(r"[^a-zA-Z0-9._-]+", "_", run_label.strip().lower())
    )
    run_dir = RUNS_DIR / f"{timestamp}__{label}"
    run_dir.mkdir(parents=True, exist_ok=True)

    (run_dir / "summary.json").write_text(
        json.dumps(payload["summary"], indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (run_dir / "results.json").write_text(
        json.dumps(payload["results"], indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print(f"\nSaved to: {run_dir}")
    return run_dir


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Agent benchmark runner")
    parser.add_argument("--benchmark", default=str(BENCHMARK_PATH))
    parser.add_argument("--random", action="store_true", help="Run random_questions.json")
    parser.add_argument(
        "--workers",
        type=int,
        default=10,
        help="Parallel workers (default 10; agent is 1 LLM call vs legacy 2)",
    )
    parser.add_argument(
        "--skip-judges",
        action="store_true",
        help="Skip LLM judges — faithfulness only, much faster",
    )
    parser.add_argument("--label", default=None)
    return parser.parse_args()


def main():
    args = parse_args()
    path = RANDOM_PATH if args.random else Path(args.benchmark)
    payload = asyncio.run(
        run_benchmark_async(
            benchmark_path=path,
            max_workers=args.workers,
            skip_judges=args.skip_judges,
        )
    )
    save_results(payload, args.label)


if __name__ == "__main__":
    main()
