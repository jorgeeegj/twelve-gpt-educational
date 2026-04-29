"""
triage_rubric.py — Deterministic cluster triage classifier.

Implements Phase 11 SPEC §4: maps a cluster dict to one of 7 action types.
No LLM call, no network I/O, no coupling to src.basic_stats.*.
Decision order matches triage_rubric.md "Decision Order" section 1:1.
"""
from __future__ import annotations

from typing import Literal

ACTION_TYPES = (
    "regression_test_needed",
    "agent_behavior_fix_needed",
    "context_missing",
    "helper_tool_needed",
    "fixture_issue",
    "non_actionable",
    "deferred",
)

ActionType = Literal[
    "regression_test_needed",
    "agent_behavior_fix_needed",
    "context_missing",
    "helper_tool_needed",
    "fixture_issue",
    "non_actionable",
    "deferred",
]


def classify(cluster: dict, hints: dict | None = None) -> ActionType:
    """Deterministic classification. No LLM call.

    Decision order (must match triage_rubric.md "Decision Order"):
      1. hints['force_action_type'] in ACTION_TYPES → return it (manual override).
      2. guard_evidence == 'faithfulness' and category == 'AMBIGUOUS' → 'fixture_issue'
      3. guard_evidence == 'refuse_expected_but_answered' and category == 'UNSUPPORTED_FUTURE':
         - hints.get('needs_code_change') is True → 'agent_behavior_fix_needed'
         - else → 'context_missing'
      4. guard_evidence == 'raw_key' → 'regression_test_needed'
      5. category == 'DEMO_RANDOM' and seen_count <= 1 → 'non_actionable'
         (note: cluster dict may not carry seen_count; fall through if missing)
      6. category in {'TOP6_VS_BIG6', 'CHAMPIONS_LEAGUE'} and guard_evidence == 'faithfulness' → 'context_missing'
      7. category == 'P90_METRICS' and guard_evidence == 'faithfulness' → 'helper_tool_needed'
      8. Default → 'deferred'
    """
    h = hints or {}
    category = cluster.get("category", "")
    guard = cluster.get("guard_evidence", "")

    # Rule 1: manual override
    forced = h.get("force_action_type")
    if forced in ACTION_TYPES:
        return forced  # type: ignore[return-value]

    # Rule 2: ambiguous faithfulness → fixture issue
    if guard == "faithfulness" and category == "AMBIGUOUS":
        return "fixture_issue"

    # Rule 3: unsupported future refusal → context or code fix
    if guard == "refuse_expected_but_answered" and category == "UNSUPPORTED_FUTURE":
        if h.get("needs_code_change") is True:
            return "agent_behavior_fix_needed"
        return "context_missing"

    # Rule 4: raw key → regression test
    if guard == "raw_key":
        return "regression_test_needed"

    # Rule 5: demo random, first-seen only → non-actionable
    seen_count = cluster.get("seen_count")
    if category == "DEMO_RANDOM" and seen_count is not None and seen_count <= 1:
        return "non_actionable"

    # Rule 6: top6/CL faithfulness → context missing
    if category in {"TOP6_VS_BIG6", "CHAMPIONS_LEAGUE"} and guard == "faithfulness":
        return "context_missing"

    # Rule 7: P90 faithfulness → helper tool needed
    if category == "P90_METRICS" and guard == "faithfulness":
        return "helper_tool_needed"

    # Rule 8: default
    return "deferred"
