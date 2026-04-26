---
phase: 9
phase_name: natural-language-polish
plan: 01
title: Natural Language Polish — Prompt enrichment + NLP-01 guard + UAT gate
wave: 1
depends_on: []
autonomous: false
files_modified:
  - src/basic_stats/prompts/agent_system.yaml
  - evals/agent_benchmark.py
  - evals/raw_key_guard.py            # new
  - tests/test_raw_key_guard.py       # new
  - .planning/ROADMAP.md
  - .planning/STATE.md
requirements_addressed:
  - NLP-01
  - NLP-02
  - NLP-03
canonical_refs:
  - .planning/phases/09-natural-language-polish/09-CONTEXT.md
  - .planning/phases/09-natural-language-polish/09-DISCUSSION-LOG.md
  - .planning/ROADMAP.md
  - .planning/REQUIREMENTS.md
  - .planning/STATE.md
  - src/basic_stats/prompts/agent_system.yaml
  - evals/agent_benchmark.py
  - evals/judges/faithfulness_judge.py
  - docs/premier_league_2024_25_context.md
  - docs/review/pre_phase9_uat_checklist.md
must_haves:
  - HOW TO WRITE YOUR ANSWER section explicitly forbids raw column tokens with examples
  - NLP-01 regex guard runs inside evals/agent_benchmark.py and fails any answer that emits a known raw token
  - At least one deterministic insight rule (goals vs xG, ±1.0 threshold) is present in agent_system.yaml in EN and ES
  - Faithfulness ≥ 0.95 on both questions_benchmark.json and random_questions.json with the new prompt
  - NLP-01 guard reports 0 violations on the post-Phase-9 run for both benchmarks
  - pre_phase9_uat_checklist.md re-run shows 0 raw-key signals and 0 hallucinated values
  - ROADMAP.md §Phase 9 success criterion #5 updated (61/61 eval_runner.py replaced with current gate per D-10)
---

# Phase 9 — Natural Language Polish

## Objective

Polish the LLM's final answers so they read as natural football-analyst prose, with deterministic enforcement of "no raw metric keys" via an eval-time regex guard, contextual framing examples in the prompt, and one deterministic insight rule (goals vs xG). Architecture stays prompt-only — no template renderer, no tool-output shaping, no runtime retry.

Grounding for every task in this plan: `09-CONTEXT.md` decisions D-01..D-10. Read it before starting.

## Scope (locked)

- ✅ In: `src/basic_stats/prompts/agent_system.yaml` enrichment, new `evals/raw_key_guard.py` helper, integration into `evals/agent_benchmark.py`, new test file, ROADMAP/STATE update.
- ❌ Out: `verbalize.yaml` template layer, tool-return shape changes, runtime retry, additional insight rules, WI-3..WI-5 robustness backlog, LLM-judge style eval.

## Wave overview

| Wave | Tasks | Parallelizable | Purpose |
|------|-------|----------------|---------|
| 1    | T1, T2 | yes (independent files) | Capture pre-Phase-9 baseline + build raw-token list |
| 2    | T3, T4 | T4 after T3 | Implement and unit-test NLP-01 guard |
| 3    | T5     | sequential | Validate guard against the captured baseline |
| 4    | T6, T7, T8, T9 | sequential (same YAML file) | Enrich `agent_system.yaml` |
| 5    | T10, T11 | parallel | Post-edit benchmark + pytest |
| 6    | T12    | sequential, manual | UAT re-run |
| 7    | T13, T14 | parallel | Doc closeout |

---

## T1 — Capture pre-Phase-9 baseline run

**Wave:** 1
**Depends on:** —
**Purpose:** Lock the "before" numbers so the guard's measurements and post-edit deltas are attributable. STATE.md cites 59/61 from `post_residual_closeout_final` (2026-04-23); this re-runs to confirm the same conditions reproduce on today's branch state.

**Read first:**
- `.planning/STATE.md` §Pre-Phase-9 Robustness Closeout (lines 258–294)
- `evals/agent_benchmark.py` (current shape; gates dict; per-result fields)
- `evals/runs/2026-04-23_18-19-20__post_residual_closeout_final/` (reference baseline)

**Action:**
```bash
PYTHONIOENCODING=utf-8 uv run python evals/agent_benchmark.py \
  --label pre_phase9_baseline_questions
PYTHONIOENCODING=utf-8 uv run python evals/agent_benchmark.py \
  --random --label pre_phase9_baseline_random
```

**Target output:** `evals/runs/<timestamp>__pre_phase9_baseline_questions/summary.json` and `..._pre_phase9_baseline_random/summary.json`.

**Verification:**
```bash
ls evals/runs/ | grep -E "pre_phase9_baseline_(questions|random)"
python -c "import json; s=json.load(open(sorted([p for p in __import__('pathlib').Path('evals/runs').iterdir() if 'pre_phase9_baseline_questions' in p.name])[-1] / 'summary.json')); print(s['gates']['faithfulness'])"
```

