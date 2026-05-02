# Roadmap: Basic Stats Analyst

**Created:** 2026-03-26 (v1), 2026-04-12 (v2.0)
**Granularity:** Standard (6 phases for v2)
**Core Value:** Every answer must stay grounded in actual data.

---

## Phases

### v1 Milestones (Complete)

- [x] **Phase 1: Project Baseline** - Clean GSD structure + confirmed 61/61 baseline
- [x] **Phase 2: Planner & Execution Fixes** - Targeted benchmark case resolution (50/50 validated)
- [x] **Phase 3: Verbalization & UI Quality** - Grounded answers + edge case handling

### v2.0 Milestones (Complete)

- [x] **Phase 4: Extract & Clean** - Repo reorganization + quality tooling + dead code removal ✓ (2026-04-12)
- [x] **Phase 5: Function Calling Core** - Responses API + 4 mother tools + follow-up memory via `previous_response_id` ✓ (2026-04-17)
- [x] **Phase 6: Random Question Robustness** - Embedding-based entity resolution (VSS) ✓ (2026-04-20)
- [x] **Phase 7: Conversation Memory** - Multi-turn follow-up support ✓ (2026-04-21)
- [x] **Phase 8: League Context** - Dynamic team classification + standings injection ✓ (2026-04-21)
- [x] **Phase 9: Natural Language Polish** - Natural answers, no raw metric keys, insight rules ✓ (2026-04-27)

---

## Phase Details

### Phase 1 — Project Baseline
**Goal:** Establish clean GSD planning structure and confirm current benchmark state before any further changes.

**Depends on:** Nothing (first phase)

**Requirements:** BASE-01, BASE-02

**Success Criteria:**
1. PROJECT.md, REQUIREMENTS.md, ROADMAP.md, STATE.md, config.json all committed and accurate
2. `eval_runner_v4.py` run and current 50/50 pass rate documented in STATE.md
3. No code changes — initialization only

**Plans:** TBD

---

### Phase 2 — Planner & Execution Fixes
**Goal:** Resolve the three known failing benchmark cases (QV4_37, QV4_38, QV5_41) with targeted, tested fixes.

**Depends on:** Phase 1

**Requirements:** PLAN-01, PLAN-02, PLAN-03, EXEC-01, EXEC-02

**Success Criteria:**
1. QV4_37, QV4_38, QV5_41 pass on eval_runner_v4
2. No regression in previously passing cases (50/50 baseline maintained)
3. Each fix has a corresponding test case in `test_query_planner.py`

**Plans:** TBD

---

### Phase 3 — Verbalization & UI Quality
**Goal:** Ensure verbalized answers accurately reflect retrieved rows and handle edge cases cleanly.

**Depends on:** Phase 2

**Requirements:** VERB-01, VERB-02, UI-01, UI-02

**Success Criteria:**
1. Verbalization output matches supporting rows for all tested question types
2. Edge cases handled correctly: zero results, ties, partial data
3. Streamlit UI displays answers and supporting rows without breakage

**Plans:** TBD

---

### Phase 4 — Extract & Clean
**Goal:** Reorganize repo structure, establish quality tooling foundation, and remove dead code — all while maintaining 61/61 benchmark pass rate.

**Depends on:** Phase 3

**Requirements:** INFRA-01, INFRA-02, INFRA-03, INFRA-04, INFRA-05

**Success Criteria:**
1. Repo reorganized to `src/basic_stats/`, `src/shared/`, `tests/`, `evals/` with all imports verified working
2. Dead code deleted: `utils/basic_stats/legacy/`, old eval runners (v0–v5), old benchmark JSONs, orphaned test files, setup artifacts
3. `pyproject.toml` created with ruff config + pinned dependencies (`openai==2.15.0` fix included) + uv as package manager
4. `.pre-commit-config.yaml` configured with ruff + basic linting hooks; passes on first commit
5. `evals/eval_runner.py` (renamed from v6) + `evals/questions_benchmark.json` (renamed from v6) confirmed as single source of truth; 61/61 passing after rename
6. **Tail task:** `league_standings` DuckDB view created from existing `team_match` data (required by Phase 7)

**Plans:** TBD

**UI hint**: no

---

### Phase 5 — Function Calling Core (Complete 2026-04-17)
**Goal:** Migrate agent to OpenAI Responses API, simplify from 9 tools to 4 mother tools, and confirm the architecture is ready for embedding-based robustness work in Phase 6.

**Depends on:** Phase 4

**Requirements:** FUNC-01, FUNC-02, FUNC-03, FUNC-04

