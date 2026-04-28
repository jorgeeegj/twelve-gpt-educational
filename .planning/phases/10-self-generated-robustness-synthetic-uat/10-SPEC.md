# Phase 10 Specification: Self-Generated Robustness / Synthetic UAT

**Authored:** 2026-04-28 by Plan 10-01
**Status:** Authoritative — Plans 02–06 implement against this contract.

---

## 1. Goal

Phase 10 builds discovery infrastructure on top of `BasicStatsAgent`. It generates synthetic natural-language football-stats questions, runs them through the agent using the existing eval entry points, evaluates outputs with existing guards (`raw_key_guard`, `faithfulness_judge`), clusters failures by category into a digestible report, and converts confirmed failures into regression tests before any production fix. Phase 10 does NOT modify production code under `src/basic_stats/*` — it is discovery infrastructure only. Every artifact it produces (runner, clusterer, regression scaffold, run outputs) is additive; `src/basic_stats/` shows zero diff throughout the phase.

---

## 2. Failure Categories (taxonomy enum)

The following 12 strings are the canonical `failure_category` enum values used throughout Phase 10. Every seed-fixture question MUST be tagged with exactly one category from this list.

```
DIRECT_STATS                # single-entity, single-metric (e.g. "Salah goals")
RANKINGS                    # top-N / bottom-N players or teams
COMPARISONS                 # player-vs-player, team-vs-team, multi-entity
FOLLOW_UPS                  # multi-turn chains where context carries
TOP6_VS_BIG6                # league-position bucket vs canonical Big Six set
CHAMPIONS_LEAGUE            # all-routes (incl. Tottenham via Europa) vs strictly via league position
P90_METRICS                 # base p90 (*_p90) and event-stat p90 in match-context
HOME_AWAY                   # single-side and dual-side comparisons
SPANISH_ENGLISH             # ES/EN mirror coverage; Spanish away-wins, top-N phrasing
UNSUPPORTED_FUTURE          # next matchday / next season — agent should refuse
AMBIGUOUS                   # under-specified entity / metric / context
DEMO_RANDOM                 # spirit of random_questions.json (Ricardo/Álvaro/Jorge)
```

These enum values are used as `category` tags in `evals/synthetic/seed_questions.json` and as `failure_category` values written by the clusterer into `results.json` and `failure_clusters.json`.

---

## 3. Synthetic Question Fixture Schema (JSON)

The synthetic question fixture lives at `evals/synthetic/seed_questions.json`. Each entry MUST conform to the following schema:

```json
{
  "id": "SYN_<NNN>",
  "category": "<one of the 12 enum values above>",
  "language": "en",
  "question": "<NL question string>",
  "expected_behavior": "answerable",
  "expected_values": {"<key>": "<number or string>"},
  "notes": "<optional free-text rationale or edge-case marker>"
}
```

Field constraints:

- `id`: string matching `SYN_` followed by zero-padded three-digit integer (e.g. `SYN_001`).
- `category`: exactly one of the 12 enum values from section 2.
- `language`: `"en"` or `"es"`.
- `question`: natural-language question string. Multi-turn chains use `|` as a turn separator (e.g. `"How many goals has Salah scored?|But against the top 6?"`).
- `expected_behavior`: one of `"answerable"`, `"refuse"`, or `"ambiguous_clarify"`.
- `expected_values`: `null` when `expected_behavior != "answerable"`. When non-null, mirrors the shape used by `evals/questions_benchmark.json` (player `short_name` / `team_name` / metric key → value) so `judge_faithfulness` can consume it directly.
- `notes`: optional free-text string; may be `null` or omitted.

Minimum fixture size: 24 entries. All 12 categories must be represented at least twice. At least one Spanish-language entry. Tottenham Champions League edge case and Top-6-vs-Big-Six distinction must both be present.

---

## 4. Runner Contract (`evals/synthetic_runner.py`)

This section specifies the public surface of `evals/synthetic_runner.py`. Implementation is in Plan 03.

### Function signature

```python
def run(fixture_path: Path, label: str, max_workers: int = 5, skip_judges: bool = False, dry_run: bool = False) -> Path:
```

Returns the run-output directory as a `Path`.

### CLI

```
uv run python -m evals.synthetic_runner \
  --fixture evals/synthetic/seed_questions.json \
  --label <label> \
  [--workers N] \
  [--skip-judges] \
  [--dry-run]
```

`--dry-run` validates the fixture only (schema check, no agent calls). CLI `--dry-run` maps 1:1 to the `dry_run=True` kwarg.

### Reuses (do NOT reimplement)

- `BasicStatsAgent` from `src.basic_stats.agent` — one instance per question (matches `agent_benchmark.py` pattern; sharing one instance across parallel workers corrupts `_last_response_id` and causes 400 errors).
- `find_violations` from `evals.raw_key_guard`.
- `judge_faithfulness` from `evals.judges.faithfulness_judge` (when `expected_values` is non-null).
- The `_ask_with_retry` retry pattern from `evals/agent_benchmark.py` (exponential backoff on `openai.RateLimitError`).

### Output directory

`evals/runs/<YYYY-MM-DD_HH-MM-SS>__synthetic_<label>/`

This path is already covered by `evals/runs/` in `.gitignore` — confirm with `git check-ignore evals/runs/` before commit.

### Output files — live run (default, `dry_run=False`)

