# Phase 11: Iterative Synthetic Discovery Loop v1 - Context

**Gathered:** 2026-04-29
**Status:** Ready for planning
**Source:** Inline brief from /gsd:add-phase + /gsd:plan-phase invocation (PRD Express equivalent — design decisions provided directly by the user)

<domain>
## Phase Boundary

Phase 11 turns the **infrastructure** built in Phase 10 (synthetic UAT runner + clusterer + regression scaffold + live-run pipeline) into a **repeatable iterative discovery loop**:

```
campaign generation
    → live/dry execution (existing synthetic_runner.py)
        → clustering (existing synthetic_clusterer.py)
            → diagnosis
                → triage (rubric → action type)
                    → backlog / regression / fix / tool / context recommendation
                        → targeted re-run
                            → compare-against-prior-runs
```

What this phase **delivers**:

1. A durable **failure-memory backlog format** (file-based, human-readable, machine-greppable) that accumulates discovered clusters and decisions across runs.
2. A **triage rubric** that classifies each cluster into one of seven action types (regression test / agent fix / context missing / helper-tool / fixture issue / non-actionable / deferred).
3. A minimal, reviewable **targeted campaign generator** that produces synthetic question sets from existing clusters, taxonomy categories, or known weak spots — file-based templates, not an autonomous agent.
4. An **iteration runner / compare-runs** capability that runs a named campaign and diffs current results against prior runs or prior clusters (repeats / disappearances / mutations).
5. **Promotion rules** that codify how repeated failures are promoted into `tests/test_synthetic_regressions.py`, follow-on fix plans, helper/tool/context recommendations, or documented deferred items.
6. **Verification + documentation:** one small targeted campaign seeded from the Phase 10 cluster `unsupported_future__refuse_expected_but_answered` (SYN_019/SYN_020) is run end-to-end through the loop, producing evidence — but the phase is NOT about fixing that cluster.

What this phase **explicitly does NOT deliver**:

- A fully autonomous self-improving system. This is **v1** of the loop.
- A production agent fix for `unsupported_future`. The cluster is the first seed *example*, not the focus.
- Any LLM-weight-update step. "Learning" here means the **ecosystem** around the agent improves (campaigns, failure memory, context, tool/helper recommendations, regression coverage, triage decisions).
- Modification of `src/basic_stats/*` source files unless a later checkpoint plan **explicitly** authorizes a narrow fix (default: read-only, same as Phase 10).
- Streamlit / UI changes.
- Visualization, qualities integration, or new core agent behaviour.

</domain>

<decisions>
## Implementation Decisions

### Read-only Constraint (default)

- **`src/basic_stats/*` is read-only** for the entire phase by default.
- A later plan in the wave structure MAY include a narrow checkpointed fix (the user must approve the checkpoint). It is NOT planned upfront — it is gated behind discovered evidence from the loop itself.

### File Layout

- New backlog/triage/campaign artifacts live under `evals/discovery/` (parallel to the existing `evals/synthetic/` from Phase 10).
- Suggested filenames (planner may adjust if a stronger naming convention exists):
  - `evals/discovery/failure_backlog.json` — durable cluster/decision memory (one entry per discovered cluster)
  - `evals/discovery/triage_rubric.md` — human-readable rubric document
  - `evals/discovery/triage_rubric.py` — small, deterministic Python helper that classifies a cluster against the rubric (returns one of the 7 action types)
  - `evals/discovery/campaigns/` — directory of named YAML/JSON campaign templates
  - `evals/discovery/campaigns/<name>.json` — individual campaign question sets (same schema as `seed_questions.json` so existing runner consumes them unchanged)
  - `evals/discovery/campaign_generator.py` — generator helper that emits a campaign file from a seed cluster / category / weak spot
  - `evals/discovery/iteration_runner.py` — wraps `synthetic_runner.run()` for named campaigns; performs run-vs-run diff
  - `evals/discovery/promote.py` — codifies promotion rules (repeated cluster → regression test stub / fix plan / context note)
