"""Synthetic UAT Regression Tests — Phase 10 scaffold.

This file ships intentionally empty of real regression tests. Phase 10's contract
is *discovery before fixes*: a regression test is added here only after a failure
has been observed in a synthetic UAT run AND reproduced across two consecutive
runs.

Regression Test Workflow (from 10-SPEC.md section 7):

  1. A failure is observed in a `python -m evals.synthetic_runner` run. The
     clusterer records it in `evals/runs/<ts>__synthetic_<label>/failure_clusters.json`
     with a `failure_signature`, `category`, `guard_evidence`, and `question_ids`.
  2. The cluster has `count >= 1` AND is reproducible across two consecutive runs
     (re-run the runner, confirm the same `failure_signature` reappears).
  3. Author a test below named `test_regression_<failure_signature_snake_case>`
     that calls `BasicStatsAgent().ask(<question>)` and asserts the failing
     condition explicitly (e.g. `"total_goals" not in answer`, `"29" in answer`).
  4. Reference the cluster's `failure_signature`, the surfacing run-ids, and the
     question_ids in the test docstring.
  5. Decorate with `pytest.mark.xfail(reason="...")` if the production fix is
     deferred to a follow-on phase; remove the decorator once the fix lands.

Constraints:

- No regression tests are added pre-emptively for hypothetical failures.
- This file MUST NOT import `BasicStatsAgent`, `DuckDB`, or any live infra at
  module load time. Imports go inside the test function body when (and only
  when) a real regression is added.
- The placeholder test below proves pytest can collect this module without
  side effects. It must remain until the first real regression is added.

See:
  - `.planning/phases/10-self-generated-robustness-synthetic-uat/10-SPEC.md` (sections 6, 7)
  - `evals/synthetic_clusterer.py` (cluster shape — copy `failure_signature` here)
  - `evals/synthetic_runner.py` (run path — `failure_clusters.json` + `REPORT.md` consumers)
"""
from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Placeholder test — keep until the first real regression is authored below.
# ---------------------------------------------------------------------------

def test_regressions_scaffold_collectable():
    """Pytest collects this file; the synthetic regression scaffold is ready.

    When Plan 06 (or a later run) surfaces a confirmed cluster, replace this
    placeholder with a real regression test following the workflow in the
    module docstring above. The new test's name MUST start with
    `test_regression_` and its docstring MUST cite the cluster's
    `failure_signature` verbatim.
    """
    assert True


# ---------------------------------------------------------------------------
# Documented xfail example — kept as a commented reference for contributors.
#
# The block below is NOT executed (it is inside a comment). It shows the
# canonical shape a deferred-fix regression takes. Copy it, uncomment, fill
# in the placeholders, and remove this comment block once a real regression
# replaces this example.
# ---------------------------------------------------------------------------
#
# @pytest.mark.xfail(
#     reason="Production fix deferred to follow-on phase; "
#            "cluster '<failure_signature>' surfaced in runs <run_id_1>, <run_id_2>",
# )
# def test_regression_<failure_signature_snake_case>():
#     """Failing cluster: `<failure_signature>` (category=<CATEGORY>, guard=<GUARD>).
#
#     Surfaced in runs:
#       - evals/runs/<ts_1>__synthetic_<label>/failure_clusters.json
#       - evals/runs/<ts_2>__synthetic_<label>/failure_clusters.json
#     Question IDs: SYN_NNN, SYN_MMM
#
#     Reproduce manually:
#         uv run python -m evals.synthetic_runner --label regression_check
#     """
#     from src.basic_stats.agent import BasicStatsAgent
#
#     answer = BasicStatsAgent().ask("<question that surfaced the failure>")
#
#     # Assert the failing condition explicitly. Examples:
#     #   assert "total_goals" not in answer        # raw-key suppression
#     #   assert "29" in answer                      # numeric grounding
#     #   assert "couldn't find" in answer.lower()   # refusal expected
#     raise AssertionError("regression not yet fixed — remove xfail once fix lands")


# ---------------------------------------------------------------------------
# Helper available to future regressions. Imports `BasicStatsAgent` lazily so
# the module remains importable without a live DuckDB at collection time.
# ---------------------------------------------------------------------------

def _ask_agent(question: str) -> str:
    """Lazy-instantiate BasicStatsAgent and return its answer.

    Used by future regression tests so that pytest collection does not pay the
    DuckDB initialization cost when no real regressions are present.
    """
    from src.basic_stats.agent import BasicStatsAgent
    return BasicStatsAgent().ask(question)
