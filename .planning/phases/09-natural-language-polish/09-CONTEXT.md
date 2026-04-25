# Phase 9: Natural Language Polish - Context

**Gathered:** 2026-04-25
**Status:** Ready for planning

<domain>
## Phase Boundary

Polish the LLM's final answer quality so outputs read as natural football-analyst prose. Specifically:

- Eliminate raw metric keys / robotic number dumps from answers (NLP-01).
- Improve contextual framing for comparison answers — home/away, bucket (top/bottom/Big Six), temporal (last N gameweeks) — within the existing answer-composition flow (NLP-02).
- Add at least one deterministic insight rule (e.g. goals vs xG) that the LLM can cite verbatim (NLP-03).

Out of scope for this phase: new tool capabilities, planner changes, additional benchmark questions, the WI-3..WI-5 robustness backlog (kept as a separate pre-phase concern), or any architectural changes to the Responses API + 4-mother-tools pipeline.

</domain>

<decisions>
## Implementation Decisions

### Polish layer (architecture)
- **D-01:** All NLP polish lives in the prompt layer. Phase 9 enriches `src/basic_stats/prompts/agent_system.yaml` (specifically the `HOW TO WRITE YOUR ANSWER` section) with style rules, good/bad examples, and an explicit insight-rule clause. **No new `verbalize.yaml`, no template renderer, no post-LLM rewrite step.** This honors the Phase 5 architecture (LLM composes answers from tool outputs) and treats the ROADMAP's "updated `verbalize.yaml`" wording as stale relative to the current code.
- **D-02:** Tool return shapes are NOT changed in this phase. The four mother tools (`query_player_stats`, `query_team_stats`, `query_ranking`, `get_league_standings` and the league-context helpers) keep their current contracts. Pre-rendered fields (`display_label`, `context_phrase`, `insight_phrase`) are explicitly rejected — they were considered and not chosen.

### NLP-01 — No raw metric keys
- **D-03:** NLP-01 is enforced with **prompt rules + a deterministic regex guard** in the eval layer. The guard lives in `evals/agent_benchmark.py` (or a sibling helper imported by it), runs against every benchmarked answer, and fails the case if any known raw token appears. No runtime retry, no in-agent post-processing — the guard is a measurement, not a behavior change.
- **D-04:** The raw-token list for the guard is derived from the `AVAILABLE STATS` section of `agent_system.yaml` (e.g. `total_goals`, `xg_total_p90`, `pass_accuracy_pct`, `total_goals_against`, `team_score`, `opponent_score`, `goal_contributions`, `metric_value`, etc.) plus a small list of known robotic patterns. The exact token set is Claude's discretion during planning; planner must derive it from the YAML, not hand-list it from memory.

### NLP-02 — Contextual framing
- **D-05:** Contextual framing for comparison answers (home/away, bucket, temporal) is delivered through **examples in the enriched prompt**, not locked phrase stems. The prompt includes 2-3 good/bad pairs per context type so the LLM picks consistent natural phrasing while keeping freedom to adapt to the question. Locking specific stems was considered and deferred.
- **D-06:** The prompt instructs the LLM to cite group categories using the canonical names from `docs/premier_league_2024_25_context.md` (e.g. "the Big Six", "Champions League qualifiers", "mid-table") rather than re-derived prose. This piggybacks on Phase 8 league-context work and is purely a wording rule, not a definition change.

### NLP-03 — Deterministic insight rule
- **D-07:** Phase 9 ships **exactly one** insight rule: **goals vs xG framing**, encoded as a prompt instruction with explicit thresholds:
  - If `goals ≥ xG + 1.0` → phrase as "finishing above expectation" (or close natural variants).
  - If `goals ≤ xG − 1.0` → phrase as "underperforming xG".
  - Otherwise → omit the insight; do not force a comment.
  Trigger: any answer where the LLM has both `goals` and `xg_total` (or `xg_total_p90` paired with `goals_p90`) for a single subject in the same response. The threshold is an explicit constant to lock determinism.
- **D-08:** Additional insight rules (shots vs shots-on-target conversion, pass accuracy framing, etc.) are explicitly out of scope and go to backlog. The success criterion only requires "at least one".

