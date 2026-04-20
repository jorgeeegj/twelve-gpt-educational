# Phase 7 — Conversation Memory

**Status:** Not started (Phase 6 complete)
**Requirements:** MEM-01 (reframed), MEM-02, MEM-03

---

## Goal

Verify that multi-turn follow-up conversations work correctly with the existing Responses API
infrastructure, fix any gaps in the system prompt, and ship a multi-turn test suite.

The `previous_response_id` mechanism is already wired (Phase 5). MEM-01 as originally written
(client-side ConversationState tracking) is obsolete — the real work is confirming the LLM
resolves implicit references correctly across turns.

---

## What's already built

- `src/basic_stats/agent.py` — `BasicStatsAgent` uses `previous_response_id` for stateful
  multi-turn. `reset()` clears `_last_response_id`.
- `pages/basic_stats.py` — agent cached with `@st.cache_resource`; `reset()` on Clear chat.
- `src/basic_stats/prompts/agent_system.yaml` — has a `FOLLOW-UP QUESTIONS` section telling
  the LLM to resolve implicit references from conversation history.
- 91 unit tests passing; 3 pre-existing failures in `tests/test_duckdb_vss_stubs.py`
  (tests assert `NotImplementedError` on methods that are now fully implemented).

---

## Steps

### Step 1 — Fix pre-existing test failures

**File:** `tests/test_duckdb_vss_stubs.py`

The three tests that assert `pytest.raises(NotImplementedError)` for `store_entity_embeddings`
and `fuzzy_resolve_entity` are stale — both methods are now real implementations (Phase 6).
Update them to assert correct behavior:

