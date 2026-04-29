"""
failure_backlog.py — Durable file-based failure-memory backlog.

Implements Phase 11 SPEC §3: JSON storage + idempotent append/update/lookup.
No coupling to src.basic_stats.* or any LLM/network calls.
"""
from __future__ import annotations

import json
from pathlib import Path

DEFAULT_BACKLOG_PATH = Path(__file__).parent / "failure_backlog.json"
_SAMPLE_TRUNC = 200  # mirrors synthetic_clusterer._SAMPLE_TRUNC


def load_backlog(path: Path = DEFAULT_BACKLOG_PATH) -> dict:
    """Read and return the backlog dict. Raises ValueError on schema mismatch."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    if "backlog_version" not in raw or "entries" not in raw:
        raise ValueError(
            f"Backlog at {path} is missing required keys 'backlog_version' and/or 'entries'."
        )
    return raw


def save_backlog(backlog: dict, path: Path = DEFAULT_BACKLOG_PATH) -> None:
    """Write backlog to disk with stable key order (sort_keys=False, indent=2)."""
    path.write_text(json.dumps(backlog, indent=2, sort_keys=False), encoding="utf-8")


def find_by_signature(backlog: dict, failure_signature: str) -> dict | None:
    """Return the entry with matching failure_signature, or None."""
    for entry in backlog["entries"]:
        if entry.get("failure_signature") == failure_signature:
            return entry
    return None


def append_or_update(backlog: dict, cluster: dict, run_id: str) -> dict:
    """Idempotent insert/update. Returns the modified backlog (in-place mutation also performed).

    Rules per 11-SPEC.md §3 (truly distinct-run idempotent):
      - If cluster.failure_signature exists in backlog:
          * Merge question_ids (set-union, sorted).
          * Append AT MOST one new sample_answer (truncated to 200 chars; skip duplicates).
          * Backfill seen_run_ids if missing (conservative: from first/last_seen_run_id).
          * If run_id NOT in entry['seen_run_ids']:
                append run_id to seen_run_ids, bump seen_count by 1, set last_seen_run_id = run_id.
          * If run_id IS in entry['seen_run_ids']:
                do NOT bump seen_count and do NOT change last_seen_run_id.
                (Any previously-seen run_id is counter-idempotent — including A→B→A replays.)
      - If not: insert a new entry with monotonic id BACKLOG_<NNN>,
        first_seen_run_id=last_seen_run_id=run_id, seen_run_ids=[run_id], seen_count=1,
        status='open', recommended_action=None, promoted_to=None, linked_campaign=None,
        diagnosis='', notes=None.

    Invariant: seen_count for a given signature equals the number of DISTINCT
    run_id values processed for that signature, not the total number of calls.
    A→B→A replays produce seen_count=2, not 3.
    """
    sig = cluster["failure_signature"]
    entry = find_by_signature(backlog, sig)

    if entry is not None:
        # Merge question_ids (set-union, sorted)
        merged_ids = sorted(set(entry["question_ids"]) | set(cluster.get("question_ids", [])))
        entry["question_ids"] = merged_ids

        # Append at most one new sample_answer (truncated; skip duplicates)
        for ans in cluster.get("sample_answers", []):
            truncated = ans[:_SAMPLE_TRUNC]
            if truncated not in entry["sample_answers"]:
                entry["sample_answers"].append(truncated)
                break  # at most one new sample per call

        # Backfill seen_run_ids for entries created before this field existed
        if "seen_run_ids" not in entry:
            seeds: list[str] = []
            for rid in [entry.get("first_seen_run_id"), entry.get("last_seen_run_id")]:
                if rid and rid not in seeds:
                    seeds.append(rid)
            entry["seen_run_ids"] = seeds

        # True distinct-run idempotency: check the full history, not just last_seen_run_id
        if run_id not in entry["seen_run_ids"]:
            entry["seen_run_ids"].append(run_id)
            entry["seen_count"] += 1
            entry["last_seen_run_id"] = run_id
        # else: run_id already in history — do nothing (counter-idempotent)

    else:
        # Insert new entry
        new_entry: dict = {
            "id": next_id(backlog),
            "first_seen_run_id": run_id,
            "last_seen_run_id": run_id,
            "seen_run_ids": [run_id],
            "seen_count": 1,
            "category": cluster.get("category", ""),
            "failure_signature": sig,
            "guard_evidence": cluster.get("guard_evidence", ""),
            "question_ids": sorted(cluster.get("question_ids", [])),
            "sample_answers": [
                ans[:_SAMPLE_TRUNC] for ans in cluster.get("sample_answers", [])
            ],
            "diagnosis": "",
            "status": "open",
            "recommended_action": None,
            "promoted_to": None,
            "linked_campaign": None,
            "notes": None,
        }
        backlog["entries"].append(new_entry)

    return backlog


def next_id(backlog: dict) -> str:
    """Return the next monotonic id 'BACKLOG_<NNN>' (one greater than the max in entries)."""
    max_n = 0
    for entry in backlog["entries"]:
        entry_id = entry.get("id", "")
        if entry_id.startswith("BACKLOG_"):
            try:
                n = int(entry_id[len("BACKLOG_"):])
                if n > max_n:
                    max_n = n
            except ValueError:
                pass
    return f"BACKLOG_{max_n + 1:03d}"
