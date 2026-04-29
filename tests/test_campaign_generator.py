"""
tests/test_campaign_generator.py — Unit tests for evals/discovery/campaign_generator.py.

Covers 11-SPEC.md §6 semantics:
  - count, schema validity, expected_behavior defaults
  - ID format, cluster-sourced notes, file writing, name sanitisation
  - synthetic_runner validation pass-through
  - LLM stub raises NotImplementedError

Zero imports from src/basic_stats or duckdb.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

import evals.discovery.campaign_generator as cg
from evals.discovery.campaign_generator import (
    generate_from_category,
    generate_from_cluster,
    generate_with_llm,
    write_campaign,
)


def test_generate_from_category_returns_count() -> None:
    """generate_from_category returns exactly count items."""
    qs = generate_from_category("DIRECT_STATS", 5)
    assert len(qs) == 5


def test_generate_from_category_schema_valid() -> None:
    """Every emitted dict has all required seed_questions.json fields."""
    required = {"id", "category", "language", "question", "expected_behavior"}
    qs = generate_from_category("RANKINGS", 4)
    for q in qs:
        assert required.issubset(q.keys()), f"Missing fields in: {q}"


def test_generate_unsupported_future_marks_refuse() -> None:
    """UNSUPPORTED_FUTURE entries have expected_behavior == 'refuse'."""
    qs = generate_from_category("UNSUPPORTED_FUTURE", 4)
    assert all(q["expected_behavior"] == "refuse" for q in qs)


def test_generate_ambiguous_marks_clarify() -> None:
    """AMBIGUOUS entries have expected_behavior == 'ambiguous_clarify'."""
    qs = generate_from_category("AMBIGUOUS", 3)
    assert all(q["expected_behavior"] == "ambiguous_clarify" for q in qs)


def test_generate_id_format() -> None:
    """All IDs match CAMP_<name>_<NNN> pattern."""
    qs = generate_from_category("DIRECT_STATS", 5)
    for q in qs:
        assert re.match(r"^CAMP_[a-z0-9_]+_\d{3}$", q["id"]), f"Bad ID: {q['id']}"


def test_generate_from_cluster_uses_cluster_category() -> None:
    """generate_from_cluster emits questions for the entry's category with notes referencing entry id."""
    entry = {
        "id": "BACKLOG_001",
        "category": "P90_METRICS",
        "failure_signature": "p90_metrics__faithfulness",
    }
    qs = generate_from_cluster(entry, count=3)
    assert all(q["category"] == "P90_METRICS" for q in qs)
    assert all("BACKLOG_001" in (q["notes"] or "") for q in qs)
    assert all("p90_metrics__faithfulness" in (q["notes"] or "") for q in qs)


def test_write_campaign_creates_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """write_campaign writes valid JSON to campaigns/<name>.json."""
    monkeypatch.setattr(cg, "CAMPAIGNS_DIR", tmp_path)
    qs = generate_from_category("DIRECT_STATS", 2)
    p = write_campaign(qs, "test_campaign")
    assert p.exists()
    loaded = json.loads(p.read_text(encoding="utf-8"))
    assert loaded == qs


def test_write_campaign_sanitises_name(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """write_campaign sanitises names with spaces and special chars."""
    monkeypatch.setattr(cg, "CAMPAIGNS_DIR", tmp_path)
    qs = generate_from_category("DIRECT_STATS", 1)
    p = write_campaign(qs, "Bad/Name with Spaces!")
    assert re.match(r"^[a-z0-9_]+\.json$", p.name), f"Unexpected filename: {p.name}"


def test_emitted_campaign_passes_synthetic_runner_validation() -> None:
    """Generated questions pass _validate_fixture — synthetic_runner consumes them unchanged."""
    from evals.synthetic_runner import _validate_fixture  # type: ignore[attr-defined]

    qs = generate_from_category("RANKINGS", 4)
    errors = _validate_fixture(qs)
    assert errors == [], f"Validation errors: {errors}"


def test_llm_stub_raises_not_implemented_when_use_llm_true() -> None:
    """generate_with_llm raises NotImplementedError when use_llm=True."""
    with pytest.raises(NotImplementedError, match="LLM-assisted generation deferred"):
        generate_with_llm("DIRECT_STATS", count=2, use_llm=True)


def test_llm_stub_delegates_when_use_llm_false() -> None:
    """generate_with_llm(use_llm=False) delegates to template mode."""
    qs = generate_with_llm("DIRECT_STATS", count=3, use_llm=False)
    assert len(qs) == 3
    assert all(q["category"] == "DIRECT_STATS" for q in qs)


def test_all_twelve_categories_generate_without_error() -> None:
    """Every category in the 12-category taxonomy generates at least 1 question."""
    categories = [
        "DIRECT_STATS", "RANKINGS", "COMPARISONS", "FOLLOW_UPS",
        "TOP6_VS_BIG6", "CHAMPIONS_LEAGUE", "P90_METRICS", "HOME_AWAY",
        "SPANISH_ENGLISH", "UNSUPPORTED_FUTURE", "AMBIGUOUS", "DEMO_RANDOM",
    ]
    for cat in categories:
        qs = generate_from_category(cat, 2)
        assert len(qs) == 2, f"Expected 2 questions for {cat}"


def test_generate_ids_are_unique_within_campaign() -> None:
    """IDs within a single generate_from_category call are unique."""
    qs = generate_from_category("HOME_AWAY", 6)
    ids = [q["id"] for q in qs]
    assert len(ids) == len(set(ids)), "Duplicate IDs found"
