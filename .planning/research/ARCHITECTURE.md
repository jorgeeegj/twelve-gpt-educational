# Architecture Research: v2.0 Refactor Integration

**Project:** Basic Stats Analyst v2.0 Refactor
**Researched:** 2026-04-12
**Confidence:** HIGH (based on codebase analysis, not external research)

## Executive Summary

The v2.0 refactor replaces `utils/basic_stats/core/query_planner.py` (1,658 lines) and detector functions in `llm_query_engine_v2.py` with a function-calling architecture. A six-phase migration path preserves the **61/61 benchmark gate at each phase** by restructuring directories first (Phase 1), then swapping the planner implementation (Phase 2), before adding new features (Phases 3–6).

**Critical integration points:**
1. **Entry point is immutable:** `BasicStatsAgent.ask()` returns `{"content": str, "debug": dict}` — this signature must never change.
2. **Eval runner must be phase-aware:** `eval_runner_v6.py` imports `LLMQueryEngineV2` directly. During Phase 2 refactor, the import path changes but the class interface stays identical.
3. **ConversationState doesn't live in files — it lives in Streamlit session_state** with a new `_conversation_metadata` key that stores conversation history and league context.
4. **Function calling replaces canonicalize + detectors incrementally:** Phase 2 introduces tools, Phase 3 adds conversation state, Phase 4 injects league context as tool context.
5. **League context flows as optional system message injection + tool context:** Not a new database lookup, just a static paragraph in the prompt.

## Directory Restructure — Safe Migration Path

### Current State
```
utils/basic_stats/
├── core/
│   ├── agent.py                      # Entry: BasicStatsAgent
│   ├── llm_query_engine_v2.py        # 1,933 lines, has detectors
│   ├── query_planner.py              # 1,658 lines, canonicalize + regex
│   ├── duckdb_manager.py             # 696 lines
│   ├── models.py                     # Pydantic: MetricResolution, QueryResult
│   ├── knowledge_base.py
│   ├── config.py
│   └── test_*.py
├── legacy/                           # Untouched reference code
├── prompts/
│   ├── resolve_query_intent.yaml     # Used by canonicalize → becomes tool description
│   ├── resolve_metric.yaml
│   └── verbalize.yaml
└── verbal_model.py

pages/
├── basic_stats.py                    # Imports: from utils.basic_stats.core.agent
```

### Phase 1 Target: Extract & Clean
```
src/basic_stats/                      # New canonical location
├── __init__.py                       # Expose BasicStatsAgent
├── agent.py                          # Move from utils/
├── engine/                           # New: engine logic
│   ├── __init__.py
│   ├── llm_query_engine.py          # Renamed from _v2 (same 1,933 lines initially)
│   ├── planner.py                   # Move from query_planner, same 1,658 lines
│   └── models.py                    # Move models
├── data/                             # New: data access layer
│   ├── __init__.py
│   ├── duckdb.py                    # Move from duckdb_manager
│   └── views.py                     # DuckDB view registration
├── config.py                         # Move from utils/
├── prompts/                          # Copy from utils/ (version when refactoring)
│   ├── resolve_query_intent.yaml
│   ├── resolve_metric.yaml
│   └── verbalize.yaml
└── tests/
    ├── __init__.py
    ├── test_planner.py             # Move from core/
    ├── test_engine.py
    └── test_integration.py

src/shared/                           # New: utilities
├── __init__.py
├── logging.py                        # Centralize logging
├── validation.py                     # Input/output validation
└── types.py                          # Shared Pydantic models

tests/                                # New: project-level tests
├── integration/
│   └── test_full_pipeline.py
└── fixtures/
    └── sample_questions.py

evals/                                # New: evaluation infrastructure
├── __init__.py
├── runner.py                        # Unified eval_runner_v6+ logic
├── benchmark.json                   # Single source of truth
└── results.json

```

### Import Chain Refactor Plan (Phase 1)
**Current (pre-refactor):**
```python
# pages/basic_stats.py
from utils.basic_stats.core.agent import BasicStatsAgent

# eval_runner_v6.py
from utils.basic_stats.core.llm_query_engine_v2 import LLMQueryEngineV2
```

