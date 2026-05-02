# Session Log — 2026-05-01

**Participants:** Ricardo + Claude (Sonnet 4.6 / Opus 4.7)
**Branch:** `feature/refactor-v2`
**Context:** First session after merging Jorge's Phase 10/11 changes

---

## 1. Checking Jorge's Remote Branch

Ricardo asked to see the latest changes on `https://github.com/jorgeeegj/twelve-gpt-educational/tree/feature/refactor-v2`.

After fetching from the `jorge` remote, **14 new commits** were found (April 29–30), ahead of the local branch. Jorge had been active that day closing Phase 11.

**Key changes discovered:**
- Phase 9 — Natural Language Polish (planning docs)
- Phase 10 — Self-Generated Robustness / Synthetic UAT infrastructure
- Phase 11 — Iterative Synthetic Discovery Loop v1

**Files changed:** 80 files, ~13,600 lines added — mostly new eval infrastructure and planning docs, zero changes to `src/basic_stats/` production code.

---

## 2. Merging Jorge's Changes

Ricardo confirmed merging. The merge was a clean fast-forward (no conflicts) from commit `5f1c5858` to `c5d99de0`.

---

## 3. Understanding What Jorge Built

Ricardo asked for a plain-language explanation of Jorge's work.

**Summary provided:**

- **Phase 9** — Fixed the agent outputting raw metric keys (`xg_total`, `goals_p90`) in responses. Agent now writes natural language.

- **Phase 10 — Synthetic UAT:** Built a pipeline that generates test questions automatically, runs them through the agent, and evaluates answers. Key files: `evals/synthetic_runner.py`, `evals/synthetic/seed_questions.json`, `evals/synthetic_clusterer.py`.

- **Phase 11 — Iterative Discovery Loop:** An automated loop that tracks failures (`failure_backlog.py`), clusters them by type (`triage_rubric.py`), generates targeted question batches (`campaign_generator.py`), runs comparisons (`iteration_runner.py`), and promotes fixes (`promote.py`).

  First real run (`unsupported_future_v1`) found a cluster: agent refuses future-prediction questions but then adds historical stats anyway. This became `BACKLOG_001` — promoted to `docs/review/context_gap_unsupported_future__refuse_expected_but_answered.md` (with empty TODOs).

**Honest assessment:** Jorge built the eval machine, not fixes. The loop diagnoses problems but stops before prescribing solutions. The `context_gap` doc it produced has blank stubs.

---

## 4. What Is Actually Broken Right Now

**One confirmed bug:** When users ask prediction/future questions ("Will Salah score next week?", "Who will win the title?"), the agent refuses correctly — then keeps talking and dumps historical stats anyway. It's a half-refusal.

Root cause: `agent_system.yaml` line ~162 explicitly says "Refuse the prediction first. You may then offer historical H2H data clearly labelled as non-predictive context." The model is following the prompt correctly — the prompt is wrong.

---

## 5. Evaluating Advice from a Prior Claude Session

Ricardo had asked Claude in a separate session how to apply Anthropic's prompt structure to fix the issue. That session proposed multiple prompt layers (task context rewrite, tone, SCOPE LIMITS block, few-shot examples, think step-by-step, output formatting).

**Evaluation:**
- **Core diagnosis correct:** The `OUT OF SCOPE` rule at line 162 permits historical context after a refusal. That's the bug.
- **Most of the other proposals were unnecessary:** The prompt already has tone, output formatting, and reasoning structure. Adding them again creates redundancy, not clarity.
- **The actual fix:** 3 lines in `agent_system.yaml` — remove "you may then offer historical context," add a hard stop + one few-shot example showing the correct refuse-and-stop behavior.

---

## 6. Full Engineering Assessment (Opus session)

Ricardo asked for a senior football AI engineer assessment of all phases, David's feedback, Agust's feedback, and whether a reasoning step should be introduced.