| File | Description |
|------|-------------|
| `summary.json` | Top-level gate counts + by-category breakdown; `"dry_run": false` |
| `results.json` | Per-question array (schema in section 5) |
| `failure_clusters.json` | Written by clusterer (see Plan 04); always present; `clusters: []` when no failures |
| `REPORT.md` | Markdown report written by clusterer (see Plan 04); always present |

### Output files - dry-run (`dry_run=True` or `--dry-run`)

| File | Description |
|------|-------------|
| `summary.json` | Minimal: `{"fixture_path": "...", "total_questions": N, "dry_run": true, "validation": "ok"}` — no category breakdown |
| `results.json` | Empty JSON array `[]` |

No `failure_clusters.json`, no `REPORT.md`. The clusterer is NOT invoked in dry-run; the run early-returns after writing the two files above.

### Exit codes

- `0`: successful run (regardless of failure count — discovery is the goal).
- `1`: fixture parse error or runner crash.

Failure presence does NOT produce a non-zero exit code.

---

## 5. Per-Question Result Schema (`results.json` entries)

Each entry in `results.json` MUST contain the following fields (mirrors `agent_benchmark.evaluate_one` output; drops benchmark-only fields such as `naturalness_score`, `completeness`; adds two multi-turn fields):

```json
{
  "id": "SYN_<NNN>",
  "category": "<taxonomy enum>",
  "language": "en",
  "question": "<original, possibly with '|' turn separators>",
  "is_multi_turn": true,
  "turn_answers": ["<turn 1 answer>", "..."],
  "answer": "<final-turn agent answer or 'ERROR: ...'",
  "expected_behavior": "answerable",
  "faithfulness_passed": true,
  "faithfulness_reason": "<string>",
  "raw_key_violations": ["<token>"],
  "raw_key_passed": true,
  "tool_calls": ["..."],
  "iterations_used": 2,
  "hit_max_iterations": false,
  "failure_category": null
}
```

Field semantics:

- `is_multi_turn`: `true` iff the original `question` string contained at least one `|` separator.
- `turn_answers`: per-turn answer array for multi-turn entries; `null` for single-turn questions.
- `answer`: always the FINAL-turn answer (the answer the user would see at the end of the chain). Guards and faithfulness are applied to this field only.
- `failure_category`: `null` when the question passed all guards. Otherwise set by the clusterer (see section 6 and Plan 04). The clusterer keys on `category` × `failure_category` only — `is_multi_turn` and `turn_answers` are persisted for human review, not for clustering.

---

## 6. Failure Cluster Schema (`failure_clusters.json`)

```json
{
  "run_id": "<run-dir-name>",
  "total_questions": 24,
  "total_failures": 3,
  "clusters": [
    {
      "category": "<taxonomy enum>",
      "failure_signature": "<short string, e.g. 'p90_returns_raw_sum' or 'tottenham_misclassified'>",
      "count": 2,
      "question_ids": ["SYN_001", "SYN_007"],
      "sample_answers": ["<first 200 chars of answer>"],
      "guard_evidence": "<which guard flagged: faithfulness | raw_key | refuse_expected | other>"
    }
  ]
}
```

Initial clustering (Plan 04) uses heuristics: group by `category` × `guard_evidence`. LLM-based sub-clustering is deferred (out of scope for Phase 10).

---

## 7. Regression Test Workflow

When and how a regression test is added to `tests/test_synthetic_regressions.py`:

1. A failure is observed in a run (a question has `failure_category != null` in `results.json`).
2. The cluster has `count >= 1` and is reproducible across two consecutive runs.
3. Author a test in `tests/test_synthetic_regressions.py` that calls `BasicStatsAgent().ask(question)` and asserts the failing condition (e.g. raw-key absence, expected number presence). Use `pytest.mark.xfail` if the production fix is deferred.
4. Reference the cluster's `failure_signature` in the test docstring.
5. The test file MUST exist after Plan 05 even with zero real regressions — it ships with a workflow comment block at the top describing steps 1–4 above.

The file does NOT import `BasicStatsAgent`, DuckDB, or `openai` at module level. All agent imports live inside test function bodies or class methods to keep collection fast.

---

## 8. Exit Gates (verbatim from CONTEXT.md)

| Gate | Description | Satisfied by |
|------|-------------|--------------|
| 1 | SPEC.md exists, names failure categories + exit criteria | Plan 01 (this) |
| 2 | Synthetic question generator + seed fixture committed and runnable | Plan 02 |
| 3 | Synthetic runner committed; one full run produces a report | Plan 03 + Plan 06 |
| 4 | At least one round of failure clustering completed | Plan 04 + Plan 06 |
| 5 | Regression test scaffold exists; tests added per cluster | Plan 05 |
| 6 | Existing tests/ suite remains green (160/160 baseline) | Plan 06 |
| 7 | STATE.md updated with Phase 10 status + exit-gate evidence | Plan 06 |

---

## 9. Non-Goals (verbatim from CONTEXT.md)

Explicitly out of scope for Phase 10 — do NOT plan or implement:

- No visualizations / Streamlit UI changes
- No qualities integration
- No production agent refactor (`src/basic_stats/*` is read-only)
- No auto-code self-modification
- No broad repo cleanup
- No new core agent behaviour
- No auto-fix of clustered failures

---

## 10. Commit Hygiene Reminders

- Never `git add .` — stage explicit paths only.
- Never stage `db/basic_stats.duckdb`, `.claude/` local files, `evals/runs/` outputs, caches, or unrelated artifacts.
- Show the exact diff of any planning-doc modification before commit unless the GSD workflow explicitly requires the docs commit at that step.

---

*Spec authored: 2026-04-28 by Plan 10-01.*
