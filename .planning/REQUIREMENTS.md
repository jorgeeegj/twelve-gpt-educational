# Requirements: Basic Stats Analyst

**Defined:** 2026-03-26
**Core Value:** Every answer must stay grounded in actual data — no invented metrics, entities, values, or support rows.

## v1 Requirements

Requirements for ongoing brownfield work. Each maps to a roadmap phase.

### Project Baseline

- [x] **BASE-01**: GSD planning structure initialized and committed (PROJECT.md, REQUIREMENTS.md, ROADMAP.md, STATE.md, config.json)
- [x] **BASE-02**: Benchmark baseline confirmed — current eval_runner_v4 pass rate documented before any new changes

### Query Planner

- [x] **PLAN-01**: Any planner improvement work must start from the validated 50/50 baseline and preserve it
- [x] **PLAN-02**: Any new planner fix is accompanied by a targeted test case in `test_query_planner.py`
- [x] **PLAN-03**: Planner changes validated with `eval_runner_v4` before merging (no regressions)

### Verbalization

- [x] **VERB-01**: Verbalized answers match the grounded rows returned (no hallucinated values or phrasing)
- [x] **VERB-02**: Verbalization handles edge cases: zero results, ties, partial data

### Execution / DuckDB

- [x] **EXEC-01**: Grounded execution returns correct rows for all supported scopes (players_summary, teams_summary, player_match, player_match_event, team_match)
- [x] **EXEC-02**: Aggregation logic (sum, avg, count, rank) verified correct for relevant question types

### UI / Demo

- [x] **UI-01**: `pages/basic_stats.py` displays answers and supporting rows without breaking on edge case responses
- [x] **UI-02**: Demo behavior matches core pipeline output (no UI-level data transformation)

---

## v2 Requirements

Milestone v2.0: Function Calling Architecture + Feature Completeness

### INFRA — Codebase Foundations

- [x] **INFRA-01**: Repo reorganized to `src/basic_stats/`, `src/shared/`, `tests/`, `evals/` — all imports verified working, 61/61 benchmark passing after restructure ✓ (2026-04-12)
- [x] **INFRA-02**: Dead code deleted: `utils/basic_stats/legacy/`, 5 old eval runners (v0–v5), old benchmark JSONs, `test_embeddings.py`, `.lnk` file, `miniprueba.py`, `setup.py`, `twelve_gpt_educational.egg-info/` ✓ (2026-04-12)
- [x] **INFRA-03**: `pyproject.toml` created with ruff config, pinned deps (`openai==2.15.0` fix included), uv as package manager ✓ (2026-04-12)
- [x] **INFRA-04**: `.pre-commit-config.yaml` configured with ruff + basic hooks; passes on first commit in `feature/refactor-v2` ✓ (2026-04-12)
- [x] **INFRA-05**: `evals/eval_runner.py` (renamed from v6) + `evals/questions_benchmark.json` (renamed from v6) — single source of truth, 61/61 confirmed after rename ✓ (2026-04-12)

### FUNC — Function Calling Core

- [x] **FUNC-01**: `BasicStatsAgent` implemented with 9 typed tools and OpenAI strict-mode schemas replacing the v1 planner heuristics (`src/basic_stats/agent.py`, `agent_tools.py`, `agent_tool_schemas.py`) ✓ (2026-04-13)
- [ ] **FUNC-02**: All 61 benchmark questions pass faithfulness gate ≥95% (51/61 = 83.6% as of 2026-04-13 — 9 failures remaining)
- [x] **FUNC-03**: Legacy planner (`llm_query_engine_v2.py`, `query_planner.py`) kept as reference; new agent is the active path ✓ (2026-04-13)
- [x] **FUNC-04**: Canonicalization rules documented in `docs/canonicalization_rules.md` ✓ (2026-04-12)

### MEM — Conversation Memory