- Run artifacts continue to land in `evals/runs/` and remain gitignored.
- No production code under `src/basic_stats/*` is touched.

### Reuse Existing Phase 10 Infrastructure

- `evals/synthetic_runner.run()` is the single execution entry point — wrap it; do NOT re-implement.
- `evals/synthetic_clusterer.cluster_failures()` produces clusters — wrap it; do NOT re-implement.
- The 12-category taxonomy from `10-SPEC.md` section 2 is the canonical category enum — reuse, do not redefine.
- The `failure_signature` format `<category_lower>__<guard>` from `synthetic_clusterer._signature` is the canonical signature — reuse.
- The seed fixture schema in `10-SPEC.md` section 3 is the canonical question schema — campaign templates MUST use it so `synthetic_runner` consumes them unchanged.

### Failure-Memory Backlog Schema (locked)

```json
{
  "backlog_version": 1,
  "entries": [
    {
      "id": "BACKLOG_<NNN>",
      "first_seen_run_id": "<run-dir-name>",
      "last_seen_run_id": "<run-dir-name>",
      "seen_count": 1,
      "category": "<one of the 12 taxonomy enum values>",
      "failure_signature": "<from synthetic_clusterer._signature()>",
      "guard_evidence": "<faithfulness | raw_key | refuse_expected_but_answered | other>",
      "question_ids": ["SYN_NNN"],
      "sample_answers": ["<truncated answer>"],
      "diagnosis": "<short free-text description of the suspected root cause>",
      "status": "<open | triaged | promoted | resolved | deferred | non_actionable>",
      "recommended_action": "<one of the 7 triage rubric action types>",
      "promoted_to": "<null | tests/test_synthetic_regressions.py:<test_name> | follow_on_phase:<id> | docs/<file>>",
      "notes": "<optional free-text>"
    }
  ]
}
```

The `id` is monotonic across all runs (never reused). The backlog is **append-only in spirit**: existing entries are updated in place when a cluster reappears (`last_seen_run_id`, `seen_count` bump, `status` may transition). Removal happens only when an entry is explicitly resolved or marked non-actionable AND the user has approved.

### Triage Rubric Action Types (locked enum)

The rubric classifies each cluster into exactly **one** of the following seven action types:

```
regression_test_needed       # add a test in tests/test_synthetic_regressions.py
agent_behavior_fix_needed    # production code change required (gated behind checkpoint)
context_missing              # system prompt / docs need a clarifying paragraph
helper_tool_needed           # new tool/helper function would unlock the answer
fixture_issue                # the synthetic question itself is malformed
non_actionable               # the failure is acceptable / inherent / out of scope
deferred                     # valid issue, intentionally delayed to a later phase
```

The rubric document (`triage_rubric.md`) explains each type with at least one example from the Phase 10 taxonomy. The rubric helper (`triage_rubric.py`) is a deterministic function: `classify(cluster_dict, hints: dict) -> action_type`. Its decision logic is small, transparent, and explicit (no LLM call required).

### Campaign Generator Boundaries

- The generator is **file-based and reviewable**. It emits a JSON file conforming to `seed_questions.json` schema. Humans inspect/edit before running.
- Inputs to the generator (any combination): a seed cluster (from backlog), a taxonomy category, a known weak spot description, an optional count.
- Output: a numbered campaign JSON under `evals/discovery/campaigns/`.
- It is **not** an autonomous agent. It does **not** call the OpenAI API directly. It emits questions either from templates (parameterized) or by routing to a small helper that uses the existing `BasicStatsAgent` / `responses` API once and writes the output to disk for review. The default path is template-based (zero API cost).
- Cost flag: campaign generator may incur OpenAI cost ONLY when the user explicitly opts in to LLM-assisted question generation; default mode is template-only / zero cost.

### Iteration Runner Compare Semantics

