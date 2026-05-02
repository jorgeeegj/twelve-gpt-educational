# Phase 13 — Scope Awareness

**Status:** Planned
**Dependencies:** Phase 12 (refusal hard-stop verified 2026-05-02)
**Requirements:** SCOPE-01, SCOPE-02, SCOPE-03

---

## Goal

Teach the agent to know the boundaries of its own dataset — which metrics exist, which entities are in scope, which season it covers — and to say so cleanly when a question falls outside those boundaries. Replace silent substitution and quiet hallucination with explicit, useful refusals that suggest the closest available alternative.

This phase resolves the three structural failure modes the system can produce today:
1. **Silent metric substitution** — user asks for `tackles_per_90`; the closest column is picked and reported as if it were the answer.
2. **Wrong entity coercion** — user asks about a non-PL player; fuzzy resolution returns a similarly-named PL player and the agent answers as if it were them.
3. **Multi-season hallucination** — user asks "compare to last season"; the agent improvises from training knowledge instead of refusing.

All three are downstream of one missing capability: **the agent does not classify a question's epistemic status before deciding to act**. Phase 13 adds that capability via prompt + a defensive guard in the tool layer.

---

## Non-Goals

- No new mother tools. The 4 existing tools stay.
- No `classify_intent` as a separate LLM call. In-prompt classification is sufficient and ~95% as effective at zero extra cost.
- No xGA derivation, no `match_date` typing, no memory compaction. Scope expansion is explicitly out — see TEAM.md "What It Cannot Do".
- No new discovery-loop machinery. The existing `synthetic_runner.py` is enough to verify this phase.

---

## Sub-Phases

### 13.1 — Closed Contract on Metrics (SCOPE-01)

**What:** Make the AVAILABLE STATS list in `agent_system.yaml` an exhaustive, closed contract. When a user asks for a metric outside that list, the agent refuses with the closest available alternative — never silently substitutes.

**Changes:**
- `src/basic_stats/prompts/agent_system.yaml` — add a `METRIC AVAILABILITY` block immediately after the AVAILABLE STATS section (after line 57, before `{league_context}`):
  ```
  METRIC AVAILABILITY
  The AVAILABLE STATS list above is exhaustive for this dataset. If the user asks
  for a metric not on the list (e.g. tackles, distance covered, xGA, expected
  assists, possession %), do NOT call a tool. Answer in one sentence:
  "I don't have [metric] in this dataset. The closest I can offer is
  [nearest available stat from the list], if useful."
  Do not silently substitute. Do not invent a column name.
  ```
- `src/basic_stats/agent_tools.py` — when a tool call requests a stat that fails `column_exists()`, return `{"error": "metric_not_available", "requested": "<stat>", "scope": "<scope>"}` instead of running a fallback. (~10 lines, defensive backstop only — the prompt rule should catch most cases first.)

**Verification (SCOPE-01 exit gate):**
- 4 manual questions return refusal-with-alternative (not zero, not fabricated, not silent substitute):
  - "How many tackles per 90 has Saliba made?"
  - "What's Liverpool's xGA this season?"
  - "How many kilometers has Salah run this season?"
  - "How many expected assists does Bruno Fernandes have?"

**Files touched:** `agent_system.yaml`, `agent_tools.py`

---

### 13.2 — Pre-Tool Intent Classification (SCOPE-02)

**What:** Before calling any tool, the agent classifies the question into exactly one of four buckets. The classification line is internal (stripped from the user-facing answer) and serves as both a routing decision and a debugging trace.

**Changes:**
- `src/basic_stats/prompts/agent_system.yaml` — add a `BEFORE CALLING A TOOL` block between the `{league_context}` section and `HOW TO USE TOOLS`:
  ```
  BEFORE CALLING A TOOL — classify the question in one sentence into exactly one of:
    - in_scope_lookup       — answerable from AVAILABLE STATS, entities exist in dataset
    - out_of_scope_future   — predicts future / next match / next season / "will"
    - out_of_scope_data     — metric not in AVAILABLE STATS, season ≠ 2024-25,
                              or entity not in this Premier League dataset
    - ambiguous             — referent unclear, name ambiguous, metric ambiguous

  Then act:
    - in_scope_lookup     → call the tool
    - out_of_scope_future → refuse in one sentence (existing OUT OF SCOPE rule)
    - out_of_scope_data   → state what's not available, offer closest alternative
    - ambiguous           → ask one clarifying question

  Write the classification on its own line prefixed `INTENT:`. Do NOT include
  the INTENT line in the final user-facing answer.
  ```