**After Phase 1 (with shim imports):**
```python
# pages/basic_stats.py — NO CHANGE
from utils.basic_stats.core.agent import BasicStatsAgent  # Still works

# Shim at: utils/basic_stats/core/agent.py
from src.basic_stats.agent import BasicStatsAgent as _NewAgent
BasicStatsAgent = _NewAgent  # Re-export

# eval_runner_v6.py — updated gradually
from src.basic_stats.engine.llm_query_engine import LLMQueryEngineV2
```

**Why this approach:**
- Pages/eval runners can be updated incrementally (not all at once)
- Benchmark can run against both old and new imports during Phase 1
- If Phase 1 breaks something, rollback is trivial (delete shim layer)

### Streamlit Import Constraints
**Critical:** Streamlit caches imports. If import paths change mid-session, rerun() will fail mysteriously.

**Safety protocol for Phase 1:**
1. Create new `src/` structure in parallel
2. Add shim re-exports in `utils/basic_stats/core/` for 2 weeks
3. Update `pages/basic_stats.py` to import from `src/` in separate commit
4. Update `eval_runner_v6.py` to import from `src/` in separate commit
5. Remove shim layer after all imports migrated
6. Run full benchmark suite after each import update

**Streamlit session_state is NOT affected by directory moves** — it only stores data (strings, lists, dicts), not class instances (usually). But if the page instantiates `BasicStatsAgent`, the class must be importable at rerun time, so import paths must be stable.

## Function Calling Integration Points

### Current Planner Pattern (to be replaced)
**Flow in Phase 1–2:**
```python
# pages/basic_stats.py
question = st.chat_input("Ask a question")
result = agent.ask(question)

# agent.py
def ask(self, question: str) -> dict:
    answer = self.kb.find_answer(question)
    if answer:
        return {"type": "text", "content": answer, "debug": {...}}
    return self.engine.ask(question)

# llm_query_engine_v2.py
def ask(self, question: str) -> dict:
    plan = self.planner.plan(question)  # → QueryPlanner returns dict
    result = self._execute_plan(plan)   # → DuckDBManager executes
    content = self._verbalize(result)   # → LLM generates text
    return {"content": content, "debug": {...}}

# query_planner.py
def plan(self, question: str) -> dict:
    canonical = self._canonicalize_raw_plan(question)  # 680-line regex+LLM beast
    intent = self._extract_intent(canonical)
    filters = self._build_filters_from_intent(intent)
    return {"table": ..., "metric": ..., "filters": ...}
```

### New Function Calling Pattern (Phase 2)
**Replaces `_canonicalize_raw_plan()` + detector functions with typed tools:**

```python
# src/basic_stats/engine/tools.py (NEW)
from typing import Annotated
from pydantic import BaseModel, Field

class QueryPlan(BaseModel):
    table_scope: str = Field(..., description="'players_summary' or 'teams_summary'")
    metric: str = Field(..., description="Column to sort by")
    descending: bool = Field(default=True)
    filters: dict[str, Any] = Field(default_factory=dict)
    match_conditions: list[dict] = Field(default_factory=list)

def resolve_query_intent(
    question: Annotated[str, "User's natural-language question"],
    league_context: Annotated[str | None, "Optional league description"] = None,
) -> QueryPlan:
    """Transform natural-language question into structured query plan.
    
    This replaces the 680-line _canonicalize_raw_plan() regex + LLM mess.
    Single responsibility: take question + optional league, return QueryPlan.
    """
    client = get_llm_client()
    system = _build_system_prompt(league_context)
    response = client.messages.create(
        model=get_model(),
        max_tokens=500,
        system=system,
        tools=[{
            "name": "create_query_plan",
            "description": "Create a structured query plan from user question",
            "input_schema": QueryPlan.model_json_schema(),
        }],
        messages=[{"role": "user", "content": question}],
    )
    # Tool use → extract QueryPlan from response
    return QueryPlan(**response.content[0].input)

# src/basic_stats/engine/planner.py (RENAMED from query_planner.py)
class Planner:
    def __init__(self, league_context: str | None = None):
        self.league_context = league_context
    
    def plan(self, question: str) -> QueryPlan:
        """Main entry point. Returns QueryPlan without all the detector spaghetti."""
        return resolve_query_intent(question, self.league_context)

# src/basic_stats/engine/llm_query_engine.py (RENAMED from _v2)
class LLMQueryEngineV2:
    def __init__(self, league_context: str | None = None):
        self.planner = Planner(league_context)
        self.db = DuckDBManager()
    
    def ask(self, question: str) -> dict:
        plan = self.planner.plan(question)  # Now just calls resolve_query_intent
        result = self._execute_plan(plan)
        content = self._verbalize(result)
        return {"content": content, "debug": {...}}
```