**Acceptance criteria:**
- Two new run directories exist under `evals/runs/` with the labels above.
- `summary.json.gates.faithfulness.value >= 0.95` for `pre_phase9_baseline_questions` (must reproduce the 59/61 ≈ 0.967 baseline; abort phase if lower).
- `summary.json.error_count == 0` (no agent crashes).
- Save the timestamps of both runs in a comment at the top of T5 (used as `BEFORE_RUN`).

---

## T2 — Build raw-key token list helper

**Wave:** 1 (parallel with T1)
**Depends on:** —
**Purpose:** D-04 says the regex guard's token list is *derived from* the `AVAILABLE STATS` block of `agent_system.yaml`, not hand-listed. Build that derivation as a small pure function so it stays in sync as new metrics are added.

**Read first:**
- `src/basic_stats/prompts/agent_system.yaml` (specifically the `AVAILABLE STATS` block and its sub-tables)
- `09-CONTEXT.md` D-04

**New file:** `evals/raw_key_guard.py`

**Action:** create the helper with this exact API:

```python
"""evals/raw_key_guard.py — NLP-01 guard.

Detects raw column/metric tokens leaking into LLM answers. The token list is
parsed from agent_system.yaml's AVAILABLE STATS block so it stays in sync as
new metrics are added.
"""
from __future__ import annotations

import re
import yaml
from pathlib import Path
from functools import lru_cache

PROMPT_PATH = Path(__file__).resolve().parents[1] / "src/basic_stats/prompts/agent_system.yaml"

# Tokens that are ALWAYS forbidden in answers regardless of the stats block.
# These are robotic patterns the LLM falls into even when not citing a column.
_HARDCODED_FORBIDDEN = frozenset({
    "metric_value",
    "team_score",
    "opponent_score",
    "is_home",
    "matchday_start",
    "matchday_end",
    "opponent_rank_lte",
    "opponent_rank_gte",
    "opponent_is_big6",
    "rank_mode",
    "min_minutes",
    "min_matches",
})

# Words to preserve even when they appear in the stats list — they are valid
# English/Spanish prose nouns when used naturally.
_PROSE_ALLOWLIST = frozenset({
    "goals", "assists", "shots", "minutes", "points", "wins",
    "saves", "interceptions", "clearances", "crosses", "recoveries",
    "passes", "fouls", "carries", "dribbles",
})

@lru_cache(maxsize=1)
def load_forbidden_tokens(prompt_path: Path = PROMPT_PATH) -> frozenset[str]:
    """Parse agent_system.yaml AVAILABLE STATS block, return forbidden tokens.

    Rule: include any token that contains '_' (snake_case columns) plus any
    token ending in '_pct', '_p90', or '_per_90'. Bare prose nouns are kept
    out via _PROSE_ALLOWLIST.
    """
    raw = yaml.safe_load(prompt_path.read_text(encoding="utf-8"))["system"]
    # Slice from "AVAILABLE STATS" header to the next ALL-CAPS header.
    block = re.search(r"AVAILABLE STATS.*?(?=\n  [A-Z][A-Z ]{3,}\n)", raw, re.DOTALL)
    text = block.group(0) if block else ""
    candidates = set(re.findall(r"\b[a-z][a-z0-9_]*\b", text))
    forbidden = {
        t for t in candidates
        if (("_" in t) or t.endswith(("_pct", "_p90")) or t.endswith("_per_90"))
        and t not in _PROSE_ALLOWLIST
    }
    return frozenset(forbidden | _HARDCODED_FORBIDDEN)

def find_violations(answer: str, forbidden: frozenset[str] | None = None) -> list[str]:
    """Return sorted list of raw tokens found in answer (case-insensitive, word-bounded)."""
    if forbidden is None:
        forbidden = load_forbidden_tokens()
    hits = []
    lowered = answer.lower()
    for tok in forbidden:
        if re.search(rf"\b{re.escape(tok)}\b", lowered):
            hits.append(tok)
    return sorted(set(hits))
```

**Acceptance criteria:**
- `evals/raw_key_guard.py` exists.
- `python -c "from evals.raw_key_guard import load_forbidden_tokens; assert 'total_goals' in load_forbidden_tokens(); assert 'goals' not in load_forbidden_tokens(); assert 'xg_total_p90' in load_forbidden_tokens(); assert 'metric_value' in load_forbidden_tokens(); print('ok')"` prints `ok`.
- `python -c "from evals.raw_key_guard import find_violations; assert find_violations('Haaland scored 5 goals') == []; assert find_violations('total_goals_p90 was 0.625') == ['total_goals_p90']; print('ok')"` prints `ok`.

