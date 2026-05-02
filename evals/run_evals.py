"""evals/run_evals.py — run the three core eval suites and print one verdict.

What it tests:
  1. Tool correctness on 61 prepared questions (faithfulness >= 95%)
  2. Tool robustness on 21 random questions    (faithfulness >= 85%)
  3. Scope awareness on 12 OOS questions       (refuse == 100%)
  4. No raw column names leaked in any answer  (== 0)

What it does NOT test (verify manually):
  - Multi-turn memory beyond single follow-ups
  - Naturalness of phrasing (logged but not gated)
"""

import json
import subprocess
import sys
from pathlib import Path

from evals.synthetic_runner import run as run_synthetic

BENCHMARK_PATH = Path("evals/questions_benchmark.json")
RANDOM_PATH = Path("evals/random_questions.json")
SCOPE_PATH = Path("evals/scope_awareness_questions.json")
RUNS_DIR = Path("evals/runs")

PREPARED_GATE = 0.95
RANDOM_GATE = 0.85


def _benchmark(path: Path, label: str, random: bool = False) -> tuple[int, int, int]:
    """Run agent_benchmark as a subprocess to avoid asyncio event-loop conflicts."""
    cmd = [
        "uv",
        "run",
        "python",
        "-m",
        "evals.agent_benchmark",
        "--workers",
        "3",
        "--skip-judges",
        "--label",
        label,
    ]
    if random:
        cmd.append("--random")
    else:
        cmd += ["--benchmark", str(path)]
    subprocess.run(cmd, check=True)
    run_dirs = sorted(RUNS_DIR.glob(f"*__{label}"), key=lambda p: p.stat().st_mtime)
    summary = json.loads((run_dirs[-1] / "summary.json").read_text())
    pass_, total = summary["gates"]["faithfulness"]["score"].split("/")
    leaks = summary["gates"]["raw_keys"]["value"]
    return int(pass_), int(total), leaks


def _scope() -> tuple[int, int, int]:
    run_dir = run_synthetic(SCOPE_PATH, label="scope", max_workers=1, skip_judges=False)
    rows = json.loads((run_dir / "results.json").read_text())
    refused = sum(1 for r in rows if r.get("refuse_passed"))
    leaks = sum(1 for r in rows if not r.get("raw_key_passed", True))
    return refused, len(rows), leaks


def main():
    print("Suite 1/3 — prepared questions (61)")
    prep_pass, prep_total, prep_leaks = _benchmark(BENCHMARK_PATH, "eval_prepared")

    print("\nSuite 2/3 — random questions (21)")
    rand_pass, rand_total, rand_leaks = _benchmark(RANDOM_PATH, "eval_random", random=True)

    print("\nSuite 3/3 — scope awareness (12)")
    refused, scope_total, scope_leaks = _scope()

    prep_rate = prep_pass / prep_total
    rand_rate = rand_pass / rand_total
    leaks = prep_leaks + rand_leaks + scope_leaks

    passed = (
        prep_rate >= PREPARED_GATE
        and rand_rate >= RANDOM_GATE
        and refused == scope_total
        and leaks == 0
    )

    print("\n=== Twelve-GPT Eval ===")
    print(
        f"Prepared questions  : {prep_pass}/{prep_total} ({prep_rate:.0%})  gate >= {PREPARED_GATE:.0%}"
    )
    print(
        f"Random questions    : {rand_pass}/{rand_total} ({rand_rate:.0%})  gate >= {RANDOM_GATE:.0%}"
    )
    print(f"Scope refusals      : {refused}/{scope_total}                   gate 100%")
    print(f"Raw key leaks       : {leaks}                                   gate 0")
    print(f"\n{'PASS' if passed else 'FAIL'}")
    print("\nNot covered by this gate (verify manually if changed):")
    print(
        "  - Multi-turn memory: run evals/synthetic_runner.py with seed_questions.json FOLLOW_UPS"
    )
    print("  - Naturalness: see naturalness_score in evals/runs/<ts>__benchmark/results.json")
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