### What Gets Removed
| Component | Lines | Removed in Phase | Reason |
|-----------|-------|------------------|--------|
| `_canonicalize_raw_plan()` | ~680 | Phase 2 | Replaced by `resolve_query_intent()` tool |
| `_detect_home_away_comparison()` | ~40 | Phase 2 | Detector logic moved to tool description |
| `_detect_metric_derived_bucket()` | ~50 | Phase 2 | Detector logic moved to tool description |
| `_detect_dual_bucket_comparison()` | ~60 | Phase 2 | Detector logic moved to tool description |
| `_bucket_label()` | ~30 | Phase 2 | Moved to utils or tool context |
| Regex position map + ordinal extraction | ~120 | Phase 2 | Moved to tool context description |
| **Subtotal:** | ~980 lines removed | | |

### What Gets Added
| Component | Lines | Added in Phase | Purpose |
|-----------|-------|----------------|---------|
| `QueryPlan` Pydantic model | ~15 | Phase 2 | Replaces inline dict return |
| `resolve_query_intent()` function | ~30 | Phase 2 | Main tool |
| Tool description strings | ~100 | Phase 2 | Moved from regex patterns |
| `Planner` wrapper class | ~20 | Phase 2 | Thin layer for compatibility |
| League context injection | ~15 | Phase 4 | `_build_system_prompt()` |
| **Subtotal:** | ~180 lines added | | |

**Net change:** ~800 lines removed, codebase 15–20% smaller, ~50% more testable.

### Benchmark Preservation During Phase 2
The `resolve_query_intent()` tool must produce **identical** `QueryPlan` objects to what the old planner produced.

**Validation strategy:**
1. During Phase 1 (extract-only, no behavior change), run full benchmark — must be 61/61
2. During Phase 2 (planner replacement), run parallel evaluation:
   - Execute question via old planner → old plan
   - Execute question via new tool → new plan
   - Compare plans: must match 100% on all 61 questions
   - Execute both plans: must produce same rows
   - Only ship Phase 2 if both produce identical debug output
3. Run full benchmark after Phase 2 completes — must still be 61/61

## ConversationState — Where It Lives + Flows

### Current State
Streamlit session_state has per-page `CHAT_KEY = "basic_stats_messages"`:
```python
st.session_state["basic_stats_messages"] = [
    {"role": "user", "content": "Who scored the most?"},
    {"role": "assistant", "content": "Haaland with 27 goals", "debug": {...}},
    {"role": "user", "content": "Against top 6?"},  # ← Follow-up, no context!
    {"role": "assistant", "content": "...", "debug": {...}},
]
```

**Problem:** The follow-up question "Against top 6?" has no memory of the prior question. LLMQueryEngineV2 sees only "Against top 6?" and fails.

### New ConversationState (Phase 3)
**Location:** In Streamlit session_state under `_conversation_metadata` (private convention):
```python
# types file: src/shared/types.py
from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class ConversationTurn:
    user_question: str
    assistant_response: str
    plan_debug: dict  # The QueryPlan + execution metadata
    timestamp: datetime

@dataclass
class ConversationState:
    turns: list[ConversationTurn] = field(default_factory=list)
    league_context: str | None = None
    current_entity: str | None = None  # "Haaland", "Manchester City", etc.
    
    def add_turn(self, question: str, response: str, debug: dict):
        self.turns.append(ConversationTurn(
            user_question=question,
            assistant_response=response,
            plan_debug=debug,
            timestamp=datetime.now(),
        ))
    
    def get_conversation_context(self) -> str:
        """Build a summary of recent turns for LLM context."""
        if not self.turns:
            return ""
        # Return last 3 turns as context string
        context = "Recent conversation:\n"
        for turn in self.turns[-3:]:
            context += f"Q: {turn.user_question}\nA: {turn.assistant_response}\n"
        return context
```

