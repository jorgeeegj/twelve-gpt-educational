"""
faithfulness_judge.py — checks that numbers in the agent's answer
match the ground-truth values from the benchmark.

Logic:
  1. Extract all numeric tokens from the answer text.
  2. Compare against the expected values from the benchmark entry.
  3. Pass if every expected value appears in the answer (within rounding tolerance).
  4. Also pass if the answer explicitly says "no data" / "couldn't find" when
     the expected answer has no numeric values (ambiguous/unanswerable questions).

This judge requires NO LLM calls — it is purely deterministic.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Numbers we allow to appear freely without matching expected values
# (meta-numbers like gameweek counts, team counts, etc.)
_META_WHITELIST = {6, 20, 38}

# Matches integers and decimals, including European thousands separators.
# Examples: 3420, 3.420, 3,420, 5.12, 0.85
_NUMBER_PATTERN = re.compile(r"\b\d{1,3}(?:[.,]\d{3})*(?:[.,]\d+)?\b|\b\d+(?:[.,]\d+)?\b")


def _parse_numbers_from_text(text: str) -> list[float]:
    """Extract all numeric values from a string.

    Handles both locale formats:
      - English decimals:  3420  /  5.12  /  3,420
      - European thousands: 3.420  (dot as thousands separator)

    Heuristic: if the pattern is X.YYY or X,YYY (exactly 3 decimal digits)
    treat it as a thousands-separated integer (3.420 → 3420), otherwise treat
    the separator as a decimal point.
    """
    results = []
    for m in _NUMBER_PATTERN.finditer(text):
        raw = m.group()
        # Detect European thousands: integer part >= 1 digit, then dot/comma,
        # then exactly 3 digits, AND the integer part itself is >= 1 (i.e. "3.420")
        # NOT "0.854" — a leading zero means it's a decimal, not thousands.
        eu_thousands = re.fullmatch(r"([1-9]\d*)[.,](\d{3})", raw)
        if eu_thousands:
            # Strip the separator → treat as plain integer (3.420 → 3420)
            value = float(raw.replace(".", "").replace(",", ""))
        else:
            # Normal: treat comma as thousands separator, dot as decimal
            value_str = raw.replace(",", "")
            try:
                value = float(value_str)
            except ValueError:
                continue
        results.append(value)
    return results


def _normalize(v) -> float | None:
    try:
        return round(float(v), 2)
    except (TypeError, ValueError):
        return None


def _values_match(expected: float, found: list[float], tolerance: float = 0.05) -> bool:
    for f in found:
        if abs(f - expected) <= tolerance:
            return True
    return False


@dataclass
class FaithfulnessResult:
    passed: bool
    reason: str
    expected_values: list[float]
    found_in_answer: list[float]
    missing: list[float]


def judge_faithfulness(answer: str, entry: dict) -> FaithfulnessResult:
    """
    Check whether all expected numeric values appear in the agent's answer.

    entry: one benchmark question dict with "answer" or "debug_expected" fields.
    """
    # Collect expected numeric values from the benchmark entry
    expected_values: list[float] = []

    raw_answer = entry.get("answer") or {}
    if isinstance(raw_answer, dict):
        for v in raw_answer.values():
            n = _normalize(v)
            if n is not None and n not in _META_WHITELIST:
                expected_values.append(n)

    # Also pull from debug_expected numeric leaves (skip internal metadata keys)
    _DEBUG_SKIP_KEYS = {"engine", "table", "metric"}
    # Skip any key that contains "p90", "pct", or "rate" as a segment (separated
    # by _ or .) — covers subset_p90, season_p90, bucket_a.p90, p90_away, etc.
    _DEBUG_SKIP_TOKENS = {"p90", "pct", "rate"}
    debug_exp = entry.get("debug_expected") or {}
    if isinstance(debug_exp, dict):
        for k, v in debug_exp.items():
            segments = re.split(r"[._]", k)
            if k in _DEBUG_SKIP_KEYS or _DEBUG_SKIP_TOKENS.intersection(segments):
                continue
            n = _normalize(v)
            if n is not None and n not in _META_WHITELIST:
                expected_values.append(n)

    # No expected values → nothing to check (question may be categorical)
    if not expected_values:
        return FaithfulnessResult(
            passed=True,
            reason="no_numeric_expectation",
            expected_values=[],
            found_in_answer=[],
            missing=[],
        )

    # Agent said it couldn't answer
    answer_lower = answer.lower()
    if any(
        phrase in answer_lower
        for phrase in ("couldn't find", "could not find", "no data", "i wasn't able", "unable to")
    ):
        return FaithfulnessResult(
            passed=False,
            reason="agent_refused",
            expected_values=expected_values,
            found_in_answer=[],
            missing=expected_values,
        )

    found = _parse_numbers_from_text(answer)
    missing = [e for e in expected_values if not _values_match(e, found)]

    passed = len(missing) == 0
    reason = "all_values_present" if passed else f"missing_values: {missing}"

    return FaithfulnessResult(
        passed=passed,
        reason=reason,
        expected_values=expected_values,
        found_in_answer=found,
        missing=missing,
    )
