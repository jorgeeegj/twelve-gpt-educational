"""
tests/test_promote.py — Unit tests for evals/discovery/promote.py.

Covers 11-SPEC.md §8 promotion semantics:
  - Eligibility gate (seen_count threshold)
  - All 7 action-type emission paths
  - Backlog status/promoted_to update
  - Hard safety rules (no src/basic_stats writes, no active xfail, no network)

No src.basic_stats or duckdb imports. Uses tmp_path + monkeypatching for isolation.
"""
from __future__ import annotations

import json
import socket
import urllib.request
from pathlib import Path
from unittest.mock import patch

import pytest

import evals.discovery.promote as pm
from evals.discovery.promote import PromotionError, promote


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_backlog(tmp_path: Path, entry: dict) -> Path:
    """Write a minimal valid backlog JSON and return its path."""
    backlog = {"backlog_version": "1.0", "entries": [entry]}
    path = tmp_path / "backlog.json"
    path.write_text(json.dumps(backlog, indent=2), encoding="utf-8")
    return path


def _entry(
    entry_id: str = "BACKLOG_001",
    seen_count: int = 2,
    recommended_action: object = "regression_test_needed",
    sig: str = "direct_stats__faithfulness",
) -> dict:
    return {
        "id": entry_id,
        "failure_signature": sig,
        "category": "DIRECT_STATS",
        "guard_evidence": "faithfulness",
        "seen_count": seen_count,
        "status": "triaged",
        "recommended_action": recommended_action,
        "promoted_to": None,
        "first_seen_run_id": "run_01",
        "last_seen_run_id": "run_02",
        "seen_run_ids": ["run_01", "run_02"],
        "linked_campaign": None,
        "diagnosis": "",
        "notes": None,
        "question_ids": ["Q001"],
        "sample_answers": ["Sample answer text"],
    }


# ---------------------------------------------------------------------------
# Eligibility + action validation
# ---------------------------------------------------------------------------

def test_promote_raises_when_seen_count_below_threshold(tmp_path: Path) -> None:
    """Entry with seen_count=1 → PromotionError."""
    entry = _entry(seen_count=1)
    bp = _make_backlog(tmp_path, entry)
    with pytest.raises(PromotionError, match="not eligible"):
        promote("BACKLOG_001", backlog_path=bp)


def test_promote_raises_when_recommended_action_null(tmp_path: Path) -> None:
    """Entry with seen_count=3 and recommended_action=None → PromotionError."""
    entry = _entry(seen_count=3, recommended_action=None)
    bp = _make_backlog(tmp_path, entry)
    with pytest.raises(PromotionError, match="recommended_action"):
        promote("BACKLOG_001", backlog_path=bp)


# ---------------------------------------------------------------------------
# Emission paths
# ---------------------------------------------------------------------------

