"""Unit tests for evals/synthetic_runner.py — Phase 10.

No live LLM, no DuckDB. Validates pure helpers + dry-run path.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from evals import synthetic_runner as sr


# --- _load_fixture ---------------------------------------------------------

def test_load_fixture_returns_list(tmp_path):
    p = tmp_path / "fix.json"
    p.write_text('[{"id": "X"}]', encoding="utf-8")
    assert sr._load_fixture(p) == [{"id": "X"}]


def test_load_fixture_raises_on_invalid_json(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("{not json", encoding="utf-8")
    with pytest.raises(ValueError):
        sr._load_fixture(p)


# --- _validate_fixture -----------------------------------------------------

_VALID_ENTRY = {
    "id": "SYN_001",
    "category": "DIRECT_STATS",
    "language": "en",
    "question": "How many goals?",
    "expected_behavior": "answerable",
    "expected_values": None,
}


def test_validate_fixture_accepts_valid_entry():
    assert sr._validate_fixture([_VALID_ENTRY]) == []


def test_validate_fixture_flags_missing_field():
    bad = {k: v for k, v in _VALID_ENTRY.items() if k != "category"}
    errors = sr._validate_fixture([bad])
    assert any("category" in e for e in errors)


def test_validate_fixture_flags_invalid_category():
    bad = dict(_VALID_ENTRY, category="NOT_A_CATEGORY")
    errors = sr._validate_fixture([bad])
    assert any("invalid category" in e for e in errors)


def test_validate_fixture_flags_duplicate_id():
    errors = sr._validate_fixture([_VALID_ENTRY, dict(_VALID_ENTRY)])
    assert any("duplicate id" in e for e in errors)


def test_validate_fixture_flags_invalid_language():
    bad = dict(_VALID_ENTRY, language="fr")
    errors = sr._validate_fixture([bad])
    assert any("invalid language" in e for e in errors)


# --- _split_turns ----------------------------------------------------------

def test_split_turns_single():
    assert sr._split_turns("hello") == ["hello"]


def test_split_turns_multi():
    assert sr._split_turns("a|b|c") == ["a", "b", "c"]


def test_split_turns_strips_whitespace():
    assert sr._split_turns("a | b ") == ["a", "b"]


def test_split_turns_drops_empty():
    assert sr._split_turns("a||b") == ["a", "b"]


# --- _classify_failure -----------------------------------------------------

def _row(**overrides):
    base = {
        "answer": "Salah has scored 29 goals.",
        "raw_key_passed": True,
        "raw_key_violations": [],
        "faithfulness_passed": True,
    }
    base.update(overrides)
    return base


def test_classify_failure_clean_passes():
    assert sr._classify_failure(_row(), "answerable") is None


def test_classify_failure_raw_key():
    r = _row(raw_key_passed=False, raw_key_violations=["total_goals"])
    assert sr._classify_failure(r, "answerable") == "raw_key"


def test_classify_failure_refuse_expected_but_answered():
    assert sr._classify_failure(_row(), "refuse") == "refuse_expected_but_answered"


def test_classify_failure_answer_expected_but_refused():
    r = _row(answer="I couldn't find that data.")
    assert sr._classify_failure(r, "answerable") == "answer_expected_but_refused"


def test_classify_failure_error_answer():
    r = _row(answer="ERROR: rate_limit")
    assert sr._classify_failure(r, "answerable") == "error"


def test_classify_failure_faithfulness_fails():
    r = _row(faithfulness_passed=False)
    assert sr._classify_failure(r, "answerable") == "faithfulness"


# --- run() --dry-run -------------------------------------------------------

def test_run_dry_run_creates_summary(tmp_path, monkeypatch):
    # Redirect RUNS_DIR to tmp_path so we don't pollute evals/runs/
    monkeypatch.setattr(sr, "RUNS_DIR", tmp_path / "runs")
    fixture = tmp_path / "fix.json"
    fixture.write_text(json.dumps([_VALID_ENTRY]), encoding="utf-8")

    run_dir = sr.run(fixture_path=fixture, label="unit_test", dry_run=True)
    assert run_dir.exists()
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    assert summary["dry_run"] is True
    assert summary["total_questions"] == 1


def test_run_raises_on_validation_error(tmp_path, monkeypatch):
    monkeypatch.setattr(sr, "RUNS_DIR", tmp_path / "runs")
    fixture = tmp_path / "fix.json"
    fixture.write_text(json.dumps([{"id": "X"}]), encoding="utf-8")  # missing fields
    with pytest.raises(ValueError, match="validation failed"):
        sr.run(fixture_path=fixture, label="unit_test", dry_run=True)


# --- Real seed fixture validates ------------------------------------------

def test_real_seed_fixture_passes_validation():
    """Guards the seed fixture in evals/synthetic/seed_questions.json."""
    fixture_path = Path("evals/synthetic/seed_questions.json")
    assert fixture_path.exists(), "seed fixture must exist (Plan 02 deliverable)"
    entries = sr._load_fixture(fixture_path)
    errors = sr._validate_fixture(entries)
    assert errors == [], f"seed fixture has validation errors: {errors}"
    # Coverage check: every category appears at least once
    categories = {e["category"] for e in entries}
    assert categories == sr._VALID_CATEGORIES, (
        f"missing categories: {sr._VALID_CATEGORIES - categories}"
    )
