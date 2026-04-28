"""
synthetic_runner.py — Phase 10 synthetic UAT runner.

Runs `evals/synthetic/seed_questions.json` (or any fixture) through BasicStatsAgent,
applies existing guards (raw_key_guard, faithfulness_judge), and writes per-question
results plus a summary to `evals/runs/<timestamp>__synthetic_<label>/`.

Reuses (does NOT reimplement):
  - BasicStatsAgent (one instance per question — sharing causes Responses API 400s)
  - find_violations from evals.raw_key_guard
  - judge_faithfulness from evals.judges.faithfulness_judge
  - _ask_with_retry pattern from evals.agent_benchmark

Usage:
    uv run python -m evals.synthetic_runner --fixture evals/synthetic/seed_questions.json --label initial
    uv run python -m evals.synthetic_runner --dry-run        # validate fixture only, no agent calls
    uv run python -m evals.synthetic_runner --workers 5 --skip-judges
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Optional

import openai

sys.path.insert(0, ".")

from evals.raw_key_guard import find_violations
from evals.judges.faithfulness_judge import judge_faithfulness

# Lazy import — agent pulls in DuckDB; --dry-run path skips this.
def _import_agent():
    from src.basic_stats.agent import BasicStatsAgent
    return BasicStatsAgent

DEFAULT_FIXTURE = Path(__file__).parent / "synthetic" / "seed_questions.json"
RUNS_DIR = Path(__file__).parent / "runs"

_VALID_CATEGORIES = frozenset({
    "DIRECT_STATS", "RANKINGS", "COMPARISONS", "FOLLOW_UPS",
    "TOP6_VS_BIG6", "CHAMPIONS_LEAGUE", "P90_METRICS", "HOME_AWAY",
    "SPANISH_ENGLISH", "UNSUPPORTED_FUTURE", "AMBIGUOUS", "DEMO_RANDOM",
})
_VALID_BEHAVIORS = frozenset({"answerable", "refuse", "ambiguous_clarify"})
_VALID_LANGUAGES = frozenset({"en", "es"})

_REFUSAL_PHRASES = (
    "couldn't find", "could not find", "no data", "i wasn't able",
    "unable to", "i don't have", "no tengo", "no puedo",
)

_MAX_RETRIES = 4
_RETRY_BASE_DELAY = 5.0


def _load_fixture(path: Path) -> list[dict]:
    """Read fixture JSON. Raises ValueError on parse error."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Fixture {path} is not valid JSON: {exc}") from exc


def _validate_fixture(entries: list[dict]) -> list[str]:
    """Return list of error strings; empty list when fixture conforms to schema."""
    errors = []
    seen_ids = set()
    required_fields = {"id", "category", "language", "question", "expected_behavior"}
    for i, entry in enumerate(entries):
        missing = required_fields - entry.keys()
        if missing:
            errors.append(f"Entry {i}: missing fields {missing}")
            continue
        if entry["id"] in seen_ids:
            errors.append(f"Entry {i}: duplicate id {entry['id']}")
        seen_ids.add(entry["id"])
        if entry["category"] not in _VALID_CATEGORIES:
            errors.append(f"Entry {entry['id']}: invalid category {entry['category']}")
        if entry["language"] not in _VALID_LANGUAGES:
            errors.append(f"Entry {entry['id']}: invalid language {entry['language']}")
        if entry["expected_behavior"] not in _VALID_BEHAVIORS:
            errors.append(f"Entry {entry['id']}: invalid expected_behavior {entry['expected_behavior']}")
    return errors


def _split_turns(question: str) -> list[str]:
    """Multi-turn chains use '|' as turn separator (no spaces around it)."""
    return [t.strip() for t in question.split("|") if t.strip()]


def _ask_with_retry(agent, question: str) -> tuple[str, dict]:
    """Exponential backoff on openai.RateLimitError. Mirrors agent_benchmark._ask_with_retry."""
    delay = _RETRY_BASE_DELAY
    for attempt in range(_MAX_RETRIES):
        try:
            answer = agent.ask(question)
            return answer, dict(getattr(agent, "last_telemetry", {}))
        except openai.RateLimitError:
            if attempt == _MAX_RETRIES - 1:
                return f"ERROR: rate_limit after {_MAX_RETRIES} retries", {}
            time.sleep(delay)
            delay *= 2
        except Exception as exc:
            return f"ERROR: {exc}", {}
    return f"ERROR: rate_limit after {_MAX_RETRIES} retries", {}


def _looks_like_refusal(answer: str) -> bool:
    lowered = answer.lower()
    return any(p in lowered for p in _REFUSAL_PHRASES)


def _classify_failure(row: dict, expected_behavior: str) -> Optional[str]:
    """Return None if pass; otherwise a short guard_evidence string."""
    if row["answer"].startswith("ERROR:"):
        return "error"
    if not row.get("raw_key_passed", True):
        return "raw_key"
    if expected_behavior == "refuse" and not _looks_like_refusal(row["answer"]):
        return "refuse_expected_but_answered"
    if expected_behavior == "answerable" and _looks_like_refusal(row["answer"]):
        return "answer_expected_but_refused"
    if row.get("faithfulness_passed") is False:
        return "faithfulness"
    return None


