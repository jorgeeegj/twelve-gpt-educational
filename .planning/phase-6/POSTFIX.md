# Phase 6 — Post-Fix (2026-04-20)

**Context:** Phase 6 originally reported 21/21 faithfulness on `random_questions.json`,
but that gate was hollow — the file had no `expected` values, so the faithfulness
judge skipped every question. Manual review of `evals/runs/2026-04-19_21-37-16__agent/results.json`
surfaced 2 clear failures and 4 suspicious p90 answers. This doc records the 6 fixes
applied on 2026-04-20 to close those gaps before re-running the benchmark.

---

## Summary of fixes

| # | Fix | File(s) |
|---|-----|---------|
| 1 | Real `expected` values on all 21 questions | `evals/random_questions.json` |
| 2 | `min_minutes=600` default for p90 rankings | `src/basic_stats/agent_tools.py` |
| 3 | Fuzzy resolve applied symmetrically to team filters | `src/basic_stats/agent_tools.py`, `duckdb_manager.py` |
| 4 | `resolved_entities` attached to every tool response | `src/basic_stats/agent_tools.py` |
| 5 | Per-turn telemetry (iterations, tool calls) | `src/basic_stats/agent.py`, `evals/agent_benchmark.py` |
| 6 | System prompt trimmed (442-player list removed) | `src/basic_stats/prompts/agent_system.yaml`, `agent_prompt.py` |

---

## 1. Expected values on `random_questions.json`

**Problem:** faithfulness judge extracts numeric expectations from `entry["answer"]`.
With no `answer` dict, every question returned `no_numeric_expectation` and the
21/21 pass rate was vacuous.

**Fix:** populated all 21 questions with ground-truth values queried directly
against DuckDB. Added structured categories:

- `factual_answerable` — direct lookup
- `factual_p90_needs_min_minutes` — must apply min_minutes to avoid small-sample
- `factual_team_filter` — regression sentinel for RQ_09
- `factual_comparison` — two entities
- `factual_ambiguous_name` — fuzzy resolve must pick + ideally flag ambiguity
- `factual_needs_domain_knowledge` — LLM must know London clubs, etc.

Where a small-sample alternative is acceptable (RQ_06, RQ_13), `acceptable_alternative`
is filled with a note clarifying when that answer is valid.

---

## 2. `min_minutes=600` default for p90 rankings

**Problem (Tipo 3):** `query_ranking` over a `_p90` stat returned whoever had
the highest rate regardless of minutes played. Examples:

- "winger with most key_passes_p90" → R. Nelson (531 min, 1.53) instead of Salah (1.23)
- "CB with most clearances_p90" → J. Cuenca (377 min, 3.10) instead of Huijsen (1.83)

**Fix:** in `rank_players`, when `stat.endswith("_p90")` and the LLM didn't pass
`min_minutes`, apply `_P90_MIN_MINUTES_DEFAULT = 600` and attach an explanatory `note`
to the tool response. The LLM can override with `min_minutes=0` if the user explicitly
wants no cutoff. 600 minutes ≈ 6–7 full matches — enough signal, removes noise.

---

## 3. Fuzzy resolve symmetric for team filters

**Problem (Tipo 2):** RQ_09 ("Which Nottingham Forest player has the most assists?")
returned Salah (Liverpool). Two bugs compounded:

1. `rank_players` resolved the primary player name via fuzzy, but did **not**
   resolve `filters.player_team` — "Nottingham Forest" was passed through as-is.
2. More seriously, the summary-path branch of `rank_players` called
   `query_summary_context()` **without** passing `team_name`, so the filter was
   silently dropped entirely.

**Fix:**

- New `_resolve_team_filters(duck, filters)` helper: returns a new filters dict
  with `player_team` and `opponent_team` resolved via fuzzy, plus a resolution log.
- New `_fuzzy_primary(duck, name, entity_type, field)` helper for primary entity names.
- `rank_players` now passes `team_name=_f(filters, "player_team")` to
  `query_summary_context` — the actual RQ_09 root cause.
