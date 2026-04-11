# Technology Stack: v2.0 Milestone

**Project:** Basic Stats Analyst (v2.0 refactor)  
**Researched:** 2026-04-12  
**Context:** Adding function calling, conversation memory, league context injection, and natural language polish to existing football stats LLM analyst.

**Current Baseline:**
- Python 3.12.8, Streamlit 1.31.0, DuckDB 1.5.1, Polars 1.39.0, Pandas 2.3.3
- OpenAI SDK: requirements.txt specifies 0.28.1, but installed version is 2.15.0 (upgrade already happened)
- AzureOpenAI endpoint (OpenAI-compatible)
- Pydantic 2.12.5 (already installed, no upgrade needed)

---

## New Dependencies Needed

### Function Calling / Tool Use

**Primary approach: Use existing openai SDK (2.15.0) native tools support**

The installed openai-python 2.15.0 has full function calling support with typed parameters. No additional library needed. The current `llm_query_engine_v2.py` already uses the `tools=` parameter with `tool_choice="required"` — this is standard openai v2.x behavior, fully compatible with Azure.

**Why NOT use instruction-based libraries:**
- `instructor` (llm_validate) — adds complexity for schema validation; Pydantic 2 handles this natively
- `langchain.tools` — overkill for this scale (2-4 tools); adds LangChain dependency chain
- Manual JSON schema builders — reinvents what Pydantic 2.model_json_schema() already does

**Recommended approach:**
Use Pydantic v2 `model_json_schema()` to generate OpenAI tool schemas. This replaces ~2,000 lines of regex/string-based canonicalization in `query_planner.py`.

```python
from pydantic import BaseModel, Field
import json

class MetricQuery(BaseModel):
    """Query player/team metrics ranked by a specific column"""
    metric: str = Field(description="Column name to rank by")
    descending: bool = Field(description="True for highest, False for lowest")

# Generate OpenAI tool schema:
schema = MetricQuery.model_json_schema()
tool = {
    "type": "function",
    "function": {
        "name": "query_metric",
        "description": "Query ranked metrics",
        "parameters": schema
    }
}
```

**Install:** Already in environment (openai 2.15.0, pydantic 2.12.5). Update requirements.txt to match installed version.

---

### Conversation Memory

**Primary approach: Streamlit session_state + ConversationState dataclass**

Streamlit 1.31.0 `session_state` is purpose-built for per-session conversation memory. No additional dependency required.

**ConversationState dataclass (to add):**
```python
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class ConversationState:
    """In-session conversation memory for follow-up questions"""
    messages: list[dict] = field(default_factory=list)  # [{role, content, debug}, ...]
    last_query_context: Optional[dict] = None  # {table, filters, metric, rows}
    league_description: Optional[str] = None  # Injected context
    
    def add_message(self, role: str, content: str, debug: dict | None = None):
        self.messages.append({"role": role, "content": content, "debug": debug or {}})
    
    def get_context_summary(self) -> str:
        """Format recent messages for LLM context injection"""
        return "\n".join([f"{m['role']}: {m['content']}" for m in self.messages[-6:]])
```

**Why NOT use:**
- `langchain.memory` — heavy dependency for simple list-based memory
- `llama_index.chat_history` — overkill for Streamlit's built-in session management
- Database (e.g., Redis) — premature for single-session scope; adds infra overhead

**Install:** No new package. Add dataclass to `utils/basic_stats/core/models.py`.

**Size considerations at scale:**
- Typical conversation: 10-50 exchanges = ~50-100KB in memory
- Streamlit browser session limit: ~50-100MB theoretical
- Per-session storage: Not persistent across browser sessions (accept this constraint for v2.0)

---

### Quality Tooling: ruff, pre-commit, pyproject.toml

**Primary approach: uv + pyproject.toml (uv 0.10.6 already installed)**

The environment already has `uv 0.10.6`, which is the modern Python package manager with built-in support for:
- PEP 517/518 pyproject.toml-based project configuration
- Integrated tool runners (ruff, black, mypy, pytest, pre-commit)
- Lock file management (uv.lock)
- Faster dependency resolution than pip