**Verification:**
```bash
uv run python -c "from evals.raw_key_guard import load_forbidden_tokens, find_violations; \
  forb = load_forbidden_tokens(); \
  assert 'total_goals' in forb and 'xg_total_p90' in forb and 'goals' not in forb; \
  assert find_violations('Haaland scored 5 goals against the Big Six.') == []; \
  assert 'total_goals' in find_violations('Haaland total_goals = 5'); \
  print(f'{len(forb)} forbidden tokens loaded, smoke checks pass')"
```

---

## T3 — Wire NLP-01 guard into `agent_benchmark.py`

**Wave:** 2
**Depends on:** T2

**Purpose:** Make the guard a hard gate of the benchmark, not a side script. Per D-03, this is a measurement only — no runtime retry, no answer mutation.

**Read first:**
- `evals/agent_benchmark.py` (current `evaluate_one`, `gates`, `summary`, `print_summary`, `save_results`)
- `evals/raw_key_guard.py` (just created)

**Target file:** `evals/agent_benchmark.py`

**Action:** apply these concrete edits:

1. After existing imports, add:
   ```python
   from evals.raw_key_guard import find_violations, load_forbidden_tokens
   ```
2. Below the existing gate constants, add:
   ```python
   RAW_KEY_GATE = 0  # 0 violations — hard gate
   ```
3. Inside `evaluate_one`, after `faith = judge_faithfulness(...)`, add:
   ```python
   raw_key_violations = find_violations(answer)
   ```
4. In the returned dict, add two fields:
   ```python
   "raw_key_violations": raw_key_violations,
   "raw_key_passed": len(raw_key_violations) == 0,
   ```
5. In `run_benchmark_async`, alongside `faith_total` / `faith_pass`, add accumulators:
   ```python
   raw_key_total = 0
   raw_key_pass = 0
   ```
   Increment inside the per-result loop:
   ```python
   raw_key_total += 1
   if r["raw_key_passed"]:
       raw_key_pass += 1
   ```
6. Add a new gate after `faithfulness`:
   ```python
   gates["raw_keys"] = {
       "value": faith_total - raw_key_pass,  # number of violating answers
       "threshold": RAW_KEY_GATE,
       "passed": (faith_total - raw_key_pass) == 0,
       "score": f"{raw_key_pass}/{raw_key_total} clean",
   }
   ```
7. In `by_category`, add `"raw_key_pass": 0` to the defaultdict factory and increment when `r["raw_key_passed"]`. Surface `raw_keys_clean: f"{b['raw_key_pass']}/{b['total']}"` in the per-category summary.
8. In the printed summary loop, the existing `for name, gate in gates.items()` already prints all gates — confirm `raw_keys` shows up.

**Acceptance criteria:**
- `grep -n "raw_key_guard" evals/agent_benchmark.py` returns at least one match.
- `grep -nE 'gates\["raw_keys"\]' evals/agent_benchmark.py` returns 1 match.
- `grep -n "RAW_KEY_GATE" evals/agent_benchmark.py` returns the constant declaration.
- The dictionary returned by `evaluate_one` contains keys `raw_key_violations` (list[str]) and `raw_key_passed` (bool).

**Verification:**
```bash
grep -nE "raw_key_guard|raw_key_violations|raw_keys|RAW_KEY_GATE" evals/agent_benchmark.py
uv run python -c "import ast,inspect; src=open('evals/agent_benchmark.py').read(); \
  assert 'from evals.raw_key_guard import' in src; \
  assert 'gates[\"raw_keys\"]' in src; \
  assert 'raw_key_passed' in src; print('wiring ok')"
```

---

## T4 — Unit tests for the guard

**Wave:** 2
**Depends on:** T3 (test file imports both helpers)

**Purpose:** Prevent the guard from drifting silently when new metrics are added.

**Read first:**
- `evals/raw_key_guard.py`
- `src/basic_stats/prompts/agent_system.yaml` (AVAILABLE STATS block)
- `tests/test_agent_prompt.py` (style reference for prompt-related tests)

**New file:** `tests/test_raw_key_guard.py`

**Action:** create with these test cases:

```python
"""Tests for the NLP-01 raw-key guard."""
from __future__ import annotations

import pytest
from evals.raw_key_guard import find_violations, load_forbidden_tokens


@pytest.fixture(scope="module")
def forb():
    return load_forbidden_tokens()


class TestForbiddenTokenLoad:
    def test_contains_known_columns(self, forb):
        assert "total_goals" in forb
        assert "xg_total_p90" in forb
        assert "pass_accuracy_pct" in forb
        assert "metric_value" in forb
        assert "opponent_is_big6" in forb

    def test_excludes_prose_nouns(self, forb):
        assert "goals" not in forb
        assert "assists" not in forb
        assert "minutes" not in forb

    def test_nonempty(self, forb):
        assert len(forb) >= 30  # current AVAILABLE STATS has well over this


class TestFindViolations:
    def test_clean_natural_answer(self):
        assert find_violations("Haaland has scored 5 goals against the Big Six.") == []

    def test_raw_column_caught(self):
        hits = find_violations("Haaland total_goals = 5 across 8 appearances")
        assert "total_goals" in hits

    def test_p90_column_caught(self):
        hits = find_violations("xg_total_p90 was 0.473 vs Big Six")
        assert "xg_total_p90" in hits

    def test_filter_key_caught(self):
        # opponent_is_big6 is a filter key, not a stat — still robotic
        assert "opponent_is_big6" in find_violations("filter opponent_is_big6=true used")

    def test_case_insensitive(self):
        assert "total_goals" in find_violations("TOTAL_GOALS = 5")

    def test_word_boundary(self):
        # "subtotal_goals" should not flag "total_goals"
        assert find_violations("That subtotal_goalsmith dribbled past") == []

    def test_multiple_distinct(self):
        hits = find_violations("returned total_goals=5 and xg_total=3.44")
        assert "total_goals" in hits and "xg_total" in hits
```

