"""Unit tests for evals/synthetic_clusterer.py — Phase 10."""
from __future__ import annotations

import json
from pathlib import Path

from evals.synthetic_clusterer import cluster_failures, write_report


def _row(id_, category, failure_category, answer="ans"):
    return {
        "id": id_,
        "category": category,
        "language": "en",
        "question": "q?",
        "answer": answer,
        "expected_behavior": "answerable",
        "faithfulness_passed": failure_category != "faithfulness",
        "raw_key_violations": [],
        "raw_key_passed": failure_category != "raw_key",
        "failure_category": failure_category,
    }


def test_cluster_empty():
    r = cluster_failures([])
    assert r == {"run_id": "", "total_questions": 0, "total_failures": 0, "clusters": []}


def test_cluster_no_failures():
    rows = [_row("SYN_001", "DIRECT_STATS", None)]
    r = cluster_failures(rows, run_id="run_x")
    assert r["total_failures"] == 0
    assert r["clusters"] == []
    assert r["run_id"] == "run_x"


def test_cluster_single_failure():
    rows = [_row("SYN_001", "DIRECT_STATS", "raw_key", answer="x has total_goals=29")]
    r = cluster_failures(rows)
    assert r["total_failures"] == 1
    assert len(r["clusters"]) == 1
    c = r["clusters"][0]
    assert c["category"] == "DIRECT_STATS"
    assert c["guard_evidence"] == "raw_key"
    assert c["count"] == 1
    assert c["question_ids"] == ["SYN_001"]
    assert c["failure_signature"] == "direct_stats__raw_key"


def test_cluster_groups_same_category_and_guard():
    rows = [
        _row("SYN_001", "DIRECT_STATS", "raw_key"),
        _row("SYN_002", "DIRECT_STATS", "raw_key"),
        _row("SYN_003", "DIRECT_STATS", "raw_key"),
    ]
    r = cluster_failures(rows)
    assert len(r["clusters"]) == 1
    assert r["clusters"][0]["count"] == 3
    assert sorted(r["clusters"][0]["question_ids"]) == ["SYN_001", "SYN_002", "SYN_003"]


def test_cluster_separates_by_guard_within_category():
    rows = [
        _row("SYN_001", "DIRECT_STATS", "raw_key"),
        _row("SYN_002", "DIRECT_STATS", "faithfulness"),
    ]
    r = cluster_failures(rows)
    assert len(r["clusters"]) == 2
    guards = {c["guard_evidence"] for c in r["clusters"]}
    assert guards == {"raw_key", "faithfulness"}


def test_cluster_separates_by_category_for_same_guard():
    rows = [
        _row("SYN_001", "DIRECT_STATS", "raw_key"),
        _row("SYN_002", "RANKINGS", "raw_key"),
    ]
    r = cluster_failures(rows)
    assert len(r["clusters"]) == 2
    cats = {c["category"] for c in r["clusters"]}
    assert cats == {"DIRECT_STATS", "RANKINGS"}


def test_cluster_sorted_by_count_desc():
    rows = (
        [_row(f"A_{i}", "RANKINGS", "raw_key") for i in range(5)]
        + [_row(f"B_{i}", "DIRECT_STATS", "raw_key") for i in range(2)]
    )
    r = cluster_failures(rows)
    assert r["clusters"][0]["count"] == 5
    assert r["clusters"][1]["count"] == 2


def test_cluster_sample_answers_truncated_to_200_chars():
    long_answer = "x" * 500
    rows = [_row("SYN_001", "DIRECT_STATS", "raw_key", answer=long_answer)]
    r = cluster_failures(rows)
    assert all(len(s) <= 200 for s in r["clusters"][0]["sample_answers"])


def test_write_report_no_failures(tmp_path):
    cluster_dict = cluster_failures([], run_id="run_zero")
    out = tmp_path / "REPORT.md"
    write_report(cluster_dict, out)
    text = out.read_text(encoding="utf-8")
    assert "All questions passed" in text
    assert "Synthetic UAT Report" in text


def test_write_report_with_failures(tmp_path):
    rows = [
        _row("SYN_001", "DIRECT_STATS", "raw_key", answer="answer with total_goals=29"),
        _row("SYN_002", "DIRECT_STATS", "raw_key", answer="more total_metric_value here"),
    ]
    cluster_dict = cluster_failures(rows, run_id="run_failing")
    out = tmp_path / "REPORT.md"
    write_report(cluster_dict, out, summary={"elapsed_seconds": 12.3, "raw_key_violations_total": 2})
    text = out.read_text(encoding="utf-8")
    assert "## Clusters" in text
    assert "DIRECT_STATS" in text
    assert "raw_key" in text
    assert "SYN_001" in text and "SYN_002" in text
    assert "12.3" in text  # elapsed shown


def test_runner_writes_clusters_and_report_in_dry_run_skips_clusterer(tmp_path, monkeypatch):
    """Dry-run path does NOT invoke clusterer — only summary.json + empty results.json."""
    from evals import synthetic_runner as sr
    monkeypatch.setattr(sr, "RUNS_DIR", tmp_path / "runs")
    fixture = tmp_path / "fix.json"
    fixture.write_text(json.dumps([{
        "id": "SYN_001",
        "category": "DIRECT_STATS",
        "language": "en",
        "question": "q?",
        "expected_behavior": "answerable",
        "expected_values": None,
    }]), encoding="utf-8")
    run_dir = sr.run(fixture_path=fixture, label="cluster_dry", dry_run=True)
    # In dry-run, clusterer outputs are NOT created
    assert not (run_dir / "failure_clusters.json").exists()
    assert not (run_dir / "REPORT.md").exists()