- `src/basic_stats/agent.py` — strip any leading `INTENT:` line from the assistant's final answer before returning to the caller. ~5 lines, regex on the final string.

**Verification (SCOPE-02 exit gate):**
- 61-question prepared benchmark: ≥59/61 faithfulness preserved.
- 21-question random benchmark: ≥19/21 preserved.
- Manual smoke: 5 in-scope questions never show `INTENT:` in the user-visible answer.

**Files touched:** `agent_system.yaml`, `agent.py`

---

### 13.3 — Scope Awareness Question Set (SCOPE-03)

**What:** Author a 12-question set covering the 3 gap categories not currently tested anywhere in the eval suite. Run it, manually inspect, fix any prompt edge cases that surface.

**Categories (4 questions each):**
- **Metric not in schema:** tackles, xGA, distance covered, expected assists
- **Entity not in dataset:** Lamine Yamal goals, Real Madrid stats, La Liga top scorer, Mbappé PL goals
- **Multi-season / out-of-window:** "compare to 2023-24", "what about last season", "matchweek 40 results", "next season top scorer"

**Changes:**
- `evals/scope_awareness_questions.json` — 12 entries, each with `id`, `question`, `expected_behavior ∈ {refuse_with_alternative, refuse_explicit, clarify}`.
- Run via `synthetic_runner.py --workers 1`.
- For any failure surfaced, edit `agent_system.yaml` only. Re-run after each edit. Stop when 12/12 pass.

**Verification (SCOPE-03 exit gate):**
- 12/12 produce one of: refusal-with-alternative, refusal-explicit, or clarifying question.
- Zero fabricated numbers, zero silent substitutions, zero non-PL entities answered as PL entities.
- 61 + 21 benchmarks remain at ≥59/61 and ≥19/21 after any prompt edits.

**Files touched:** `evals/scope_awareness_questions.json` (new), possibly `agent_system.yaml` (rule tuning).

---

## Phase Exit Gate

All three sub-phase exit gates pass:
- 4/4 metric-not-available questions (13.1)
- ≥59/61 prepared + ≥19/21 random + INTENT line never visible to user (13.2)
- 12/12 scope-awareness questions pass + benchmarks preserved (13.3)

`src/basic_stats/` diff:
- `agent_system.yaml` — additions only (METRIC AVAILABILITY, BEFORE CALLING A TOOL); no rule deletions
- `agent_tools.py` — ~10 lines (defensive metric_not_available error)
- `agent.py` — ~5 lines (INTENT line strip)

---

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| INTENT line leaks into user answer | Regex strip in `agent.py` is the backstop; manual smoke check on 5 questions before declaring 13.2 done |
| Pre-tool classification block breaks prompt-cache prefix and increases latency | Place the new block after the dynamic `{team_names}`/`{positions}`/`{league_context}` template fills — keeps the cache-relevant prefix stable |
| New refusal rules over-trigger and regress in-scope benchmarks | Run full 61 + 21 after every prompt edit; revert any edit that loses >1 question |
| Tool-layer `metric_not_available` error confuses the LLM and creates a livelock | Existing livelock detection (Phase 12, `agent.py`) already catches repeated calls with identical args; this surfaces as a clean error to the user |

---

## Estimated Effort

~3.5 hours across 3 commits. One session, sequential sub-phases.

---

## Out of Scope (deferred)

- xGA team view in `duckdb_manager.py`
- `match_date` typing for weekday filters
- Memory compaction / summarization
- `classify_intent` as a separate tool
- 40-question adversarial sweep across 6 categories
- Discovery-loop pruning / archival

These may become Phase 14+ if and only if eval evidence after Phase 13 demands them.