- [ ] **MEM-01**: `ConversationState` dataclass in Streamlit `session_state` tracks entity, metric, active filters, and last result across turns
- [ ] **MEM-02**: Follow-up question chain works end-to-end: "How many goals has Haaland scored?" → "But against top 6?" → "Is that more than the rest?" → "What about per 90?"
- [ ] **MEM-03**: Multi-turn test suite (10+ conversation flows) passes before Phase 6 ships

### CTX — League Context

- [ ] **CTX-01**: League description paragraph injected into LLM system prompt so "top 6", "big 6", "relegation zone" are classified dynamically without hardcoded labels
- [ ] **CTX-02**: `league_standings` DuckDB view created from existing `team_match` data (standings derivable from match results)
- [ ] **CTX-03**: At least 5 league-context questions answered correctly that previously failed or required hardcoded lookup

### ROB — Random Question Robustness

- [ ] **ROB-01**: 20+ diverse unprepared questions tested beyond the 61-question benchmark; pass rate documented
- [ ] **ROB-02**: Alias gaps identified and resolved for common player/team name variants (accents, abbreviations, nicknames)

### NLP — Natural Language Polish

- [x] **NLP-01**: Verbalized answers use natural language — no raw metric keys, no robotic number dumps ✓ (2026-04-27) — 61/61 clean on benchmark
- [x] **NLP-02**: Contextual framing for comparison answers (home/away, bucket, temporal) via `agent_system.yaml` HOW TO WRITE YOUR ANSWER enrichment ✓ (2026-04-27)
- [x] **NLP-03**: Deterministic goals vs xG insight rule implemented (±1.0 threshold → "finishing above expectation" / "underperforming xG") ✓ (2026-04-27)

---

## Out of Scope

| Feature | Reason |
|---------|--------|
| Broad architectural rewrites beyond v2 plan | Risk of regressions; no justified need at current scale |
| New product features (Scout, WVS, etc.) | Not the active development focus |
| Distributed query engines | Current dataset fits in-process DuckDB |
| Mobile / API-first interfaces | Streamlit web is sufficient |
| OAuth / auth changes | Not relevant to Basic Stats module |
| Local LLM fallback | Not required for current usage pattern |
| Vector DB / long-term memory (mem0) | Short-term session memory is sufficient for follow-ups |
| Qualities integration | Out of scope per Agust (course constraint) |
| Visualization (shot maps, heatmaps) | Backlog — interesting but not next step |
| PR to upstream Twelve-Educational/main | Not planned for v2; fork is source of truth |

---

## Phase 10 — Self-Generated Robustness / Synthetic UAT

### SYNTH-01 — Phase 10 Specification

**Phase:** 10
**Asserts:** A `10-SPEC.md` document exists in `.planning/phases/10-self-generated-robustness-synthetic-uat/` that names the 12-category failure taxonomy, declares the `synthetic_runner.run()` contract (signature, CLI, output paths, exit codes), defines the per-question result schema (section 5), the failure-cluster schema (section 6), the regression-test workflow (section 7), and the 7 exit gates (section 8). SPEC is the single authoritative contract for Plans 02–06.

### SYNTH-02 — Synthetic Question Fixture

**Phase:** 10
**Asserts:** `evals/synthetic/seed_questions.json` exists with at least 24 entries, every entry tagged with one of the 12 SPEC taxonomy categories. All 12 categories are represented at least twice. At least one Spanish entry. Tottenham Champions League edge case present. Top 6 vs Big Six distinction present (one of each).

### SYNTH-03 — Synthetic Runner

**Phase:** 10
**Asserts:** `evals/synthetic_runner.py` exists. Exposes `run(fixture_path, label, max_workers=5, skip_judges=False, dry_run=False) -> Path`. Reuses `BasicStatsAgent`, `find_violations` from `evals.raw_key_guard`, `judge_faithfulness` from `evals.judges.faithfulness_judge`, and the `_ask_with_retry` retry pattern. Supports `--dry-run` (validates fixture only). Multi-turn entries (`|`-separated) are called sequentially without `reset()`.