For two run directories `A` (older) and `B` (newer) over the same campaign:
- **repeated** failure: same `failure_signature` appears in both `A` and `B` for the same `question_ids` (or any overlap).
- **disappeared** failure: `failure_signature` in `A` is absent in `B`.
- **mutated** failure: a `question_id` in `B` is failing, was passing in `A` (or vice versa), OR same `question_id` failure changed signature.
- **new** failure: `failure_signature` only in `B`.

The iteration runner writes `evals/runs/<B-run-dir>/diff_against_<A-run-dir>.json` with the four lists. No cross-run state is persisted outside the runs directory.

### Promotion Rules (locked thresholds)

- A cluster is **eligible** for promotion when `seen_count >= 2` (i.e., reproduced in two consecutive runs of the same or similar campaign), matching the `10-SPEC.md` section 7 regression-workflow rule.
- `promote.py` is a small CLI / library that, given a backlog entry id, performs the action implied by `recommended_action`:
  - `regression_test_needed` → emits a stubbed test in `tests/test_synthetic_regressions.py` (commented xfail block, signature copied verbatim) — does NOT enable the test (humans uncomment).
  - `agent_behavior_fix_needed` → emits a `docs/review/follow_on_<signature>.md` capturing the cluster, sample answers, and proposed fix scope. Does NOT modify `src/basic_stats/`.
  - `context_missing` → emits `docs/review/context_gap_<signature>.md` with the missing context paragraph proposal.
  - `helper_tool_needed` → emits `docs/review/tool_proposal_<signature>.md`.
  - `fixture_issue` → flags the offending fixture entry; emits a unified-diff suggestion under `evals/discovery/fixture_fixes/<signature>.diff`.
  - `non_actionable` / `deferred` → updates backlog status only; emits no artefact.

Promotion is a **manual**, human-approved gate. `promote.py` writes proposals — it never edits production code, never enables xfail-marked tests, and never opens PRs.

### Verification Campaign

- The Wave 6 verification campaign is **small** (target: 4–8 questions). It is seeded from the Phase 10 backlog entry for `unsupported_future__refuse_expected_but_answered` (SYN_019/SYN_020).
- The campaign exercises the loop end-to-end: campaign generation → run → cluster → backlog update → triage → promotion proposal.
- Evidence delivered: a campaign file under `evals/discovery/campaigns/`, a run directory under `evals/runs/` (gitignored, NOT staged), an updated `failure_backlog.json` with at least one entry, and a `docs/review/follow_on_*.md` or equivalent promotion artefact.
- The phase does **NOT** assert that the agent's behaviour for `unsupported_future` improves. The phase asserts the loop **observes, classifies, and routes** the failure correctly.

### Constraints carried over from Phase 10

- `evals/runs/` is gitignored. Verify with `git check-ignore evals/runs/` before any commit.
- Never commit `db/basic_stats.duckdb`.
- Never stage `.claude/settings.local.json` or `.planning/config.json` unless a plan explicitly states otherwise.
- Never stage `docs/review/*` files accidentally — only when promotion explicitly emitted them and the user approved staging.
- Stage by **explicit paths only**. No `git add .`. No `git add -A`. No `git add <directory>` shortcuts that pull in unintended siblings.
- Plans MUST cite Phase 10 artefacts (`10-SPEC.md`, `synthetic_runner.py`, `synthetic_clusterer.py`, `seed_questions.json`, `test_synthetic_regressions.py`) when reusing them — link with relative paths.

### Wave Structure (7 waves, planner may refine)