**Acceptance criteria:**
- File exists at `tests/test_raw_key_guard.py`.
- `uv run pytest tests/test_raw_key_guard.py -q` exits 0.
- All 9 tests pass (3 in `TestForbiddenTokenLoad`, 6 in `TestFindViolations`).

**Verification:**
```bash
uv run pytest tests/test_raw_key_guard.py -q
```

---

## T5 — Validate guard against pre-Phase-9 baseline

**Wave:** 3
**Depends on:** T1, T3, T4

**Purpose:** Document the "before" picture: what raw-key violations exist *today*, before any prompt edit. This is the delta we need to drive to zero.

**Read first:**
- The two run dirs from T1: `evals/runs/<ts>__pre_phase9_baseline_questions/results.json`, `..._random/results.json`

**Action:** run a one-shot script (do **not** create a new file — use a here-doc):

```bash
uv run python - <<'PY'
import json, sys
from pathlib import Path
from evals.raw_key_guard import find_violations

runs = sorted(Path("evals/runs").glob("*__pre_phase9_baseline_*"))
for run in runs:
    results = json.load(open(run / "results.json", encoding="utf-8"))
    violators = []
    for r in results:
        v = find_violations(r["answer"])
        if v:
            violators.append((r["id"], v, r["answer"][:120]))
    print(f"\n=== {run.name} ===")
    print(f"  total={len(results)} violators={len(violators)}")
    for vid, vtoks, snippet in violators[:20]:
        print(f"  - {vid}: {vtoks}  «{snippet}…»")
PY
```

**Expected outcome:** the script prints non-zero violator counts (proves the baseline contains raw-key leakage — the very thing Phase 9 will eliminate). Save the printed report into the phase dir for the closeout commit:

```bash
uv run python - <<'PY' > .planning/phases/09-natural-language-polish/09-BASELINE-VIOLATIONS.md
# ... same script, but with markdown framing ...
PY
```

**Acceptance criteria:**
- The script runs without error.
- Output prints at least one violator per benchmark (if zero, halt — the guard or the prompt is misaligned and Phase 9 has no measurable target).
- File `.planning/phases/09-natural-language-polish/09-BASELINE-VIOLATIONS.md` exists with the violator list.

**Verification:**
```bash
test -f .planning/phases/09-natural-language-polish/09-BASELINE-VIOLATIONS.md && echo "baseline captured"
grep -cE "violators=" .planning/phases/09-natural-language-polish/09-BASELINE-VIOLATIONS.md  # expect 2
```

---

## T6 — Enrich `agent_system.yaml` — NLP-01 explicit ban + examples

**Wave:** 4 (sequential within file)
**Depends on:** T5

**Purpose:** D-01 + D-03 prompt half. Replace the current short bullet "State the key stat(s) in natural language — never expose raw column names" with an explicit ban list and 2 good/bad pairs.

**Read first:**
- `src/basic_stats/prompts/agent_system.yaml` (specifically `HOW TO WRITE YOUR ANSWER`)
- `09-BASELINE-VIOLATIONS.md` (what the LLM actually leaks today — pick examples from real failures)

**Target file:** `src/basic_stats/prompts/agent_system.yaml`

**Action:** in the `HOW TO WRITE YOUR ANSWER` section, replace the line
```
  - State the key stat(s) in natural language — never expose raw column names
    like total_goals, team_score, or metric_value.
```
with:

```
  - NEVER write raw metric keys, filter keys, or schema column names in your answer.
    Examples of FORBIDDEN tokens (this is not exhaustive — apply the rule):
      total_goals, total_goals_p90, total_goals_against, xg_total, xg_total_p90,
      pass_accuracy_pct, team_score, opponent_score, metric_value, opponent_is_big6,
      opponent_rank_lte, matchday_start, is_home, min_minutes, min_matches.
    State quantities in natural prose: "5 goals", "0.625 goals per 90 minutes",
    "73% pass accuracy", "5 goals against the Big Six", "Liverpool's home form".
  - GOOD: "Haaland has scored 6 goals with an xG of 3.44, finishing well above expectation."
  - BAD : "Haaland total_goals=6 xg_total=3.44."
  - GOOD: "Salah averaged 0.62 goals per 90 minutes against the Big Six."
  - BAD : "Salah total_goals_p90 with opponent_is_big6=true was 0.62."
```

