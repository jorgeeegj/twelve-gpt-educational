# Session Log — 2026-05-02

## What We Did

### Phase 12: Refusal Hard-Stop

**Problem:** `BACKLOG_001` — `unsupported_future__refuse_expected_but_answered`. The agent refused future-prediction questions but then appended historical stats ("What I can tell you is that historically this season Haaland scored X goals..."). The root cause was in `agent_system.yaml` lines 159–170: the CORRECT example explicitly demonstrated the half-refusal pattern the model was copying.

**Fix:** Two-pass edit to `src/basic_stats/prompts/agent_system.yaml`:
- First pass: removed "You may then offer historical H2H data clearly labelled as non-predictive context." Changed CORRECT example to a 1-sentence refusal.
- Result: agent still offered to answer a follow-up ("Which opponent is Salah's next match against?") — a one-step-removed workaround.
- Second pass: added explicit WRONG case — "Refusing then offering to show historical stats or asking a follow-up about the opponent — stop completely after the refusal."
- Final verification: all 8 BACKLOG_001 questions now get clean 1–2 sentence refusals. No trailing stats.

### DuckDB Concurrency Fix

**Problem:** Benchmark `--workers 3` caused `TransactionException: Catalog write-write conflict on alter with players_summary`. Root cause: `_register_base_views()` runs `CREATE OR REPLACE VIEW` on every `BasicStatsAgent` init — a DDL write operation. Multiple workers share the same `.duckdb` file and conflict.

**Fix:**
- Added `in_memory: bool = False` param to `BasicStatsAgent.__init__` and `DuckDBManager.__init__`
- Added `DuckDBManager._copy_embeddings_from_file()`: ATTACHes the file DB read-only, copies `entity_embeddings` table to memory, recreates HNSW index, DETACHes
- Benchmark workers now use `BasicStatsAgent(in_memory=True)` — each gets a private in-memory DuckDB with no lock conflicts
- Result: `--workers 5` runs cleanly. Benchmark went from serial-only (~68 min) to ~20 min

### Benchmark Result (2026-05-02, before livelock fix)

```
56/61 faithfulness — gate FAIL (requires >=58/61)
```

**Failure breakdown:**
- QV4_38, QV5_49 — pre-existing, present before Phase 12 changes
- QV5_47, QV6_53, QV6_57 — appeared in this run; LLM variance, not caused by prompt edit

**Diagnosis of 3 "new" failures:**
- All 3 involve multi-hop questions where the model calls a tool, gets results, then calls the same tool with identical arguments again (tool-call livelock), exhausts `_MAX_ITERATIONS=6`, and returns the generic fallback
- This is pre-existing fragility exposed by LLM non-determinism — these questions were borderline before, and this run happened to land on the failing side
- Root cause: no livelock detection in `agent.py`; model silently hits max iterations with no signal

### Fix 2: Livelock Detection

**What it does:** In `agent.py`'s iteration loop, after collecting `fc_items`, compare `frozenset((name, args))` tuples against the prior iteration. If any overlap is found (same tool + same args), inject an error output for every `call_id` in the repeated set:
```
{"error": "Repeated call with identical arguments. Try different parameters or state that you cannot answer this question."}
```
Then `continue` to the next iteration. The model sees this as a tool result, reasons about it, and either tries different args or verbalizes that it cannot answer.

**Why this is architectural, not a patch:**
- Addresses a structural silent failure: `_MAX_ITERATIONS` exhaustion presents identically to "no data" from the user's perspective
- Works for any future tool/question combination that hits the same trap — not tied to specific questions
- Saves API tokens on every livelock (stops after first repeated call instead of consuming all remaining iterations)
- Zero behavior change on the happy path
- ~25 lines in `agent.py`, no new dependencies

---

## Two Patterns That Define This Project

### 1. The Prompt Is the Configuration Surface

Every agent behavior — what it answers, how it refuses, how it labels tiers, how it writes follow-ups — is controlled by `src/basic_stats/prompts/agent_system.yaml`. No if/else heuristics in Python.

The rule: if the LLM can handle it with the right instruction or tool description, don't put it in code. Only heuristics when strictly necessary.

This is why all three core priorities (robustness, follow-up memory, league context) were solved with prompt edits and tool schema descriptions — not new Python logic. And why BACKLOG_001 was fixed in ~15 lines of YAML.

### 2. The Self-Improving Eval Loop

The project has a built-in feedback cycle:

```
Run questions → Cluster failures → Identify root cause → Fix prompt → Re-run → Verify cluster closed
```

Implemented in `evals/`:
- `agent_benchmark.py` — 61 prepared + 21 random questions, faithfulness judge
- `synthetic_runner.py` — runs any question batch through the agent
- `discovery/failure_backlog.json` — known failure clusters with history
- `discovery/campaigns/` — targeted question sets for specific failure types

**How it closed BACKLOG_001:**
1. Phase 10 synthetic run surfaced 2 failures → clustered as `unsupported_future__refuse_expected_but_answered`
2. Phase 11 targeted campaign (6 questions) confirmed the cluster: 6/6 failures
3. Phase 12 identified root cause: a single prompt rule licensed the bad behavior
4. Prompt fix shipped → manual verification: all 8 questions now refuse cleanly

---

## State After This Session

| What | Status |
|------|--------|
| BACKLOG_001 (refusal bug) | Fixed — verified manually on all 8 questions |
| DuckDB concurrency | Fixed — in-memory agents, `--workers 5` clean |
| Livelock detection | Implemented in `agent.py` |
| Benchmark | 56/61 pre-fix; re-run pending with livelock fix |
| Tests | 229/229 passing |

## Commits Pending

1. `fix(prompt): hard-stop after refusal on future-prediction questions` — `agent_system.yaml`
2. `fix(agent): in-memory DuckDB for benchmark workers` — `agent.py`, `duckdb_manager.py`, `agent_benchmark.py`
3. `fix(agent): livelock detection in tool-call loop` — `agent.py`
4. `chore(state): align STATE.md frontmatter — 11 phases complete`
5. `docs(team): update TEAM.md with Phase 12 progress and two core patterns`

## What's Next

1. Re-run regression benchmark with livelock fix to verify 56 → >=59
2. If benchmark passes → commit all changes and the project is done
3. If new failure class appears → scope the intent-classifier tool against those specific failures; do not build it speculatively