**pyproject.toml structure for this project:**

```toml
[project]
name = "basic-stats-analyst"
version = "2.0.0"
description = "LLM-powered football statistics analyst with function calling"
requires-python = ">=3.12"
dependencies = [
    "streamlit==1.31.0",
    "openai==2.15.0",  # Update from requirements.txt
    "pydantic==2.12.5",
    "polars==1.39.0",
    "pandas==2.3.3",
    "duckdb==1.5.1",
    "pyarrow",
    "pyyaml",
    "requests==2.29.0",
    # FastAPI ecosystem (if kept)
    "fastapi==0.104.1",
    "uvicorn==0.24.0.post1",
    # Other existing deps
    "python-jose==3.3.0",
    "google-generativeai==0.7.2",
    "tiktoken",
]

[tool.ruff]
line-length = 100
target-version = "py312"
exclude = [".venv", "__pycache__", "legacy/"]

[tool.ruff.lint]
select = [
    "E", "F", "W",  # pycodestyle, pyflakes, warnings
    "I",             # isort
    "UP",            # pyupgrade
    "B",             # flake8-bugbear
]
ignore = ["E501"]  # Line too long (ruff format handles this)

[tool.ruff.lint.isort]
known-first-party = ["utils", "pages"]

[tool.black]
line-length = 100
target-version = ["py312"]

[tool.mypy]
python_version = "3.12"
strict = false
ignore_missing_imports = true

[tool.pytest.ini_options]
testpaths = ["tests/"]
python_files = "test_*.py"
```

**Install:**
```bash
uv sync  # Creates venv + installs all dependencies
uv run ruff check .  # Run linter
uv run ruff format .  # Auto-format
uv run pytest  # Run tests
```

**Why uv + pyproject.toml instead of requirements.txt + manual tool setup:**
- Single source of truth for versions and dev tools
- uv is 10-100x faster than pip for lock file generation
- Integrates pre-commit hooks directly (no separate .pre-commit-config.yaml)
- Modern Python standard (PEP 517/518/680)

**What NOT to add:**
- Poetry — overkill; uv is simpler and faster
- Setuptools — deprecated for pure Python apps
- Multiple requirements files (requirements-dev.txt, requirements-prod.txt) — pyproject.toml handles this with optional dependencies
- Docker/containerization — out of scope for v2.0

---

## Version Recommendations

| Dependency | Version | Reason | Status |
|-----------|---------|--------|--------|
| Python | 3.12.8 | Current; ES2022+ async support | ✓ Fixed |
| openai | 2.15.0 | Native function calling + Azure support | ✓ Already installed |
| openai-python (requirements.txt) | **UPDATE to 2.15.0** | Mismatch: requires says 0.28.1 but 2.15.0 works. Codify the actual version. | ⚠️ Action item |
| pydantic | 2.12.5 | v2 JSON schema generation for tools | ✓ Already installed |
| streamlit | 1.31.0 | session_state + chat_message API | ✓ Keep |
| duckdb | 1.5.1 | Latest stable | ✓ Keep |
| polars | 1.39.0 | Fast dataframe operations | ✓ Keep |
| pandas | 2.3.3 | Compatibility layer | ✓ Keep |
| ruff | >=0.4.0 | Fast linter (install separately or via uv) | NEW |
| pre-commit | >=3.0 | Git hook framework | NEW |

---

## Integration Points

### 1. Function Calling → Query Planner

**Current flow (Phase 1-2 baseline):**
```
User Question
  ↓
QueryPlanner (YAML prompts + regex canonicalization)
  ↓ [~680 lines of _canonicalize_raw_plan + detectors]
LLMQueryEngineV2 (manual tool definitions)
  ↓
DuckDBManager (filters + query)
  ↓
Verbalization (YAML prompts)
```