**Acceptance criteria:**
- `grep -nE "NEVER write raw metric keys" src/basic_stats/prompts/agent_system.yaml` returns 1 match.
- `grep -nE "GOOD:.*Haaland has scored" src/basic_stats/prompts/agent_system.yaml` returns 1 match.
- `grep -nE "BAD :.*total_goals=6" src/basic_stats/prompts/agent_system.yaml` returns 1 match.
- The file still parses as YAML: `uv run python -c "import yaml; yaml.safe_load(open('src/basic_stats/prompts/agent_system.yaml'))"` exits 0.

**Verification:**
```bash
grep -cE "NEVER write raw metric keys|GOOD:|BAD :" src/basic_stats/prompts/agent_system.yaml  # >= 5
uv run python -c "import yaml; yaml.safe_load(open('src/basic_stats/prompts/agent_system.yaml')); print('yaml ok')"
uv run pytest tests/test_agent_prompt.py -q  # existing prompt tests must still pass
```

---

## T7 — Add NLP-02 contextual framing examples

**Wave:** 4
**Depends on:** T6

**Purpose:** D-05 + D-06. Provide 2-3 good/bad pairs per context type (home/away, bucket, temporal) and force canonical category names from the league context doc.

**Read first:**
- `docs/premier_league_2024_25_context.md` (canonical category names: "the Big Six", "Champions League qualifiers", "mid-table", "the bottom three")
- `src/basic_stats/prompts/agent_system.yaml` (after T6 edits)

**Target file:** `src/basic_stats/prompts/agent_system.yaml`

**Action:** append to `HOW TO WRITE YOUR ANSWER` (after the GOOD/BAD pairs from T6):

```
  - For HOME / AWAY answers, frame the venue explicitly:
    GOOD: "At home, Salah has scored 14 goals; on the road, 9."
    BAD : "is_home=true value 14, is_home=false value 9."
  - For BUCKET answers (top N, bottom N, Big Six, mid-table), name the group with
    the canonical label from the league context paragraph above — verbatim:
    "the Big Six", "Champions League qualifiers", "mid-table", "the bottom three".
    GOOD: "Haaland has scored 5 goals against the Big Six this season."
    BAD : "Haaland scored 5 vs opponent_is_big6=true teams."
  - For TEMPORAL answers (last N gameweeks, between MD X and Y), state the window
    in matchday or gameweek prose:
    GOOD: "Over the last 5 gameweeks, Haaland scored 4 goals."
    BAD : "matchday_start=34 matchday_end=38 metric=4."
  - When citing a group of teams (e.g. derived buckets), list the team names you
    received from the tool — do not just print the count.
    GOOD: "Salah scored 2 goals against the three teams that have conceded the
           fewest: Arsenal, Liverpool, and Chelsea."
    BAD : "Salah scored 2 against the bottom-3 conceders."
```

**Acceptance criteria:**
- `grep -cE "For HOME / AWAY answers|For BUCKET answers|For TEMPORAL answers" src/basic_stats/prompts/agent_system.yaml` returns 3.
- `grep -cE "the Big Six|Champions League qualifiers|mid-table|the bottom three" src/basic_stats/prompts/agent_system.yaml` returns ≥ 4 (canonical labels mentioned).
- YAML still parses.

**Verification:**
```bash
grep -cE "For HOME / AWAY|For BUCKET|For TEMPORAL" src/basic_stats/prompts/agent_system.yaml
uv run python -c "import yaml; yaml.safe_load(open('src/basic_stats/prompts/agent_system.yaml'))"
```

---

## T8 — Add canonical-category rule

**Wave:** 4
**Depends on:** T7

**Purpose:** D-06. The bucket examples in T7 already use canonical names; this task adds an explicit rule so the LLM doesn't re-derive labels from the question text.

**Read first:**
- `src/basic_stats/prompts/agent_system.yaml` (after T7)
- `docs/premier_league_2024_25_context.md`

**Target file:** `src/basic_stats/prompts/agent_system.yaml`

**Action:** insert in `HOW TO WRITE YOUR ANSWER`, after the bucket example block:

```
  - When the user asks about a named group (Big Six, Champions League teams,
    mid-table, bottom three, European competition, etc.), use the EXACT label
    from the league context paragraph in your answer. Do not paraphrase, do not
    invent new labels, do not list the teams unless the user explicitly asks.
```

**Acceptance criteria:**
- `grep -nE "use the EXACT label" src/basic_stats/prompts/agent_system.yaml` returns 1 match.
- YAML still parses.

**Verification:**
```bash
grep -nE "use the EXACT label" src/basic_stats/prompts/agent_system.yaml
uv run python -c "import yaml; yaml.safe_load(open('src/basic_stats/prompts/agent_system.yaml'))"
```