### SYNTH-04 — Failure Clusterer + Markdown Report

**Phase:** 10
**Asserts:** `evals/synthetic_clusterer.py` exists. `cluster_failures(results, run_id) -> dict` groups failing rows by `(category, failure_category)`. `write_report(cluster_dict, output_path, summary)` writes a Markdown report. `synthetic_runner.run()` invokes both on every live (non-dry-run) execution and writes `failure_clusters.json` + `REPORT.md` to the run directory. No LLM dependency in the clusterer.

### SYNTH-05 — Regression-Test Scaffold

**Phase:** 10
**Asserts:** `tests/test_synthetic_regressions.py` exists with a module docstring reproducing the 5-step regression workflow from SPEC section 7, a documented (commented or active) `pytest.mark.xfail` example, and a placeholder test that keeps the file collectable. The file does NOT import `BasicStatsAgent`, DuckDB, or `openai` at module level. NO real regression tests are added pre-emptively — only when a failure is observed across two consecutive runs.

### SYNTH-06 — Verification + STATE.md Evidence

**Phase:** 10
**Asserts:** A live synthetic run (or skip-judges variant) produces `summary.json` + `results.json` + `failure_clusters.json` + `REPORT.md`. The new Phase 10 unit tests pass and the existing baseline (>= 160 tests, excluding `test_fuzzy_resolve.py`) is preserved. `.planning/STATE.md` is updated with Phase 10 status, exit-gate evidence, and the live run-dir name. `src/basic_stats/*` shows zero diff throughout Phase 10.

---

## Phase 11 — Iterative Synthetic Discovery Loop v1

### LOOP-01 — Phase 11 Specification

**Phase:** 11
**Asserts:** A `11-SPEC.md` document exists in `.planning/phases/11-iterative-synthetic-discovery-loop-v1/` that locks: artefact paths under `evals/discovery/`, the failure-memory backlog schema (with `id`, `first_seen_run_id`, `last_seen_run_id`, `seen_count`, `category`, `failure_signature`, `guard_evidence`, `question_ids`, `sample_answers`, `diagnosis`, `status`, `recommended_action`, `promoted_to`, `linked_campaign`, `notes` fields), the 7-action-type triage rubric enum, the campaign-generator contract, the iteration-runner compare-run semantics (repeated/disappeared/mutated/new), the promotion rules, the verification campaign contract, the exit gates, and the non-goals. SPEC is the single authoritative contract for Plans 11-02..11-07. Inherits the 12-category taxonomy and question schema from `10-SPEC.md` (does not redefine them).

### LOOP-02 — Failure Memory / Discovery Backlog

**Phase:** 11
**Asserts:** `evals/discovery/failure_backlog.json` exists with the schema declared in `11-SPEC.md` (`backlog_version: 1`, `entries: []`). A helper module (e.g. `evals/discovery/failure_backlog.py`) provides `load_backlog(path)`, `append_or_update(backlog, cluster, run_id) -> backlog`, and `find_by_signature(backlog, signature) -> entry|None`. Idempotent updates: re-running on the same cluster does NOT duplicate entries; it bumps `seen_count` and updates `last_seen_run_id`. Unit tests cover load/append/idempotent-update/find-by-signature. No production code touched.

### LOOP-03 — Cluster Triage Rubric

**Phase:** 11
**Asserts:** `evals/discovery/triage_rubric.md` (human-readable) and `evals/discovery/triage_rubric.py` (deterministic) exist. The rubric document explains each of the 7 action types (`regression_test_needed`, `agent_behavior_fix_needed`, `context_missing`, `helper_tool_needed`, `fixture_issue`, `non_actionable`, `deferred`) with at least one Phase-10-grounded example each. The classifier exposes `classify(cluster: dict, hints: dict | None = None) -> str` returning one of the 7 enum values; logic is small, transparent, and uses NO LLM call. Unit tests cover all 7 outcomes plus the default-fallthrough case.