### Where the project stands

The architecture is sound: principled function-calling agent, self-improving evals, 231 tests, 59/61 benchmark, multi-turn memory, league context, discovery loop. No longer a prototype.

### The two stakeholder perspectives

- **Agust:** reduce complexity, answer fewer things reliably
- **David (latest presentation feedback):** your domain is unusually suited to self-improving evals — lean into that direction

Both are right about different layers:
- `src/basic_stats/` → Agust's domain. Keep it small and surgical.
- `evals/` → David's domain. This is where exploration lives.

The Phase 11 zero-diff guarantee on `src/basic_stats/` is exactly that discipline working.

### What's actually missing

1. **The discovery loop diagnoses but doesn't prescribe** — finds bugs, stops before proposing the fix
2. **No intent classification before acting** — model decides scope and tool selection in one pass
3. **No self-verification gate** — model generates the answer in one shot

### On introducing a reasoning step

**Three options, in order of preference:**

1. **Prompt-level (cheapest):** Fix the existing `OUT OF SCOPE` rule — change "you may then offer historical context" to "stop." Add one few-shot example. Ships today, no architectural change.

2. **Tool-level (next):** Add a `classify_intent` tool the agent must call first. Returns `{intent, reasoning, should_proceed}`. If `out_of_scope`, agent exits without calling any data tool.

3. **Structured output gate (later):** Use OpenAI structured outputs to force `{intent, answer}` together, validated server-side.

**Recommendation:** Do option 1 now, evaluate via the discovery loop, only build option 2 if the eval run shows the prompt fix isn't enough.

### Proposed path forward

1. **Fix the refusal prompt** (today, 30 min) — edit `agent_system.yaml`, rerun the `unsupported_future_v1` campaign
2. **Close the discovery loop** — add a `propose_fix` step in `promote.py` that drafts the prompt patch, not just emits a blank doc
3. **Run a broader synthetic sweep** — generate ~50 questions across all 12 categories, find what other failure types exist
4. **Only then decide** on the `classify_intent` tool — based on evidence, not intuition

---

## 7. TEAM.md Rewrite

Ricardo flagged that Jorge's TEAM.md update was too long, mixed Spanish/English, and full of Phase 10/11 internal jargon. The "where we are / what's next" clarity he'd maintained before was lost.

**Rewrite goals:**
- Keep the v1→v2 narrative (useful for presentations)
- Keep the git setup section (non-technical team members need it)
- Clean up current-state sections to be plain and actionable
- Single "Immediate Next Step" with an exit gate

**Result:** TEAM.md rewritten. Key additions:
- "What the Agent Can Do / Cannot Do Yet" table — clearest current-state summary
- Phases table — one row per phase, one sentence each
- "Immediate Next Step" — single concrete action with exit gate
- "After That — Option 2 (only if needed)" — gated on eval evidence

---

## 8. What Is a "Campaign"?

Ricardo asked what the campaign thing in TEAM.md meant.

**Plain answer:** It's Jorge's name for a batch of test questions targeting a specific failure type. `unsupported_future_v1.json` is just a JSON file with 6 questions like "Will Salah score next week?" — all future-prediction questions the agent should refuse. It's a mini benchmark focused on one bug category. Nothing more.

---

## 9. Does Fixing the Refusal Bug Satisfy David and Agust?

Ricardo asked for an honest verdict on whether the planned fixes would wrap up the agent project per STAKEHOLDER.md.

**Honest answer: the agent already satisfies Agust's feedback. The prompt fix is cleanup, not a requirement.**

Agust's three priorities from STAKEHOLDER.md (written April 16):
1. Random question robustness → **Done.** 19/21 Phase 6 + Phase 9.
2. Follow-up / conversation memory → **Done.** Agust's exact 4-turn chain passes.
3. League context injection → **Done.** Dynamic league paragraph, no hardcoded labels.