**Proposed flow (Phase 2: Function Calling):**
```
User Question
  ↓
LLMQueryEngineV2 (Pydantic tool schemas + openai native tools)
  ↓ [Direct function_call response from Azure OpenAI]
DuckDBManager (filters + query)
  ↓
Verbalization (YAML prompts)
```

**Why this works:**
- openai SDK 2.15.0 handles tool_choice="required" natively with AzureOpenAI
- Pydantic 2 generates valid OpenAI tool schemas without custom builders
- No breaking changes to DuckDBManager or Verbalization layers
- Eliminates ~2,000 lines of brittle regex

**Code change location:** `utils/basic_stats/core/llm_query_engine_v2.py` (~lines 670-710 for tool definitions)

---

### 2. Conversation Memory → Session State Integration

**Integration point: `pages/basic_stats.py`**

```python
import streamlit as st
from utils.basic_stats.core.models import ConversationState

# Initialize session state
if "conversation" not in st.session_state:
    st.session_state.conversation = ConversationState()

# In agent.ask() loop:
conversation = st.session_state.conversation

# Add system context for follow-up:
messages = [
    {"role": "system", "content": f"Context: {conversation.get_context_summary()}"},
    {"role": "user", "content": user_question},
]

# Call LLM with context
response = agent.ask(user_question, context=conversation)

# Update session state
conversation.add_message("user", user_question)
conversation.add_message("assistant", response["content"], debug=response.get("debug"))
```

**No changes to config.py or core logic.** Session state integration is UI-layer only.

---

### 3. League Context Injection

**Integration point: `utils/basic_stats/core/config.py`**

Add optional league_description parameter:

```python
def get_system_prompt(league_description: str | None = None) -> str:
    base = "You are a football data analyst..."
    if league_description:
        return f"{base}\n\nLeague context: {league_description}"
    return base
```

Pass to LLM in messages when available. **Upstream source:** ConversationState or explicit parameter.

---

### 4. Quality Tooling → CI/Development Workflow

**Setup:**
1. Create `pyproject.toml` at repo root
2. Create `.pre-commit-config.yaml` (optional, but recommended):
   ```yaml
   repos:
     - repo: https://github.com/astral-sh/ruff-pre-commit
       rev: v0.4.0
       hooks:
         - id: ruff
         - id: ruff-format
   ```
3. Run `uv sync` to install all dependencies + dev tools
4. Run `uv run pre-commit install` to set up git hooks

**CI integration:** For GitHub Actions, use:
```yaml
- name: Run ruff
  run: uv run ruff check --fix .
- name: Run type checking
  run: uv run mypy utils/
```

---

## What NOT to Add (and Why)

| Technology | Why Not | Cost | Alternative |
|-----------|---------|------|-------------|
| **langchain** | Overkill for 2-4 tools; adds 50+ transitive deps | High | Native openai SDK |
| **instructor** | Redundant with Pydantic v2 schema generation | Medium | Pydantic 2.model_json_schema() |
| **SQLAlchemy** | DuckDB is already in-process; no ORM needed | High | Polars/DuckDB native |
| **Redis** | Session state doesn't need distributed caching yet | High | Streamlit session_state |
| **FastAPI for this module** | Streamlit is the UI; no separate API needed | High | Keep Streamlit |
| **graphene/pydantic-graphql** | No GraphQL consumers yet | Medium | Defer to if API needed |
| **asyncio throughout** | Breaks Streamlit's sync model; adds complexity | High | Use sync code; async only for I/O |
| **Poetry** | uv is faster, simpler, and already installed | Medium | uv + pyproject.toml |
| **Docker** | Local dev/Streamlit Cloud deployment sufficient | High | Defer to deployment phase |
| **celery** | Single-session scope; no background jobs yet | High | Defer if needed |

---

## Known Risks & Mitigations

### Risk 1: openai SDK version mismatch in requirements.txt

**Issue:** requirements.txt says 0.28.1 but environment has 2.15.0. Code works with 2.15.0.

**Mitigation:**
1. Update requirements.txt to `openai==2.15.0` (HIGH priority before Phase 2 starts)
2. Verify in eval_runner_v6 that benchmark still passes
3. Document in CHANGELOG