---

## T9 — Add NLP-03 insight rule (goals vs xG, ±1.0)

**Wave:** 4
**Depends on:** T8

**Purpose:** D-07. Single deterministic insight rule, EN + ES surface forms, explicit thresholds. Triggered only when the answer references both `goals` and `xg_total` (or both p90 forms) for a single subject.

**Read first:**
- `src/basic_stats/prompts/agent_system.yaml` (after T8)
- `09-CONTEXT.md` D-07

**Target file:** `src/basic_stats/prompts/agent_system.yaml`

**Action:** add a new sub-section right below `HOW TO WRITE YOUR ANSWER`:

```yaml
  INSIGHT RULE — GOALS vs xG
  - When your answer cites BOTH the goals and xG (or goals_p90 and xg_total_p90)
    of a single player or team for the same scope, append exactly one short
    insight clause based on delta = goals - xG (or goals_p90 - xg_total_p90):
      delta >= +1.0  → "finishing above expectation" (ES: "finalizando por encima de lo esperado")
      delta <= -1.0  → "underperforming xG"          (ES: "rindiendo por debajo de su xG")
      otherwise      → omit the insight clause entirely (do not force a comment)
  - The clause is informational, not a separate sentence — append it after the
    facts using a comma. No probabilistic language ("might", "could"); the rule
    is deterministic.
    GOOD: "Haaland has scored 6 goals with an xG of 3.44, finishing above expectation."
    GOOD: "Haaland tiene 6 goles con un xG de 3.44, finalizando por encima de lo esperado."
    GOOD: "Mbappé tiene 4 goles con un xG de 5.5, rindiendo por debajo de su xG."
    BAD : "Haaland scored 6 goals with an xG of 3.44 (+2.56 above expected)." # numeric arithmetic — forbidden
    BAD : "Haaland scored 6 goals with an xG of 3.44, which is incredible." # subjective — not the rule
  - Do NOT compute the delta numerically in your answer. Do NOT use this rule
    when only one of {goals, xG} is present. Do NOT extend it to other metric
    pairs (shots vs shots_on_target, etc.) — that is out of scope for this phase.
```

**Acceptance criteria:**
- `grep -nE "INSIGHT RULE — GOALS vs xG" src/basic_stats/prompts/agent_system.yaml` returns 1 match.
- `grep -cE "finishing above expectation|underperforming xG|finalizando por encima|rindiendo por debajo" src/basic_stats/prompts/agent_system.yaml` returns ≥ 4.
- `grep -nE "delta >= \+1\.0|delta <= -1\.0" src/basic_stats/prompts/agent_system.yaml` returns 2 matches.
- YAML still parses.

**Verification:**
```bash
grep -nE "INSIGHT RULE|finishing above expectation|finalizando por encima" src/basic_stats/prompts/agent_system.yaml
uv run python -c "import yaml; yaml.safe_load(open('src/basic_stats/prompts/agent_system.yaml'))"
uv run pytest tests/test_agent_prompt.py -q  # prompt assembly tests must still pass
```

---

## T10 — Post-edit benchmark run (faithfulness + raw-key gates)

**Wave:** 5
**Depends on:** T6, T7, T8, T9

**Purpose:** D-09 hard gate. Both benchmarks (`questions_benchmark.json` and `random_questions.json`) must pass faithfulness ≥ 0.95 AND raw_keys gate (0 violations).

**Read first:**
- `09-CONTEXT.md` D-09 (gate definition)
- T1 artifacts (baseline numbers — for diff)

**Action:**
```bash
PYTHONIOENCODING=utf-8 uv run python evals/agent_benchmark.py \
  --label phase9_post_prompt_questions
PYTHONIOENCODING=utf-8 uv run python evals/agent_benchmark.py \
  --random --label phase9_post_prompt_random
```

**Acceptance criteria:**
- Two run dirs under `evals/runs/` with the labels above.
- For both runs, `summary.json.gates.faithfulness.passed == true` AND `summary.json.gates.raw_keys.passed == true`.
- For both runs, `summary.json.gates.raw_keys.value == 0` (zero violating answers).
- For both runs, `error_count == 0`.
- Faithfulness on `questions_benchmark.json` did not regress vs T1's baseline (allow ±1 case noise; investigate if drop is larger).

**Verification:**
```bash
uv run python - <<'PY'
import json
from pathlib import Path
for label in ("phase9_post_prompt_questions", "phase9_post_prompt_random"):
    run = sorted(Path("evals/runs").glob(f"*__{label}"))[-1]
    s = json.load(open(run / "summary.json", encoding="utf-8"))
    f = s["gates"]["faithfulness"]
    r = s["gates"]["raw_keys"]
    assert f["passed"], f"faithfulness FAILED for {label}: {f}"
    assert r["passed"] and r["value"] == 0, f"raw_keys FAILED for {label}: {r}"
    print(f"{label}: faithfulness={f['score']} raw_keys={r['score']} ✓")
PY
```