David's feedback was about the self-improving eval pattern — Jorge built it in Phases 10/11. The prompt fix closes the first discovery loop cycle, which is a complete demonstration of the pattern.

**Verdict:** The agent is done for the course. The refusal fix is polish. The real remaining action before any presentation: fix the refusal prompt (10 min) + run the benchmark once to confirm no regressions.

---

---

## Follow-Up Diagnosis — Engineering Assessment & Path Forward

> This section was added in a follow-up exchange the same session after the initial summary was written. It supersedes any "next steps" from sections 1–9 above and represents the current definitive picture of where the project stands and what we're doing next.

### Diagnosis

**Summary**

The agent and the data layer are in better shape than the conversation history suggests. The architecture is sound (4 mother tools over Responses API, fuzzy resolution, league context injection), and 59/61 + 19/21 benchmarks are real. There is no rewrite-shaped problem.

The single user-visible defect is a self-inflicted prompt rule: `agent_system.yaml:159-169` explicitly licenses the "refuse + then dump historical context" behavior the eval flagged. The model is compliant; the spec is wrong.

The data layer has more than the prompt admits — `xg_total`, `xg_total_p90`, and `xg_total` per match exist on teams. The system prompt's AVAILABLE STATS list under-advertises these (`teams_summary` block at `agent_system.yaml:45-51` lists `xg_total` for teams but never `xg_against`/xGA, despite `total_goals_against` being documented), so the LLM does not reach for xG in adversarial questions even when it could degrade gracefully.

The discovery loop (`evals/discovery/`) is over-engineered for one team of three. The 7-action triage rubric, promotion artefacts, and "campaign" abstraction added 13.6k LOC and produced one actionable insight that was already known. Keeping the runner + clusterer is correct; the rest is debt.

Memory is implemented client-side as a flat list of all turn outputs (`agent.py:120`) — this works for Agust's 4-turn chain, but has no compaction, no token-budget guard, no separation of "what the user asked" from "what tools returned." On long sessions this will degrade.

---

**Findings**

**Agent reasoning & prompt design**

- **[Observed — Prompt]** `agent_system.yaml:159-169` OUT OF SCOPE block ends with: *"You may then offer historical H2H data clearly labelled as non-predictive context."* Followed by a CORRECT pattern example that demonstrates the half-refusal. Symptom: failure cluster `unsupported_future__refuse_expected_but_answered`. Root cause: the prompt commands the behavior. Why it matters: this is the only confirmed user-facing defect; everything else in this file is downstream of fixing it.

- **[Observed — Prompt]** `agent_system.yaml` is 284 lines of prose-heavy rules with overlapping concerns: tool routing, label policy, language policy, refusal policy, insight policy, numeric grounding, follow-up policy, comparison Yes/No self-check. Multiple sections re-state Big Six labelling rules (L62-L71 and again at L193-L200). Symptom: hard to audit, easy to introduce contradictions. Root cause: prompt grew accretively. Why it matters: the next edit (refusal fix) risks colliding with another rule; consolidation pays off if any further prompt work is planned.

- **[Inferred — Prompt]** No explicit instruction to refuse or ask for clarification when the question references metrics outside the documented AVAILABLE STATS list. The fallback today is the LLM picking the closest-named column. Symptom: silent miscoercion possible (e.g. "key passes per 90 from open play" → `key_passes_p90`, dropping the open-play qualifier). Why it matters: David's "edge-case adversarial" axis isn't covered by any rule; the model improvises.

**Tool / function-calling layer**

- **[Observed — Tooling]** `agent_tool_schemas.py:118-134` — `_STAT_DESCRIPTION` is a freeform prose list of column names. No enum, no validation. The actual DuckDB tables hold 253 columns on `players_summary` and 203 on `teams_summary` (verified via DESCRIBE), but the description names ~25. Symptom: model can pass `progressive_carries` (a real column documented in the prompt at L26 but absent from the tool schema description). It works because `agent_tools.py:520` does `duck.column_exists(...)` and routes accordingly. Root cause: schema description and prompt list have drifted from each other and from the DB. Why it matters: any new metric the user asks for that exists in DB but isn't in either list is a coin flip.

