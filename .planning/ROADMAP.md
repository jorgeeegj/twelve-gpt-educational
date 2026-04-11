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

### v2.0 Milestones (Pending)

- [ ] **Phase 4: Extract & Clean** - Repo reorganization + quality tooling + dead code removal
- [ ] **Phase 5: Function Calling Core** - Replace regex canonicalization with typed tools
- [ ] **Phase 6: Conversation Memory** - Multi-turn follow-up support via ConversationState
- [ ] **Phase 7: League Context** - Dynamic team classification + standings injection
- [ ] **Phase 8: Random Question Robustness** - Stress test + alias hardening
- [ ] **Phase 9: Natural Language Polish** - Verbalization templates + insight rules

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

### Phase 5 — Function Calling Core
**Goal:** Replace ~680 lines of regex-based `_canonicalize_raw_plan` and detector functions with 4 typed Python tools using Pydantic v2 schemas.

**Depends on:** Phase 4

**Requirements:** FUNC-01, FUNC-02, FUNC-03, FUNC-04

**Success Criteria:**
1. `canonicalization_rules.md` document created in `docs/` containing all implicit rules from old planner (prerequisite: must be written before implementation begins)
2. 4 typed tools implemented with Pydantic v2 schemas: `query_entity_stats`, `compare_across_buckets`, `rank_by_metric`, `query_temporal_window`
3. All 61 benchmark questions produce identical results via function calling path (dual-run validation: old plan vs new plan field-by-field for every metric and row)
4. Graceful fallback to legacy planner via `use_function_calling` flag; removed only after 100% coverage confirmed
5. 61/61 eval_runner.py benchmark passes after Phase 5 completes

**Plans:** TBD

**UI hint**: no

---

### Phase 6 — Conversation Memory
**Goal:** Enable multi-turn follow-up questions by tracking entity, metrics, filters, and last result across turns.

**Depends on:** Phase 5

**Requirements:** MEM-01, MEM-02, MEM-03

**Success Criteria:**
1. `ConversationState` dataclass implemented in Streamlit `session_state` tracking entity focus, active filters (opponent, time window, position), last metric, and last result rows
2. Follow-up question chain works end-to-end: "How many goals has Haaland scored?" → "But against top 6?" → "Is that more than the rest?" → "What about per 90?"
3. Multi-turn test suite (10+ conversation flows) passes before Phase 6 ships
4. Token budget for context capped at 1,500 tokens per LLM call
5. 61/61 eval_runner.py benchmark still passes after Phase 6 completes (regression check)

**Plans:** TBD

**UI hint**: yes

---

### Phase 7 — League Context
**Goal:** Inject dynamic league classification (top 6, relegation zone, etc.) into LLM system prompt and enable standings-based queries.

**Depends on:** Phase 4 (league_standings view), Phase 5 (function calling structure)

**Requirements:** CTX-01, CTX-02, CTX-03

**Success Criteria:**
1. League description paragraph injected into LLM system prompt so "top 6", "big 6", "relegation zone" are classified dynamically without hardcoded labels
2. `league_standings` DuckDB view (created in Phase 4 tail) successfully used in queries; standings derivable from match results
3. At least 5 league-context questions answered correctly that previously failed or required hardcoded lookup
4. Timestamp injected context ("as of Matchday X") to ground team classification in time
5. 61/61 eval_runner.py benchmark still passes after Phase 7 completes (regression check)

**Plans:** TBD

**UI hint**: no

---

### Phase 8 — Random Question Robustness
**Goal:** Stress test the analyst with diverse unprepared questions and harden alias mapping for player/team name variants.

**Depends on:** Phase 7

**Requirements:** ROB-01, ROB-02

**Success Criteria:**
1. 20+ diverse unprepared questions tested beyond the 61-question benchmark; pass rate documented and tracked
2. Alias gaps identified and resolved for common player/team name variants (accents, abbreviations, nicknames)
3. Alias hardening prevents silent failures on unrecognized entity names
4. 61/61 eval_runner.py benchmark still passes after Phase 8 completes (regression check)

**Plans:** TBD

**UI hint**: no

---

### Phase 9 — Natural Language Polish
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

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Project Baseline | 0/2 | Complete | 2026-03-26 |
| 2. Planner & Execution Fixes | 0/3 | Complete | 2026-03-27 |
| 3. Verbalization & UI Quality | 0/2 | Complete | 2026-03-27 |
| 4. Extract & Clean | 0/6 | Not started | — |
| 5. Function Calling Core | 0/5 | Not started | — |
| 6. Conversation Memory | 0/5 | Not started | — |
| 7. League Context | 0/5 | Not started | — |
| 8. Random Question Robustness | 0/4 | Not started | — |
| 9. Natural Language Polish | 0/5 | Not started | — |

---

## Guardrails (apply to all phases)

- **Benchmark gate:** 61/61 `evals/eval_runner.py` must pass after EVERY phase — no exceptions
- **Phase 4 prerequisite:** `canonicalization_rules.md` MUST be written in Phase 4 tail BEFORE Phase 5 implementation begins
- **Phase 4 tail task:** `league_standings` DuckDB view MUST be created in Phase 4 (needed by Phase 7)
- **Phase 5 validation:** Dual-run validation (old plan vs new plan field-by-field for all 61 questions) required before fallback flag removal
- **Phase 5 safety:** `use_function_calling` graceful fallback flag MUST be implemented before deleting old planner
- **Prefer small, local fixes over large refactors**
- **Any change to very-sensitive files requires eval_runner validation before closing the task**
- **No broad rewrites without explicit approved plan**

---

*v1 roadmap created: 2026-03-26*
*v2.0 roadmap created: 2026-04-12*
