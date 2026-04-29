"""
promote.py — Promotion-rules executor.

Implements Phase 11 SPEC §8: gate on seen_count >= ELIGIBILITY_THRESHOLD,
emit one of seven proposal artefacts, update the backlog entry status.

Hard rules:
- NEVER writes to src/basic_stats/*
- NEVER emits an uncommented xfail decorator — stubs are fully commented
- NEVER makes network calls (no openai, no requests, no urllib)
- NEVER shells out for VCS operations
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from evals.discovery.failure_backlog import (
    DEFAULT_BACKLOG_PATH,
    load_backlog,
    save_backlog,
)
from evals.discovery.triage_rubric import ACTION_TYPES

PROJECT_ROOT = Path(__file__).resolve().parents[2]  # repo root
DOCS_REVIEW = PROJECT_ROOT / "docs" / "review"
FIXTURE_FIXES = Path(__file__).parent / "fixture_fixes"
REGRESSIONS_FILE = PROJECT_ROOT / "tests" / "test_synthetic_regressions.py"
ELIGIBILITY_THRESHOLD = 2  # 11-SPEC.md §8


class PromotionError(RuntimeError):
    """Raised when an entry is not eligible for promotion or the action is unknown."""


def promote(backlog_entry_id: str, backlog_path: Path = DEFAULT_BACKLOG_PATH) -> Optional[Path]:
    """Emit the proposal artefact for the entry's recommended_action.

    Pre-conditions:
      - The entry exists in the backlog at backlog_path.
      - entry['seen_count'] >= ELIGIBILITY_THRESHOLD.
      - entry['recommended_action'] is one of the 7 enum values.

    Effects:
      - Emits the artefact path described in 11-SPEC.md §8 (or returns None for
        non_actionable / deferred).
      - Updates the backlog entry: status='promoted', promoted_to=<artefact path or None>.
      - Saves the backlog.

    Returns the artefact Path, or None for status-only updates.

    Raises PromotionError if seen_count < threshold or recommended_action is unknown/null.
    """
    backlog = load_backlog(backlog_path)
    entry = next(
        (e for e in backlog.get("entries", []) if e.get("id") == backlog_entry_id),
        None,
    )
    if entry is None:
        raise PromotionError(f"Entry {backlog_entry_id!r} not found in backlog")

    seen_count = entry.get("seen_count", 0)
    if seen_count < ELIGIBILITY_THRESHOLD:
        raise PromotionError(
            f"Entry {backlog_entry_id!r} not eligible: seen_count={seen_count} < {ELIGIBILITY_THRESHOLD}"
        )

    action = entry.get("recommended_action")
    if action not in ACTION_TYPES:
        raise PromotionError(
            f"Entry {backlog_entry_id!r} has invalid recommended_action: {action!r}"
        )

    artefact: Optional[Path] = None
    if action == "regression_test_needed":
        artefact = _emit_regression_test_stub(entry)
    elif action == "agent_behavior_fix_needed":
        artefact = _emit_followon_doc(entry, "follow_on")
    elif action == "context_missing":
        artefact = _emit_followon_doc(entry, "context_gap")
    elif action == "helper_tool_needed":
        artefact = _emit_followon_doc(entry, "tool_proposal")
    elif action == "fixture_issue":
        artefact = _emit_fixture_diff(entry)
    # non_actionable, deferred: no artefact — status-only update

    promoted_to = str(artefact) if artefact is not None else None
    _update_backlog_entry(backlog, backlog_entry_id, "promoted", promoted_to)
    save_backlog(backlog, backlog_path)
    return artefact


def _emit_regression_test_stub(entry: dict) -> Path:
    """Append a commented-xfail stub to tests/test_synthetic_regressions.py.

    The stub is COMMENTED (every line starts with '#'). Humans uncomment after
    the production fix lands. Returns REGRESSIONS_FILE.

    Stub contents (template):
      # @pytest.mark.xfail(reason="<sig> surfaced in <run_id>; promoted by Phase 11 LOOP-06")
      # def test_regression_<failure_signature_snake_case>():
      #     '''<failure_signature>'''
      #     answer = _ask_agent("<question for <qid>>")
      #     assert ...  # TODO: assert the failing condition explicitly
    """
    sig = entry.get("failure_signature", "unknown")
    run_id = entry.get("last_seen_run_id", "unknown_run")
    snake_sig = re.sub(r"[^a-z0-9]+", "_", sig.lower()).strip("_")
    qids = entry.get("question_ids", [])
    q_hint = qids[0] if qids else "UNKNOWN_ID"

    stub_lines = [
        "",
        f'# @pytest.mark.xfail(reason="{sig} surfaced in {run_id}; promoted by Phase 11 LOOP-06")',
        f"# def test_regression_{snake_sig}():",
        f"#     '''{sig}'''",
        f"#     answer = _ask_agent(\"<question for {q_hint}>\")",
        "#     assert ...  # TODO: assert the failing condition explicitly",
    ]
    stub = "\n".join(stub_lines) + "\n"
    with REGRESSIONS_FILE.open("a", encoding="utf-8") as fh:
        fh.write(stub)
    return REGRESSIONS_FILE


def _emit_followon_doc(entry: dict, kind: str) -> Path:
    """Write docs/review/<kind>_<signature>.md with the proposal template.

    kind in {'follow_on', 'context_gap', 'tool_proposal'} — chosen by the caller
    based on recommended_action.

    Creates DOCS_REVIEW/ if missing. Returns the file path.
    """
    sig = entry.get("failure_signature", "unknown")
    DOCS_REVIEW.mkdir(parents=True, exist_ok=True)
    path = DOCS_REVIEW / f"{kind}_{sig}.md"
    action = entry.get("recommended_action", "unknown")
    content = (
        f"# {kind}: {sig}\n\n"
        f"**failure_signature:** {sig}\n"
        f"**recommended_action:** {action}\n"
        f"**seen_count:** {entry.get('seen_count', '?')}\n"
        f"**last_seen_run_id:** {entry.get('last_seen_run_id', '?')}\n\n"
        "## Summary\n\n"
        "<!-- TODO: describe the issue -->\n\n"
        "## Proposed action\n\n"
        "<!-- TODO: describe the fix, context addition, or tool needed -->\n\n"
        "## Evidence\n\n"
        f"question_ids: {entry.get('question_ids', [])}\n\n"
        f"sample_answers: {entry.get('sample_answers', [])}\n"
    )
    path.write_text(content, encoding="utf-8")
    return path


def _emit_fixture_diff(entry: dict) -> Path:
    """Write a unified-diff suggestion to evals/discovery/fixture_fixes/<signature>.diff.

    Body is a placeholder template; humans edit it. Returns the file path.
    """
    sig = entry.get("failure_signature", "unknown")
    FIXTURE_FIXES.mkdir(parents=True, exist_ok=True)
    path = FIXTURE_FIXES / f"{sig}.diff"
    content = (
        f"# fixture_fix: {sig}\n"
        f"# failure_signature: {sig}\n"
        "# recommended_action: fixture_issue\n"
        f"# seen_count: {entry.get('seen_count', '?')}\n"
        "#\n"
        "# Placeholder diff. Replace with a real unified diff once the\n"
        "# fixture correction is identified.\n"
        "#\n"
        "--- a/evals/synthetic/seed_questions.json\n"
        "+++ b/evals/synthetic/seed_questions.json\n"
        "@@ -TODO,? +TODO,? @@\n"
        "-  TODO: remove/correct offending fixture entry\n"
        "+  TODO: replacement entry\n"
    )
    path.write_text(content, encoding="utf-8")
    return path


def _update_backlog_entry(
    backlog: dict, entry_id: str, status: str, promoted_to: Optional[str]
) -> dict:
    """In-place update; returns the modified backlog."""
    for entry in backlog.get("entries", []):
        if entry.get("id") == entry_id:
            entry["status"] = status
            entry["promoted_to"] = promoted_to
            break
    return backlog