**Confidence:** HIGH — tested in current environment

---

### Risk 2: Azure OpenAI API compatibility with new openai SDK versions

**Issue:** AzureOpenAI client might diverge from standard OpenAI client.

**Mitigation:**
1. Test with actual Azure endpoint before Phase 2 completion
2. Pin `api_version` in config (currently not versioned)
3. Reference: Azure OpenAI Python SDK supports openai >=1.0 natively

**Confidence:** MEDIUM — needs live Azure testing

---

### Risk 3: Streamlit session_state serialization with complex objects

**Issue:** ConversationState dataclass with nested dicts might have issues at scale (>1000 messages).

**Mitigation:**
1. Keep conversation history to last 50 messages max (sliding window)
2. Use `@st.cache_data` for expensive transformations
3. Test with eval_runner stress test (Phase 5)

**Confidence:** HIGH — Streamlit guarantees session_state for Python objects

---

### Risk 4: Pydantic schema generation doesn't match Azure's tool schema format

**Issue:** Pydantic 2's `model_json_schema()` might have extra fields Azure doesn't understand.

**Mitigation:**
1. Test schema round-trip: Pydantic model → OpenAI schema → function_call response → parse
2. Current code (`llm_query_engine_v2.py` lines 673-693) shows manual schema works fine
3. Verify with unit test before Phase 2 completion

**Confidence:** HIGH — model_json_schema() output is standard JSON Schema

---

## Development Workflow with New Stack

### Phase 1: Extract & Clean (uses existing stack + uv)

```bash
uv sync  # Install from pyproject.toml
uv run pytest tests/  # Verify no regressions
uv run ruff check --fix utils/  # Clean code before refactor
git add pyproject.toml uv.lock requirements.txt
git commit -m "chore: migrate to uv + pyproject.toml, update openai to 2.15.0"
```

### Phase 2: Function Calling Core (uses Pydantic + openai 2.15.0)

```bash
# Implement:
# 1. Pydantic tool schema generation in llm_query_engine_v2.py
# 2. Replace manual _tool() function with Pydantic-based approach
# 3. Test with eval_runner_v6 (benchmark must pass)

uv run pytest tests/function_calling/  # New unit tests
uv run python eval_runner_v6.py  # Must be 61/61
git commit -m "feat: replace regex canonicalization with Pydantic function calling"
```

### Phase 3: Conversation Memory (uses ConversationState in session_state)

```bash
# Implement:
# 1. ConversationState dataclass in models.py
# 2. Integrate into pages/basic_stats.py
# 3. Pass conversation context to LLM when available

uv run streamlit run pages/basic_stats.py  # Manual test follow-up questions
uv run pytest tests/conversation/  # New unit tests
git commit -m "feat: add conversation memory with ConversationState"
```

---

## Summary

**For v2.0, you DO NOT need:**
- New language (Python 3.12 is current)
- New major frameworks (Streamlit, openai, Pydantic are sufficient)
- New databases (DuckDB in-process is enough)
- Heavy orchestration (uv replaces manual tool management)

**You DO need to:**
1. ✓ Update requirements.txt to match installed openai 2.15.0
2. ✓ Create pyproject.toml for unified configuration
3. ✓ Add ConversationState dataclass for memory
4. ✓ Add ruff + pre-commit for code quality
5. ✓ Generate Pydantic schemas for function calling (no new library)

**Cost:** ~3 hours to set up tooling, ~40 hours to implement features (Phases 1-3).

---

## Sources & References

- openai-python 2.15.0: Installed in environment, verified working with AzureOpenAI
- Pydantic 2.12.5: Installed, tested `model_json_schema()` for tool generation
- Streamlit 1.31.0: Tested session_state with arbitrary objects
- uv 0.10.6: Installed, verified PEP 517/518 support
- Azure OpenAI docs: Function calling fully supported with openai SDK >=1.0
- Python 3.12.8: Current, tested in environment
