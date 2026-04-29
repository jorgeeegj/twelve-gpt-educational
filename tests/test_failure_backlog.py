"""
tests/test_failure_backlog.py — Unit tests for evals/discovery/failure_backlog.py.

Covers 11-SPEC.md §3 semantics:
  - load/save round-trip
  - insert new entry (BACKLOG_001, seen_count=1, status='open')
  - counter-idempotency on run_id (same run does NOT bump seen_count)
  - seen_count increments only on distinct run_ids
  - question_ids set-union (sorted)
  - find_by_signature returns None for unknown signature

Zero imports from src/basic_stats or duckdb.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from evals.discovery.failure_backlog import (
    append_or_update,
    find_by_signature,
    load_backlog,
    next_id,
    save_backlog,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _seed_file(tmp_path: Path) -> Path:
    """Write a fresh seed backlog to a temp path and return the path."""
    p = tmp_path / "failure_backlog.json"
    p.write_text(json.dumps({"backlog_version": 1, "entries": []}), encoding="utf-8")
    return p


def _make_cluster(
    signature: str,
    question_ids: list[str],
    answer: str = "some answer text",
    category: str = "UNSUPPORTED_FUTURE",
    guard_evidence: str = "refuse_expected_but_answered",
) -> dict:
    return {
        "category": category,
        "failure_signature": signature,
        "guard_evidence": guard_evidence,
        "question_ids": question_ids,
        "sample_answers": [answer],
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_load_empty_backlog(tmp_path: Path) -> None:
    """Round-trip the seed file; assert version == 1 and entries == []."""
    p = _seed_file(tmp_path)
    backlog = load_backlog(path=p)
    assert backlog["backlog_version"] == 1
    assert backlog["entries"] == []


def test_append_inserts_new_entry(tmp_path: Path) -> None:
    """Given a synthetic cluster dict, append_or_update adds an entry with
    id='BACKLOG_001', seen_count=1, first_seen_run_id == last_seen_run_id, status='open'.
    """
    p = _seed_file(tmp_path)
    backlog = load_backlog(path=p)

    cluster = _make_cluster("unsupported_future__refuse_expected_but_answered", ["SYN_019"])
    append_or_update(backlog, cluster, run_id="run_A")
    save_backlog(backlog, path=p)

    reloaded = load_backlog(path=p)
    assert len(reloaded["entries"]) == 1
    entry = reloaded["entries"][0]
    assert entry["id"] == "BACKLOG_001"
    assert entry["seen_count"] == 1
    assert entry["first_seen_run_id"] == "run_A"
    assert entry["last_seen_run_id"] == "run_A"
    assert entry["seen_run_ids"] == ["run_A"]
    assert entry["status"] == "open"
    assert entry["failure_signature"] == "unsupported_future__refuse_expected_but_answered"


def test_append_same_run_id_does_not_bump_seen_count(tmp_path: Path) -> None:
    """Calling append_or_update twice with the SAME run_id produces seen_count == 1 (NOT 2).
    Re-processing the same run is counter-idempotent per 11-SPEC.md §3.
    """
    p = _seed_file(tmp_path)
    backlog = load_backlog(path=p)

    cluster = _make_cluster("some_category__raw_key", ["SYN_001"])
    run_id = "run_identical"

    append_or_update(backlog, cluster, run_id=run_id)
    append_or_update(backlog, cluster, run_id=run_id)  # same run_id — must NOT bump
    save_backlog(backlog, path=p)

    reloaded = load_backlog(path=p)
    assert len(reloaded["entries"]) == 1
    entry = reloaded["entries"][0]
    assert entry["seen_count"] == 1  # NOT 2
    assert entry["last_seen_run_id"] == run_id
    assert entry["seen_run_ids"] == [run_id]


def test_append_different_run_id_bumps_seen_count(tmp_path: Path) -> None:
    """Same cluster, DIFFERENT run_id → one entry, seen_count == 2,
    last_seen_run_id updated to the new run, first_seen_run_id unchanged.
    """
    p = _seed_file(tmp_path)
    backlog = load_backlog(path=p)

    cluster = _make_cluster("some_category__faithfulness", ["SYN_005"])
    append_or_update(backlog, cluster, run_id="run_first")
    append_or_update(backlog, cluster, run_id="run_second")  # distinct → bump
    save_backlog(backlog, path=p)

    reloaded = load_backlog(path=p)
    assert len(reloaded["entries"]) == 1
    entry = reloaded["entries"][0]
    assert entry["seen_count"] == 2
    assert entry["last_seen_run_id"] == "run_second"
    assert entry["first_seen_run_id"] == "run_first"
    assert entry["seen_run_ids"] == ["run_first", "run_second"]


def test_append_three_distinct_runs_seen_count_three(tmp_path: Path) -> None:
    """Same signature observed in three distinct run_ids in sequence
    → one entry, seen_count == 3, last_seen_run_id is the third run's id,
    first_seen_run_id is the first run's id.
    """
    p = _seed_file(tmp_path)
    backlog = load_backlog(path=p)

    cluster = _make_cluster("direct_stats__raw_key", ["SYN_010"])
    append_or_update(backlog, cluster, run_id="run_1")
    append_or_update(backlog, cluster, run_id="run_2")
    append_or_update(backlog, cluster, run_id="run_3")
    save_backlog(backlog, path=p)

    reloaded = load_backlog(path=p)
    assert len(reloaded["entries"]) == 1
    entry = reloaded["entries"][0]
    assert entry["seen_count"] == 3
    assert entry["last_seen_run_id"] == "run_3"
    assert entry["first_seen_run_id"] == "run_1"
    assert entry["seen_run_ids"] == ["run_1", "run_2", "run_3"]


def test_append_unions_question_ids(tmp_path: Path) -> None:
    """Second cluster (different run_id) has overlapping + new question_ids;
    the entry's question_ids is the set-union, sorted.
    """
    p = _seed_file(tmp_path)
    backlog = load_backlog(path=p)

    cluster_a = _make_cluster("rankings__raw_key", ["SYN_001", "SYN_002"])
    cluster_b = _make_cluster("rankings__raw_key", ["SYN_002", "SYN_003"])  # SYN_002 overlaps

    append_or_update(backlog, cluster_a, run_id="run_alpha")
    append_or_update(backlog, cluster_b, run_id="run_beta")
    save_backlog(backlog, path=p)

    reloaded = load_backlog(path=p)
    entry = reloaded["entries"][0]
    assert entry["question_ids"] == ["SYN_001", "SYN_002", "SYN_003"]  # sorted union


def test_find_by_signature_returns_none_for_unknown(tmp_path: Path) -> None:
    """Lookup of a signature not present returns None."""
    p = _seed_file(tmp_path)
    backlog = load_backlog(path=p)

    result = find_by_signature(backlog, "nonexistent__signature")
    assert result is None


def test_next_id_empty_backlog(tmp_path: Path) -> None:
    """next_id on empty backlog returns BACKLOG_001."""
    p = _seed_file(tmp_path)
    backlog = load_backlog(path=p)
    assert next_id(backlog) == "BACKLOG_001"


def test_next_id_after_two_entries(tmp_path: Path) -> None:
    """next_id returns one past the current maximum id."""
    p = _seed_file(tmp_path)
    backlog = load_backlog(path=p)

    append_or_update(backlog, _make_cluster("sig_a__raw_key", ["SYN_001"]), run_id="run_1")
    append_or_update(backlog, _make_cluster("sig_b__faithfulness", ["SYN_002"]), run_id="run_1")

    assert next_id(backlog) == "BACKLOG_003"


def test_append_replayed_older_run_id_does_not_bump_seen_count(tmp_path: Path) -> None:
    """A→B→A replay: replaying run_A after run_B must NOT bump seen_count.
    seen_count should be 2 (run_A + run_B), not 3.
    """
    p = _seed_file(tmp_path)
    backlog = load_backlog(path=p)

    cluster = _make_cluster("unsupported_future__refuse_expected_but_answered", ["SYN_019"])
    append_or_update(backlog, cluster, run_id="run_A")   # new entry, seen_count=1
    append_or_update(backlog, cluster, run_id="run_B")   # distinct → seen_count=2
    append_or_update(backlog, cluster, run_id="run_A")   # replay — must NOT bump
    save_backlog(backlog, path=p)

    reloaded = load_backlog(path=p)
    assert len(reloaded["entries"]) == 1
    entry = reloaded["entries"][0]
    assert entry["seen_count"] == 2                          # NOT 3
    assert entry["first_seen_run_id"] == "run_A"
    assert entry["last_seen_run_id"] == "run_B"              # unchanged after replay
    assert set(entry["seen_run_ids"]) == {"run_A", "run_B"}  # exactly two distinct runs


def test_load_backlog_raises_on_invalid_schema(tmp_path: Path) -> None:
    """load_backlog raises ValueError when required keys are missing."""
    p = tmp_path / "bad.json"
    p.write_text(json.dumps({"wrong_key": "oops"}), encoding="utf-8")
    with pytest.raises(ValueError):
        load_backlog(path=p)
