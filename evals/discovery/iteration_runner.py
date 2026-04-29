"""
iteration_runner.py — Iteration runner and compare-runs primitive.

Wraps synthetic_runner.run() for named campaigns and provides compare_runs()
to classify cluster differences between two run directories.

synthetic_runner is imported lazily inside run_campaign so this module can be
collected and its compare_runs / write_diff functions tested without DuckDB or
OpenAI installed.
"""
from __future__ import annotations

import json
from pathlib import Path


def run_campaign(
    campaign_path: Path,
    label: str,
    max_workers: int = 1,
    skip_judges: bool = False,
) -> Path:
    """Wrap synthetic_runner.run() for a named campaign file.

    Default max_workers=1 mirrors the Phase 10 lesson: BasicStatsAgent init is not
    concurrency-safe under DuckDB write-write conflicts. Callers may override but
    are warned in this docstring.

    Returns the run-output Path produced by synthetic_runner.run().
    """
    # Lazy import keeps this module collectable without DuckDB / openai installed.
    from evals.synthetic_runner import run as _synthetic_run
    return _synthetic_run(
        fixture_path=campaign_path,
        label=label,
        max_workers=max_workers,
        skip_judges=skip_judges,
        dry_run=False,
    )


def _load_clusters(run_dir: Path) -> dict:
    """Load failure_clusters.json from a run directory; raise FileNotFoundError if missing."""
    path = run_dir / "failure_clusters.json"
    if not path.exists():
        raise FileNotFoundError(f"failure_clusters.json not found in {run_dir}")
    return json.loads(path.read_text(encoding="utf-8"))


def _index_by_signature(clusters: list[dict]) -> dict[str, dict]:
    """Return {failure_signature: cluster_dict}."""
    return {c["failure_signature"]: c for c in clusters}


def _index_question_to_signature(clusters: list[dict]) -> dict[str, str]:
    """Return {question_id: failure_signature} for the first signature seen per id."""
    result: dict[str, str] = {}
    for c in clusters:
        sig = c["failure_signature"]
        for qid in c.get("question_ids", []):
            if qid not in result:
                result[qid] = sig
    return result


def compare_runs(older_dir: Path, newer_dir: Path) -> dict:
    """Classify cluster differences between two run directories.

    Returns dict matching 11-SPEC.md §7:
      {
        "older_run": str,
        "newer_run": str,
        "repeated":     [{"signature": str, "question_ids": [str]}],
        "disappeared":  [{"signature": str, "question_ids": [str]}],
        "mutated":      [{"question_id": str, "older_signature": str, "newer_signature": str}],
        "new":          [{"signature": str, "question_ids": [str]}],
      }

    Definitions (11-SPEC.md §7):
      - repeated: same failure_signature in both, with at least one shared question_id.
      - disappeared: signature in older, absent in newer (or same sig with no shared qids).
      - mutated: a question_id that appears in both runs' failure clusters under DIFFERENT
                 signatures. Note: pure pass→fail / fail→pass transitions are implicitly
                 captured by the new / disappeared buckets; this bucket captures same-qid
                 signature changes between two failing runs (cluster-based detection, no
                 results.json needed).
      - new: signature only in newer.
    """
    older_data = _load_clusters(older_dir)
    newer_data = _load_clusters(newer_dir)

    older_clusters = older_data.get("clusters", [])
    newer_clusters = newer_data.get("clusters", [])

    older_by_sig = _index_by_signature(older_clusters)
    newer_by_sig = _index_by_signature(newer_clusters)

    older_q_to_sig = _index_question_to_signature(older_clusters)
    newer_q_to_sig = _index_question_to_signature(newer_clusters)

    repeated: list[dict] = []
    disappeared: list[dict] = []
    new_clusters: list[dict] = []

    for sig, cluster in older_by_sig.items():
        if sig in newer_by_sig:
            older_qids = set(cluster.get("question_ids", []))
            newer_qids = set(newer_by_sig[sig].get("question_ids", []))
            shared = sorted(older_qids & newer_qids)
            if shared:
                repeated.append({"signature": sig, "question_ids": shared})
            else:
                disappeared.append({"signature": sig, "question_ids": sorted(cluster.get("question_ids", []))})
        else:
            disappeared.append({"signature": sig, "question_ids": sorted(cluster.get("question_ids", []))})

    for sig, cluster in newer_by_sig.items():
        if sig not in older_by_sig:
            new_clusters.append({"signature": sig, "question_ids": sorted(cluster.get("question_ids", []))})

    mutated: list[dict] = []
    for qid, older_sig in older_q_to_sig.items():
        if qid in newer_q_to_sig:
            newer_sig = newer_q_to_sig[qid]
            if older_sig != newer_sig:
                mutated.append({
                    "question_id": qid,
                    "older_signature": older_sig,
                    "newer_signature": newer_sig,
                })

    return {
        "older_run": older_dir.name,
        "newer_run": newer_dir.name,
        "repeated": repeated,
        "disappeared": disappeared,
        "mutated": mutated,
        "new": new_clusters,
    }


def write_diff(diff: dict, newer_dir: Path) -> Path:
    """Write `diff_against_<older_run>.json` to newer_dir.

    Returns the path written.
    """
    older_run = diff["older_run"]
    path = newer_dir / f"diff_against_{older_run}.json"
    path.write_text(json.dumps(diff, indent=2, ensure_ascii=False), encoding="utf-8")
    return path