### Regression gate
- **D-09:** Phase 9 honors the post-closeout gate: `evals/agent_benchmark.py` faithfulness ≥ 0.95 (current baseline 59/61 = 0.967, run `post_residual_closeout_final`, 2026-04-23) **plus** a clean re-run of `docs/review/pre_phase9_uat_checklist.md` with zero raw-key signals and zero hallucinated values.
- **D-10:** The ROADMAP §Phase 9 success criterion #5 ("61/61 eval_runner.py benchmark") is treated as **stale**. `eval_runner.py` was deleted in Phase 5 (commit `92689d9d`) and is not being restored. Faithfulness + UAT replaces it. Update ROADMAP.md as part of Phase 9 closeout.

### Claude's Discretion
- Exact wording of new prompt rules and good/bad example pairs in `agent_system.yaml`.
- Token set for the NLP-01 regex guard (must be derived programmatically from `AVAILABLE STATS` rather than typed by hand).
- Whether the insight clause is added inline in `HOW TO WRITE YOUR ANSWER` or in a new short section right below it.
- Whether the eval guard reports per-case violations as faithfulness failures, or as a separate counter that must be 0.
- Concrete phrase stems for "finishing above expectation" / "underperforming xG" — both English and Spanish surface forms.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope and requirements
- `.planning/ROADMAP.md` §Phase 9 — Goal, dependencies, success criteria (note #5 is stale per D-10)
- `.planning/REQUIREMENTS.md` §NLP — NLP-01, NLP-02, NLP-03 acceptance criteria
- `.planning/STATE.md` — Current architectural state, post-closeout faithfulness baseline, pending WI-3..WI-5 status
- `.planning/PROJECT.md` — Groundedness rule (no invented values), sensitivity map for `agent_system.yaml`

### Implementation surface (the only files Phase 9 should touch)
- `src/basic_stats/prompts/agent_system.yaml` — Sole prompt file; HOW TO WRITE YOUR ANSWER section is the polish target
- `evals/agent_benchmark.py` — Where the NLP-01 regex guard plugs in
- `evals/faithfulness_judge.py` — Existing judge; guard runs alongside, not inside it

### Domain references the prompt cites verbatim
- `docs/premier_league_2024_25_context.md` — Group definitions (Big Six, Champions League qualifiers, mid-table). Prompt instructs LLM to use these names directly per D-06.

### UAT and benchmark contracts
- `docs/review/pre_phase9_uat_checklist.md` — UAT batería (22 questions, 11 areas) used as the second leg of the regression gate (D-09)
- `evals/random_questions.json` — 21-question robustness benchmark consumed by `agent_benchmark.py`
- `evals/runs/2026-04-23_18-19-20__post_residual_closeout_final/` — Current 59/61 baseline run; planner reads this to confirm starting point

### Related context (read for grounding, not edited in Phase 9)
- `docs/review/pre_phase9_robustness_backlog.md` — WI-1..WI-5 work items; WI-1 and WI-2 are merged, WI-3..WI-5 are pending and out of scope for Phase 9 (see Deferred section)
- `docs/review/pre_phase9_robustness_plan.md` — Notes WI-3 as a Phase 9 precondition; risk acknowledged, deferred per user decision
- `src/basic_stats/agent_tools.py` — Source of truth for current tool return shapes (do not change in Phase 9 per D-02)
- `src/basic_stats/agent.py` — Responses API loop; do not modify in Phase 9

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`agent_system.yaml`**: Already structured with `HOW TO WRITE YOUR ANSWER` — Phase 9 enriches this section in place rather than adding a new file.
- **`evals/agent_benchmark.py` + `faithfulness_judge.py`**: Existing eval harness. Adding the NLP-01 regex guard plugs in next to the faithfulness judge; the guard's signal can be merged into the same per-case verdict or reported separately.
- **`pre_phase9_uat_checklist.md`**: Already covers all NLP-01/NLP-02 surface (raw-key signal, framing categories, language variation). Reusable verbatim as the second regression gate; only the "Phase 9 raw-key signal — anotar pero no bloquear" row needs flipping to a hard-fail.
- **Phase 8 league context loader (`agent_prompt.py`)**: Already injects `{league_context}` into the system prompt with canonical category names. Phase 9 builds on top — D-06 just instructs the LLM to use those names.

### Established Patterns
- **LLM composes answers from tool outputs** (Phase 5 architecture). Polish must respect this contract: no template renderer, no post-LLM rewrite, no synchronous transformation of tool returns.
- **Prompt is the single source of style truth.** The current `HOW TO WRITE YOUR ANSWER` block is short; Phase 9 expands it but keeps the file readable (it is loaded on every request).
- **Eval-time guards are how this project measures correctness** (faithfulness judge, UAT checklist) — adding a regex guard fits the existing pattern.

### Integration Points
- **`agent_system.yaml` (HOW TO WRITE YOUR ANSWER section)**: The single edit point for D-01, D-05, D-06, D-07 prose.
- **`evals/agent_benchmark.py`**: One new helper (regex check) + wiring into the per-case loop. Output flows into the existing per-run JSON under a new key.
- **Token list derivation**: Read `agent_system.yaml` at eval time (or at module import), parse the `AVAILABLE STATS` block, build the regex from those tokens — keeps the guard in sync with the schema as new metrics are added.

### Anti-patterns to avoid
- Do not introduce `prompts/verbalize.yaml`. The roadmap text is stale; D-01 explicitly rules it out.
- Do not modify tool return shapes in `agent_tools.py` for cosmetic reasons (D-02). If a future phase wants pre-rendered fields, it is a separate decision.
- Do not add a runtime retry on raw-key detection (D-03). The guard is a measurement, not a behavior change.

</code_context>

<specifics>
## Specific Ideas

- **xG insight thresholds are explicit constants**, not LLM-judged ranges: `delta = goals - xg_total`; `delta ≥ +1.0` → above expectation; `delta ≤ −1.0` → underperforming; otherwise no comment. Lock this in the prompt verbatim.
- **The ROADMAP's "updated `verbalize.yaml`" wording is stale** and is being explicitly retired. Planner should add a note in ROADMAP.md §Phase 9 documenting this when closing the phase.
- **The regression gate already passes today** at 59/61 faithfulness (`post_residual_closeout_final`). Phase 9 must not regress that — the success bar is "stays at ≥ 0.95 faithfulness AND adds 0 raw-key signals AND adds 0 hallucinated insight phrasing".
- **Benchmark answers will get re-graded by the new guard**, so the 59/61 baseline may shift on the first run after Phase 9 lands. Planner should re-run `post_residual_closeout_final` with the guard active to capture the new baseline before any prompt edit, so before/after deltas are attributable.

</specifics>

<deferred>
## Deferred Ideas

### Out of scope for Phase 9 (kept for future phases / backlog)
- **Additional insight rules** beyond goals vs xG (shots vs shots-on-target, pass accuracy context, etc.) — explicitly deferred per D-08. Add to backlog when a second insight is needed.
- **Locked phrase stems for NLP-02 contexts** — D-05 keeps LLM discretion guided by examples. If post-Phase-9 telemetry shows phrasing drift, revisit with stems.
- **Tool-output shaping** (`display_label`, `context_phrase`, `insight_phrase` on tool returns) — considered and rejected for Phase 9; revisit if prompt-only enforcement proves insufficient after one production cycle.
- **`verbalize.yaml` template layer** — explicitly rejected. Re-introducing a template renderer would undo the Phase 5 architectural choice.
- **LLM-judge style eval** for naturalness scoring — not picked; the regex guard plus existing faithfulness judge are sufficient for the Phase 9 gate.
- **Restoring `eval_runner.py` for the 61/61 gate** — not picked; the runner was deleted in Phase 5 and the gate is replaced by the faithfulness + UAT pair (D-09).

### Pre-Phase-9 robustness backlog (separate scope, not Phase 9)
- **WI-3 — Arithmetic consistency** (P0 in robustness plan): the LLM occasionally writes a secondary cifra that doesn't match the tool output ("…which means 2 more goals than…"). The robustness plan flags this as a Phase 9 precondition. **Deferred per user decision** — the gray area was raised but not selected for discussion. Risk: Phase 9 generates more secondary phrases ("finishing above expectation", contextual framing) which amplify any latent arithmetic-consistency bugs. Mitigation: the new NLP-01 regex guard does not catch arithmetic contradictions, so this risk lands on the UAT re-run (D-09). Recommend handling WI-3 before merging Phase 9 to production.
- **WI-4 — Group-definition disambiguation** (P1): noted in the robustness plan as a Phase 9 precondition because Phase 9 cites group categories ("Big Six", "Champions League teams") in prose. D-06 mitigates this by forcing canonical names from the league context doc, but the underlying ambiguity in `docs/premier_league_2024_25_context.md` remains.
- **WI-5 — Context hygiene + TEAM.md refresh** (P2): unaffected by Phase 9.

</deferred>

---

*Phase: 09-natural-language-polish*
*Context gathered: 2026-04-25*