---

## T11 — Full pytest suite

**Wave:** 5 (parallel with T10)
**Depends on:** T6, T7, T8, T9

**Purpose:** Catch any prompt-assembly or downstream test breakage from the YAML edits.

**Action:**
```bash
uv run pytest tests/ -q -k "not fuzzy_resolve"
```

**Acceptance criteria:**
- Exit 0.
- Total count ≥ 98 + 9 (existing 98 + 9 new from T4) = 107 passing.
- `test_agent_prompt.py` passes — confirms the new YAML still loads and renders correctly.

**Verification:** the pytest output line `passed in Xs` shows the count and exit status is 0.

---

## T12 — UAT checklist re-run

**Wave:** 6
**Depends on:** T10, T11

**Purpose:** D-09 second leg. The 22-question manual checklist must show 0 raw-key signals and 0 hallucinated values.

**Read first:**
- `docs/review/pre_phase9_uat_checklist.md`
- T10 run summaries (sanity reference)

**Action:** run the Streamlit app locally and execute every question in `pre_phase9_uat_checklist.md` §3 (A1–K22, including the 4-turn H16 chain). For each, log the answer and apply the §5 "Señales de Bug o Regresión" filter.

**Output file:** `.planning/phases/09-natural-language-polish/09-UAT-RESULTS.md`. Use the §6 plantilla per question. At the end, summarise:
- raw-key signal count (must be 0)
- hallucinated-value count (must be 0)
- pass/total
- any new regressions

**Acceptance criteria:**
- `09-UAT-RESULTS.md` exists.
- Summary line `raw-key signals: 0` is present.
- Summary line `hallucinated values: 0` is present.
- Summary line `pass: ≥ 18 / 22` (UAT minimum from §1).
- H16 four-turn chain passes (no entity loss, no contradiction).

**Verification:**
```bash
test -f .planning/phases/09-natural-language-polish/09-UAT-RESULTS.md
grep -E "raw-key signals: 0|hallucinated values: 0" .planning/phases/09-natural-language-polish/09-UAT-RESULTS.md
```

**Note:** this task is manual and human-driven. Mark as ◆ in progress in STATE.md while running, then ✓ on completion.

---

## T13 — ROADMAP and REQUIREMENTS update

**Wave:** 7
**Depends on:** T10, T11, T12

**Purpose:** D-10 closeout. Retire the stale "61/61 eval_runner.py" line, mark Phase 9 complete in the progress table, mark NLP-01..NLP-03 done in REQUIREMENTS.md.

**Read first:**
- `.planning/ROADMAP.md` §Phase 9 (lines 188–204) and §Progress Tracking (lines 208–223)
- `.planning/REQUIREMENTS.md` §NLP (lines 74–78) and §Coverage (lines 131–133)

**Target files:** `.planning/ROADMAP.md`, `.planning/REQUIREMENTS.md`

**Action — ROADMAP.md:**

1. In §Phase 9 success criteria, replace
   ```
   5. 61/61 eval_runner.py benchmark still passes after Phase 9 completes (final validation)
   ```
   with
   ```
   5. Regression gate replaces the stale "61/61 eval_runner.py" criterion (eval_runner.py was deleted in Phase 5):
      a. evals/agent_benchmark.py faithfulness ≥ 0.95 on questions_benchmark.json AND random_questions.json
      b. evals/agent_benchmark.py raw_keys gate = 0 violations on both benchmarks
      c. docs/review/pre_phase9_uat_checklist.md re-run with 0 raw-key signals and 0 hallucinated values
   ```
2. Flip the Phase 9 row in the progress table from `Not started | —` to `Complete | <YYYY-MM-DD>`.
3. Flip the top checklist item `- [ ] **Phase 9: Natural Language Polish**` to `- [x]`.

**Action — REQUIREMENTS.md:**

1. Flip NLP-01, NLP-02, NLP-03 from `[ ]` to `[x]`.
2. In the coverage table, change the three NLP rows from `Pending` to `Complete`.

**Acceptance criteria:**
- `grep -n "evals/agent_benchmark.py raw_keys gate = 0" .planning/ROADMAP.md` returns 1 match.
- `grep -nE "^\- \[x\] \*\*Phase 9" .planning/ROADMAP.md` returns 1 match.
- `grep -nE "^\| 9 \| Natural Language Polish.*Complete" .planning/ROADMAP.md` returns 1 match.
- `grep -cE "^- \[x\] \*\*NLP-0[123]" .planning/REQUIREMENTS.md` returns 3.
- `grep -cE "^\| NLP-0[123] \| Phase 9 \| Complete" .planning/REQUIREMENTS.md` returns 3.