- **[Observed — Tooling]** `agent_tools.py:828-885` — `query_player_stats` mother tool dispatches on the combination of `opponent_teams`, `last_n_gameweeks`, `match_conditions`, `stat`. Five branches, one of them (`opponent_teams_fill_stat`) requires the LLM to pass two coordinated args matching a prior tool call. Symptom: the system prompt (L113-L132) burns ~20 lines explaining how to use this correctly, with CONCRETE EXAMPLE blocks. Root cause: dynamic-bucket questions ("3 teams that conceded the fewest") were forced into the player tool instead of being a first-class operation. Why it matters: this is the most fragile path — failures here look like correct numbers against the wrong opponents. Inferred risk: not currently tested adversarially.

- **[Observed — Tooling]** `agent.py:32` — `_MAX_ITERATIONS = 6`. `agent.py:152-160` returns the `_FALLBACK_MESSAGE` ("I wasn't able to answer that question…") when the model loops out. There is no telemetry exposing why the loop ran out or what the last tool call was. Symptom: silent failure mode hard to debug. Why it matters: when loop-exhaustion happens in production it presents identically to "no data" — a reviewer can't tell them apart from the user-facing string.

**Memory & multi-turn state**

- **[Observed — Memory]** `agent.py:86-94, 120` — `self._history` accumulates system + user + assistant + every `function_call` + every `function_call_output` for the entire session. No truncation, no compaction. Symptom: token cost grows linearly per turn; latency too. Agust's 4-turn chain is fine; a 30-turn UAT session will hit cost/latency walls. Root cause: Phase 7 traded the broken `previous_response_id` for the simplest thing that works — explicit history. The "next step" (compaction, summary) was deferred and never planned.

- **[Observed — Memory]** No prompt cache hinting on the system prompt. `agent.py:105` calls `client.responses.create` with full input each turn. The static portion of the system prompt is ~10k tokens (284 lines plus the `league_context` markdown injected at `agent_prompt.py:45`). Symptom: every turn re-pays full input tokenization. Why it matters: OpenAI/Azure prompt-cache discounts apply automatically when inputs share the prefix; current code already gets some of this for free, but no measurement, no guard against breaking the prefix when prompts are edited.

- **[Inferred — Memory]** No notion of "what entity is the user currently anchored on." `agent_system.yaml:256-277` FOLLOW-UP QUESTIONS rule is a prompt instruction asking the LLM to track topic resets. When it works, it works; when it doesn't, there's no structured fallback. Risk: any deviation from the canonical Agust 4-turn pattern (e.g. "actually scratch that, who's the leading scorer at home?") relies entirely on the LLM's interpretation of TOPIC RESET paragraphs.

**Data layer**

