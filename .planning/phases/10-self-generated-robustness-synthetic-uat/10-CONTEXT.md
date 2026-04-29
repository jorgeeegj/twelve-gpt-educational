# Phase 10: Self-Generated Robustness / Synthetic UAT — Context

**Gathered:** 2026-04-28
**Status:** Ready for planning
**Source:** Synthesized from `/gsd:add-phase 10` invocation message (2026-04-28). User confirmed synthesis path over interactive `/gsd:discuss-phase`.

<domain>
## Phase Boundary

Build a small, verifiable robustness loop on top of the existing `BasicStatsAgent` + eval stack:

1. **Generate** controlled synthetic / adversarial natural-language football-stats questions (LLM-assisted or seeded fixtures).
2. **Run** them through `BasicStatsAgent` using the existing eval entry points.
3. **Evaluate** outputs with the existing guards (`raw_key_guard`, `faithfulness_judge`, prompt-rule tests) plus lightweight new checks where the existing guards don't cover.
4. **Cluster** failures by category (route, language, qualifier type, etc.) into a digestible report.
5. **Convert** real, observed failures into regression tests **before** any production fix.

Phase 10 is **discovery infrastructure**. It does not change agent behavior. Production fixes for failures it surfaces are explicitly out of scope and will be opened as follow-on phases or hotfixes.

</domain>

<decisions>
## Implementation Decisions

### Methodology (locked)
- **Spec → Plan → Execute → Review.** Phase 10 produces SPEC.md and PLAN.md before any executable code.
- **Small, verifiable changes.** No broad refactors, no speculative abstractions.
- **Discovery before fixes.** Regression tests are written only after a real failure is observed and clustered.

### Scope coverage (locked — synthetic question categories)
The synthetic question set MUST exercise at least these categories. They map to known robustness surface area from Phases 5–9:
- **Direct stats** — single-entity, single-metric (e.g. "How many goals has Salah scored?")
- **Rankings** — top-N / bottom-N players or teams
- **Comparisons** — player-vs-player, team-vs-team, multi-entity
- **Follow-ups** — multi-turn chains where context carries (subject, filter, metric)
- **Top 6 vs Big Six** — semantic distinction between league-position bucket vs canonical Big Six set
- **Champions League** — all-routes (group stage + qualifiers + via league position) vs strictly league-position-derived qualifiers; Tottenham edge case explicitly covered
- **p90 metrics** — both base p90 (`*_p90`) and event-stat p90 in match-context
- **Home/away** — single-side and dual-side comparisons
- **Spanish/English (multilingüe)** — mirror coverage; especially Spanish away-wins, top-N phrasing
- **Unsupported / future-tense** — questions the agent should refuse rather than hallucinate (next matchday, next season, etc.)
- **Ambiguous phrasing** — under-specified entities, ambiguous metrics, missing context
- **Demo-style random** — questions in the spirit of `random_questions.json` (Ricardo / Álvaro / Jorge style)

### Reuse principle (locked)
- **Reuse `evals/raw_key_guard.py`** for raw-metric-key violations
- **Reuse `evals/judges/faithfulness_judge.py`** for grounded-answer scoring
- **Reuse `tests/test_prompt_rules.py`** patterns for prompt-rule assertions
- **Reuse `evals/agent_benchmark.py`** runner shape for the new synthetic runner
- New checks are added **only** where existing guards are inadequate (e.g. category-specific routing assertions).

### Artifact layout (locked)
- Synthetic question fixtures: `evals/synthetic/` (new directory). Format: JSON, mirroring `evals/questions_benchmark.json` shape.
- Runner script: `evals/synthetic_runner.py` (new). Records `{question, answer, tool_calls (if available), guard_results, failure_category}`.
- Run outputs: `evals/runs/<timestamp>__synthetic_<label>/` (already gitignored — do not stage).
- Failure cluster report: written by the runner under the same run directory; format = JSON + Markdown summary.
- Regression tests for confirmed failures: `tests/test_synthetic_regressions.py` (new, added incrementally).

### Workflow guardrails (locked)
- **Start by checking `git status`** before any change.
- **Never** run `git add .`. Stage explicit paths.
- **Never** commit `db/basic_stats.duckdb`, `.claude/` local files, `evals/runs/`, caches, or unrelated artifacts.
- **Show the exact diff** of any planning-doc modification before commit unless the GSD workflow explicitly requires the docs commit at that step.

### Exit gates (locked)
1. SPEC.md exists, names the failure categories and exit criteria.
2. Synthetic question generator + seed fixture committed and runnable.
3. Synthetic runner committed; one full run completes against `BasicStatsAgent` and produces a report.
4. At least one round of failure clustering completed; categories documented in the run output.
5. For each cluster of confirmed failures: a regression test exists in `tests/test_synthetic_regressions.py` (test may xfail if fix is deferred — but the test must exist).
6. Existing `tests/` suite remains green (160/160 baseline, give or take any new regression-tests that intentionally xfail).
7. STATE.md updated with Phase 10 status and exit-gate evidence.

