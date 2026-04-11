# Phase Implementation Checklist

Reference for developers executing each phase of the v2.0 refactor.

---

## Phase 1: Extract & Clean

### Pre-Phase Verification
- [ ] Current benchmark: 61/61 (run `python eval_runner_v6.py`)
- [ ] All imports resolve: `python -c "from utils.basic_stats.core.agent import BasicStatsAgent"`
- [ ] Streamlit runs: `streamlit run app.py`

### Step 1.1: Create New Directory Structure

```bash
mkdir -p src/basic_stats/{engine,data,prompts,tests}
mkdir -p src/shared
mkdir -p tests/{integration,fixtures}
mkdir -p evals
```

### Step 1.2: Copy Files (No Logic Changes)

**Core engine files:**
```bash
cp utils/basic_stats/core/agent.py src/basic_stats/agent.py
cp utils/basic_stats/core/llm_query_engine_v2.py src/basic_stats/engine/llm_query_engine_v2.py
cp utils/basic_stats/core/query_planner.py src/basic_stats/engine/planner.py
cp utils/basic_stats/core/models.py src/basic_stats/engine/models.py
cp utils/basic_stats/core/duckdb_manager.py src/basic_stats/data/duckdb.py
cp utils/basic_stats/core/knowledge_base.py src/basic_stats/knowledge_base.py
cp utils/basic_stats/core/config.py src/basic_stats/config.py
```

**Prompts:**
```bash
cp -r utils/basic_stats/prompts/* src/basic_stats/prompts/
```

**Test files:**
```bash
cp utils/basic_stats/core/test_*.py src/basic_stats/tests/
```

### Step 1.3: Create __init__.py Files

```python
# src/__init__.py
# Empty

# src/basic_stats/__init__.py
from .agent import BasicStatsAgent

__all__ = ["BasicStatsAgent"]

# src/basic_stats/engine/__init__.py
from .llm_query_engine_v2 import LLMQueryEngineV2
from .planner import QueryPlanner
from .models import MetricResolution, QueryResult

__all__ = ["LLMQueryEngineV2", "QueryPlanner", "MetricResolution", "QueryResult"]

# src/basic_stats/data/__init__.py
from .duckdb import DuckDBManager

__all__ = ["DuckDBManager"]

# src/shared/__init__.py
# Empty (add types.py later in Phase 3)
```

### Step 1.4: Update Internal Imports in Copied Files

**In src/basic_stats/agent.py:**
```python
# OLD
from utils.basic_stats.core.knowledge_base import KnowledgeBase
from utils.basic_stats.core.llm_query_engine_v2 import LLMQueryEngineV2

# NEW
from .knowledge_base import KnowledgeBase
from .engine.llm_query_engine_v2 import LLMQueryEngineV2
```

**In src/basic_stats/engine/llm_query_engine_v2.py:**
```python
# OLD
from utils.basic_stats.core.config import (...)
from utils.basic_stats.core.duckdb_manager import DuckDBManager
from utils.basic_stats.core.models import MetricResolution, QueryResult
from utils.basic_stats.core.query_planner import QueryPlanner

# NEW
from ..config import (...)
from ..data.duckdb import DuckDBManager
from .models import MetricResolution, QueryResult
from .planner import QueryPlanner
```

**In src/basic_stats/engine/planner.py:**
```python
# OLD
from utils.basic_stats.core.config import (...)

# NEW
from ..config import (...)
```

**In src/basic_stats/data/duckdb.py:**
- Check path resolution: `BASE = Path(__file__).resolve().parents[3]`
- Should still resolve to repo root (count: duckdb.py → data/ → basic_stats/ → src/ → REPO)
- Test: `python -c "from src.basic_stats.data.duckdb import DuckDBManager; DuckDBManager()"`

### Step 1.5: Create Shim Re-exports in Old Location

```python
# utils/basic_stats/core/agent.py (SHIM)
"""
TEMPORARY SHIM: Phase 1 only.
Re-exports BasicStatsAgent from new location.
Delete this file after pages/basic_stats.py imports updated.
"""
from src.basic_stats.agent import BasicStatsAgent

__all__ = ["BasicStatsAgent"]
```