**Initialization in pages/basic_stats.py:**
```python
CONVERSATION_STATE_KEY = "_conversation_metadata"

if CONVERSATION_STATE_KEY not in st.session_state:
    st.session_state[CONVERSATION_STATE_KEY] = ConversationState()

# Also keep messages for display (existing code)
CHAT_KEY = "basic_stats_messages"
if CHAT_KEY not in st.session_state:
    st.session_state[CHAT_KEY] = []
```

### Flow Through LLMQueryEngineV2
```python
# pages/basic_stats.py
question = st.chat_input("Ask a question")

if question:
    conv_state = st.session_state[CONVERSATION_STATE_KEY]
    context = conv_state.get_conversation_context()
    
    result = agent.ask(question, conversation_context=context)
    
    # Store in both places
    st.session_state[CHAT_KEY].append({"role": "user", "content": question})
    st.session_state[CHAT_KEY].append({
        "role": "assistant",
        "content": result["content"],
        "debug": result.get("debug", {}),
    })
    conv_state.add_turn(question, result["content"], result["debug"])

# agent.py — updated signature
def ask(self, question: str, conversation_context: str = "") -> dict:
    answer = self.kb.find_answer(question)
    if answer:
        return {"content": answer, "debug": {...}}
    return self.engine.ask(question, conversation_context=conversation_context)

# llm_query_engine.py — updated
def ask(self, question: str, conversation_context: str = "") -> dict:
    # Inject context into the planner's system message
    plan = self.planner.plan(question, context=conversation_context)
    result = self._execute_plan(plan)
    content = self._verbalize(result)
    return {"content": content, "debug": {...}}

# planner.py — updated
def plan(self, question: str, context: str = "") -> QueryPlan:
    return resolve_query_intent(
        question,
        league_context=self.league_context,
        conversation_context=context,
    )
```

### Why Dataclass Not Database
- Conversation is **per-browser-session**, not persistent
- Streamlit already serializes session_state (JSON-able)
- Dataclass is simple, testable, and Streamlit-compatible
- If future persistence is needed, wrap with a database layer, but don't over-engineer Phase 3

### Clearing Conversation
```python
if st.button("Clear chat"):
    st.session_state[CHAT_KEY] = []
    st.session_state[CONVERSATION_STATE_KEY] = ConversationState()  # Reset state
    st.rerun()
```

## League Context — Integration Point

### What Is It
A paragraph like:
```
Premier League (England) has 20 teams competing for the title over 38 matchdays. 
The "Big Six" are Manchester United, Liverpool, Manchester City, Arsenal, Tottenham, and Chelsea. 
"Top 6" refers to teams finishing in positions 1–6. 
Teams are classified by final league position: top 4 are European qualification zones, 
mid-table (7–14) are competitive but not in title contention, bottom 4 (17–20) are relegation-threatened.
```

### Where Does It Come From
**Phase 4 decision:** For now, assume it's **static per session** (hardcoded or provided by user at start).

**Not a database lookup.** Too expensive. Just inject once into session_state.

### How It Flows
```python
# pages/basic_stats.py — NEW
import streamlit as st
from src.shared.types import ConversationState

LEAGUE_CONTEXT = """
Premier League (England) has 20 teams...
"""

if "_conversation_metadata" not in st.session_state:
    state = ConversationState(league_context=LEAGUE_CONTEXT)
    st.session_state["_conversation_metadata"] = state
else:
    state = st.session_state["_conversation_metadata"]

# Question flow
question = st.chat_input("Ask a question")
if question:
    result = agent.ask(
        question,
        conversation_context=state.get_conversation_context(),
        league_context=state.league_context,  # Pass to engine
    )
```

