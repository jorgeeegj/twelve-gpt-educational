# Phase 11 Specification: Iterative Synthetic Discovery Loop v1

**Authored:** 2026-04-29 (during Phase 11 planning; will be re-authored / locked by Plan 11-01)
**Status:** Authoritative — Plans 11-02 through 11-07 implement against this contract.
**Inherits from:** `10-SPEC.md` (taxonomy enum, question schema, runner contract, cluster schema, regression workflow). This SPEC does NOT redefine those.

---

## 1. Goal

Phase 11 turns Phase 10's synthetic UAT infrastructure into a **repeatable iterative discovery loop**:

```
campaign generation
  → live/dry execution (existing synthetic_runner.py)
    → clustering (existing synthetic_clusterer.py)
      → diagnosis
        → triage (rubric → action type)
          → backlog/regression/fix/tool/context recommendation
            → targeted re-run
              → compare-against-prior-runs
```

It is **v1 of the loop**, not a fully autonomous self-improving system. Production code under `src/basic_stats/*` is read-only for the entire phase.

---

## 2. Artefact Layout (locked)

All Phase 11 artefacts live under `evals/discovery/`. Run outputs continue to land under `evals/runs/` (gitignored).

```
evals/discovery/
├── failure_backlog.json        # durable cluster/decision memory (LOOP-02)
├── failure_backlog.py          # backlog helper module (LOOP-02)
├── triage_rubric.md            # human rubric document (LOOP-03)
├── triage_rubric.py            # deterministic classifier (LOOP-03)
├── campaign_generator.py       # campaign emitter (LOOP-04)
├── campaigns/                  # generated campaign question sets (LOOP-04)
│   ├── .gitkeep
│   └── <name>.json             # one per generated campaign
├── iteration_runner.py         # wraps synthetic_runner.run() + compare-runs (LOOP-05)
├── promote.py                  # promotion-rules executor (LOOP-06)
└── fixture_fixes/              # diff suggestions for fixture_issue clusters (LOOP-06)
    └── .gitkeep
```

Tests live alongside the existing test tree:
```
tests/
├── test_failure_backlog.py
├── test_triage_rubric.py
├── test_campaign_generator.py
├── test_iteration_runner.py
└── test_promote.py
```

---

## 3. Failure-Memory Backlog Schema (locked)

`evals/discovery/failure_backlog.json` is a single JSON document with the following shape:

```json
{
  "backlog_version": 1,
  "entries": [
    {
      "id": "BACKLOG_001",
      "first_seen_run_id": "<run-dir-name>",
      "last_seen_run_id": "<run-dir-name>",
      "seen_run_ids": ["<run-dir-name>"],
      "seen_count": 1,
      "category": "<one of the 12 taxonomy enum values from 10-SPEC.md §2>",
      "failure_signature": "<from synthetic_clusterer._signature() — '<category_lower>__<guard>'>",
      "guard_evidence": "<faithfulness | raw_key | refuse_expected_but_answered | other>",
      "question_ids": ["SYN_NNN"],
      "sample_answers": ["<truncated answer (≤200 chars)>"],
      "diagnosis": "<short free-text root-cause hypothesis>",
      "status": "<open | triaged | promoted | resolved | deferred | non_actionable>",
      "recommended_action": "<one of the 7 triage rubric action types from §4>",
      "promoted_to": null,
      "linked_campaign": null,
      "notes": null
    }
  ]
}
```

### Field semantics

- `id`: monotonic `BACKLOG_<NNN>`. Never reused.
- `first_seen_run_id` / `last_seen_run_id`: directory names under `evals/runs/`.
- `seen_run_ids`: durable list of every distinct `run_id` ever processed for this signature. The source of truth for distinct-run counting. Backfilled from `first_seen_run_id`/`last_seen_run_id` for entries created before this field existed.
- `seen_count`: **distinct-run** appearance counter. Equals `len(seen_run_ids)`. Incremented only when `run_id` is not already in `seen_run_ids`. Re-processing any previously-seen run_id (including A→B→A replays) does NOT increment. Eligibility for promotion (§8) is `seen_count >= 2` — the cluster must have appeared in at least two distinct runs.
- `category` / `failure_signature` / `guard_evidence` / `question_ids` / `sample_answers`: copied from the originating cluster in `failure_clusters.json`. Sample answers are truncated to ≤200 chars (matches `synthetic_clusterer._SAMPLE_TRUNC`).
- `diagnosis`: free-text — set by humans during triage; default `""` on insert.
- `status`: lifecycle — see §5 for transitions.
- `recommended_action`: one of the 7 enum values from §4; `null` until triage runs.
- `promoted_to`: nullable string. Examples: `"tests/test_synthetic_regressions.py:test_regression_<sig>"`, `"docs/review/follow_on_<sig>.md"`, `"follow_on_phase:12"`.
- `linked_campaign`: nullable filename under `evals/discovery/campaigns/` — set when a campaign was generated specifically to probe this cluster.
- `notes`: nullable free-text.