- `test_store_entity_embeddings_raises_not_implemented` → verify the method is callable without
  raising (smoke test: call with a valid `DuckDBManager` instance and assert no exception is
  raised, OR check the embeddings table exists post-call if practical — use whichever is
  faster and doesn't require a full rebuild)
- `test_fuzzy_resolve_entity_raises_not_implemented` → assert `fuzzy_resolve_entity("Salah",
  "player")` returns a non-empty string (or specifically `"M. Salah"` if the embeddings table
  is present)
- `test_fuzzy_resolve_entity_raises_not_implemented_for_team` → assert
  `fuzzy_resolve_entity("Man City", "team")` returns a non-empty string

**Important:** These 3 tests live alongside 2 others that already pass
(`test_existing_query_dicts_still_works`, `test_existing_table_counts_still_works`) — don't
touch those.

**Gate:** `python -m pytest tests/ -x` — all tests pass (was 91 pass / 3 fail; should be
94 pass / 0 fail after this step).

---

### Step 2 — Run Agust's 4-turn chain manually

Verify the chain works end-to-end by calling `agent.ask()` directly (no Streamlit needed).

Create a **throwaway script** `scripts/verify_multiturn.py` that runs the 4 turns in sequence
and prints each answer:

```
Turn 1: "How many goals has Haaland scored this season?"
Turn 2: "But against top 6 teams?"
Turn 3: "Is that more than the rest of his goals?"
Turn 4: "What about per 90?"
```

The script should:
1. Instantiate `BasicStatsAgent()`.
2. Call `agent.ask(turn)` for each turn in sequence (using the shared agent instance so
   `previous_response_id` chains correctly).
3. Print `Turn N: <question>\n→ <answer>\n`.
4. Exit with code 0 if all 4 turns returned a non-empty, non-fallback answer; exit 1 otherwise.

Run the script. Document in a code comment what each turn returned. If any turn fails
(returns the fallback message or an empty string), move to Step 3.

**Gate:** Script exits 0 and all 4 answers are plausible football stats sentences (no
"I wasn't able to answer" responses).

---

### Step 3 — Fix system prompt if needed

**Only execute this step if Step 2 reveals failures.**

Inspect which turns failed and why. The likely culprits in `agent_system.yaml`:

- The `FOLLOW-UP QUESTIONS` section is minimal (3 lines). It may need explicit examples
  for implicit comparisons like "is that more than the rest?" and relative-stat follow-ups
  like "what about per 90?".
- If Turn 3 fails ("Is that more than the rest?"), add an example:
  `"Is that more than the rest?" → resolve entity from prior turn (Haaland), split goals
  into against-top6 vs all-others, compare the two values.`
- If Turn 4 fails ("What about per 90?"), add an example:
  `"What about per 90?" → repeat prior query but use the corresponding _p90 stat column.`

Keep edits surgical — add only the examples that address observed failures. Do not rewrite
the section.

**File:** `src/basic_stats/prompts/agent_system.yaml`

**Gate:** Re-run `scripts/verify_multiturn.py` — exits 0.

---

### Step 4 — Write multi-turn test suite

**File:** `tests/test_multi_turn.py`

This test file requires real LLM + DuckDB calls. Mirror the header convention from
`tests/test_fuzzy_resolve.py`:

```python
# NOTE: Requires Azure credentials in .streamlit/secrets.toml.
# Run manually: python -m pytest tests/test_multi_turn.py -v
```

**Fixture:** One `BasicStatsAgent` instance per test function (use `@pytest.fixture` with
`scope="function"` and `autouse=False`). Each test calls `agent.reset()` at the start to
ensure a clean slate.

**10+ conversation flows to cover:**

| # | Flow | Turns | What it validates |
|---|------|-------|-------------------|
| 1 | Haaland goals → against top 6 → per 90 | 3 | entity + filter + stat carry-forward |
| 2 | Salah assists → at home → last 10 GWs | 3 | entity + location + window carry-forward |
| 3 | Man City goals → away goals | 2 | team entity carry-forward |
| 4 | Top 5 scorers → who is the most efficient? | 2 | ranking follow-up |
| 5 | Arsenal stats → how many points? | 2 | team + stat switch |
| 6 | Haaland xG → how does that compare to Salah? | 2 | entity pivot in follow-up |
| 7 | Which team scored most at home? → and away? | 2 | filter flip |
| 8 | Clear/reset: ask Q1, reset, ask Q2 | 2 | `reset()` clears state |
| 9 | Position-filtered ranking → who is the runner-up? | 2 | position + rank follow-up |
| 10 | Gameweek window → and in the other half? | 2 | temporal carry-forward |

**Assertion strategy for each turn:**
- `assert answer` — not empty
- `assert answer != agent._FALLBACK_MESSAGE` (expose `_FALLBACK_MESSAGE` or check for
  "wasn't able to answer")
- For flows where the answer is deterministic, assert the expected name or number is
  present in `answer.lower()` (e.g. `"haaland" in answer.lower()`)

**Gate:** `python -m pytest tests/test_multi_turn.py -v` — all 10+ tests pass.

---

## Exit gate (from ROADMAP.md)

1. Agust's 4-turn chain works end-to-end (verified in Step 2 / fixed in Step 3).
2. Entity + filter context carries across turns without the user repeating themselves
   (validated by the 10+ flows in Step 4).
3. Multi-turn test suite passes.
4. Clear chat resets conversation state correctly (covered by Flow 8 in Step 4).
5. All unit tests pass: `python -m pytest tests/ -x` (Step 1 fix).

---

## Files touched

| File | Change |
|------|--------|
| `tests/test_duckdb_vss_stubs.py` | Flip 3 assertions from NotImplementedError to correct behavior |
| `scripts/verify_multiturn.py` | New throwaway script (kept for manual re-runs) |
| `src/basic_stats/prompts/agent_system.yaml` | Conditional: add follow-up examples only if Step 2 fails |
| `tests/test_multi_turn.py` | New: 10+ multi-turn conversation flows |

---

## Key constraints

- Multi-turn tests require Azure credentials — they are **not** CI tests. Mark clearly.
- Do not add client-side conversation history. The `previous_response_id` mechanism is the
  memory layer — do not build a parallel system.
- System prompt edits must be minimal. If the 4-turn chain already works, skip Step 3
  entirely.
- The `_FALLBACK_MESSAGE` constant in `agent.py` is the sentinel for a failed answer —
  use it in test assertions rather than hard-coding the string.