- `DuckDBManager.fuzzy_resolve_entity_verbose()` added (returns input, canonical,
  similarity, resolved); `fuzzy_resolve_entity` is now a thin wrapper.

**Verified:** `filters={"player_team": "Nottm Forest"}` → A. Elanga (NF, 10 assists),
with fuzzy sim 0.92 for "Nottm Forest" → "Nottingham Forest".

---

## 4. `resolved_entities` in tool response

Every mother tool (`query_player_stats`, `query_team_stats`, `query_ranking`) now
attaches a `resolved_entities` list to its response:

```json
{
  "rows": [...],
  "resolved_entities": [
    {"field": "player_team", "input": "Nottm Forest",
     "canonical": "Nottingham Forest", "similarity": 0.92, "resolved": true}
  ]
}
```

**Why:** the LLM can reference it in answers (e.g. surface ambiguity for "Bruno"),
and the benchmark can audit what was matched. Closes the black-box problem from
the OPUS briefing.

---

## 5. Per-turn telemetry

`BasicStatsAgent.last_telemetry` now holds, after every `ask()`:

```python
{
  "iterations_used": int,        # 1..6
  "tool_calls": [                # each entry: name, arguments,
     {"name": ..., "arguments": ...,   resolved_entities, note, error
      "resolved_entities": ..., "note": ..., "error": ...}
  ],
  "hit_max_iterations": bool,
}
```

`evals/agent_benchmark.py` captures this per question and writes it into
`results.json` (`iterations_used`, `tool_calls_count`, `tool_calls`,
`hit_max_iterations`). Lets us see *which* tool got called with *which* args
on each question — essential for diagnosing misroutes without re-running.

---

## 6. System prompt trim

**Before:** prompt inlined all 442 player short names (a comma-separated block).
Token cost per turn + dilutes instruction signal.

**After:** the PLAYERS section is replaced with a short directive — "there are 442
players, don't try to list them, pass the user's raw name and let fuzzy resolve
map it". Team list kept (only 20 teams, cheap + useful for team-name disambiguation).

Token savings per system prompt: ~5k chars → ~500 chars on that block alone.
Fuzzy resolve already guarantees the canonical name, so the list served no purpose.

---

## Files touched (net)

```
evals/random_questions.json                         — expected values added
src/basic_stats/agent_tools.py                      — helpers + p90 default + filter fix + resolved_entities
src/basic_stats/duckdb_manager.py                   — fuzzy_resolve_entity_verbose
src/basic_stats/agent.py                            — telemetry
src/basic_stats/agent_prompt.py                     — no longer interpolates player_names
src/basic_stats/prompts/agent_system.yaml           — PLAYERS block trimmed
evals/agent_benchmark.py                            — telemetry threaded through
.planning/phase-6/POSTFIX.md                        — this doc
```

---

## Verification

End-to-end smoke test on the RQ_09 regression sentinel:

```
Q: "Which Nottingham Forest player has the most assists?"
A: "Anthony Elanga (A. Elanga) — 10 assists for Nottingham Forest in the
    2024-25 Premier League season."
iterations_used: 2, tool_calls: 1 (query_ranking)
resolved_entities: [{field: player_team, input: Nottingham Forest,
                     canonical: Nottingham Forest, similarity: 1.0}]
```

Full benchmark re-run pending — label `phase6_postfix`.

---

## Known gaps (not fixed in this pass)

- **RQ_12 (Wolves yellow cards):** `teams_summary.total_yellow_cards` exists in
  the DB (value 75) — the agent previously returned `fouls_committed` instead.
  No code fix applied; this is an agent-initiative / prompt issue. Will be
  revisited if the re-run still fails on RQ_12.
- **Prompt few-shot examples:** considered but deferred. Worth adding 3–5
  worked examples for p90, team filter, and ambiguous name cases if the re-run
  still leaks.
- **Benchmark LLM judges:** not run in the post-fix re-run (skip-judges for
  speed). Naturalness and completeness still need a judged run before Phase 6
  can be formally re-closed.