### Idempotent updates

`append_or_update(backlog, cluster, run_id)` MUST:

1. Look up an existing entry by `failure_signature`.
2. If found:
   - Merge `question_ids` (set-union, sorted).
   - Append at most one new sample answer (truncated ≤200 chars; skip if it duplicates an existing one).
   - Backfill `seen_run_ids` if missing (from `first_seen_run_id`/`last_seen_run_id`).
   - **If `run_id NOT in entry["seen_run_ids"]`:** append to `seen_run_ids`, bump `seen_count` by 1, set `last_seen_run_id = run_id`.
   - **If `run_id IN entry["seen_run_ids"]`:** do NOT bump `seen_count` and do NOT change `last_seen_run_id` (any previously-seen run_id is counter-idempotent — including A→B→A replays).
3. If not found: insert a new entry with monotonic `id`, `first_seen_run_id = last_seen_run_id = run_id`, `seen_run_ids = [run_id]`, `seen_count = 1`, `status = "open"`, `recommended_action = null`, `promoted_to = null`, `linked_campaign = null`, `diagnosis = ""`, `notes = null`.

**Counter-idempotency invariant:** for any sequence of `append_or_update` calls, `seen_count` for a given signature equals `len(seen_run_ids)` — the number of **distinct** `run_id` values ever processed. A→B→A replays produce `seen_count=2`, not 3.

---

## 4. Triage Rubric Action Types (locked enum)

The classifier returns exactly one of:

```
regression_test_needed       # add a test in tests/test_synthetic_regressions.py
agent_behavior_fix_needed    # production code change required (deferred to a later phase)
context_missing              # system prompt / docs need a clarifying paragraph
helper_tool_needed           # a new tool/helper would unlock the answer
fixture_issue                # the synthetic question itself is malformed
non_actionable               # the failure is acceptable / inherent / out of scope
deferred                     # valid issue, intentionally delayed to a later phase
```

### Classifier signature

```python
def classify(cluster: dict, hints: dict | None = None) -> str:
    """Return one of the 7 action types. No LLM call — deterministic logic only."""
```

### Decision rules (examples — LOOP-03 plan finalises)

- `guard_evidence == "raw_key"` AND `category in {DIRECT_STATS, RANKINGS, P90_METRICS, ...}` → `regression_test_needed`
- `guard_evidence == "refuse_expected_but_answered"` AND `category == "UNSUPPORTED_FUTURE"` → `context_missing` (default) or `agent_behavior_fix_needed` (when `hints["needs_code_change"]`)
- `guard_evidence == "faithfulness"` AND `category == "AMBIGUOUS"` → `fixture_issue`
- `category == "DEMO_RANDOM"` AND `seen_count == 1` → `non_actionable`
- Default fallthrough → `deferred`

The rubric document (`triage_rubric.md`) explains each type with at least one Phase-10-grounded example.

---

## 5. Backlog Status Lifecycle

```
open ──(triage runs)──> triaged ──(promote.py runs)──> promoted ──(fix lands)──> resolved
  │                          │
  │                          └──(human marks)──> deferred / non_actionable
  └──(human marks)──> non_actionable
```

State transitions are explicit; nothing happens automatically except `open → triaged` when `recommended_action` is set, and `triaged → promoted` when `promote.py` emits an artefact.

---

## 6. Targeted Campaign Generator Contract

### Public API

```python
def generate_from_cluster(backlog_entry: dict, count: int = 4) -> list[dict]: ...
def generate_from_category(category: str, count: int = 4) -> list[dict]: ...
def write_campaign(questions: list[dict], name: str) -> Path: ...
```

### Output schema

Each emitted question MUST conform to the `seed_questions.json` schema (`10-SPEC.md` §3): `id` (campaign-local `CAMP_<name>_<NNN>`), `category`, `language`, `question`, `expected_behavior`, `expected_values`, `notes`.

### Modes

- **Default (template-based, zero OpenAI cost):** parameterised templates per category. Example: `RANKINGS` → `"Top {N} {entity_type} by {metric} this season?"` with parameter combinations.
- **Opt-in LLM mode:** `use_llm=True`. Calls existing `BasicStatsAgent` infrastructure to suggest parameterisations or rephrasings. Writes the proposed questions to disk for human review BEFORE running the campaign.

The generator is **not** an autonomous agent. It writes a JSON file; humans review and run it manually with `iteration_runner.run_campaign(...)`.

### Output path

`evals/discovery/campaigns/<name>.json` — `name` is sanitised (lowercase, alphanumerics + underscores).