### Claude's Discretion (open — to be decided in PLAN.md)
- LLM choice and prompt for the synthetic question generator (seed fixture vs live generation vs both).
- Exact failure-cluster taxonomy (heuristics vs LLM clustering).
- Whether the runner uses the existing `agent_benchmark.py` parallel `ThreadPoolExecutor` shape or a simpler serial loop for the first cut.
- Whether `failure_category` is assigned by the runner (heuristic) or by a small classifier judge.
- Naming of the synthetic question categories enum.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Eval stack (reuse — do not duplicate)
- `evals/agent_benchmark.py` — current parallel runner; shape to mirror for `synthetic_runner.py`
- `evals/smoke_test.py` — minimal exit-0/1 sanity check
- `evals/raw_key_guard.py` — raw-metric-key violation detector; reuse as-is
- `evals/judges/faithfulness_judge.py` — grounded-answer LLM judge; reuse as-is
- `evals/judges/naturalness_judge.py` — naturalness scoring; reuse if applicable
- `evals/questions_benchmark.json` — canonical 61-question benchmark; reference for fixture schema
- `evals/random_questions.json` — Ricardo/Álvaro/Jorge demo questions; reference for "demo-style random" category

### Agent surface (read-only — do not modify in Phase 10)
- `src/basic_stats/agent.py` — `BasicStatsAgent` entry point (`ask()`, `reset()`)
- `src/basic_stats/agent_tools.py` — 4 mother tools + helpers
- `src/basic_stats/agent_tool_schemas.py` — tool schemas (Responses API flat format)
- `src/basic_stats/duckdb_manager.py` — data access layer
- `src/basic_stats/prompts/agent_system.yaml` — system prompt with HOW TO USE TOOLS / HOW TO WRITE YOUR ANSWER

### Test suite (reuse patterns)
- `tests/test_agent_tools.py` — mother tool unit tests
- `tests/test_agent_parallel_tools.py` — parallel function_call handling regression test
- `tests/test_agent_prompt.py` — system prompt assertions (e.g. `{league_context}` injection)
- `tests/test_prompt_rules.py` — rule-based prompt assertions; pattern to mirror for synthetic regressions
- `tests/test_raw_key_guard.py` — raw-key guard unit tests
- `tests/test_fuzzy_resolve.py` — VSS entity resolution tests

### Domain context
- `docs/premier_league_2024_25_context.md` — static league standings, Big Six list, Champions League routes; source of truth for "top 6 vs Big Six" and "Tottenham" edge cases

### Roadmap & state
- `.planning/ROADMAP.md` — Phase 10 entry (currently a stub; PLAN.md will refine the goal text)
- `.planning/STATE.md` — Phase 10 entry already added; update on phase completion only
- `.planning/REQUIREMENTS.md` — REQ-IDs to be added by `/gsd:plan-phase` if appropriate

</canonical_refs>

<specifics>
## Specific Ideas

### Failure-discovery loop (concrete shape)
```
synthetic_questions.json  ──▶  synthetic_runner.py  ──▶  evals/runs/<ts>__synthetic_<label>/
                                  │
                                  ├── BasicStatsAgent.ask()       # reuse
                                  ├── raw_key_guard                # reuse
                                  ├── faithfulness_judge           # reuse
                                  ├── new: category_check          # only where needed
                                  └── new: failure_clusterer       # heuristic, lightweight
                                                                   │
                                                                   ▼
                                                       failure_clusters.json + REPORT.md
```

### Edge cases that must appear in the seed fixture
From the user's prior session work, these are known live-fire issues that closed under v2.0 and must stay closed:
- **Tottenham Hotspur Champions League qualification** — won via Europa League; not via league position. Synthetic fixture must include this.
- **Top 6 vs Big Six distinction** — "top 6" = current standings rank 1–6 (dynamic); "Big Six" = canonical {Arsenal, Chelsea, Liverpool, Man City, Man Utd, Tottenham} (static).
- **Comparison direction** — "more than" vs "less than" must be reflected correctly in the answer.
- **Subject exclusion** — when ranking opponents-faced, exclude the subject's own team.
- **Contextual p90** — `xg_p90` etc. must return ratios under match context, not raw sums.

### Spec ↔ Plan boundary
- **SPEC.md** lives under the phase dir as `10-SPEC.md`; describes WHAT the synthetic loop must do and WHAT failure categories must be covered. Written by the planner (or this orchestrator) before PLAN.md is finalized.
- **PLAN.md** lives under the phase dir as one or more `10-NN-PLAN.md` files; describes HOW each milestone is implemented. Generated by `gsd-planner`.

### Proposed milestones (from user — to be sequenced by planner)
1. Inventory current tests/evals and identify reusable guards (output: SPEC.md sections).
2. Design synthetic question categories and generation format (output: schema doc + seed fixture).
3. Implement a question-set generator OR commit a seed fixture without touching agent logic.
4. Implement `synthetic_runner.py` recording `{question, answer, tool_calls, guard_results}`.
5. Add lightweight failure clustering / reporting.
6. Add regression-test workflow for discovered failures.
7. Run verification + update STATE.md.

</specifics>

<deferred>
## Deferred Ideas

Explicitly out of scope for Phase 10 — do **not** plan or implement:
- **Visualizations** — no charts, no Streamlit UI changes.
- **Qualities integration** — no `qualities` framework hookup.
- **Production agent refactor** — `agent.py`, `agent_tools.py`, `agent_tool_schemas.py`, `duckdb_manager.py`, `agent_system.yaml` are read-only in Phase 10. Fixes for surfaced failures are separate work.
- **Auto-code self-modification** — the runner does not edit code. It produces reports.
- **Broad repo cleanup** — leave existing review docs (`docs/review/*.md`), prior eval runs, and unrelated pending changes alone.
- **New core agent behaviour** — no new tools, no new mother dispatches, no prompt edits to `agent_system.yaml`.
- **Auto-fix of clustered failures** — clusters become regression tests (possibly xfail), not patches.

</deferred>

---

*Phase: 10-self-generated-robustness-synthetic-uat*
*Context gathered: 2026-04-28 via synthesis from `/gsd:add-phase 10` message*
