# v2.0 Refactor Integration Summary

**For:** Roadmapper creating 6 phases  
**Key Deliverable:** ARCHITECTURE.md (detailed integration guide)

## Three Critical Constraints

1. **Benchmark Gate:** 61/61 must pass after EVERY phase. Any regression = block the phase.
2. **Entry Point is Sacred:** `BasicStatsAgent.ask(question)` signature can only evolve additively (optional params), never break existing calls.
3. **Import Stability:** Streamlit caches imports. Directory moves must use 2-week shim re-export window to avoid session_state breakage.

---

## Phase Build Order (Safe Migration Path)

```
Phase 1: Extract & Clean
├─ Create src/basic_stats/, src/shared/, tests/, evals/
├─ Copy files (zero behavior change)
├─ Add shim re-exports in utils/basic_stats/core/
└─ BENCHMARK GATE: 61/61

Phase 2: Function Calling Core
├─ Replace _canonicalize_raw_plan() with resolve_query_intent() tool
├─ Dual-run validation: old planner vs new tool on all 61 questions
├─ If plans match, delete old code and detectors (~980 lines removed)
└─ BENCHMARK GATE: 61/61

Phase 3: Conversation Memory
├─ Add ConversationState to session_state (dataclass, not DB)
├─ Pass conversation_context through engine → planner → system prompt
├─ Make parameter optional (default "") so Phase 2 tests still work
└─ BENCHMARK GATE: 61/61

Phase 4: League Context Injection
├─ Add league_context parameter (optional, hardcoded for Phase 4)
├─ Inject into system prompt via _build_system_prompt()
├─ Test dynamic team classification
└─ BENCHMARK GATE: 61/61

Phase 5: Random Question Robustness
├─ Stress test 50+ unprepared questions
├─ Fix aliases, improve edge-case handling
├─ Document known limitations
└─ BENCHMARK GATE: 61/61

Phase 6: Natural Language Polish
├─ Refine verbalize.yaml for natural phrasing
├─ Test verbalization quality on sample questions
└─ BENCHMARK GATE: 61/61
```

---

## Integration Points by Phase

### Phase 1: Files Move, Imports Updated
**What changes:**
- New directory structure: `src/basic_stats/`, `src/shared/`, `tests/`, `evals/`
- Shim re-exports in old location for 2 weeks
- `pages/basic_stats.py` imports updated (separate commit)
- `eval_runner_v6.py` imports updated (separate commit)

**What stays the same:**
- `BasicStatsAgent.ask()` signature: `ask(question: str) -> dict`
- All behavior: 61/61 benchmark unchanged

**Risk:** Import failures in Streamlit → mitigation: shim layer + gradual migration

---

### Phase 2: Planner Replaced
**What changes:**
- `_canonicalize_raw_plan()` deleted (~680 lines)
- Detector functions deleted (~300 lines)
- New `resolve_query_intent()` tool (function calling)
- New `Planner` wrapper class

**What stays the same:**
- `BasicStatsAgent.ask()` signature
- Output format: `{"content": str, "debug": dict}`
- All behavior: 61/61 benchmark unchanged

**New signature capability:**
```python
def ask(self, question: str, conversation_context: str = "") -> dict:
    # conversation_context is optional, used in Phase 3
```

**Risk:** New planner produces different plans → mitigation: dual-run validation before deletion

---

### Phase 3: Conversation State Added
**What changes:**
- `ConversationState` dataclass in `src/shared/types.py`
- `_conversation_metadata` key in Streamlit session_state
- `conversation_context` passed through engine → planner → system prompt
- "Clear chat" button resets `_conversation_metadata`

**What stays the same:**
- `BasicStatsAgent.ask()` signature (conversation_context is optional)
- Behavior for single questions: 61/61 unchanged (context injection only if non-empty)

**New capability:**
```python
# Follow-up questions now work
Q: "Who scored the most goals?"
A: "Haaland with 27 goals"
Q: "Against top 6?"
A: [knows to filter against top 6 because conversation context includes first Q&A]
```

---

### Phase 4: League Context Injection
**What changes:**
- `league_context` parameter added to `ConversationState`
- `league_context` passed to engine → planner → system prompt
- League description injected via `_build_system_prompt()`

**What stays the same:**
- `BasicStatsAgent.ask()` signature (league_context is optional)
- Behavior if league_context is None: 61/61 unchanged

**New capability:**
```python
# Dynamic team classification
league_context = "Premier League: Big Six are Man City, Liverpool, Arsenal, Man United, Tottenham, Chelsea. Top 4 = European zones..."
# Now planner can classify teams without hardcoded labels
```

---

### Phase 5 & 6: Refinement
**What changes:**
- Alias additions (aliases_para_ricardo.json)
- Prompt refinements (verbalize.yaml, resolve_query_intent.yaml)

**What stays the same:**
- All signatures
- Behavior: 61/61 unchanged (only edge cases + polish)

---

## Import Chain Refactor (Phase 1 Detail)

**Before:**
```python
# pages/basic_stats.py
from utils.basic_stats.core.agent import BasicStatsAgent

# eval_runner_v6.py
from utils.basic_stats.core.llm_query_engine_v2 import LLMQueryEngineV2
```

