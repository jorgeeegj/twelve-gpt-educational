# Cluster Triage Rubric

This rubric is consumed by `triage_rubric.classify(cluster, hints)` (implemented in `triage_rubric.py`). The classifier is **deterministic and LLM-free** — given the same `cluster` dict and `hints` dict, it always returns the same action type. Humans MAY override the classifier's verdict by setting `recommended_action` directly on the backlog entry before running `promote.py`.

---

## regression_test_needed

A well-understood failure where the agent produces a wrong answer for a known-correct query, and the fix is to lock the correct behaviour with a regression test in `tests/test_synthetic_regressions.py`.

**When it applies:**
- The cluster's `guard_evidence` is `raw_key` — the agent returned a value but the expected raw key was not present in the response.
- The category is a concrete stats type (`DIRECT_STATS`, `RANKINGS`, `P90_METRICS`, `TEAM_BUCKETS`, etc.) where ground truth is deterministic and a regression test can encode it.

**Worked example:**
- signature: `direct_stats__raw_key`
- category: `DIRECT_STATS`
- guard_evidence: `raw_key`
- sample question IDs: `SYN_005`, `SYN_007`
- The agent answered with paraphrased stats but omitted the expected label string; adding a `pytest.mark.xfail` stub (then removing the xfail after the fix) locks correct behaviour.

**Promotion artefact:** `tests/test_synthetic_regressions.py` (commented xfail stub appended)

---

## agent_behavior_fix_needed

A failure that requires a change to production code in `src/basic_stats/` or the agent's core reasoning path — not just a prompt tweak or context addition.

**When it applies:**
- The cluster's `guard_evidence` is `refuse_expected_but_answered` and `category` is `UNSUPPORTED_FUTURE`, **and** a human has confirmed (via `hints["needs_code_change"] = True`) that the agent's response stems from a logic error rather than missing context.
- The agent handles a supported category in a structurally incorrect way that documentation alone cannot fix.

**Worked example:**
- signature: `unsupported_future__refuse_expected_but_answered`
- category: `UNSUPPORTED_FUTURE`
- guard_evidence: `refuse_expected_but_answered`
- sample question IDs: `SYN_019`, `SYN_020` (Phase 10 live run)
- If investigation reveals the agent has a branch that incorrectly answers future-event questions instead of refusing, a code fix is needed. Set `hints["needs_code_change"] = True` before calling `classify()`.

**Promotion artefact:** `docs/review/follow_on_<signature>.md`

---

## context_missing

The agent fails because its system prompt or supporting documentation lacks a clarifying paragraph for this category or question type. Adding context (without changing code) is expected to resolve the failure.

**When it applies:**
- `guard_evidence` is `refuse_expected_but_answered` and `category` is `UNSUPPORTED_FUTURE` (default path — no `needs_code_change` hint).
- `category` is `TOP6_VS_BIG6` or `CHAMPIONS_LEAGUE` and `guard_evidence` is `faithfulness` — the agent answers but gets team membership or league affiliation wrong, suggesting it lacks the relevant factual context.

**Worked example:**
- signature: `unsupported_future__refuse_expected_but_answered`
- category: `UNSUPPORTED_FUTURE`
- guard_evidence: `refuse_expected_but_answered`
- sample question IDs: `SYN_019`, `SYN_020` (Phase 10 live run, default triage path)
- The agent answered a question about a future season instead of refusing. Adding a paragraph to the system prompt clarifying the agent's temporal scope (only historical data) is expected to fix this without a code change.

**Promotion artefact:** `docs/review/context_gap_<signature>.md`

---

## helper_tool_needed

The agent could answer correctly if it had access to a new tool or helper function that this version does not expose. The failure is architectural — not a prompt issue or code bug.

**When it applies:**
- `category` is `P90_METRICS` and `guard_evidence` is `faithfulness` — the agent attempts to answer but produces an incorrect percentile calculation, indicating it lacks a dedicated P90 helper.
- The failure pattern repeats across multiple question IDs and run IDs, ruling out a one-off hallucination.

