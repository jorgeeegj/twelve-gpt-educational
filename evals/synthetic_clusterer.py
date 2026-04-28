"""
synthetic_clusterer.py — Phase 10 heuristic failure clusterer + Markdown report.

Groups synthetic_runner result rows by (category, guard_evidence) into clusters.
No LLM dependency — pure dict aggregation. LLM-based sub-clustering deferred
per 10-CONTEXT.md.

Public API:
    cluster_failures(results: list[dict], run_id: str = "") -> dict
    write_report(cluster_dict: dict, output_path: Path, summary: dict | None = None) -> None
"""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Optional


_SAMPLE_TRUNC = 200  # chars to keep from each sample answer


def _signature(category: str, guard_evidence: str) -> str:
    """Short, stable cluster signature. Heuristic: '<category_lower>__<guard>'."""
    return f"{category.lower()}__{guard_evidence}"


def cluster_failures(results: list[dict], run_id: str = "") -> dict:
    """Group failing result rows by (category, failure_category) into clusters.

    Returns dict matching 10-SPEC.md section 6.
    """
    failing = [r for r in results if r.get("failure_category") is not None]

    buckets: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in failing:
        key = (row["category"], row["failure_category"])
        buckets[key].append(row)

    clusters = []
    for (category, guard), rows in buckets.items():
        clusters.append({
            "category": category,
            "failure_signature": _signature(category, guard),
            "count": len(rows),
            "question_ids": [r["id"] for r in rows],
            "sample_answers": [r["answer"][:_SAMPLE_TRUNC] for r in rows[:3]],
            "guard_evidence": guard,
        })

    clusters.sort(key=lambda c: (-c["count"], c["category"]))

    return {
        "run_id": run_id,
        "total_questions": len(results),
        "total_failures": len(failing),
        "clusters": clusters,
    }


def write_report(
    cluster_dict: dict,
    output_path: Path,
    summary: Optional[dict] = None,
) -> None:
    """Write a human-readable Markdown report of clusters."""
    lines = []
    lines.append(f"# Synthetic UAT Report — {cluster_dict.get('run_id', '<unknown>')}")
    lines.append("")
    lines.append(f"- Total questions: **{cluster_dict['total_questions']}**")
    lines.append(f"- Total failures:  **{cluster_dict['total_failures']}**")
    if summary:
        if "elapsed_seconds" in summary:
            lines.append(f"- Elapsed: {summary['elapsed_seconds']}s")
        if "raw_key_violations_total" in summary:
            lines.append(f"- Raw-key violations: {summary['raw_key_violations_total']}")
    lines.append("")

    if not cluster_dict["clusters"]:
        lines.append("All questions passed. No clusters to report.")
        output_path.write_text("\n".join(lines), encoding="utf-8")
        return

    # Top-level cluster table
    lines.append("## Clusters (sorted by count desc)")
    lines.append("")
    lines.append("| # | Category | Guard | Count | Signature |")
    lines.append("|---|----------|-------|-------|-----------|")
    for i, c in enumerate(cluster_dict["clusters"], 1):
        lines.append(
            f"| {i} | {c['category']} | {c['guard_evidence']} | {c['count']} | `{c['failure_signature']}` |"
        )
    lines.append("")

    # Per-cluster details
    lines.append("## Cluster Details")
    lines.append("")
    for i, c in enumerate(cluster_dict["clusters"], 1):
        lines.append(f"### {i}. {c['failure_signature']}")
        lines.append("")
        lines.append(f"- Category: `{c['category']}`")
        lines.append(f"- Guard evidence: `{c['guard_evidence']}`")
        lines.append(f"- Count: {c['count']}")
        lines.append(f"- Question IDs: {', '.join(c['question_ids'])}")
        lines.append("")
        lines.append("**Sample answers (first 3, truncated):**")
        lines.append("")
        for j, sample in enumerate(c["sample_answers"], 1):
            lines.append(f"  {j}. `{sample}`")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("_Next step: review clusters, then add regression tests in "
                 "`tests/test_synthetic_regressions.py` (see 10-SPEC.md section 7)._")

    output_path.write_text("\n".join(lines), encoding="utf-8")