- **[Observed — Data]** Verified via DESCRIBE:
  - `players_summary`: 253 cols, 444 rows. Includes `xg_total`, `xg_total_p90`, plus rich event metrics (`progressive_carries`, `actions_z3-z5`, `aerial_duels_won`, `pass_z3_to_z4`).
  - `teams_summary`: 203 cols, 20 rows. Has `xg_total`, `total_goals_against` — but no team xG-against (xGA) column. There is no `xg_against` column.
  - `team_match_stats`: 760 rows (20 teams × 38), gameweeks 1–38 complete. Has `xg_total` per match but no `opponent_xg`.
  - `player_match_stats`: 11,567 rows. Match dates with timestamps (`'2024-08-16 21:00:00'`).
  - `league_standings`: final standings, `is_big6` flag.

  Why this matters: A canonical "best xG vs xGA differential" question can't be answered directly because xGA doesn't exist as a column. It can be derived (sum opponent's `xg_total` per fixture for each team, GROUP BY team), but neither the tool layer nor the prompt knows this. Symptom: agent will likely say "no such stat" or substitute `total_goals_against`. Root cause: Phase 8 documented the league but didn't audit metric coverage.

- **[Observed — Data]** `match_date` is a VARCHAR containing timestamps. Symptom: no weekday filter possible without parsing in SQL. The "weekends only" axis of the example adversarial question is currently unanswerable. The schema documents it as VARCHAR (DuckDB's `strptime`/DATE would fix this with a view).

- **[Inferred — Data]** With 253 columns on `players_summary` and only ~30 named in the prompt and tool schema, the discoverability gap is structural. Either we close it (prompt enumerates more, or tool returns a manifest) or we accept a hard ceiling on edge-case coverage.

**Evaluation & failure modes**

- **[Observed — Eval]** `evals/agent_benchmark.py` (61 prepared) and `random_questions.json` (21) are the trustworthy oracles. `evals/synthetic/seed_questions.json` (24, generated for Phase 10) is the third source. The Phase 10/11 "discovery loop" (`evals/discovery/`) re-clusters failures, but produced exactly one insight in 13.6k LOC: BACKLOG_001 (`unsupported_future`). Root cause: the abstraction (failure backlog → triage → campaign → promotion) was built before there were enough failures to justify the structure. Why it matters: the loop's artefacts (`docs/review/context_gap_*.md` with empty TODOs) read as cargo-cult planning to a new reader.

- **[Observed — Eval]** No adversarial-by-design eval set. Both 61 and 21 question sets were authored by the team or generated from templates. No questions of the form: "ambiguous referent" ("how many goals did he score?" with no antecedent), "metric not in schema" ("how many tackles per 90?"), "compound out-of-scope" ("compare this season to last"), "trick wording" ("the team that finished bottom of the Big Six"). Why it matters: these are the David-axis questions; the agent has never been tested on them.

- **[Observed — Eval]** `evals/judges/faithfulness_judge.py` (referenced from `synthetic_runner.py:36`) is the only programmatic correctness check. Symptom: a judge LLM grading a producer LLM. Inferred risk: judge agreement is unmeasured; we don't know if 0.967 faithfulness is 0.95 with judge variance ±0.04 or a tight number.

**Engineering hygiene**

- **[Observed]** 231/231 tests passing — verified count. Test surface heavy on Phase 11 internals (`test_failure_backlog.py`, `test_triage_rubric.py`, `test_campaign_generator.py`, `test_iteration_runner.py`, `test_promote.py`, `test_synthetic_runner.py`, `test_synthetic_clusterer.py`). Production-path tests are smaller (`test_agent_tools.py`, `test_agent_parallel_tools.py`, `test_prompt_rules.py`). Why it matters: the test-to-impact ratio is inverted — most tests guard the eval scaffolding.

- **[Observed]** `docs/review/` contains two orphan files: `pre_phase9_robustness_plan.md` (stale, work done) and `context_gap_unsupported_future__refuse_expected_but_answered.md` (empty TODO stubs from Phase 11 promotion). Symptom: noise. Why it matters: a teammate opening this folder has no way to know which doc is live.

- **[Observed]** `STATE.md` frontmatter reads `total_phases: 3, completed_phases: 1, total_plans: 14, completed_plans: 13`. The body documents Phases 1–11 complete. Symptom: GSD frontmatter is stale; body is correct. Why it matters: any GSD command that reads frontmatter (`/gsd:progress`, `/gsd:next`) gets wrong signal.

- **[Observed]** No CI. No GitHub Actions, no pre-merge benchmark gate. Pre-commit only runs ruff. The "golden rule" in TEAM.md ("benchmark must pass before commit") is honor-system. Why it matters: with three contributors of mixed level, a regression on `src/basic_stats/` will land eventually.

---

**Unknowns to resolve before week 1**

1. **Judge variance.** Run `faithfulness_judge` 3× on the same 61-question run; measure pass-rate spread. If σ > 0.02, either tighten the judge prompt or move to a structured rubric.
2. **Real production usage.** Has anyone outside the team actually used the Streamlit app? If yes, are there logs of real questions in `evals/runs/` or session traces? If no, the entire eval program is operating on synthetic distributions.
3. **Latency p50/p95.** No instrumentation visible. Need a one-day measurement run on the 61-question benchmark to know if `_MAX_ITERATIONS=6` is even hit and what tool-call counts look like.
4. **Token cost per multi-turn session.** Synthesise a 10-turn chain, log total input tokens. Decides the urgency of memory compaction.
5. **xGA derivability check.** Confirm the SQL: `SELECT team_name, SUM(opp.xg_total) AS xga FROM team_match_stats t JOIN team_match_stats opp ON t.match_id = opp.match_id AND t.team_id != opp.team_id GROUP BY team_name`. If that works, xGA is a one-view-away feature — not a missing-data problem.
6. **What David actually wants from "self-improving evals."** His feedback was a comment, not a spec. Before building anything else under `evals/discovery/`, get a single question from him: *"Show me one example of what 'great' looks like for this loop."*

---

### Plan

**Guiding principles**

- Don't grow `src/basic_stats/` without an eval failure pointing at it. Every change to production code carries a benchmark-rerun cost; spend it only when there's evidence.
- The prompt is the configuration surface. All three v2 stakeholder priorities (robustness, follow-up, league context) are already prompt-driven. Lean into that — don't add new architectural layers.
- Cut everything that doesn't move the needle on robustness, follow-up, or league context. Phase 11 internals are mostly debt. Reclaim the headspace.

---

**Phase 12 — Refusal Hard-Stop & Prompt Consolidation (must-ship)**

Goal: Close the only known eval cluster. Compact the prompt so future edits don't fight existing rules.

Success criteria (testable):
- All 8 questions in `evals/discovery/failure_backlog.json` BACKLOG_001 receive refusal-only answers (no historical stats appended).
- 61/61 prepared benchmark: ≥59 faithfulness preserved (no regression).
- 21 random benchmark: ≥19 preserved.
- `agent_system.yaml` line count ≤220 (currently 284) without losing any rule that traces to a passing benchmark question.

Key tasks:
1. Rewrite `agent_system.yaml:159-169` — remove the "you may then offer historical context" sentence and the CORRECT pattern example showing the historical follow-up. Replace with a single hard-stop instruction and one negative few-shot example. ~15 lines net change.
2. Consolidate Big Six labelling: keep L66-L71, delete duplicate at L193-L200.
3. Run `evals/discovery/iteration_runner.py` against `unsupported_future_v1.json` and confirm cluster closure.
4. Run `agent_benchmark.py` (prepared + random); diff faithfulness vs `post_residual_closeout_final`.

Files to touch: `src/basic_stats/prompts/agent_system.yaml` only.

Risks: Tightening refusal could over-trigger on legitimate "what happened in matchweek 38" questions phrased with future-tense verbs. Mitigation: include 2 in-scope-but-future-tense questions in the verification set.

---

**Phase 13 — Adversarial Robustness (must-ship)**

Goal: Test what we haven't tested. Probe metric-coverage and edge cases — fix what breaks, document what doesn't.

Success criteria (testable):
- New `evals/adversarial_questions.json` with ≥40 questions across 6 categories: ambiguous-referent, metric-not-in-schema, compound out-of-scope, trick-wording, derived-metric (xGA), language-mix.
- ≥80% pass rate on the adversarial set, with explicit refusal/clarify behavior for the ambiguous and OOS items.
- For every failure: a `failure_backlog.json` entry, without triggering the Phase 11 promotion machinery (skip `promote.py`).

Key tasks:
1. Author the adversarial set by hand. ~3 hours. Each question annotated with `expected_behavior ∈ {answer, refuse, clarify, derive}`.
2. Run through `synthetic_runner.run` (which is good — it works), cluster failures.
3. For metric-not-in-schema: extend the prompt's AVAILABLE STATS list at `agent_system.yaml:19-57` to include the top-30 most-asked-about metrics from the new test set, and add a single rule: *"If the user asks for a metric not on the list, ask one clarifying question naming the closest available metric. Do not silently substitute."*
4. For ambiguous-referent: extend the FOLLOW-UP QUESTIONS rule with a "no anchor → ask for the entity" instruction.

Files to touch: `evals/adversarial_questions.json` (new), `agent_system.yaml` (rule additions).

Risks: New refusal/clarify rules could regress the existing benchmarks. Mitigation: run all three benchmarks (61 + 21 + 24 synthetic) after each prompt edit; revert any edit that loses >1 question.

---

**Phase 14 — Memory Discipline & Cost Guards (must-ship)**

Goal: Make multi-turn cheap and bounded so a long UAT session doesn't blow up.

Success criteria (testable):
- 20-turn synthetic conversation: total input tokens at turn 20 ≤ 2× turn 5 (currently linear, so ~5×).
- A `last_telemetry` field exposes per-turn input/output token counts and cumulative session cost.
- `_MAX_ITERATIONS` exhaustion logs the last tool call and reason to a structured trace under `evals/runs/<session>/trace.jsonl`.

Key tasks:
1. Add a turn-count threshold in `agent.py`: when `len(self._history) > N`, summarize older turns into a single system-injected `<previous_context>` message. Use the LLM itself for the summary, gated to one call per N turns.
2. Add token telemetry — `response.usage` already returns counts; expose them in `last_telemetry`.
3. Add a tracer: each loop iteration appends `{iteration, tool_name, tool_args_keys, latency_ms}` to a session JSONL.
4. Verify prompt-cache prefix integrity: introduce a tiny test that asserts `build_system_prompt(duck)` is byte-identical across two calls.

Files to touch: `src/basic_stats/agent.py`, `tests/test_agent_memory.py` (new).

Risks: Summarization can lose the entity anchor for follow-ups. Mitigation: keep the last 4 turns verbatim, summarize only turns `1..N-4`.

---

**Later / nice-to-have (one-liners)**

- **xGA view in DuckDB.** One CTE in `duckdb_manager.py`, exposed as `team_xg_against` column on a `team_xg_view`. Unlocks "best xG vs xGA differential" class.
- **Match-date typing.** Add a `match_dt TIMESTAMP` view derived from the VARCHAR field; enables weekday/weekend filters cleanly.
- **`classify_intent` tool (Option 2 from yesterday).** Defer until the adversarial set in Phase 13 shows the prompt-only refusal isn't enough.
- **Discovery loop pruning.** After Phase 13, archive the unused parts of `evals/discovery/` (`triage_rubric`, `promote`, `campaign_generator`) into a `legacy/` folder. Keep `failure_backlog.py` and `synthetic_runner.py`. Saves ~1500 LOC of mental load.
- **CI benchmark gate.** GitHub Action that runs `smoke_test.py` on every PR, full benchmark on merge to `feature/refactor-v2`.
- **Streamlit telemetry surface.** Show `last_telemetry` in a sidebar so non-technical reviewers can see what the agent did per turn.

---

### Evaluation plan

A small canonical golden set the team can run anytime (≤10 min on `--workers 5`):

| Question | Category | Expected behavior | Passes if |
|---|---|---|---|
| "How many goals has Salah scored at home this season?" | normal/lookup | Calls `query_player_stats(player_name='M. Salah', stat='total_goals', filters.is_home=true)` | Number matches DB; answer contains "at home"; no raw keys in text. |
| "Which midfielder has the most progressive passes per 90?" | normal/ranking | Calls `query_ranking(entity_type='player', rank_mode=true, stat='progressive_passes_p90', filters.position='Midfielder', limit=1)` | Returns one player; states the value; minutes-floor note surfaced. |
| "How many goals has Haaland scored?" → "But against the top 6 teams?" → "Is that more than against the rest?" → "What about per 90?" | follow-up chain (Agust) | Tool calls track entity Haaland; final per-90 reflects the bucket. | Each Yes/No matches arithmetic; per-90 derived from the bucket, not season total. |
| "Compare Salah and Saka's goal contributions against teams that finished in the bottom three." | derived bucket + comparison | Two-step: (a) `query_team_stats` to find bottom-3, (b) `query_ranking` with that opponent list. | Both players present; named bottom-3 teams listed; numbers match DB. |
| "Will Salah score against City next week?" | OOS / future | Refuse; do NOT add historical stats. | Answer is ≤2 sentences, no numbers, no "historically Salah has…". |
| "Who's the leading scorer?" (no prior turn) | ambiguous | Ask "Goals or goal contributions? Player or team?" OR default with explicit framing. | Does not silently pick `goal_contributions`; framing matches what was returned. |
| "How many tackles per 90 has Saliba made?" | metric-not-in-schema | Ask one clarifying question naming closest available. | Does not invent a number; does not silently substitute without saying so. |
| "How does this season compare to last?" | OOS / multi-season | Refuse cleanly: "I only have 2024-25 data." | No fabricated 2023-24 comparison. |
| "Who scored more on the road, Isak or Solanke?" | normal/comparison/away | `query_ranking(rank_mode=false, entities=[…], stat='total_goals', filters.is_home=false)` | Returns both with away framing. |
| "¿Cuántos goles ha marcado Lamine Yamal esta temporada?" | OOS by entity | Refuse: not a Premier League player. | Does not return 0 or fabricate. |

These 10 should run in CI on every prompt-touching PR.

---

### First-week action list (≤7 items, Monday-startable)

1. **Verify data layer assumptions** — run the xGA SQL probe; check whether `match_date` parses with `strptime`. ~30 min.
2. **Ship the refusal hard-stop fix** — single edit to `agent_system.yaml:159-169`, run `unsupported_future_v1` campaign, run 61+21 benchmarks, commit if green. ~1.5 h.
3. **Author 40-question adversarial set** in `evals/adversarial_questions.json` covering the 6 categories listed in Phase 13. ~3 h.
4. **Run adversarial set baseline** through `synthetic_runner.run`, cluster failures, write a 1-page list of what fails and why. ~1 h.
5. **Fix `STATE.md` frontmatter** so `/gsd:progress` and `/gsd:next` return correct phase counts. ~10 min.
6. **Archive `docs/review/` orphans** (delete `pre_phase9_robustness_plan.md`, decide on `context_gap_*.md`) and remove the discovery-loop test bloat from the default test run with a pytest marker. ~30 min.
7. **Add `last_telemetry` token counts** from `response.usage` to the agent — preparatory hook for Phase 14 without changing behavior. ~45 min.

If items 1–4 land green by end-of-week, you have an honest measurement of where the agent stands on adversarial robustness — and that's the answer to David. If they don't, you have specific failures pointing at the next concrete change. Either outcome is shippable progress; neither requires rebuilding anything.

---

## Open Items at End of Session

1. **Fix `agent_system.yaml` lines ~159–169** — hard stop after refusal, one few-shot example, remove "you may then offer historical context"
2. **Rerun `unsupported_future_v1` campaign** to verify the cluster closes
3. **Optionally:** fill in the TODO stubs in `docs/review/context_gap_unsupported_future__refuse_expected_but_answered.md` (or delete it — the information is in the backlog)
4. **Decision pending:** whether to build the `classify_intent` tool (Option 2) — gated on eval results from item 2
