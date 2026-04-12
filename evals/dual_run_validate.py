#!/usr/bin/env python
"""
Phase 5 dual-run validation: compare legacy vs function-calling QueryPlan
for all 61 benchmark questions, field-by-field.

Usage:
    python evals/dual_run_validate.py [--verbose] [--stop-on-first-diff] [--question N]

Exit code:
    0 — all plans match (or only known acceptable differences)
    1 — unexpected plan mismatches found

Acceptable differences (do not count as failures):
    - opponent_rank_lte=6 vs opponent_is_big6=True (semantically equivalent for "top 6"/"big six")
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, ".")

from src.basic_stats.query_planner import QueryPlanner

BENCHMARK_PATH = str(Path(__file__).parent / "questions_benchmark.json")

PLAN_FIELDS = ["table_scope", "entity_type", "metric", "aggregation"]
FILTER_FIELDS = [
    "player_name",
    "team_name",
    "opponent_team_name",
    "position",
    "is_home",
    "opponent_rank_lte",
    "opponent_rank_gte",
    "opponent_rank_between",
    "opponent_is_big6",
    "matchday_start",
    "matchday_end",
]
RANKING_FIELDS = ["mode", "n", "ordinal"]

# Pairs that are semantically equivalent — count as MATCH not DIFF
ACCEPTABLE_FILTER_EQUIVALENCES = [
    # (field_a, val_a, field_b, val_b) — if legacy has a and fc has b (or vice versa)
    # top-6 via rank vs big6 flag
    ("opponent_rank_lte", 6, "opponent_is_big6", True),
]


def _is_acceptable_difference(ld: dict, fd: dict) -> bool:
    """Return True if the only filter differences are known semantically equivalent pairs."""
    for field in PLAN_FIELDS + RANKING_FIELDS:
        key = field if field in PLAN_FIELDS else None
        if key and ld.get(key) != fd.get(key):
            return False

    lf = ld["filters"]
    ff = fd["filters"]

    for field in FILTER_FIELDS:
        lv = lf.get(field)
        fv = ff.get(field)
        if lv == fv:
            continue
        # Check if this difference is an acceptable equivalence
        accepted = False
        for fa, va, fb, vb in ACCEPTABLE_FILTER_EQUIVALENCES:
            if (field == fa and lv == va and ff.get(fb) == vb and fv is None) or (
                field == fb and lv == vb and ff.get(fa) == va and fv is None
            ):
                accepted = True
                break
            if (field == fa and fv == va and lf.get(fb) == vb and lv is None) or (
                field == fb and fv == vb and lf.get(fa) == va and lv is None
            ):
                accepted = True
                break
        if not accepted:
            return False

    return True


def compare_plans(legacy_plan, fc_plan) -> list[str]:
    """Return list of field differences. Empty list = plans match."""
    diffs = []
    ld = legacy_plan.model_dump()
    fd = fc_plan.model_dump()

    for field in PLAN_FIELDS:
        if ld[field] != fd[field]:
            diffs.append(f"  {field}: legacy={ld[field]!r}  fc={fd[field]!r}")

    for field in FILTER_FIELDS:
        lv = ld["filters"].get(field)
        fv = fd["filters"].get(field)
        if lv != fv:
            diffs.append(f"  filters.{field}: legacy={lv!r}  fc={fv!r}")

    for field in RANKING_FIELDS:
        lv = ld["ranking"].get(field)
        fv = fd["ranking"].get(field)
        if lv != fv:
            diffs.append(f"  ranking.{field}: legacy={lv!r}  fc={fv!r}")

    return diffs


def main():
    parser = argparse.ArgumentParser(
        description="Dual-run validation: legacy vs function-calling QueryPlanner"
    )
    parser.add_argument("--verbose", action="store_true", help="Print all field diffs")
    parser.add_argument(
        "--stop-on-first-diff", action="store_true", help="Stop after first mismatch"
    )
    parser.add_argument("--question", type=int, default=None, help="Run only question N (1-based)")
    args = parser.parse_args()

    with open(BENCHMARK_PATH) as f:
        benchmark = json.load(f)

    questions = [item["question"] for item in benchmark]

    if args.question is not None:
        idx = args.question - 1
        questions = [questions[idx]]
        print(f"Running single question [{args.question}]: {questions[0]}\n")

    # Both planners use legacy path by default; fc_planner gets flag set below
    legacy_planner = QueryPlanner()
    legacy_planner.use_function_calling = False

    fc_planner = QueryPlanner()
    fc_planner.use_function_calling = True  # Enable function calling path

    total = len(questions)
    matches = 0
    acceptable = 0
    mismatches = 0
    errors = 0

    for i, question in enumerate(questions, 1):
        label = f"[{i:02d}/{total}]"
        preview = question[:65] + "…" if len(question) > 65 else question
        print(f"{label} {preview}", end="", flush=True)

        try:
            legacy_plan = legacy_planner.resolve(question)
        except Exception as e:
            print(f"\n  → LEGACY ERROR: {e}")
            errors += 1
            if args.stop_on_first_diff:
                break
            continue

        try:
            fc_plan = fc_planner.resolve(question)
        except Exception as e:
            print(f"\n  → FC ERROR: {e}")
            errors += 1
            if args.stop_on_first_diff:
                break
            continue

        diffs = compare_plans(legacy_plan, fc_plan)

        if not diffs:
            matches += 1
            print(" ✓")
        else:
            ld = legacy_plan.model_dump()
            fd = fc_plan.model_dump()
            if _is_acceptable_difference(ld, fd):
                acceptable += 1
                print(" ~ (acceptable)")
                if args.verbose:
                    for d in diffs:
                        print(f"    {d}")
            else:
                mismatches += 1
                print(f" ✗ ({len(diffs)} diffs)")
                if args.verbose or args.stop_on_first_diff:
                    for d in diffs:
                        print(d)
            if args.stop_on_first_diff and mismatches > 0:
                break

    print()
    print(
        f"Results: {matches} match, {acceptable} acceptable, "
        f"{mismatches} mismatch, {errors} error  (total {total})"
    )

    if mismatches == 0 and errors == 0:
        print("PASS — function calling path matches legacy for all benchmark questions")
        sys.exit(0)
    else:
        print(f"FAIL — {mismatches} mismatches, {errors} errors")
        sys.exit(1)


if __name__ == "__main__":
    main()