---

## 7. Iteration Runner / Compare-Runs Semantics (locked)

### Public API

```python
def run_campaign(campaign_path: Path, label: str) -> Path:
    """Wraps synthetic_runner.run(). Returns the run output directory."""

def compare_runs(older_dir: Path, newer_dir: Path) -> dict:
    """Returns {repeated, disappeared, mutated, new} keyed by failure_signature."""
```

### Comparison semantics

For two run directories `A` (older) and `B` (newer) over the same campaign:

| Bucket | Definition |
|--------|------------|
| `repeated` | Same `failure_signature` in both `A` and `B` — at least one shared `question_id` |
| `disappeared` | `failure_signature` in `A`, absent in `B` |
| `mutated` | A `question_id` failing in `B` was passing in `A` (or vice versa), OR same `question_id` failure changed signature |
| `new` | `failure_signature` only in `B` |

### Output

`compare_runs` writes `evals/runs/<B-run-dir>/diff_against_<A-run-dir>.json`:

```json
{
  "older_run": "<A-run-dir>",
  "newer_run": "<B-run-dir>",
  "repeated": [{"signature": "...", "question_ids": ["..."]}],
  "disappeared": [{"signature": "...", "question_ids": ["..."]}],
  "mutated": [{"question_id": "...", "older_signature": "...", "newer_signature": "..."}],
  "new": [{"signature": "...", "question_ids": ["..."]}]
}
```

No additional state is persisted outside the runs directory.

---

## 8. Promotion Rules (locked)

### Eligibility

A backlog entry is eligible for promotion when `seen_count >= 2` (i.e. the cluster has appeared in at least **two distinct runs** per §3). This matches `10-SPEC.md` §7 (regression test added only after a failure is reproduced across two consecutive runs).

### Public API (canonical — backlog-driven)

```python
def promote(backlog_entry_id: str, backlog_path: Path = DEFAULT_BACKLOG_PATH) -> Path | None:
    """Emit the proposal artefact for the entry's recommended_action.

    The action type is NOT a parameter — it is read from the backlog entry's
    `recommended_action` field (set by `triage_rubric.classify(...)` during triage).

    Returns the artefact Path, or None for status-only updates (`non_actionable`,
    `deferred`).

    Raises PromotionError when:
      - the entry id is not found in the backlog
      - the entry's seen_count < 2 (eligibility threshold)
      - the entry's recommended_action is None or not in the 7-action-type enum
    """
```

**API stability rule:** Plans 11-06 and 11-07 MUST conform to this signature. Any plan that introduces an `action_type` parameter to `promote()` is a contract violation.

### Per-action emission

| `action_type` | Emission | Path |
|---------------|----------|------|
| `regression_test_needed` | Commented-xfail stub appended to the regression scaffold | `tests/test_synthetic_regressions.py` |
| `agent_behavior_fix_needed` | Markdown follow-on proposal | `docs/review/follow_on_<signature>.md` |
| `context_missing` | Markdown context-gap proposal | `docs/review/context_gap_<signature>.md` |
| `helper_tool_needed` | Markdown tool proposal | `docs/review/tool_proposal_<signature>.md` |
| `fixture_issue` | Unified-diff suggestion | `evals/discovery/fixture_fixes/<signature>.diff` |
| `non_actionable` | Backlog status update only | (no artefact) |
| `deferred` | Backlog status update only | (no artefact) |

### Hard rules

- `promote.py` NEVER enables xfail-marked tests. Stubs are commented out; humans uncomment after the fix lands.
- `promote.py` NEVER edits files under `src/basic_stats/`.
- `promote.py` NEVER opens PRs, sends notifications, or makes network calls.
- After emission, `promote.py` updates the backlog entry: `status = "promoted"`, `promoted_to = "<emitted path or null>"`.

---

## 9. Verification Campaign Contract (Wave 7)

### Source seed

The Phase 10 live-run cluster `unsupported_future__refuse_expected_but_answered` (run dir `evals/runs/2026-04-29_09-51-54__synthetic_phase10_first`, question IDs `SYN_019` / `SYN_020`).

### Steps

1. Generate campaign (`evals/discovery/campaigns/unsupported_future_v1.json`) with 4–8 questions in the `UNSUPPORTED_FUTURE` category. Use `campaign_generator.generate_from_cluster()` or `generate_from_category()`.
2. Run live: `iteration_runner.run_campaign(<campaign>, label="unsupported_future_v1")`. This invokes `synthetic_runner.run()` with `--workers 1` (Phase 10 DuckDB-concurrency lesson) and writes the standard 4 output files under `evals/runs/<ts>__synthetic_unsupported_future_v1/`.
3. The runner's clusterer output feeds `failure_backlog.append_or_update(...)`. At least one entry written.
4. `triage_rubric.classify(...)` runs against the new/updated entry → `recommended_action` set.
5. `promote.py` runs against the entry → at least one proposal artefact emitted (commented xfail stub, `docs/review/*.md`, or fixture diff).
6. `compare_runs(phase10_run_dir, new_run_dir)` writes the diff JSON.
7. STATE.md, ROADMAP.md, REQUIREMENTS.md updated.
8. `11-07-SUMMARY.md` written with evidence table, run-dir name, and pending follow-on items.

