# Phase 9: Natural Language Polish - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-25
**Phase:** 09-natural-language-polish
**Areas discussed:** Implementation layer for polish

---

## Gray-area selection

| Option | Description | Selected |
|--------|-------------|----------|
| Implementation layer for polish | Where polish lives — prompt vs new template vs hybrid (defines NLP-01 enforcement) | ✓ |
| Insight rule design (NLP-03) | Which insights ship and how (deterministic Python vs prompt rules) | |
| Contextual framing scope (NLP-02) | What counts as "contextual framing"; LLM discretion vs locked phrase stems | |
| Scope vs pending WI-3..WI-5 | Whether the pending robustness items get folded into Phase 9 | |

**User's choice:** Implementation layer for polish only. Other gray areas explicitly deferred.

---

## Implementation layer for polish

### Where should the NLP polish logic live?

| Option | Description | Selected |
|--------|-------------|----------|
| Prompt-only (Recommended) | Enrich `agent_system.yaml` HOW TO WRITE YOUR ANSWER with style rules, examples, and NLP-01 constraints. No new modules. | ✓ |
| Prompt + post-processor guardrail | Prompt enrichment plus a small post-hoc checker that scans the final answer for raw column tokens and forces a retry. | |
| Tool-output shaping | Extend the 4 mother tool returns with pre-rendered `display_label`, `context_phrase`, `insight_phrase` fields. | |
| `verbalize.yaml` template layer | Back-fit the original ROADMAP plan: add `prompts/verbalize.yaml` + a renderer that emits the final answer, bypassing the LLM for verbalization. | |

**User's choice:** Prompt-only.
**Notes:** Honors the Phase 5 architecture. The ROADMAP's "updated `verbalize.yaml`" wording is treated as stale.

---

### How should NLP-01 (no raw metric keys) be enforced?

| Option | Description | Selected |
|--------|-------------|----------|
| Prompt + eval guard (Recommended) | Prompt forbids raw keys; agent benchmark adds a deterministic regex check that scans every answer for known raw tokens and fails the case on hit. | ✓ |
| Prompt only | Trust the prompt + good/bad examples. No automated check. | |
| Prompt + runtime retry | Detect raw keys in the LLM's draft and force a retry within `agent.py`. | |

**User's choice:** Prompt + eval guard.
**Notes:** Guard lives in `evals/agent_benchmark.py` (or sibling helper) — measurement, not behavior change. Runtime retry rejected to avoid latency and infinite-loop risk.

---

### How should NLP-03 (insight rules) ship in this phase?

| Option | Description | Selected |
|--------|-------------|----------|
| One rule via prompt (Recommended) | Lock to a single deterministic insight: goals vs xG framing with explicit thresholds (above expectation if goals ≥ xG + 1.0; underperforming if goals ≤ xG − 1.0; otherwise omit). Encoded as a prompt rule. | ✓ |
| One rule via tool field | Add a Python helper that computes the insight phrase server-side and returns it as a tool field. | |
| Two rules via prompt | Goals vs xG plus a second rule (shots vs shots-on-target conversion, or pass accuracy framing). | |

**User's choice:** One rule via prompt.
**Notes:** Tool-field option rejected as inconsistent with the prompt-only architectural choice. Second rule deferred to backlog — success criterion only requires "at least one".

---

### Which regression gate does Phase 9 honor?

| Option | Description | Selected |
|--------|-------------|----------|
| Faithfulness 59/61 + UAT (Recommended) | Reuse current Phase-8/closeout gate: `evals/agent_benchmark.py` faithfulness ≥ 0.95 (currently 0.967), plus pre-Phase-9 UAT checklist re-run with 0 raw-key signals and 0 hallucinated values. | ✓ |
| Faithfulness + style judge | Above plus an LLM-judge eval scoring naturalness/no-raw-keys. | |
| Restore 61/61 eval_runner.py | Honor the ROADMAP text literally and restore the legacy benchmark. | |

**User's choice:** Faithfulness 59/61 + UAT.
**Notes:** `eval_runner.py` was deleted in Phase 5 (commit `92689d9d`); restoring it would be its own scope. ROADMAP success criterion #5 marked stale.

---

## Wrap-up

### "More questions, ready for context, or revisit a deferred area?"

| Option | Description | Selected |
|--------|-------------|----------|
| Ready for context | Write CONTEXT.md with the four locked decisions; remaining gray areas resolved by planner from prompt + roadmap. | ✓ |
| Discuss WI-3..WI-5 scope | Decide whether WI-3/WI-4/WI-5 fold into Phase 9 or stay separate. | |
| Discuss contextual framing (NLP-02) | Lock-stems vs LLM discretion for home/away/bucket/temporal phrasing. | |
| Discuss insight catalog beyond xG | Enumerate candidate insight rules for backlog. | |

**User's choice:** Ready for context.

---

## Claude's Discretion (carried into CONTEXT.md)

- Exact wording of new prompt rules and good/bad example pairs in `agent_system.yaml`.
- Token set for the NLP-01 regex guard (must be derived programmatically from `AVAILABLE STATS`).
- Whether the insight clause is added inline in `HOW TO WRITE YOUR ANSWER` or in a new short section right below it.
- Whether the eval guard reports per-case violations as faithfulness failures or as a separate counter that must be 0.
- Concrete phrase stems for "finishing above expectation" / "underperforming xG", in both English and Spanish.

## Deferred Ideas (carried into CONTEXT.md)

- Additional insight rules beyond goals vs xG.
- Locked phrase stems for NLP-02 contexts.
- Tool-output shaping (pre-rendered fields on tool returns).
- `verbalize.yaml` template layer (explicitly rejected).
- LLM-judge style eval.
- Restoring `eval_runner.py`.
- WI-3 (arithmetic consistency), WI-4 (group definitions), WI-5 (context hygiene) — robustness backlog, separate from Phase 9. WI-3 risk acknowledged in CONTEXT.md.