```python
# utils/basic_stats/core/llm_query_engine_v2.py (SHIM)
"""
TEMPORARY SHIM: Phase 1 only.
Re-exports LLMQueryEngineV2 from new location.
Delete this file after eval_runner_v6.py imports updated.
"""
from src.basic_stats.engine.llm_query_engine_v2 import LLMQueryEngineV2

__all__ = ["LLMQueryEngineV2"]
```

```python
# utils/basic_stats/core/query_planner.py (SHIM)
from src.basic_stats.engine.planner import QueryPlanner

__all__ = ["QueryPlanner"]
```

```python
# utils/basic_stats/core/models.py (SHIM)
from src.basic_stats.engine.models import MetricResolution, QueryResult

__all__ = ["MetricResolution", "QueryResult"]
```

```python
# utils/basic_stats/core/duckdb_manager.py (SHIM)
from src.basic_stats.data.duckdb import DuckDBManager

__all__ = ["DuckDBManager"]
```

```python
# utils/basic_stats/core/__init__.py (SHIM)
"""
TEMPORARY SHIM: Phase 1 only.
All imports routed to src/basic_stats/.
"""
from .agent import BasicStatsAgent
from .llm_query_engine_v2 import LLMQueryEngineV2
from .query_planner import QueryPlanner
from .models import MetricResolution, QueryResult
from .duckdb_manager import DuckDBManager

__all__ = [
    "BasicStatsAgent",
    "LLMQueryEngineV2",
    "QueryPlanner",
    "MetricResolution",
    "QueryResult",
    "DuckDBManager",
]
```

### Step 1.6: Verify Shims Work

```bash
python -c "from utils.basic_stats.core.agent import BasicStatsAgent; print('✓ agent')"
python -c "from utils.basic_stats.core.llm_query_engine_v2 import LLMQueryEngineV2; print('✓ engine')"
python -c "from utils.basic_stats.core.query_planner import QueryPlanner; print('✓ planner')"
python -c "from utils.basic_stats.core.models import MetricResolution, QueryResult; print('✓ models')"
python -c "from utils.basic_stats.core.duckdb_manager import DuckDBManager; print('✓ duckdb')"
```

### Step 1.7: Run Benchmark (Shim + Old Imports)

```bash
python eval_runner_v6.py
```

Expected: **61/61 pass**

If fails: Debug imports, check path resolution in duckdb.py.

### Step 1.8: Update pages/basic_stats.py Imports

**Commit message:** "refactor: update basic_stats.py to import from src/basic_stats"

```python
# OLD
from utils.basic_stats.core.agent import BasicStatsAgent

# NEW
from src.basic_stats.agent import BasicStatsAgent
```

Test:
```bash
streamlit run app.py  # navigate to Basic Stats page
```

### Step 1.9: Update eval_runner_v6.py Imports

**Commit message:** "refactor: update eval_runner_v6.py to import from src/"

```python
# OLD
from utils.basic_stats.core.llm_query_engine_v2 import LLMQueryEngineV2

# NEW
from src.basic_stats.engine.llm_query_engine_v2 import LLMQueryEngineV2
```

Test:
```bash
python eval_runner_v6.py
```

Expected: **61/61 pass**

### Step 1.10: Run Benchmark (New Imports, No Shims)

```bash
python eval_runner_v6.py
```

Expected: **61/61 pass**

### Step 1.11: Verify Streamlit Rerun