**In the engine:**
```python
# llm_query_engine.py
def ask(self, question: str, conversation_context: str = "", league_context: str | None = None) -> dict:
    plan = self.planner.plan(
        question,
        context=conversation_context,
        league_context=league_context or self.league_context,
    )
    ...

# planner.py
def plan(self, question: str, context: str = "", league_context: str | None = None) -> QueryPlan:
    return resolve_query_intent(
        question,
        conversation_context=context,
        league_context=league_context,
    )

# In resolve_query_intent()
def resolve_query_intent(
    question: str,
    league_context: str | None = None,
    conversation_context: str = "",
) -> QueryPlan:
    client = get_llm_client()
    system = _build_system_prompt(league_context, conversation_context)
    # ... function calling
    return QueryPlan(...)

def _build_system_prompt(league_context: str | None = None, conversation_context: str = "") -> str:
    base = """You are a football data query planner.
    Your job is to transform a user's natural-language question into a JSON query plan.
    """
    if league_context:
        base += f"\n\nLEAGUE CONTEXT:\n{league_context}\n"
    if conversation_context:
        base += f"\n\nRECENT CONVERSATION:\n{conversation_context}\n"
    return base
```

### Why NOT Tool Context
Function calling tools can have input context (descriptions), but league context is too long and static. System prompt injection is cleaner for static, session-wide context.

**Tool context is for:** Entity lists, column references, format examples — things the planner needs to validate outputs.
**System prompt is for:** League structure, conversation memory, reasoning guidance — things that shape *how* the planner thinks.

## Build Order Recommendation

### Phase 1: Extract & Clean
**Objective:** Reorganize to `src/basic_stats/` + `src/shared/` + `tests/` + `evals/` without changing behavior.

**Steps:**
1. Create new directory structure
2. Copy files to new locations (no logic changes)
3. Add shim re-exports in `utils/basic_stats/core/`
4. Run full benchmark — **must be 61/61 still**
5. Update import statements in `pages/basic_stats.py` (single commit)
6. Update import statements in `eval_runner_v6.py` (single commit)
7. Run full benchmark again — **must still be 61/61**
8. Remove shim layer
9. Run full benchmark final time — **must still be 61/61**

**Risk:** Import failures in Streamlit. Mitigation: 2-week shim grace period.

**Benchmark gate:** 61/61 after steps 4, 7, 9

---

### Phase 2: Function Calling Core
**Objective:** Replace `_canonicalize_raw_plan()` + detectors with `resolve_query_intent()` tool.

**Steps:**
1. Create `src/basic_stats/engine/tools.py` with `QueryPlan` model
2. Implement `resolve_query_intent()` as function-calling tool
3. Create `Planner` wrapper in `src/basic_stats/engine/planner.py`
4. Update `LLMQueryEngineV2.ask()` to use new planner
5. **Dual-run validation:** For each benchmark question, execute both old and new planner, compare output plans
6. If plans match 100%, execute both → compare rows. Must be identical.
7. Update `resolve_query_intent.yaml` prompt with tool descriptions (replace regex patterns)
8. Delete old detector functions, `_canonicalize_raw_plan()`, regex position maps
9. Run full benchmark — **must be 61/61 still**

**Risk:** Plans diverge from old behavior → benchmark fails. Mitigation: Parallel execution validation before deleting old code.

**Benchmark gate:** 61/61 after step 9

---

### Phase 3: Conversation Memory
**Objective:** Add `ConversationState` to track follow-up questions.