### LOOP-04 — Targeted Campaign Generator

**Phase:** 11
**Asserts:** `evals/discovery/campaign_generator.py` exists. Exposes `generate_from_cluster(backlog_entry, count) -> dict[]`, `generate_from_category(category, count) -> dict[]`, and `write_campaign(questions, name) -> Path` writing `evals/discovery/campaigns/<name>.json`. Output entries conform to `seed_questions.json` schema so `synthetic_runner` consumes them unchanged. Default mode is template-based (zero OpenAI cost); LLM-assisted mode is opt-in via an explicit `use_llm=True` flag. Unit tests cover both modes (LLM path mocked). `evals/discovery/campaigns/.gitkeep` exists.

### LOOP-05 — Iteration Runner / Compare Runs

**Phase:** 11
**Asserts:** `evals/discovery/iteration_runner.py` exists. Exposes `run_campaign(campaign_path, label) -> Path` (wraps `synthetic_runner.run()`) and `compare_runs(older_dir: Path, newer_dir: Path) -> dict` returning `{repeated: [...], disappeared: [...], mutated: [...], new: [...]}` lists keyed by `failure_signature` and/or `question_id`. `compare_runs` writes `diff_against_<older>.json` to the newer run directory. Unit tests use two stub run directories (no live runner invocation). No production code touched.

### LOOP-06 — Promotion Rules

**Phase:** 11
**Asserts:** `evals/discovery/promote.py` exists. Exposes `promote(backlog_entry_id, action_type, backlog_path) -> Path|None` that, gated on `seen_count >= 2`, emits the appropriate proposal artefact: `regression_test_needed` → commented-xfail stub appended to `tests/test_synthetic_regressions.py`; `agent_behavior_fix_needed` / `context_missing` / `helper_tool_needed` → `docs/review/<follow_on|context_gap|tool_proposal>_<signature>.md`; `fixture_issue` → `evals/discovery/fixture_fixes/<signature>.diff`; `non_actionable` / `deferred` → backlog status update only. NEVER enables xfail tests. NEVER edits `src/basic_stats/`. Unit tests cover all 7 emission paths.

### LOOP-07 — Verification + Documentation

**Phase:** 11
**Asserts:** A small targeted campaign (4–8 questions) is generated from the Phase 10 backlog seed `unsupported_future__refuse_expected_but_answered` (SYN_019/SYN_020), saved under `evals/discovery/campaigns/`, and run live via `iteration_runner.run_campaign()`. The run produces `summary.json` + `results.json` + `failure_clusters.json` + `REPORT.md` under `evals/runs/` (gitignored, NOT staged). `failure_backlog.json` is updated with at least one entry. At least one promotion proposal artefact is emitted under `docs/review/` or `tests/test_synthetic_regressions.py` (commented stub). `.planning/STATE.md`, `.planning/ROADMAP.md`, and `.planning/REQUIREMENTS.md` are updated with Phase 11 completion evidence. `git diff --name-only src/basic_stats/` returns zero files. `11-07-SUMMARY.md` documents the live-run dir name, evidence table, and pending follow-on items.