1. Open Streamlit app: `streamlit run app.py`
2. Navigate to Basic Stats page
3. Ask a question
4. Verify answer appears
5. Ask another question (triggers rerun)
6. Verify second answer appears (rerun doesn't break imports)

### Step 1.12: Delete Shim Layer

```bash
# Remove shim files
rm utils/basic_stats/core/agent.py
rm utils/basic_stats/core/llm_query_engine_v2.py
rm utils/basic_stats/core/query_planner.py
rm utils/basic_stats/core/models.py
rm utils/basic_stats/core/duckdb_manager.py
rm utils/basic_stats/core/__init__.py

# Keep legacy/ and prompts/ (if not moved yet)
```

### Step 1.13: Final Benchmark Verification

```bash
python eval_runner_v6.py
```

Expected: **61/61 pass**

### Phase 1 Commits

1. "refactor: create src/ structure and copy core files" (Phase 1.1–1.6)
2. "refactor: update basic_stats.py imports" (Phase 1.8)
3. "refactor: update eval_runner_v6.py imports" (Phase 1.9)
4. "refactor: remove shim layer" (Phase 1.12)

---

## Phase 2: Function Calling Core

### Pre-Phase Verification
- [ ] Phase 1 complete, 61/61 pass
- [ ] All imports from src/ work

### Step 2.1: Create Function Calling Tool

**File: src/basic_stats/engine/tools.py**

```python
from typing import Annotated, Any
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
    """Transform natural-language question into structured query plan."""
    from ..config import get_llm_client, get_model
    from pathlib import Path
    import yaml
    
    client = get_llm_client()
    
    # Load system prompt from YAML or build inline
    system = f"""You are a football data query planner.

Your job is to transform a user's natural-language question into a JSON query plan.

You must:
1. Infer the correct table scope.
2. Infer the metric.
3. Infer any filters explicitly or strongly implied by the question.
4. Infer the ranking mode.

Only use the allowed values provided below.
Never invent metrics, scopes, or filters.

"""
    if league_context:
        system += f"\nLEAGUE CONTEXT:\n{league_context}\n"
    
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
    
    # Extract tool use
    for block in response.content:
        if block.type == "tool_use":
            return QueryPlan(**block.input)
    
    raise ValueError("No tool use in response")
```

### Step 2.2: Create Planner Wrapper

**File: src/basic_stats/engine/planner.py** (rename from old query_planner.py)

```python
from .tools import QueryPlan, resolve_query_intent

class Planner:
    """Thin wrapper around resolve_query_intent for compatibility."""
    
    def __init__(self, league_context: str | None = None):
        self.league_context = league_context
    
    def plan(self, question: str, context: str = "") -> QueryPlan:
        """Main entry point. Returns QueryPlan."""
        return resolve_query_intent(
            question,
            league_context=self.league_context,
        )
```

### Step 2.3: Create Parallel Validation Test

**File: src/basic_stats/tests/test_phase2_parallel_execution.py**

```python
import json
from pathlib import Path
from src.basic_stats.engine.planner import Planner as NewPlanner
# Also import old planner temporarily for comparison
import sys
sys.path.insert(0, "utils/basic_stats/core")
from query_planner import QueryPlanner as OldPlanner

BENCHMARK_PATH = "questions_benchmark_v6.json"

def test_parallel_execution():
    """Run both planners on all benchmark questions, compare output."""
    with open(BENCHMARK_PATH) as f:
        benchmark = json.load(f)
    
    old_planner = OldPlanner()
    new_planner = NewPlanner()
    
    divergences = []
    
    for q in benchmark["questions"]:
        question = q["question"]
        
        try:
            old_plan = old_planner.plan(question)
            new_plan = new_planner.plan(question)
            
            # Compare key fields
            if (old_plan.get("table") != new_plan.table_scope or
                old_plan.get("metric") != new_plan.metric or
                old_plan.get("descending") != new_plan.descending or
                old_plan.get("filters") != new_plan.filters):
                
                divergences.append({
                    "question": question,
                    "old": old_plan,
                    "new": new_plan.model_dump(),
                })
        except Exception as e:
            divergences.append({
                "question": question,
                "error": str(e),
            })
    
    if divergences:
        print(f"\n{len(divergences)} divergences found:")
        for div in divergences:
            print(f"\nQ: {div['question']}")
            print(f"  Error: {div.get('error', 'Plan mismatch')}")
            if "old" in div:
                print(f"  Old: {div['old']}")
                print(f"  New: {div['new']}")
        return False
    
    print("✓ All 61 questions produce identical plans")
    return True
```

Run:
```bash
python -m pytest src/basic_stats/tests/test_phase2_parallel_execution.py -v
```

Expected: All tests pass (0 divergences)

### Step 2.4: Update LLMQueryEngineV2

**File: src/basic_stats/engine/llm_query_engine_v2.py**

```python
# Update imports
from .tools import QueryPlan, resolve_query_intent
from .planner import Planner

# Update __init__
def __init__(self, league_context: str | None = None):
    self.planner = Planner(league_context)
    self.db = DuckDBManager()

# Update ask()
def ask(self, question: str) -> dict:
    plan = self.planner.plan(question)  # Returns QueryPlan
    result = self._execute_plan(plan)
    content = self._verbalize(result)
    return {"content": content, "debug": {...}}

# Update _execute_plan to accept QueryPlan instead of dict
def _execute_plan(self, plan: QueryPlan) -> QueryResult:
    # Convert QueryPlan to execution logic
    table = plan.table_scope
    metric = plan.metric
    # ... rest of logic
```

### Step 2.5: Delete Old Detector Functions

In src/basic_stats/engine/llm_query_engine_v2.py, delete:

- `_detect_home_away_comparison()`
- `_detect_metric_derived_bucket()`
- `_detect_dual_bucket_comparison()`
- `_bucket_label()`
- All regex position maps
- `_canonicalize_raw_plan()` (in planner.py, kept only for reference)

### Step 2.6: Run Full Benchmark

```bash
python eval_runner_v6.py
```

Expected: **61/61 pass**

### Step 2.7: Update Test Files

Update src/basic_stats/tests/test_query_planner.py to import from new location:

```python
# OLD
from utils.basic_stats.core.query_planner import QueryPlanner

# NEW
from src.basic_stats.engine.planner import Planner as QueryPlanner
```

### Phase 2 Commits

1. "feat: add function calling tools and QueryPlan model" (Step 2.1)
2. "feat: create Planner wrapper with resolve_query_intent" (Step 2.2)
3. "test: add parallel execution validation for planners" (Step 2.3)
4. "refactor: update LLMQueryEngineV2 to use new Planner" (Step 2.4–2.5)
5. "refactor: remove old detector functions" (Step 2.5)

---

## Phase 3: Conversation Memory

### Pre-Phase Verification
- [ ] Phase 2 complete, 61/61 pass
- [ ] All tests in Phase 2 passing

### Step 3.1: Create ConversationState

**File: src/shared/types.py**

```python
from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class ConversationTurn:
    user_question: str
    assistant_response: str
    plan_debug: dict
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class ConversationState:
    turns: list[ConversationTurn] = field(default_factory=list)
    league_context: str | None = None
    current_entity: str | None = None
    
    def add_turn(self, question: str, response: str, debug: dict):
        self.turns.append(ConversationTurn(
            user_question=question,
            assistant_response=response,
            plan_debug=debug,
        ))
    
    def get_conversation_context(self) -> str:
        if not self.turns:
            return ""
        context = "Recent conversation:\n"
        for turn in self.turns[-3:]:
            context += f"Q: {turn.user_question}\nA: {turn.assistant_response}\n"
        return context
```

### Step 3.2: Update BasicStatsAgent

**File: src/basic_stats/agent.py**

```python
def ask(self, question: str, conversation_context: str = "") -> dict:
    answer = self.kb.find_answer(question)
    if answer:
        return {
            "type": "text",
            "content": answer,
            "debug": {...},
        }
    
    return self.engine.ask(question, conversation_context=conversation_context)
```

### Step 3.3: Update LLMQueryEngineV2

**File: src/basic_stats/engine/llm_query_engine_v2.py**

```python
def ask(self, question: str, conversation_context: str = "") -> dict:
    plan = self.planner.plan(question, context=conversation_context)
    result = self._execute_plan(plan)
    content = self._verbalize(result)
    return {"content": content, "debug": {...}}
```

### Step 3.4: Update Planner

**File: src/basic_stats/engine/planner.py**

```python
def plan(self, question: str, context: str = "") -> QueryPlan:
    return resolve_query_intent(
        question,
        league_context=self.league_context,
        conversation_context=context,
    )
```

### Step 3.5: Update resolve_query_intent Tool

**File: src/basic_stats/engine/tools.py**

```python
def resolve_query_intent(
    question: Annotated[str, "User's natural-language question"],
    league_context: Annotated[str | None, "Optional league description"] = None,
    conversation_context: Annotated[str, "Recent conversation context"] = "",
) -> QueryPlan:
    """Transform natural-language question into structured query plan."""
    
    system = "..."  # existing system prompt
    
    if league_context:
        system += f"\n\nLEAGUE CONTEXT:\n{league_context}\n"
    
    if conversation_context:
        system += f"\n\nRECENT CONVERSATION:\n{conversation_context}\n"
    
    # ... rest of function calling logic
```

### Step 3.6: Update pages/basic_stats.py

**File: pages/basic_stats.py**

```python
from src.shared.types import ConversationState

CONVERSATION_STATE_KEY = "_conversation_metadata"
CHAT_KEY = "basic_stats_messages"

if CONVERSATION_STATE_KEY not in st.session_state:
    st.session_state[CONVERSATION_STATE_KEY] = ConversationState()

if CHAT_KEY not in st.session_state:
    st.session_state[CHAT_KEY] = []

# ... render existing messages ...

question = st.chat_input("Ask a question")

if question:
    conv_state = st.session_state[CONVERSATION_STATE_KEY]
    context = conv_state.get_conversation_context()
    
    st.session_state[CHAT_KEY].append({
        "role": "user",
        "content": question,
    })
    
    try:
        with st.spinner("Analysing..."):
            result = agent.ask(question, conversation_context=context)
        
        st.session_state[CHAT_KEY].append({
            "role": "assistant",
            "content": result["content"],
            "debug": result.get("debug", {}),
        })
        
        conv_state.add_turn(question, result["content"], result["debug"])
        
        st.rerun()
    
    except Exception as e:
        # ... error handling ...

# Update Clear button
with col3:
    if st.button("Clear chat"):
        st.session_state[CHAT_KEY] = []
        st.session_state[CONVERSATION_STATE_KEY] = ConversationState()
        st.rerun()
```

### Step 3.7: Run Benchmark

```bash
python eval_runner_v6.py
```

Expected: **61/61 pass** (context injection is optional, doesn't affect single questions)

### Step 3.8: Test Follow-up Questions (Manual)

1. Open Streamlit app: `streamlit run app.py`
2. Ask: "Who scored the most goals?"
3. Check answer mentions a player
4. Ask: "Against top 6?"
5. System should understand "top 6" in context of the player mentioned

### Phase 3 Commits

1. "feat: add ConversationState dataclass" (Step 3.1)
2. "feat: add conversation_context parameter to agent.ask()" (Step 3.2)
3. "refactor: thread conversation_context through engine→planner" (Step 3.3–3.5)
4. "feat: update basic_stats.py UI for conversation memory" (Step 3.6)

---

## Phase 4: League Context Injection

### Pre-Phase Verification
- [ ] Phase 3 complete, 61/61 pass
- [ ] Follow-up questions work in Streamlit

### Step 4.1: Add league_context to ConversationState

**File: src/shared/types.py** (already done, but verify)

```python
@dataclass
class ConversationState:
    turns: list[ConversationTurn] = field(default_factory=list)
    league_context: str | None = None
    current_entity: str | None = None
```

### Step 4.2: Update pages/basic_stats.py

**File: pages/basic_stats.py**

```python
LEAGUE_CONTEXT = """
Premier League (England) has 20 teams competing over 38 matchdays.
The Big Six: Manchester City, Liverpool, Arsenal, Manchester United, Tottenham, Chelsea.
Top 4 teams qualify for European competitions.
Mid-table (7–14): competitive but not in title race.
Bottom 4 (17–20): relegation-threatened.
"""

# In initialization
if CONVERSATION_STATE_KEY not in st.session_state:
    state = ConversationState(league_context=LEAGUE_CONTEXT)
    st.session_state[CONVERSATION_STATE_KEY] = state

# In question handling
if question:
    conv_state = st.session_state[CONVERSATION_STATE_KEY]
    context = conv_state.get_conversation_context()
    
    result = agent.ask(
        question,
        conversation_context=context,
        league_context=conv_state.league_context,  # NEW
    )
```

### Step 4.3: Update BasicStatsAgent

**File: src/basic_stats/agent.py**

```python
def ask(
    self,
    question: str,
    conversation_context: str = "",
    league_context: str | None = None,  # NEW
) -> dict:
    answer = self.kb.find_answer(question)
    if answer:
        return {...}
    
    return self.engine.ask(
        question,
        conversation_context=conversation_context,
        league_context=league_context,  # NEW
    )
```

### Step 4.4: Update LLMQueryEngineV2

**File: src/basic_stats/engine/llm_query_engine_v2.py**

```python
def __init__(self, league_context: str | None = None):
    self.planner = Planner(league_context)
    self.db = DuckDBManager()

def ask(
    self,
    question: str,
    conversation_context: str = "",
    league_context: str | None = None,  # NEW
) -> dict:
    effective_league_context = league_context or self.league_context
    plan = self.planner.plan(
        question,
        context=conversation_context,
        league_context=effective_league_context,
    )
    result = self._execute_plan(plan)
    content = self._verbalize(result)
    return {"content": content, "debug": {...}}
```

### Step 4.5: Verify resolve_query_intent Tool

**File: src/basic_stats/engine/tools.py** (should already support league_context from Phase 3)

Confirm function signature:
```python
def resolve_query_intent(
    question: str,
    league_context: str | None = None,
    conversation_context: str = "",
) -> QueryPlan:
```

### Step 4.6: Run Benchmark

```bash
python eval_runner_v6.py
```

Expected: **61/61 pass** (league_context is optional, doesn't affect existing questions)

### Step 4.7: Test Dynamic Team Classification (Manual)

1. Ask: "Which Big Six team has the most points?"
2. System should identify Big Six teams without hardcoded labels
3. Ask: "How many goals has a top-4 team scored?"
4. System should dynamically identify top 4 teams

### Phase 4 Commits

1. "feat: add league_context injection to agent and engine" (Step 4.2–4.4)
2. "test: verify league context enables dynamic team classification" (Step 4.7)

---

## Phase 5 & 6: Quick Reference

### Phase 5: Random Question Robustness
- [ ] Generate 50+ diverse test questions
- [ ] Test each via agent.ask()
- [ ] Fix aliases or prompts for failures
- [ ] Run 61/61 benchmark
- [ ] Document pass rate on new questions

### Phase 6: Natural Language Polish
- [ ] Review verbalize.yaml prompts
- [ ] Identify robotic phrasing patterns
- [ ] Refine for natural tone
- [ ] Test 20–30 sample questions
- [ ] Run 61/61 benchmark

---

## General Validation Commands

```bash
# Full benchmark
python eval_runner_v6.py

# Import check
python -c "from src.basic_stats.agent import BasicStatsAgent; print('✓')"

# Streamlit
streamlit run app.py

# Unit tests
python -m pytest src/basic_stats/tests/ -v

# Single benchmark question (add to eval_runner)
python eval_runner_v6.py --question "Who scored the most?"
```

---

## Rollback Procedure

If any phase shows < 61/61:

1. **Identify divergence:** Run eval_runner_v6.py with verbose output
2. **Isolate question:** Which specific question(s) failed?
3. **Compare plans:** If Phase 2+, run parallel_execution test
4. **Revert or fix:** Either revert phase commits or fix specific issue
5. **Re-validate:** Confirm 61/61 before moving forward

Example:
```bash
# Save current state
git stash

# Revert to last known good phase
git reset --hard <last-good-commit>

# Run benchmark
python eval_runner_v6.py  # Should show 61/61

# Re-apply changes with fix
git stash pop
# ... fix the issue ...
git add .
git commit -m "fix: ..."
```

---

## Critical Paths to Avoid

❌ **Don't:**
- Modify QueryPlanner logic during Phase 2 before dual-run validation
- Delete detector functions without confirming zero impact on benchmark
- Change Streamlit session_state structure without updating pages/basic_stats.py
- Run Phase N without Phase N-1 showing 61/61
- Update eval_runner imports before confirming new imports work

✓ **Do:**
- Run eval_runner_v6.py after every phase
- Keep shims in place for 2 weeks (Phase 1)
- Validate with parallel execution (Phase 2)
- Make all new parameters optional (Phase 3+)
- Test manual follow-up questions (Phase 3)
- Document pass rates on new test questions (Phase 5–6)