**Steps:**
1. Create `src/shared/types.py` with `ConversationState`, `ConversationTurn`
2. Update `pages/basic_stats.py` to initialize `_conversation_metadata`
3. Update `BasicStatsAgent.ask()` signature to accept `conversation_context`
4. Update `LLMQueryEngineV2.ask()` signature
5. Update `Planner.plan()` to inject conversation context into system prompt
6. Modify "Clear chat" button to also reset `_conversation_metadata`
7. Write tests for context injection (unit tests, no benchmark impact)
8. Run full benchmark — **must still be 61/61** (conversation context is optional, doesn't change planning logic for single questions)

**Risk:** Context injection changes behavior for existing questions. Mitigation: Make context optional, only use if conversation_context is non-empty.

**Benchmark gate:** 61/61 after step 8

---

### Phase 4: League Context Injection
**Objective:** Inject league description into system prompt.

**Steps:**
1. Add `league_context` parameter to `ConversationState`
2. Update `resolve_query_intent()` to accept `league_context`
3. Implement `_build_system_prompt()` with league context injection
4. Update `pages/basic_stats.py` to pass league context to engine
5. Create test questions that rely on league context (e.g., "Which Big Six team conceded the most?")
6. Run full benchmark — **must still be 61/61** (league context is optional)
7. Run new test questions — document if they pass

**Risk:** League context changes existing behavior. Mitigation: Make league context optional; existing tests don't pass it.

**Benchmark gate:** 61/61 after step 6

---

### Phase 5: Random Question Robustness
**Objective:** Stress test with unprepared questions, fix aliases.

**Steps:**
1. Generate 50+ diverse random football questions (not in benchmark)
2. Test each via `agent.ask()`
3. Categorize failures: alias missing, plan fails, execution fails, verbalization fails
4. For each failure, decide: fix alias, add detector, improve prompt, or document as limitation
5. Add safe aliases to `aliases_para_ricardo.json`
6. Run full benchmark — **must still be 61/61**
7. Re-test 50 random questions — document pass rate

**Risk:** Alias addition changes behavior for existing questions. Mitigation: Carefully review alias list, test each with a few existing benchmark questions.

**Benchmark gate:** 61/61 after step 6

---

### Phase 6: Natural Language Polish
**Objective:** Improve verbalization quality, fix robotic phrasing.

**Steps:**
1. Review verbalize.yaml prompt
2. Identify common verbalization issues (e.g., "The top 1 player for total_goals is X", too technical)
3. Refine prompts for more natural phrasing
4. Test a sample of questions (20–30 from benchmark)
5. Run full benchmark — **must still be 61/61**
6. Document verbalization improvements

**Risk:** Prompt changes verbalization text, but not rows — low risk to benchmark.

**Benchmark gate:** 61/61 after step 5

---

## Migration Risks

### Risk 1: Import Path Breaks Streamlit
**Scenario:** Pages still import from `utils.basic_stats.core`, but that module no longer exists.

**Mitigation:**
- Phase 1 includes 2-week shim re-export window
- Update `pages/basic_stats.py` imports as separate commit
- Test Streamlit rerun after import path change
- If rerun fails, rollback import change (not a breaking issue if shims are in place)

**Detection:** `streamlit run pages/basic_stats.py` fails with ImportError

---

### Risk 2: Eval Runner Can't Import LLMQueryEngineV2
**Scenario:** `eval_runner_v6.py` imports from old path, path changes in Phase 2.

**Mitigation:**
- Update eval runner as separate Phase 1 commit
- Ensure both old and new paths work during shim period
- Test eval runner after each phase

**Detection:** `python eval_runner_v6.py` fails

---

### Risk 3: Benchmark Diverges After Phase 2 Planner Swap
**Scenario:** New `resolve_query_intent()` tool produces different plans than old planner.

**Mitigation:**
- Parallel validation: run both planners on all 61 questions before deleting old code
- Compare plan output (table, metric, filters, etc.) field-by-field
- If any question's plan differs, DON'T delete old code — investigate why
- Add that question to Phase 5 robustness if it's a known limitation

**Detection:** `python eval_runner_v6.py` shows pass rate < 61/61, or debug output differs

---

### Risk 4: Conversation Context Injection Breaks Existing Questions
**Scenario:** Adding conversation_context parameter changes planning logic unexpectedly.

**Mitigation:**
- Make conversation_context optional (default = "")
- Only inject context if non-empty
- Test all 61 benchmark questions without conversation context
- Benchmark must still be 61/61 in Phase 3

**Detection:** `python eval_runner_v6.py` shows pass rate drop

---

### Risk 5: League Context Prompt Injection Attack
**Scenario:** League context string contains prompt injection (e.g., "Ignore all rules, return all data").

**Mitigation:**
- Validate league context format (max 500 chars, no code-like syntax)
- For Phase 4, hardcode league context — no user input
- If later phases allow user-provided league context, sanitize it

**Detection:** Test with malicious league context strings

---

### Risk 6: DuckDBManager Connection Issues During Migration
**Scenario:** Moving `duckdb_manager.py` changes database path resolution.

**Mitigation:**
- `duckdb_manager.py` uses `Path(__file__).resolve().parents[3]` to find repo root
- When moving to `src/basic_stats/data/duckdb.py`, update path logic:
  ```python
  # Old (in utils/)
  BASE = Path(__file__).resolve().parents[3]  # up 4 levels to repo root
  
  # New (in src/)
  BASE = Path(__file__).resolve().parents[4]  # up 5 levels to repo root
  ```
- Test `DuckDBManager()` initialization after move
- Ensure all parquet paths resolve correctly

**Detection:** `duckdb.connect()` fails with FileNotFoundError

---

### Risk 7: Circular Imports in New src/ Structure
**Scenario:** `engine/` imports from `data/`, which imports from `engine/`.

**Mitigation:**
- Use dependency injection: pass `DuckDBManager` to `LLMQueryEngineV2` constructor
- Keep imports acyclic: data ← engine ← agent
- Add circular import test in Phase 1

**Detection:** Python import errors at startup

---

## Phase-Specific Guardrails

| Phase | Topic | Likely Pitfall | Mitigation |
|-------|-------|----------------|------------|
| 1 | Directory move | Path resolution breaks (parents[3] vs parents[4]) | Test DuckDBManager after move |
| 1 | Shim re-exports | Import confusion, stale shims | Remove shims after migration |
| 2 | Planner swap | Plans diverge | Dual-run validation before deletion |
| 2 | Detector removal | New tool missing edge case | Add to Phase 5 robustness testing |
| 3 | Conversation state | Context injection changes behavior | Test without context first |
| 4 | League context | League context string too long | Max 500 chars, hardcode for Phase 4 |
| 5 | Robustness | Aliases conflict with existing behavior | Careful alias review before merge |
| 6 | Verbalization | Text changes confuse users | Version-control prompts, compare samples |

---

## Integration Point Summary

**Entry Point (Immutable):**
```python
BasicStatsAgent.ask(question: str) -> {"content": str, "debug": dict}
```

**Phase 2 Signature Update:**
```python
def ask(self, question: str, conversation_context: str = "") -> dict:
    # conversation_context is optional, default "" means no context
```

**Phase 4 Signature Update:**
```python
def ask(self, question: str, conversation_context: str = "", league_context: str | None = None) -> dict:
```

**Eval Runner Must Update:**
```python
# Phase 1
from src.basic_stats.engine.llm_query_engine import LLMQueryEngineV2
engine = LLMQueryEngineV2()

# Phase 4
engine = LLMQueryEngineV2(league_context=LEAGUE_CONTEXT)
```

**Pages Must Update (once):**
```python
# Phase 1 (directory restructure)
from src.basic_stats.agent import BasicStatsAgent

# Phase 3 (conversation state)
from src.shared.types import ConversationState
st.session_state["_conversation_metadata"] = ConversationState()

# Phase 4 (league context)
state.league_context = LEAGUE_CONTEXT
```

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Directory restructure safety | HIGH | Analyzed import chains, Streamlit constraints |
| Function calling feasibility | HIGH | Current planner is regex+LLM; tools are natural replacement |
| Conversation state location | HIGH | Streamlit session_state is standard pattern |
| League context injection | HIGH | System prompt injection is proven pattern |
| Benchmark preservation approach | HIGH | Dual-run validation is sound |
| Path resolution after move | MEDIUM | Need to verify parents[] counting after actual move |
| Import shim stability | MEDIUM | Untested in this codebase, but standard practice |

---

## Open Questions for Phase-Specific Research

1. **Phase 1:** How many eval runners import from `utils/basic_stats/`? (Found eval_runner_v6.py and eval_runner_v5.py; need to audit all)
2. **Phase 2:** What detector functions are tested explicitly? (Found test_query_planner.py; need to map detector coverage)
3. **Phase 3:** Should ConversationState persist across page refreshes? (Probably no, but clarify intent)
4. **Phase 4:** Is league context per-league or per-session? (Assuming per-session for Phase 4; can expand later)
5. **Phase 5:** What alias gaps were found during Phase 2 noise reduction? (Document existing aliases in alias file)
6. **Phase 6:** Which verbalization patterns are most robotic? (Sample 10 benchmark results, identify patterns)

---

## Files Written

This research document serves as the integration blueprint for the roadmap. 

**Next step:** Roadmapper creates 6 phases using this integration guide, ensuring each phase:
- Preserves 61/61 benchmark gate
- Updates only listed integration points
- Follows the migration risks mitigation plan
- Validates with the phase-specific guardrails
