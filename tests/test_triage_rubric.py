"""
tests/test_triage_rubric.py — Unit tests for evals/discovery/triage_rubric.py.

Covers 11-SPEC.md §4 semantics:
  - manual override via force_action_type hint
  - all 7 action-type rules
  - default fallthrough
  - unknown force value falls through to rule chain

Zero imports from src/basic_stats or duckdb.
"""
from __future__ import annotations

from evals.discovery.triage_rubric import classify, ACTION_TYPES


def test_action_types_has_seven_entries() -> None:
    """Sanity check: ACTION_TYPES tuple has exactly 7 entries."""
    assert len(ACTION_TYPES) == 7


def test_force_action_type_override() -> None:
    """Rule 1: force_action_type hint returns that type regardless of cluster contents."""
    cluster = {"category": "DIRECT_STATS", "guard_evidence": "raw_key"}
    result = classify(cluster, hints={"force_action_type": "deferred"})
    assert result == "deferred"


def test_fixture_issue_for_ambiguous_faithfulness() -> None:
    """Rule 2: faithfulness + AMBIGUOUS → fixture_issue."""
    cluster = {"category": "AMBIGUOUS", "guard_evidence": "faithfulness"}
    assert classify(cluster) == "fixture_issue"


def test_context_missing_for_unsupported_future_default() -> None:
    """Rule 3 (default): refuse_expected_but_answered + UNSUPPORTED_FUTURE → context_missing."""
    cluster = {
        "category": "UNSUPPORTED_FUTURE",
        "guard_evidence": "refuse_expected_but_answered",
    }
    assert classify(cluster) == "context_missing"


def test_agent_behavior_fix_for_unsupported_future_with_hint() -> None:
    """Rule 3 (hint): same cluster + needs_code_change=True → agent_behavior_fix_needed."""
    cluster = {
        "category": "UNSUPPORTED_FUTURE",
        "guard_evidence": "refuse_expected_but_answered",
    }
    assert classify(cluster, hints={"needs_code_change": True}) == "agent_behavior_fix_needed"


def test_regression_test_for_raw_key() -> None:
    """Rule 4: raw_key → regression_test_needed."""
    cluster = {"category": "DIRECT_STATS", "guard_evidence": "raw_key"}
    assert classify(cluster) == "regression_test_needed"


def test_non_actionable_for_demo_random_first_seen() -> None:
    """Rule 5: DEMO_RANDOM + seen_count <= 1 → non_actionable."""
    cluster = {"category": "DEMO_RANDOM", "guard_evidence": "other", "seen_count": 1}
    assert classify(cluster) == "non_actionable"


def test_context_missing_for_top6_faithfulness() -> None:
    """Rule 6: TOP6_VS_BIG6 + faithfulness → context_missing."""
    cluster = {"category": "TOP6_VS_BIG6", "guard_evidence": "faithfulness"}
    assert classify(cluster) == "context_missing"


def test_context_missing_for_champions_league_faithfulness() -> None:
    """Rule 6: CHAMPIONS_LEAGUE + faithfulness → context_missing."""
    cluster = {"category": "CHAMPIONS_LEAGUE", "guard_evidence": "faithfulness"}
    assert classify(cluster) == "context_missing"


def test_helper_tool_for_p90_faithfulness() -> None:
    """Rule 7: P90_METRICS + faithfulness → helper_tool_needed."""
    cluster = {"category": "P90_METRICS", "guard_evidence": "faithfulness"}
    assert classify(cluster) == "helper_tool_needed"


def test_deferred_default() -> None:
    """Rule 8: unrecognized combo → deferred."""
    cluster = {"category": "SOME_OTHER_CATEGORY", "guard_evidence": "some_other_evidence"}
    assert classify(cluster) == "deferred"


def test_unknown_force_value_falls_through() -> None:
    """Rule 1 guard: unknown force_action_type is ignored; falls through to rule chain."""
    # raw_key → regression_test_needed (rule 4), not the garbage force value
    cluster = {"category": "DIRECT_STATS", "guard_evidence": "raw_key"}
    result = classify(cluster, hints={"force_action_type": "garbage"})
    assert result == "regression_test_needed"


def test_demo_random_no_seen_count_falls_through() -> None:
    """Rule 5 guard: DEMO_RANDOM without seen_count in cluster dict → falls through to deferred."""
    cluster = {"category": "DEMO_RANDOM", "guard_evidence": "other"}
    # seen_count absent → rule 5 does not fire → deferred
    assert classify(cluster) == "deferred"


def test_hints_none_behaves_same_as_empty_dict() -> None:
    """hints=None and hints={} produce identical results."""
    cluster = {"category": "UNSUPPORTED_FUTURE", "guard_evidence": "refuse_expected_but_answered"}
    assert classify(cluster, hints=None) == classify(cluster, hints={})