| Wave | Plan | Deliverables | Requirement | Production code? | OpenAI cost? | Autonomous? |
|------|------|--------------|-------------|------------------|--------------|-------------|
| 1 | 11-01 Phase 11 SPEC | `11-SPEC.md` — authoritative contract for plans 11-02..11-07. Locks artefact paths, schemas, action-type enum, exit gates (mirrors how Plan 10-01 wrote `10-SPEC.md`). | LOOP-01 | No | No | Autonomous |
| 2 | 11-02 Failure Memory / Discovery Backlog | `evals/discovery/failure_backlog.json` (initial empty/seed), backlog schema doc, helper module (read/append/update/lookup-by-signature), unit tests | LOOP-02 | No | No | Autonomous |
| 3 | 11-03 Cluster Triage Rubric | `evals/discovery/triage_rubric.md` (human doc), `evals/discovery/triage_rubric.py` (deterministic classifier), unit tests covering all 7 action types | LOOP-03 | No | No | Autonomous |
| 4 | 11-04 Targeted Campaign Generator | `evals/discovery/campaign_generator.py`, `evals/discovery/campaigns/.gitkeep`, template strings, unit tests, README (template-default + opt-in LLM mode) | LOOP-04 | No | No (template default); opt-in only | Autonomous |
| 5 | 11-05 Iteration Runner / Compare Runs | `evals/discovery/iteration_runner.py` (wraps `synthetic_runner.run()`), `diff_against_*.json` writer, unit tests fed by two stub run directories | LOOP-05 | No | No (tests use stub directories, not live runner) | Autonomous |
| 6 | 11-06 Promotion Rules | `evals/discovery/promote.py`, promotion-proposal templates, unit tests covering each of the 7 action types' emission paths; never enables xfail tests; never edits production code | LOOP-06 | No (emits stubs to `tests/test_synthetic_regressions.py` and proposals to `docs/review/`) | No | Autonomous |
| 7 | 11-07 Verification + Documentation | One small targeted campaign file (4–8 questions) seeded from `unsupported_future__refuse_expected_but_answered`, one live small run via `synthetic_runner`, backlog entry update, promotion-artefact emission, STATE.md update, ROADMAP.md tick, REQUIREMENTS.md tick, 11-07-SUMMARY.md | LOOP-07 | No (read-only on `src/basic_stats/`) | YES (live small run, limited to ≤8 questions) | **Checkpointed** — live run + STATE update needs explicit user approval |

The planner is expected to:
- Confirm or refine the wave-to-plan mapping (target: 7 plans).
- For each plan, supply the full GSD plan structure: frontmatter (wave, depends_on, autonomous, files_modified, requirements), tasks with `<read_first>` + `<acceptance_criteria>` + `<action>`, verification criteria, must_haves.
- Mark `11-07` as `autonomous: false` (checkpointed) — it includes a live run with OpenAI cost and STATE.md updates.
- Tag every plan's `production_code_touch: false` in frontmatter (no exception is planned upfront).
- Plan 11-01 MUST be the SPEC author. All later plans MUST cite `11-SPEC.md` in their `<read_first>` blocks.
- Plan 11-07 MUST cite the existing live run dir from Phase 10 (`evals/runs/2026-04-29_09-51-54__synthetic_phase10_first`) as the source of the seed cluster.

### Per-Plan Required Metadata (in addition to standard GSD plan frontmatter)