---

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| BASE-01 | Phase 1 | Complete |
| BASE-02 | Phase 1 | Complete |
| PLAN-01 | Phase 2 | Complete |
| PLAN-02 | Phase 2 | Complete |
| PLAN-03 | Phase 2 | Complete |
| VERB-01 | Phase 3 | Complete |
| VERB-02 | Phase 3 | Complete |
| EXEC-01 | Phase 3 | Complete |
| EXEC-02 | Phase 3 | Complete |
| UI-01 | Phase 3 | Complete |
| UI-02 | Phase 3 | Complete |
| INFRA-01 | Phase 4 | Complete ✓ (2026-04-12) |
| INFRA-02 | Phase 4 | Complete ✓ (2026-04-12) |
| INFRA-03 | Phase 4 | Complete ✓ (2026-04-12) |
| INFRA-04 | Phase 4 | Complete ✓ (2026-04-12) |
| INFRA-05 | Phase 4 | Complete ✓ (2026-04-12) |
| FUNC-01 | Phase 5 | Complete ✓ (2026-04-13) |
| FUNC-02 | Phase 5 | In Progress — scope revised 2026-04-16 (exit gate changed from 61/61 to architecture gate) |
| FUNC-03 | Phase 5 | Complete ✓ (2026-04-13, deleted 2026-04-16 — legacy fully removed) |
| FUNC-04 | Phase 5 | Complete ✓ (2026-04-12) |
| ROB-01 | Phase 6 ⬆️ | Pending |
| ROB-02 | Phase 6 ⬆️ | Pending |
| MEM-01 | Phase 7 ⬆️ | Pending |
| MEM-02 | Phase 7 ⬆️ | Pending |
| MEM-03 | Phase 7 ⬆️ | Pending |
| CTX-01 | Phase 8 ⬆️ | Pending |
| CTX-02 | Phase 8 ⬆️ | Pending |
| CTX-03 | Phase 8 ⬆️ | Pending |
| NLP-01 | Phase 9 | Complete ✓ (2026-04-27) |
| NLP-02 | Phase 9 | Complete ✓ (2026-04-27) |
| NLP-03 | Phase 9 | Complete ✓ (2026-04-27) |
| SYNTH-01 | Phase 10 | Complete ✓ (2026-04-28) |
| SYNTH-02 | Phase 10 | Complete ✓ (2026-04-28) |
| SYNTH-03 | Phase 10 | Complete ✓ (2026-04-29) |
| SYNTH-04 | Phase 10 | Complete ✓ (2026-04-29) |
| SYNTH-05 | Phase 10 | Complete ✓ (2026-04-29) |
| SYNTH-06 | Phase 10 | Complete ✓ (2026-04-29) |
| LOOP-01 | Phase 11 | Pending |
| LOOP-02 | Phase 11 | Complete |
| LOOP-03 | Phase 11 | Complete |
| LOOP-04 | Phase 11 | Complete |
| LOOP-05 | Phase 11 | Complete |
| LOOP-06 | Phase 11 | Pending |
| LOOP-07 | Phase 11 | Pending |

**Coverage:**
- v1 requirements: 11 total — all complete ✓
- v2 requirements: 19 total — 11 complete, 1 in progress (FUNC-02), 7 pending
- Phase 10 requirements: 6 total — all complete ✓ (SYNTH-01 through SYNTH-06)
- Phase 11 requirements: 7 total — all pending (LOOP-01 through LOOP-07)
- Mapped to phases: 43/43 ✓

---

*Requirements defined: 2026-03-26*
*v2 requirements added: 2026-04-12 — function calling, conversation memory, league context, robustness, NLP polish*
*Phase 4 (INFRA) marked complete: 2026-04-12*
*FUNC-01/03/04 marked complete: 2026-04-13 — FUNC-02 in progress at 51/61*
*NLP-01/02/03 marked complete: 2026-04-27 — 61/61 raw-key clean, contextual framing, goals vs xG insight rule; faithfulness 59/61 (0.967)*
*SYNTH-01 marked complete: 2026-04-28 — 10-SPEC.md authored with 12-category taxonomy, runner contract, cluster schema, 7 exit gates*
*SYNTH-04/05/06 marked complete: 2026-04-29 — clusterer, regression scaffold, live run evidence all delivered*
*Phase 11 requirements added: 2026-04-29 — LOOP-01..LOOP-07 (iterative discovery loop v1: SPEC, backlog, triage rubric, campaign generator, iteration runner, promotion rules, verification)*