**Worked example:**
- signature: `p90_metrics__faithfulness`
- category: `P90_METRICS`
- guard_evidence: `faithfulness`
- sample question IDs: `SYN_012`, `SYN_013`
- The agent consistently returns mean values instead of P90 values because no percentile-aware query helper is wired up. A new `get_p90(metric, filters)` helper would resolve it.

**Promotion artefact:** `docs/review/tool_proposal_<signature>.md`

---

## fixture_issue

The synthetic question itself is malformed — ambiguous wording, incorrect `expected_values`, or a guard condition that cannot be satisfied by any correct answer. The failure is in the test fixture, not the agent.

**When it applies:**
- `guard_evidence` is `faithfulness` and `category` is `AMBIGUOUS` — faithfulness failures on ambiguous questions are more likely to reflect poorly written questions than agent errors.
- The same signature produces failures across many distinct question IDs with no consistent agent-side pattern, suggesting the questions are the common factor.

**Worked example:**
- signature: `ambiguous__faithfulness`
- category: `AMBIGUOUS`
- guard_evidence: `faithfulness`
- sample question IDs: `SYN_031`, `SYN_032`
- Questions ask "who performed best last season?" without specifying a metric; any agent answer can be judged faithful or unfaithful depending on interpretation. The fixture needs a more precise `expected_behavior` field.

**Promotion artefact:** `evals/discovery/fixture_fixes/<signature>.diff`

---

## non_actionable

The failure is acceptable, inherent, or out of scope — not worth fixing. Examples include one-off randomness in demo questions or failures that are by design (the agent is supposed to refuse or hedge).

**When it applies:**
- `category` is `DEMO_RANDOM` and `seen_count <= 1` — a single occurrence of a failure in demo/random questions is not a reliable signal.
- The failure reflects correct agent behaviour (e.g., refusing a question the agent should refuse) that the guard incorrectly flagged.

**Worked example:**
- signature: `demo_random__faithfulness`
- category: `DEMO_RANDOM`
- guard_evidence: `faithfulness`
- sample question IDs: `SYN_099`
- The demo question asked for a "fun fact" and the guard expected a specific stat string; the agent's creative response is valid. Seen in a single run — non-actionable.

**Promotion artefact:** (none — backlog status updated to `non_actionable`)

---

## deferred

A valid failure that warrants attention but is intentionally delayed to a later phase or milestone. The issue is real, understood, and tracked, but the cost/benefit of fixing it now does not justify immediate action.

**When it applies:**
- The failure does not match any of the above concrete patterns — it is real but the right fix path is unclear.
- The failure is in a category or feature area slated for a future phase and acting on it now would create merge conflicts or scope creep.

**Worked example:**
- signature: `champions_league__raw_key`
- category: `CHAMPIONS_LEAGUE`
- guard_evidence: `raw_key`
- sample question IDs: `SYN_045`
- Champions League data integration is planned for Phase 13. The failure is real but fixing it now would conflict with the upcoming data-layer refactor. Deferring to Phase 13 prevents rework.

**Promotion artefact:** (none — backlog status updated to `deferred`)

---

## Decision Order

The classifier applies rules in this exact order and returns on the first match:

1. `hints["force_action_type"]` is a valid ACTION_TYPE string → return it immediately (manual override).
2. `guard_evidence == "faithfulness"` AND `category == "AMBIGUOUS"` → `fixture_issue`
3. `guard_evidence == "refuse_expected_but_answered"` AND `category == "UNSUPPORTED_FUTURE"`:
   - `hints.get("needs_code_change") is True` → `agent_behavior_fix_needed`
   - else → `context_missing`
4. `guard_evidence == "raw_key"` → `regression_test_needed`
5. `category == "DEMO_RANDOM"` AND `cluster.get("seen_count", 2) <= 1` → `non_actionable`
6. `category in {"TOP6_VS_BIG6", "CHAMPIONS_LEAGUE"}` AND `guard_evidence == "faithfulness"` → `context_missing`
7. `category == "P90_METRICS"` AND `guard_evidence == "faithfulness"` → `helper_tool_needed`
8. Default → `deferred`

Rules 6 and 7 are tested only after rule 4 (`raw_key`) fails; `faithfulness` failures for specific
categories are therefore only reached when `guard_evidence != "raw_key"`.