**After (with shims):**
```python
# pages/basic_stats.py — UNCHANGED (during shim period)
from utils.basic_stats.core.agent import BasicStatsAgent

# Shim: utils/basic_stats/core/agent.py
from src.basic_stats.agent import BasicStatsAgent as _NewAgent
BasicStatsAgent = _NewAgent

# After shim removal: pages/basic_stats.py — UPDATED
from src.basic_stats.agent import BasicStatsAgent

# eval_runner_v6.py — UPDATED
from src.basic_stats.engine.llm_query_engine import LLMQueryEngineV2
```

**Why two-step:** Streamlit caches imports. If pages still use old import path while code has moved, session_state breaks.

---

## Path Resolution After Move

**Critical:** DuckDB path resolution uses `Path(__file__).resolve().parents[3]`.

**Before (in utils/basic_stats/core/):**
```
utils/basic_stats/core/duckdb_manager.py
├─ parents[0] = core/
├─ parents[1] = basic_stats/
├─ parents[2] = utils/
└─ parents[3] = REPO ROOT ← BASE = parents[3]
```

**After (in src/basic_stats/data/):**
```
src/basic_stats/data/duckdb.py
├─ parents[0] = data/
├─ parents[1] = basic_stats/
├─ parents[2] = src/
├─ parents[3] = REPO ROOT ← Must update to parents[3]
└─ parents[4] = ???
```

Actually **same level** — no change needed. Test after move.

---

## Eval Runner Updates Required

**eval_runner_v6.py:**
```python
# Phase 1+
from src.basic_stats.engine.llm_query_engine import LLMQueryEngineV2

# Phase 4+
engine = LLMQueryEngineV2(league_context=LEAGUE_CONTEXT)
```

**Validation:** Run `python eval_runner_v6.py` after each phase, ensure 61/61.

---

## ConversationState: Dataclass Not Database

**Why:** 
- Conversation is per-session, not persistent
- Streamlit session_state is already JSON-serializable
- Simpler, more testable
- If persistence needed later, wrap with DB layer

**Location:** 
```python
# src/shared/types.py
@dataclass
class ConversationState:
    turns: list[ConversationTurn]
    league_context: str | None
    current_entity: str | None

# pages/basic_stats.py
st.session_state["_conversation_metadata"] = ConversationState()
```

---

## League Context: Static Paragraph, System Prompt Injection

**NOT a database lookup.** Too expensive. Just a paragraph describing league structure.

**Example:**
```
"Premier League (England) has 20 teams. The Big Six are Man City, Liverpool, Arsenal, Man United, 
Tottenham, Chelsea. Top 4 = European zones. Mid-table (7–14) = competitive. Bottom 4 = relegation. 
Top 6 matches are high-profile."
```

**Injected via:**
```python
def _build_system_prompt(league_context: str | None) -> str:
    base = "You are a football data query planner..."
    if league_context:
        base += f"\n\nLEAGUE CONTEXT:\n{league_context}\n"
    return base
```

**Flow:**
```
pages/basic_stats.py
  ↓ (league_context in ConversationState)
BasicStatsAgent.ask(question, league_context=...)
  ↓
LLMQueryEngineV2.ask(question, league_context=...)
  ↓
Planner.plan(question, league_context=...)
  ↓
resolve_query_intent(question, league_context=...)
  ↓ (inject into system prompt)
LLM with function calling
```

---

## Migration Risks (Simplified)

| Risk | Mitigation |
|------|-----------|
| **Streamlit import cache breaks** | 2-week shim re-export window |
| **New planner produces different plans** | Dual-run validation before deletion |
| **Conversation context changes behavior** | Make parameter optional, test without first |
| **Path resolution breaks after move** | Test DuckDBManager() immediately after move |
| **Eval runner can't import** | Update imports as separate commit |
| **Circular imports in src/** | Use dependency injection, test imports |
| **League context prompt injection** | Validate format, hardcode for Phase 4 |

---

## Roadmap Template

Each phase should include:

1. **Objective** — What's being done
2. **Integration Points** — Which signatures change, which files update
3. **Test Plan** — How to validate (eval runner, unit tests, etc.)
4. **Benchmark Validation** — When to run `eval_runner_v6.py`, expected result: 61/61
5. **Rollback Plan** — What to do if benchmark drops
6. **Commits** — How many commits, what each does
7. **Risk Checklist** — Specific risks for this phase + mitigations

**Example for Phase 2:**
```
Objective: Replace QueryPlanner._canonicalize_raw_plan() with resolve_query_intent() function calling

Integration Points:
- New file: src/basic_stats/engine/tools.py (QueryPlan model, resolve_query_intent function)
- New file: src/basic_stats/engine/planner.py (Planner wrapper)
- Modified: src/basic_stats/engine/llm_query_engine.py (call new planner)
- Deleted: old query_planner.py, detector functions (~980 lines)

Test Plan:
- Create test_phase2_parallel_execution.py: run both old and new planner on all 61 questions, compare plans
- Require 100% plan match before deleting old code
- Run full eval_runner_v6.py

Benchmark Validation:
- Before: 61/61 (from Phase 1)
- After: Must still be 61/61
- If < 61: investigate divergence, don't merge

...
```

---

## Files Delivered

- **ARCHITECTURE.md** — Full integration guide (this research)
  - Directory restructure details
  - Function calling integration (what gets replaced)
  - ConversationState location and flow
  - League context injection
  - Build order with risks
  - Phase-specific guardrails

- **INTEGRATION_SUMMARY.md** — This file (quick reference for roadmapper)

**Next:** Roadmapper reads ARCHITECTURE.md and creates detailed 6-phase roadmap.