**What was built:**
- `BasicStatsAgent` migrated to `client.responses.create` (Responses API)
- 9 tools collapsed to 4 mother tools: `query_player_stats`, `query_team_stats`, `query_ranking`, `get_league_standings`
- Tool schemas in flat format (name/description/parameters at root level)
- Follow-up conversation history wired via `previous_response_id` — server carries context, client only sends new message
- `duckdb_manager.py` extended with 2 VSS stubs for Phase 6: `store_entity_embeddings()`, `fuzzy_resolve_entity()`
- 31 unit tests passing; `@st.cache_resource` on agent init in Streamlit

**Exit gate:** Met. See `.planning/phase-5/COMPLETION.md`.

**UI hint**: no

---

### Phase 6 — Random Question Robustness (Reprioritised 2026-04-16)
**Goal:** Make the agent answer arbitrary Premier League questions it has never seen — no hardcoded entity lists, no regex fallbacks. Uses embedding search for entity resolution.

**Depends on:** Phase 5

**Requirements:** ROB-01, ROB-02

**Why this moved up:** Agust's #1 priority. The 61-question benchmark tests known questions; this phase tests unknown ones. Embedding-based entity resolution is the core enabler.

**Success Criteria:**
1. `text-embedding-3-large` embeddings generated for all player short names and team names in the DB, stored in DuckDB VSS table
2. `fuzzy_resolve_entity(user_input, entity_type)` resolves "Salah" → "M. Salah", "Man City" → "Manchester City" with ≥95% accuracy on a 20-name test set
3. Resolution wired inside tool functions (data layer), not in the agent loop — LLM calls tool with raw user string, tool resolves before querying DB
4. 20+ unprepared questions (7 each from Ricardo, Álvaro, Jorge — no peeking at benchmark) tested and pass rate documented
5. Pass rate target: ≥80% faithful answers on unprepared questions

**Plans:** TBD

**UI hint**: no

---

### Phase 7 — Conversation Memory (Reprioritised 2026-04-16)
**Goal:** Enable multi-turn follow-up questions so users can dig deeper into topics across turns.

**Depends on:** Phase 6

**Requirements:** MEM-01, MEM-02, MEM-03