Each `11-NN-PLAN.md` MUST include the following in its frontmatter or `<context>` block:
- `objective:` — single sentence
- `files_likely_created:` — list
- `files_likely_modified:` — list (must be empty for `src/basic_stats/`)
- `success_criteria:` — bullet list
- `autonomous:` — bool (`false` only for Wave 7 / live-run plan)
- `touches_production_code:` — bool (must be `false` for every plan in Phase 11 v1)
- `may_incur_openai_cost:` — bool (`true` only for Wave 7 by default)
- `verification_commands:` — exact shell commands to run (e.g. `uv run pytest tests/test_<file>.py -q`, `uv run python -m evals.discovery.<module> --dry-run`)
- `commit_expectations:` — list of explicit paths the plan is allowed to stage; MUST exclude `evals/runs/`, `db/basic_stats.duckdb`, `.claude/settings.local.json`, `.planning/config.json`, and `docs/review/*` (unless the plan explicitly emits a `docs/review/` proposal)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 10 contracts (REUSE — do not duplicate)
- `.planning/phases/10-self-generated-robustness-synthetic-uat/10-SPEC.md` — 12-category taxonomy (section 2), question schema (section 3), runner contract (section 4), result schema (section 5), cluster schema (section 6), regression workflow (section 7), exit gates (section 8). Phase 11 inherits all of these.
- `.planning/phases/10-self-generated-robustness-synthetic-uat/10-06-SUMMARY.md` — live run evidence; `unsupported_future__refuse_expected_but_answered` cluster is the Wave 6 verification seed.
- `evals/synthetic_runner.py` — single execution entry point. Wrap it. Do not re-implement. Note `--workers 1` constraint due to DuckDB write-write conflict (documented in 10-06-SUMMARY.md).
- `evals/synthetic_clusterer.py` — `cluster_failures()` and `_signature()` are reused verbatim. The cluster schema is the input to backlog entries.
- `evals/synthetic/seed_questions.json` — fixture schema reference; campaign templates MUST conform to it.
- `tests/test_synthetic_regressions.py` — promotion target for `regression_test_needed` action type. The 5-step workflow in the module docstring is the canonical promotion procedure.

### Project planning artifacts
- `.planning/PROJECT.md` — core value, milestone, sensitivity map.
- `.planning/STATE.md` — current state, Phase Progression table, Roadmap Evolution.
- `.planning/REQUIREMENTS.md` — Phase 11 requirement IDs (LOOP-01 through LOOP-06).
- `.planning/ROADMAP.md` — Phase 11 entry with goal/success criteria.

### Project rules (read both before planning)
- `CLAUDE.md` — top-level project guidelines (think before coding, simplicity, surgical changes, goal-driven execution).
- `.claude/rules/development-workflow.md`, `.claude/rules/git-workflow.md`, `.claude/rules/testing.md` — workflow, commit format, testing standards.

</canonical_refs>

<specifics>
## Specific Ideas

- **Use the `unsupported_future` cluster as Wave 6 seed only**. Do NOT design any other plan around it. Do NOT include "fix the agent's future-question refusal" as a Phase 11 deliverable.
- **Backlog file is JSON, not Markdown**. The triage rubric document is Markdown (human-readable); the rubric classifier is Python; the backlog is JSON for machine readability.
- **Idempotent backlog updates**. Re-running the loop on the same run output MUST NOT duplicate entries — a `(failure_signature, category)` lookup determines update-vs-insert.
- **Compare-runs uses run directory names as keys**. No additional metadata file required; both run dirs already contain `failure_clusters.json` which is sufficient input.
- **Promotion never enables xfail tests**. It emits commented-out test stubs only. Humans uncomment after the production fix lands.
- **Phase 11 plans should reference each other via wave / depends_on**. Wave 4 depends on Wave 1 (backlog) for compare semantics. Wave 5 depends on Waves 1+2 (backlog + rubric). Wave 6 depends on all prior waves.

</specifics>

<deferred>
## Deferred Ideas

- LLM-based sub-clustering of failure clusters (Phase 10 already deferred this; Phase 11 keeps it deferred).
- Auto-promotion (no manual approval gate). Phase 11 v1 keeps promotion human-gated.
- Cross-campaign correlation analytics (which campaigns surface which categories most often). Possible v2.
- Slack / GitHub-issue notification when a new cluster is promoted. Not in scope.
- A web dashboard for the backlog. Not in scope.
- Auto-fix of `agent_behavior_fix_needed` clusters via subagents. Phase 11 only emits proposal documents; the actual fix plans go through GSD's normal `/gsd:add-phase` + `/gsd:plan-phase` flow.
- Removing the `--workers 1` constraint on `synthetic_runner` by making `BasicStatsAgent` init concurrency-safe. Out of Phase 11 scope (production code change).

</deferred>

---

*Phase: 11-iterative-synthetic-discovery-loop-v1*
*Context gathered: 2026-04-29 — design decisions provided inline by user as PRD-equivalent express path*