def _evaluate_entry(entry: dict, BasicStatsAgent, skip_judges: bool) -> dict:
    """Run one entry (single-turn or multi-turn) and return a result row."""
    turns = _split_turns(entry["question"])
    is_multi_turn = len(turns) > 1

    agent = BasicStatsAgent()
    answers, telemetries = [], []
    for turn in turns:
        ans, tel = _ask_with_retry(agent, turn)
        answers.append(ans)
        telemetries.append(tel)
    final_answer = answers[-1]
    final_telemetry = telemetries[-1] if telemetries else {}

    raw_violations = find_violations(final_answer)

    # Faithfulness only when answerable + expected_values present (judge expects 'answer' key)
    faith_passed: Optional[bool] = None
    faith_reason = "skipped"
    if (
        not skip_judges
        and entry.get("expected_behavior") == "answerable"
        and entry.get("expected_values") is not None
        and not final_answer.startswith("ERROR:")
    ):
        faith_entry = {"answer": entry["expected_values"]}
        faith_result = judge_faithfulness(final_answer, faith_entry)
        faith_passed = faith_result.passed
        faith_reason = faith_result.reason

    row = {
        "id": entry["id"],
        "category": entry["category"],
        "language": entry["language"],
        "question": entry["question"],
        "is_multi_turn": is_multi_turn,
        "turn_answers": answers if is_multi_turn else None,
        "answer": final_answer,
        "expected_behavior": entry["expected_behavior"],
        "faithfulness_passed": faith_passed,
        "faithfulness_reason": faith_reason,
        "raw_key_violations": raw_violations,
        "raw_key_passed": len(raw_violations) == 0,
        "tool_calls": final_telemetry.get("tool_calls"),
        "iterations_used": final_telemetry.get("iterations_used"),
        "hit_max_iterations": final_telemetry.get("hit_max_iterations"),
        "failure_category": None,  # filled below
    }
    row["failure_category"] = _classify_failure(row, entry["expected_behavior"])
    return row


def run(
    fixture_path: Path = DEFAULT_FIXTURE,
    label: str = "initial",
    max_workers: int = 5,
    skip_judges: bool = False,
    dry_run: bool = False,
) -> Path:
    """Run synthetic UAT. Returns the output run-dir Path."""
    fixture_path = Path(fixture_path)
    entries = _load_fixture(fixture_path)
    errors = _validate_fixture(entries)
    if errors:
        raise ValueError("Fixture validation failed:\n  " + "\n  ".join(errors))

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    safe_label = re.sub(r"[^a-zA-Z0-9._-]+", "_", label.strip().lower()) or "initial"
    run_dir = RUNS_DIR / f"{timestamp}__synthetic_{safe_label}"
    run_dir.mkdir(parents=True, exist_ok=True)

    if dry_run:
        summary = {
            "fixture_path": str(fixture_path),
            "total_questions": len(entries),
            "dry_run": True,
            "validation": "ok",
        }
        (run_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        (run_dir / "results.json").write_text("[]", encoding="utf-8")
        print(f"[dry-run] {len(entries)} entries validated. Output: {run_dir}")
        return run_dir

    BasicStatsAgent = _import_agent()

    t0 = time.perf_counter()
    results: list[dict] = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(_evaluate_entry, e, BasicStatsAgent, skip_judges): e["id"]
            for e in entries
        }
        for fut in as_completed(futures):
            results.append(fut.result())
    elapsed = round(time.perf_counter() - t0, 1)

    # Re-sort to fixture order
    id_order = {e["id"]: i for i, e in enumerate(entries)}
    results.sort(key=lambda r: id_order.get(r["id"], 9999))

    # Aggregate summary
    by_category: dict = {}
    failures = 0
    raw_key_violations_total = 0
    for r in results:
        cat = r["category"]
        b = by_category.setdefault(cat, {"total": 0, "failures": 0, "raw_key_violations": 0})
        b["total"] += 1
        if r["failure_category"] is not None:
            b["failures"] += 1
            failures += 1
        if not r["raw_key_passed"]:
            b["raw_key_violations"] += 1
            raw_key_violations_total += 1

    summary = {
        "fixture_path": str(fixture_path),
        "total_questions": len(entries),
        "elapsed_seconds": elapsed,
        "max_workers": max_workers,
        "skip_judges": skip_judges,
        "dry_run": False,
        "total_failures": failures,
        "raw_key_violations_total": raw_key_violations_total,
        "by_category": by_category,
    }

    (run_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (run_dir / "results.json").write_text(
        json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"Synthetic run complete: {failures} failures / {len(entries)} questions in {elapsed}s")
    print(f"Output: {run_dir}")
    return run_dir


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Phase 10 synthetic UAT runner")
    p.add_argument("--fixture", default=str(DEFAULT_FIXTURE))
    p.add_argument("--label", default="initial")
    p.add_argument("--workers", type=int, default=5)
    p.add_argument("--skip-judges", action="store_true")
    p.add_argument("--dry-run", action="store_true",
                   help="Validate fixture only; no agent calls; exits 0 on valid")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    try:
        run(
            fixture_path=Path(args.fixture),
            label=args.label,
            max_workers=args.workers,
            skip_judges=args.skip_judges,
            dry_run=args.dry_run,
        )
        return 0
    except (ValueError, FileNotFoundError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
