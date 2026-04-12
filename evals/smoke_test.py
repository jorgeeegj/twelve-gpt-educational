"""
smoke_test.py — 10-question sanity check for the Basic Stats engine.

Verifies that the repo structure, imports, data paths, and LLM planner all
work end-to-end after a pull / environment setup.  Exits 0 on pass, 1 on fail.

Usage:
    python evals/smoke_test.py          # 10-question smoke test (fast)
    python evals/smoke_test.py --full   # full 61-question benchmark
    uv run evals/smoke_test.py          # same, via uv

The 10 smoke questions are a representative subset of questions_benchmark.json
covering all sprint stages — no data is duplicated.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, ".")

from evals.eval_runner import BENCHMARK_PATH, STAGE_NAMES, evaluate_question

# IDs chosen to cover baseline, sprint_1–10 with known-passing questions
SMOKE_IDS = {
    "QV4_01",  # baseline   — top scorer (goals)
    "QV4_06",  # baseline   — team goals
    "QV4_21",  # sprint_1   — NL synonym ("top scorer")
    "QV4_27",  # sprint_1   — ordinal ranking (2nd in assists)
    "QV4_33",  # sprint_2   — match-level derived (goal+assist matches)
    "QV4_37",  # sprint_3   — opponent context (goals vs top-6)
    "QV5_41",  # sprint_4   — event-level (progressive passes vs top-6)
    "QV5_46",  # sprint_5   — team match context (points vs Big Six)
    "QV6_51",  # sprint_6   — player name hardening (Haaland)
    "QV6_55",  # sprint_8   — home/away comparison (Salah)
}


def load_questions(full: bool) -> list[dict]:
    benchmark = json.loads(Path(BENCHMARK_PATH).read_text(encoding="utf-8"))
    if full:
        return benchmark
    return [q for q in benchmark if q["id"] in SMOKE_IDS]


def run(questions: list[dict]) -> tuple[int, int, list[dict]]:
    # Import here so startup errors surface clearly
    from evals.benchmark_runner import _run_one

    failures = []
    passed = 0

    for i, entry in enumerate(questions, 1):
        row = _run_one(entry)
        stage_name = STAGE_NAMES.get(row["expected_stage"], row["expected_stage"])
        status = "PASS" if row["passed"] else "FAIL"
        print(f"[{i:02}/{len(questions)}] {status}  {row['id']:12}  {stage_name}")
        if not row["passed"]:
            print(f"         Q: {row['question']}")
            print(f"         expected : {row['expected'] or row['debug_expected']}")
            print(f"         got      : {row['agent_text']}")
            failures.append(row)
        else:
            passed += 1

    return passed, len(questions), failures


def main() -> None:
    parser = argparse.ArgumentParser(description="Basic Stats smoke test")
    parser.add_argument("--full", action="store_true", help="Run all 61 benchmark questions")
    args = parser.parse_args()

    questions = load_questions(args.full)
    label = "FULL BENCHMARK (61)" if args.full else "SMOKE TEST (10)"

    print(f"\n{'=' * 60}")
    print(f"  Basic Stats — {label}")
    print(f"{'=' * 60}\n")

    passed, total, failures = run(questions)

    print(f"\n{'=' * 60}")
    print(f"  Result: {passed}/{total} passed")
    print(f"{'=' * 60}\n")

    if failures:
        print(f"{len(failures)} question(s) failed:")
        for f in failures:
            print(f"  - [{f['id']}] {f['question']}")
        sys.exit(1)

    print("All checks passed. Environment is healthy.")
    sys.exit(0)


if __name__ == "__main__":
    main()