**Why this moved here:** Agust said robustness (#1) and memory (#2) can run in parallel but robustness is harder — do it first. Memory is simpler now that Responses API handles state natively via `previous_response_id`.

**Note:** Core infrastructure (Responses API `previous_response_id`, `reset()`, `@st.cache_resource`) was delivered in Phase 5. This phase validates conversation quality and adds multi-turn test coverage.

**Success Criteria:**
1. Agust's example chain works end-to-end in Streamlit UI:
   "How many goals has Haaland scored?" → "But against top 6?" → "Is that more than the rest?" → "What about per 90?"
2. Entity + filter context carries across turns without user repeating themselves
3. Multi-turn test suite (10+ conversation flows) passes
4. "Clear chat" resets conversation state correctly (already wired in Phase 5)

**Plans:** TBD

**UI hint**: yes

---

### Phase 8 — League Context (Reprioritised 2026-04-16)
**Goal:** Inject dynamic league classification into the system prompt so the LLM classifies teams without hardcoded labels.

**Depends on:** Phase 7

**Requirements:** CTX-01, CTX-02, CTX-03

**Why this moved here:** Agust's priority #3. Simple to implement — one paragraph + standings view already built in Phase 4.

**Success Criteria:**
1. League description paragraph (as worded by Agust) injected into system prompt dynamically — no hardcoded "top 6 = [Arsenal, Chelsea, ...]" lists anywhere in code
2. `league_standings` DuckDB view used to derive dynamic team classifications (top 4, top 6, relegation zone) at query time
3. Timestamp injected: "as of Matchday X" grounds classifications in time
4. At least 5 league-context questions answered correctly that previously required hardcoded lookup
5. "No hardcoded labels" rule verified: grep for hardcoded team group lists returns zero results

**Plans:** TBD

**UI hint**: no

---

### Phase 9: Natural Language Polish
**Goal:** Replace robotic metric output with natural language templates and implement deterministic insight rules.

**Depends on:** Phase 8

**Requirements:** NLP-01, NLP-02, NLP-03

**Success Criteria:**
1. Verbalized answers use natural language — no raw metric keys, no robotic number dumps (e.g., "Haaland has scored 6 goals with an xG of 3.44" not "Haaland 6 goals 3.44 xG")
2. Contextual framing for comparison answers (home/away, bucket, temporal) implemented using updated `verbalize.yaml` templates
3. At least one deterministic insight rule implemented (e.g., goals vs xG relationship expressed as natural language interpretation: "finishing above expectation", "underperforming xG")
4. All singular/plural/comparative forms per metric handled correctly in templates
5. 61/61 eval_runner.py benchmark still passes after Phase 9 completes (final validation)

**Plans:** TBD

**UI hint**: yes

---

## Progress Tracking

| Phase | Name | Plans | Status | Completed |
|-------|------|-------|--------|-----------|
| 1 | Project Baseline | 0/2 | Complete | 2026-03-26 |
| 2 | Planner & Execution Fixes | 0/3 | Complete | 2026-03-27 |
| 3 | Verbalization & UI Quality | 0/2 | Complete | 2026-03-27 |
| 4 | Extract & Clean | 6/6 | Complete | 2026-04-12 |
| 5 | Function Calling Core | 7/7 | Complete | 2026-04-17 |
| 6 | Random Question Robustness | 0/5 | Complete | 2026-04-20 |
| 7 | Conversation Memory | 0/4 | Complete | 2026-04-21 |
| 8 | League Context | 0/5 | Complete | 2026-04-21 |
| 9 | Natural Language Polish | 0/5 | Complete | 2026-04-27 |
| 10 | Self-Generated Robustness / Synthetic UAT | 6/6 | Complete    | 2026-04-29 |
| 11 | Iterative Synthetic Discovery Loop v1 | 7/7 | Complete | 2026-04-30 |
| 12 | Refusal Hard-Stop | 1/1 | Complete | 2026-05-02 |
| 13 | Scope Awareness | 0/3 | Planned | — |

> Phase order revised 2026-04-16 per Agust feedback: Robustness (was Phase 8) → Phase 6, Memory (was Phase 6) → Phase 7, League Context (was Phase 7) → Phase 8.

---

## Guardrails (apply to all phases)

- **31 unit tests gate:** `tests/test_agent_tools.py` must pass after every phase — no exceptions
- **Phase 4 tail task:** `league_standings` DuckDB view created in Phase 4 (needed by Phase 8)
- **Prefer small, local fixes over large refactors**
- **No broad rewrites without explicit approved plan**
- **Tool layer owns data access:** entity resolution, DB queries, and filters belong in `agent_tools.py` / `duckdb_manager.py`, not in the agent loop

### Phase 10: Self-Generated Robustness / Synthetic UAT

**Goal:** Build a small, verifiable robustness-discovery loop that generates synthetic NL football-stats questions, runs them through `BasicStatsAgent`, evaluates outputs with existing guards (raw_key_guard, faithfulness_judge), clusters failures, and creates a regression-test scaffold — without modifying production code under `src/basic_stats/*`.

**Depends on:** Phase 9

**Requirements:** SYNTH-01, SYNTH-02, SYNTH-03, SYNTH-04, SYNTH-05, SYNTH-06

**Success Criteria:**
1. `10-SPEC.md` authored with 12-category failure taxonomy + runner contract + cluster + regression-workflow + exit gates (SYNTH-01)
2. `evals/synthetic/seed_questions.json` ships >=24 entries spanning all 12 categories (SYNTH-02)
3. `evals/synthetic_runner.py` runs the fixture against `BasicStatsAgent` with `--dry-run` validation mode (SYNTH-03)
4. `evals/synthetic_clusterer.py` produces `failure_clusters.json` + `REPORT.md` on every live run (SYNTH-04)
5. `tests/test_synthetic_regressions.py` ships as scaffold; no pre-emptive regressions (SYNTH-05)
6. Live synthetic run produces 4 output files; baseline tests preserved; STATE.md updated (SYNTH-06)
7. `src/basic_stats/*` has zero diff (read-only constraint enforced throughout)

**Plans:** 6/6 plans complete

**UI hint:** no

### Phase 11: Iterative Synthetic Discovery Loop v1

**Goal:** Turn Phase 10's synthetic UAT infrastructure (runner + clusterer + regression scaffold) into a repeatable iterative discovery loop: campaign generation → live/dry execution → clustering → diagnosis → triage → backlog/regression/fix/tool/context recommendation → targeted re-run → compare-against-prior-runs. The loop's "learning" is in the ecosystem around the LLM (campaigns, failure memory, context, tool/helper recommendations, regression coverage, triage decisions) — not in model weights. This is v1 of the loop, not a fully autonomous self-improving system.

**Depends on:** Phase 10

**Requirements:** LOOP-01, LOOP-02, LOOP-03, LOOP-04, LOOP-05, LOOP-06, LOOP-07

**Success Criteria:**
1. `11-SPEC.md` authored with backlog schema + 7-action-type triage rubric + campaign-generator contract + compare-runs semantics + promotion rules + verification campaign contract + exit gates (LOOP-01)
2. `evals/discovery/failure_backlog.json` + helper module exist with idempotent append/update; unit tests pass (LOOP-02)
3. `evals/discovery/triage_rubric.md` + `triage_rubric.py` deterministic classifier exist; unit tests cover all 7 action types (LOOP-03)
4. `evals/discovery/campaign_generator.py` + `campaigns/` directory exist; default mode is template-only / zero OpenAI cost; LLM-assisted mode opt-in (LOOP-04)
5. `evals/discovery/iteration_runner.py` exists with `run_campaign()` and `compare_runs()`; diff JSON written to newer run directory; tests use stub directories (LOOP-05)
6. `evals/discovery/promote.py` exists; emits proposal artefacts only (commented xfail stubs, `docs/review/*.md` proposals, fixture diffs); never enables xfail; never edits `src/basic_stats/` (LOOP-06)
7. One small targeted campaign (4–8 questions) seeded from `unsupported_future__refuse_expected_but_answered` is run live; backlog updated; promotion proposal emitted; STATE.md / ROADMAP.md / REQUIREMENTS.md updated; `src/basic_stats/` zero diff confirmed; 11-07-SUMMARY.md authored (LOOP-07)

**Plans:** 7/7 plans complete

**UI hint:** no

### Phase 13: Scope Awareness

**Goal:** Teach the agent the boundaries of its dataset (which metrics, which entities, which season) so it refuses cleanly with the closest available alternative instead of silently substituting, coercing wrong entities, or hallucinating across seasons.

**Depends on:** Phase 12

**Requirements:** SCOPE-01, SCOPE-02, SCOPE-03

**Success Criteria:**
1. METRIC AVAILABILITY rule added to `agent_system.yaml`; `agent_tools.py` returns `metric_not_available` error for stats outside the documented list; 4/4 metric-not-in-schema questions pass (SCOPE-01)
2. `BEFORE CALLING A TOOL` intent classification block added to `agent_system.yaml`; `agent.py` strips `INTENT:` line from user answer; 61 + 21 benchmarks preserved at ≥59/61 and ≥19/21 (SCOPE-02)
3. `evals/scope_awareness_questions.json` ships with 12 questions across 3 gap categories (metric-not-in-schema, entity-not-in-dataset, multi-season); 12/12 produce refusal-with-alternative, refusal-explicit, or clarifying question; benchmarks preserved (SCOPE-03)

**Plans:** 0/3 (single PLAN.md, three sub-phases)

**UI hint:** no

---

*v1 roadmap created: 2026-03-26*
*v2.0 roadmap created: 2026-04-12*
*Phase 4 marked complete: 2026-04-12*
*Phase 5 marked complete: 2026-04-17 — Responses API + 4 mother tools + previous_response_id*
*Phase order revised 2026-04-16 per Agust feedback: Robustness → Phase 6, Memory → Phase 7, League Context → Phase 8*
*Phase 6 marked complete: 2026-04-20 — VSS entity resolution, 19/21 random questions faithfulness*
*Phase 7 marked complete: 2026-04-21 — Client-side history, Agust's 4-turn chain passes end-to-end*
*Phase 8 marked complete: 2026-04-21 — Dynamic league context paragraph, 6/6 context questions, no hardcoded labels*
*Phase 9 marked complete: 2026-04-27 — NLP polish: 61/61 raw-key clean, goals vs xG insight rule, contextual framing; faithfulness 59/61 (0.967 ≥ 0.95 gate)*
*Phase 10 marked complete: 2026-04-29 — Synthetic UAT: runner + clusterer + regression scaffold; live run 24 questions, 2 failures (1 cluster: unsupported_future__refuse_expected_but_answered)*
*Phase 11 added: 2026-04-29 — Iterative Synthetic Discovery Loop v1 (turns Phase 10 infrastructure into a repeatable discovery cycle).*
*Phase 11 planned: 2026-04-29 — 7 plans across 7 waves; LOOP-01..LOOP-07 added to REQUIREMENTS.md; 11-CONTEXT.md + 11-SPEC.md + seven 11-NN-PLAN.md files authored; src/basic_stats/ zero diff verified.*
*Phase 11 marked complete: 2026-04-30 — All 9 SPEC exit gates met; live run 2026-04-30_09-37-53__synthetic_unsupported_future_v1 (6 questions, 6 failures, 1 cluster); backlog seeded + promoted; context_gap proposal emitted; 231/231 tests passing; src/basic_stats/ zero diff.*
*Phase 12 added + completed: 2026-05-02 — Refusal Hard-Stop. agent_system.yaml OUT OF SCOPE rule rewritten; backlog_001_verify campaign confirms BACKLOG_001 cluster closed (4/6 clean refusals; 2 "non-refusals" are correct behavior on completed-season questions).*
*Phase 13 added + planned: 2026-05-02 — Scope Awareness. SCOPE-01..SCOPE-03 added to REQUIREMENTS.md; single PLAN.md with three sub-phases under .planning/phases/13-scope-awareness/.*