**Verification:**
```bash
grep -nE "raw_keys gate = 0|^\- \[x\] \*\*Phase 9|^\| 9 \| Natural Language Polish.*Complete" .planning/ROADMAP.md
grep -nE "^- \[x\] \*\*NLP-0[123]|^\| NLP-0[123] \| Phase 9 \| Complete" .planning/REQUIREMENTS.md
```

---

## T14 — STATE.md closeout

**Wave:** 7
**Depends on:** T10, T11, T12

**Purpose:** Reflect Phase 9 completion in the live status doc. Capture the new baseline numbers from T10 so future phases have an attributable reference.

**Read first:**
- `.planning/STATE.md`
- T10 run summaries

**Target file:** `.planning/STATE.md`

**Action:**
1. Replace the line `**Phase 9 — Natural Language Polish** ○ Pending ⬆️ *next*` with a complete block:
   ```markdown
   **Phase 9 — Natural Language Polish** ✓ Complete (<YYYY-MM-DD>)
   - ✓ `agent_system.yaml` HOW TO WRITE YOUR ANSWER enriched: NLP-01 raw-key ban + GOOD/BAD pairs, NLP-02 home/away/bucket/temporal framing, D-06 canonical category rule, NLP-03 goals-vs-xG insight rule (EN + ES, ±1.0 threshold)
   - ✓ NLP-01 regex guard (`evals/raw_key_guard.py` + 9 tests in `tests/test_raw_key_guard.py`) wired into `evals/agent_benchmark.py` as a hard gate
   - ✓ Post-Phase-9 benchmark — questions: faithfulness <X>/61 (run `phase9_post_prompt_questions`), random: faithfulness <X>/21 (run `phase9_post_prompt_random`); raw_keys gate = 0 in both
   - ✓ pre_phase9_uat_checklist.md re-run: 0 raw-key signals, 0 hallucinated values, ≥18/22 pass — see `09-UAT-RESULTS.md`
   - ✓ ROADMAP §Phase 9 success criterion #5 replaced (D-10 closeout); REQUIREMENTS NLP-01/02/03 marked Complete
   - Out of scope (deferred to backlog): WI-3 arithmetic consistency, WI-4 group-definition disambiguation, WI-5 context hygiene; additional insight rules; tool-output shaping; verbalize.yaml renderer
   ```
2. In the §Phase Progression table, change the Phase 9 row to `✓ Complete | Faithfulness ≥ 0.95 + raw_keys = 0 + UAT clean`.
3. Update the file's footer line `*Last updated: ...*` to today's date.

**Acceptance criteria:**
- `grep -n "Phase 9 — Natural Language Polish.*Complete" .planning/STATE.md` returns 1 match.
- `grep -n "raw_keys gate = 0" .planning/STATE.md` returns 1 match.
- The pending-phase marker `Phase 9 — Natural Language Polish ○ Pending` is GONE: `grep -c "Phase 9 — Natural Language Polish.*Pending" .planning/STATE.md` returns 0.

**Verification:**
```bash
grep -nE "Phase 9 — Natural Language Polish.*Complete|raw_keys gate = 0" .planning/STATE.md
test "$(grep -c 'Phase 9 — Natural Language Polish.*Pending' .planning/STATE.md)" = "0"
```

---

## Cross-task references

- **CONTEXT grounding:** every task's reasoning traces back to a D-XX in `09-CONTEXT.md`. T6 → D-01/D-03/D-04. T7 → D-05. T8 → D-06. T9 → D-07. T3+T4 → D-03. T10 → D-09. T13 → D-10. T1+T5+T14 → STATE.md continuity.
- **Discussion log:** `09-DISCUSSION-LOG.md` documents the alternatives ruled out (post-processor guardrail, tool-output shaping, `verbalize.yaml` renderer, runtime retry, second insight rule). If during execution a task seems to need one of those, stop and revisit the gray area instead of expanding scope.

## Rollback plan

If T10 fails the faithfulness or raw_keys gate after one revision iteration:

1. `git diff src/basic_stats/prompts/agent_system.yaml` — review the prompt diff.
2. If the prompt grew >50 lines, the LLM may be choking on length. Trim examples (keep one GOOD/BAD per category, drop the second).
3. If raw_keys gate fails on a specific question category, add a targeted GOOD/BAD pair for that category rather than tightening the global ban.
4. If both gates fail, revert the YAML to pre-T6 state and re-run T1 to confirm the baseline still reproduces — if it doesn't, the regression is in another file (check git log for accidental changes).
5. Do NOT lower `RAW_KEY_GATE` from 0 to "permit a few" — that defeats the phase.

## Out-of-scope reminders

- Do not add a runtime retry in `agent.py` (D-03).
- Do not add a second insight rule (D-08); add to backlog instead.
- Do not change tool return shapes (D-02); answer the same data, frame it differently.
- Do not touch WI-3..WI-5; if the UAT in T12 surfaces an arithmetic-consistency or group-definition bug, log it as a NEW finding and continue — Phase 9 ships when the explicit gates pass.