### Pass criteria

- Live run produces 4 output files in the new run directory.
- Backlog file contains at least one entry sourced from this run.
- At least one promotion proposal artefact exists on disk.
- `git diff --name-only src/basic_stats/` returns empty.
- 173/173 unit tests still passing (Phase 10 baseline) plus the new Phase 11 tests (target: 180+ total).
- The phase does NOT assert that the agent's behaviour for `UNSUPPORTED_FUTURE` improves. It asserts the loop **observes, classifies, and routes** the failure correctly.

---

## 10. Exit Gates

| Gate | Description | Satisfied by |
|------|-------------|--------------|
| 1 | `11-SPEC.md` exists and locks artefact layout, schemas, action-type enum, exit gates | Plan 11-01 |
| 2 | `evals/discovery/failure_backlog.json` + helper module + tests | Plan 11-02 |
| 3 | Triage rubric document + classifier + tests covering all 7 action types | Plan 11-03 |
| 4 | Campaign generator + `campaigns/` dir + tests for both modes | Plan 11-04 |
| 5 | Iteration runner + `compare_runs` + diff JSON writer + tests | Plan 11-05 |
| 6 | `promote.py` + per-action proposal templates + tests covering all 7 emission paths | Plan 11-06 |
| 7 | Live verification campaign run + backlog/promotion evidence + STATE.md/ROADMAP.md/REQUIREMENTS.md updated + 11-07-SUMMARY.md | Plan 11-07 |
| 8 | `src/basic_stats/*` shows zero diff throughout the phase | Continuous (every plan) |
| 9 | Phase 10 baseline (173/173 tests) preserved; new Phase 11 tests pass | Continuous (every plan) |

---

## 11. Non-Goals

Explicitly out of scope for Phase 11 v1 — do NOT plan or implement:

- Production code changes under `src/basic_stats/*` (read-only constraint).
- Auto-promotion (no manual approval gate). v1 keeps every promotion human-gated.
- Auto-fix of `agent_behavior_fix_needed` clusters via subagents — `promote.py` only emits proposal documents.
- LLM-based sub-clustering of failure clusters (Phase 10 deferred this; v1 keeps it deferred).
- Cross-campaign correlation analytics, web dashboards, Slack/GitHub-issue integrations.
- Removing the `--workers 1` constraint on `synthetic_runner` (would require touching `BasicStatsAgent` init — out of scope).
- Streamlit / UI changes; visualisation; qualities integration.
- Enabling xfail-marked regression tests automatically.
- Modifying upstream Phase 10 artefacts (`10-SPEC.md`, `synthetic_runner.py`, `synthetic_clusterer.py`, `seed_questions.json`, `test_synthetic_regressions.py`) beyond the explicit append patterns documented in §8.

---

## 12. Commit Hygiene Reminders

- Never `git add .` or `git add -A`. Stage explicit paths only.
- Never stage `db/basic_stats.duckdb`, `.claude/settings.local.json`, `.planning/config.json`, or `evals/runs/*` outputs.
- Never stage `docs/review/*` files unless they were emitted by `promote.py` AND the user has approved staging.
- Verify `evals/runs/` is gitignored before any commit: `git check-ignore evals/runs/`.
- Verify `src/basic_stats/` zero diff before any Phase 11 commit: `git diff --name-only src/basic_stats/` MUST return empty.

---

## 13. Inheritance from Phase 10

This SPEC explicitly inherits the following from `10-SPEC.md` and uses them verbatim:

- 12-category failure taxonomy (`10-SPEC.md` §2).
- Synthetic question fixture schema (`10-SPEC.md` §3).
- Synthetic runner contract (`10-SPEC.md` §4) — the `--workers 1` constraint documented in `10-06-SUMMARY.md` MUST be respected.
- Per-question result schema (`10-SPEC.md` §5).
- Failure cluster schema (`10-SPEC.md` §6) — backlog entries derive from this.
- Regression test workflow (`10-SPEC.md` §7) — promotion rules in §8 above implement this.

---

*Spec authored: 2026-04-29 during Phase 11 planning. Plan 11-01 (Wave 1) re-authors / locks this file as the formal phase contract before Plans 11-02..11-07 execute.*
