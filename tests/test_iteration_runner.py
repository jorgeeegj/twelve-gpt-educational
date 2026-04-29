"""
tests/test_iteration_runner.py — Unit tests for evals/discovery/iteration_runner.py.

Covers 11-SPEC.md §7 compare_runs semantics plus write_diff and the lazy-import
contract for run_campaign. The live runner is NOT invoked (requires DuckDB + OpenAI).

No src.basic_stats or BasicStatsAgent imports.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

import evals.discovery.iteration_runner as ir
from evals.discovery.iteration_runner import compare_runs, write_diff


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_run_dir(tmp_path: Path, name: str, clusters: list[dict]) -> Path:
    """Write a stub run directory with failure_clusters.json."""
    run_dir = tmp_path / name
    run_dir.mkdir()
    payload = {
        "run_id": name,
        "total_questions": 4,
        "total_failures": len(clusters),
        "clusters": clusters,
    }
    (run_dir / "failure_clusters.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )
    return run_dir


def _cluster(sig: str, qids: list[str]) -> dict:
    cat, guard = sig.split("__", 1) if "__" in sig else (sig, "unknown")
    return {
        "category": cat.upper(),
        "guard_evidence": guard,
        "failure_signature": sig,
        "count": len(qids),
        "question_ids": qids,
        "sample_answers": [],
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_compare_runs_no_failures_in_either(tmp_path: Path) -> None:
    """Both runs have empty clusters — all 4 result buckets are empty."""
    older = _make_run_dir(tmp_path, "run_old", [])
    newer = _make_run_dir(tmp_path, "run_new", [])
    diff = compare_runs(older, newer)
    assert diff["repeated"] == []
    assert diff["disappeared"] == []
    assert diff["mutated"] == []
    assert diff["new"] == []


def test_repeated_cluster_with_shared_question_id(tmp_path: Path) -> None:
    """Same signature in both runs with overlapping question_ids → entry in repeated."""
    sig = "direct_stats__faithfulness"
    older = _make_run_dir(tmp_path, "run_old", [_cluster(sig, ["Q001", "Q002"])])
    newer = _make_run_dir(tmp_path, "run_new", [_cluster(sig, ["Q001", "Q003"])])
    diff = compare_runs(older, newer)
    assert len(diff["repeated"]) == 1
    assert diff["repeated"][0]["signature"] == sig
    assert "Q001" in diff["repeated"][0]["question_ids"]
    assert diff["disappeared"] == []
    assert diff["new"] == []


def test_disappeared_cluster(tmp_path: Path) -> None:
    """Signature in older only → entry in disappeared."""
    sig = "rankings__faithfulness"
    older = _make_run_dir(tmp_path, "run_old", [_cluster(sig, ["Q010"])])
    newer = _make_run_dir(tmp_path, "run_new", [])
    diff = compare_runs(older, newer)
    assert len(diff["disappeared"]) == 1
    assert diff["disappeared"][0]["signature"] == sig
    assert diff["repeated"] == []
    assert diff["new"] == []


def test_new_cluster(tmp_path: Path) -> None:
    """Signature in newer only → entry in new."""
    sig = "comparisons__refuse_expected_but_answered"
    older = _make_run_dir(tmp_path, "run_old", [])
    newer = _make_run_dir(tmp_path, "run_new", [_cluster(sig, ["Q020"])])
    diff = compare_runs(older, newer)
    assert len(diff["new"]) == 1
    assert diff["new"][0]["signature"] == sig
    assert diff["repeated"] == []
    assert diff["disappeared"] == []


def test_mutated_question_id_changed_signature(tmp_path: Path) -> None:
    """Same question_id fails under different signatures in the two runs → entry in mutated."""
    qid = "Q_M1"
    older = _make_run_dir(tmp_path, "run_old", [_cluster("p90_metrics__faithfulness", [qid])])
    newer = _make_run_dir(tmp_path, "run_new", [_cluster("p90_metrics__raw_key", [qid])])
    diff = compare_runs(older, newer)
    assert len(diff["mutated"]) == 1
    m = diff["mutated"][0]
    assert m["question_id"] == qid
    assert m["older_signature"] == "p90_metrics__faithfulness"
    assert m["newer_signature"] == "p90_metrics__raw_key"


def test_mixed_buckets(tmp_path: Path) -> None:
    """Runs with at least one entry in each bucket → all four lists populated."""
    # repeated: sig_r in both with shared Q_R
    sig_r = "home_away__faithfulness"
    # disappeared: sig_d in older only
    sig_d = "follow_ups__faithfulness"
    # new: sig_n in newer only
    sig_n = "top6_vs_big6__faithfulness"
    # mutated: Q_M in both but different sigs
    sig_m_old = "rankings__faithfulness"
    sig_m_new = "rankings__raw_key"

    older_clusters = [
        _cluster(sig_r, ["Q_R1", "Q_R2"]),
        _cluster(sig_d, ["Q_D1"]),
        _cluster(sig_m_old, ["Q_M1"]),
    ]
    newer_clusters = [
        _cluster(sig_r, ["Q_R1", "Q_R3"]),
        _cluster(sig_n, ["Q_N1"]),
        _cluster(sig_m_new, ["Q_M1"]),
    ]

    older = _make_run_dir(tmp_path, "run_old", older_clusters)
    newer = _make_run_dir(tmp_path, "run_new", newer_clusters)
    diff = compare_runs(older, newer)

    assert any(e["signature"] == sig_r for e in diff["repeated"])
    assert any(e["signature"] == sig_d for e in diff["disappeared"])
    assert any(e["signature"] == sig_n for e in diff["new"])
    assert any(e["question_id"] == "Q_M1" for e in diff["mutated"])


def test_write_diff_writes_named_file(tmp_path: Path) -> None:
    """write_diff writes diff_against_<older_run_name>.json and content round-trips."""
    older = _make_run_dir(tmp_path, "run_A", [])
    newer = _make_run_dir(tmp_path, "run_B", [])
    diff = compare_runs(older, newer)

    path = write_diff(diff, newer)
    assert path.exists()
    assert path.name == "diff_against_run_A.json"
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert loaded == diff


def test_run_campaign_does_not_import_synthetic_runner_at_module_load() -> None:
    """Importing iteration_runner must not pull in synthetic_runner (lazy import guard)."""
    # If synthetic_runner was already imported in a prior test run, re-check via AST.
    import ast

    src = Path("evals/discovery/iteration_runner.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    top_imports = [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]
    for node in top_imports:
        module = getattr(node, "module", "") or ""
        assert "synthetic_runner" not in module, (
            f"synthetic_runner appears as a top-level import: {ast.dump(node)}"
        )