def test_promote_regression_test_needed_emits_commented_stub(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """All appended lines start with '#'; the signature appears in the stub."""
    reg_file = tmp_path / "test_synthetic_regressions.py"
    reg_file.write_text("# existing content\n", encoding="utf-8")
    monkeypatch.setattr(pm, "REGRESSIONS_FILE", reg_file)

    entry = _entry(recommended_action="regression_test_needed", sig="rankings__raw_key")
    bp = _make_backlog(tmp_path, entry)
    result = promote("BACKLOG_001", backlog_path=bp)

    assert result == reg_file
    lines_before = 1  # the one existing line
    all_lines = reg_file.read_text(encoding="utf-8").splitlines()
    new_lines = [l for l in all_lines[lines_before:] if l.strip()]  # skip blank
    assert all(l.startswith("#") for l in new_lines), f"Non-commented lines: {new_lines}"
    assert any("rankings__raw_key" in l for l in all_lines)


def test_promote_agent_behavior_fix_writes_followon(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """action=agent_behavior_fix_needed → docs/review/follow_on_<sig>.md emitted."""
    docs = tmp_path / "docs" / "review"
    monkeypatch.setattr(pm, "DOCS_REVIEW", docs)

    sig = "home_away__faithfulness"
    entry = _entry(recommended_action="agent_behavior_fix_needed", sig=sig)
    bp = _make_backlog(tmp_path, entry)
    result = promote("BACKLOG_001", backlog_path=bp)

    assert result is not None
    assert result.name == f"follow_on_{sig}.md"
    assert result.exists()

    backlog = json.loads(bp.read_text(encoding="utf-8"))
    assert backlog["entries"][0]["promoted_to"] == str(result)
    assert backlog["entries"][0]["status"] == "promoted"


def test_promote_context_missing_writes_context_gap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """action=context_missing → docs/review/context_gap_<sig>.md emitted."""
    docs = tmp_path / "docs" / "review"
    monkeypatch.setattr(pm, "DOCS_REVIEW", docs)

    sig = "top6_vs_big6__faithfulness"
    entry = _entry(recommended_action="context_missing", sig=sig)
    bp = _make_backlog(tmp_path, entry)
    result = promote("BACKLOG_001", backlog_path=bp)

    assert result is not None
    assert result.name == f"context_gap_{sig}.md"
    assert result.exists()


def test_promote_helper_tool_writes_tool_proposal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """action=helper_tool_needed → docs/review/tool_proposal_<sig>.md emitted."""
    docs = tmp_path / "docs" / "review"
    monkeypatch.setattr(pm, "DOCS_REVIEW", docs)

    sig = "p90_metrics__faithfulness"
    entry = _entry(recommended_action="helper_tool_needed", sig=sig)
    bp = _make_backlog(tmp_path, entry)
    result = promote("BACKLOG_001", backlog_path=bp)

    assert result is not None
    assert result.name == f"tool_proposal_{sig}.md"
    assert result.exists()


def test_promote_fixture_issue_writes_diff(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """action=fixture_issue → evals/discovery/fixture_fixes/<sig>.diff emitted."""
    fixes = tmp_path / "fixture_fixes"
    monkeypatch.setattr(pm, "FIXTURE_FIXES", fixes)

    sig = "ambiguous__faithfulness"
    entry = _entry(recommended_action="fixture_issue", sig=sig)
    bp = _make_backlog(tmp_path, entry)
    result = promote("BACKLOG_001", backlog_path=bp)

    assert result is not None
    assert result.name == f"{sig}.diff"
    assert result.exists()


def test_promote_non_actionable_returns_none_and_status_promoted(
    tmp_path: Path
) -> None:
    """action=non_actionable → returns None; backlog entry status='promoted', promoted_to=None."""
    entry = _entry(recommended_action="non_actionable")
    bp = _make_backlog(tmp_path, entry)
    result = promote("BACKLOG_001", backlog_path=bp)

    assert result is None
    backlog = json.loads(bp.read_text(encoding="utf-8"))
    assert backlog["entries"][0]["status"] == "promoted"
    assert backlog["entries"][0]["promoted_to"] is None


def test_promote_deferred_returns_none_and_status_promoted(
    tmp_path: Path
) -> None:
    """action=deferred → returns None; backlog entry status='promoted', promoted_to=None."""
    entry = _entry(recommended_action="deferred")
    bp = _make_backlog(tmp_path, entry)
    result = promote("BACKLOG_001", backlog_path=bp)

    assert result is None
    backlog = json.loads(bp.read_text(encoding="utf-8"))
    assert backlog["entries"][0]["status"] == "promoted"
    assert backlog["entries"][0]["promoted_to"] is None


# ---------------------------------------------------------------------------
# Safety rules
# ---------------------------------------------------------------------------

def test_promote_does_not_touch_src_basic_stats(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """After promotion, no file under src/basic_stats/ has been written."""
    agent_file = Path("src/basic_stats/agent.py")
    if not agent_file.exists():
        pytest.skip("src/basic_stats/agent.py not found — skipping mtime check")

    mtime_before = agent_file.stat().st_mtime_ns

    docs = tmp_path / "docs" / "review"
    monkeypatch.setattr(pm, "DOCS_REVIEW", docs)

    entry = _entry(recommended_action="context_missing")
    bp = _make_backlog(tmp_path, entry)
    promote("BACKLOG_001", backlog_path=bp)

    mtime_after = agent_file.stat().st_mtime_ns
    assert mtime_before == mtime_after, "src/basic_stats/agent.py was touched by promote()"


def test_promote_never_enables_xfail(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Emitting a regression stub adds NO active (uncommented) xfail decorators."""
    reg_file = tmp_path / "test_synthetic_regressions.py"
    reg_file.write_text(
        "import pytest\n\n"
        "# @pytest.mark.xfail(reason='example already commented')\n"
        "def test_placeholder(): pass\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(pm, "REGRESSIONS_FILE", reg_file)

    def _active_xfail_count(text: str) -> int:
        return sum(
            1 for line in text.splitlines()
            if not line.lstrip().startswith("#") and "@pytest.mark.xfail" in line
        )

    before = _active_xfail_count(reg_file.read_text(encoding="utf-8"))

    entry = _entry(recommended_action="regression_test_needed")
    bp = _make_backlog(tmp_path, entry)
    promote("BACKLOG_001", backlog_path=bp)

    after = _active_xfail_count(reg_file.read_text(encoding="utf-8"))
    assert after == before, f"Active xfail count increased from {before} to {after}"


def test_promote_does_not_call_network(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """promote() does not make network calls — patched socket/urlopen still succeed."""
    docs = tmp_path / "docs" / "review"
    monkeypatch.setattr(pm, "DOCS_REVIEW", docs)

    def _raise(*args, **kwargs):
        raise RuntimeError("Network call attempted by promote()")

    entry = _entry(recommended_action="context_missing")
    bp = _make_backlog(tmp_path, entry)

    with patch.object(socket, "socket", side_effect=_raise):
        with patch.object(urllib.request, "urlopen", side_effect=_raise):
            # Should complete without raising — no network call made
            result = promote("BACKLOG_001", backlog_path=bp)
            assert result is not None
