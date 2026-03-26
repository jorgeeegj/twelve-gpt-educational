# Coding Conventions

**Analysis Date:** 2026-03-26

## Naming Patterns

**Files:**
- Snake case for module files: `query_planner.py`, `duckdb_manager.py`, `llm_query_engine_v2.py`
- Version numbering appended for major revisions: `eval_runner_v2.py`, `eval_runner_v5.py`
- Test files follow pattern: `test_query_planner.py`
- Classes in dedicated files with matching names: `Data` in `data_source.py`, `Chat` in `chat.py`

**Functions:**
- Snake case for all function names: `_normalize_text()`, `_extract_numeric_ordinal()`, `check_expected()`
- Private/internal functions prefixed with underscore: `_normalize_text()`, `_extract_top_rank_bucket()`
- Public methods without prefix: `get_processed_data()`, `handle_input()`, `add_message()`
- Helper functions for string operations typically use `_` prefix: `_targets_player_subject()`, `_normalize_metric_key()`

**Variables:**
- Snake case for all variables: `test_cases`, `expected_value`, `plan_dict`
- Constant values in UPPERCASE: `BENCHMARK_PATH`, `OUTPUT_DIR`, `BASE`, `DUCKDB_PATH`
- Dictionary keys generally snake_case: `table_scope`, `entity_type`, `ranking_mode`
- Configuration constants grouped at module top: `NEGATIVE_METRICS`, `PLAYER_COLS`, `TEAM_COLS`

**Types:**
- Type hints using modern Python syntax: `str | None`, `list[str]`, `dict[str, Any]`
- Pydantic BaseModel for data contracts: `MetricResolution`, `QueryResult`
- Class names in PascalCase: `QueryPlanner`, `DuckDBManager`, `LLMQueryEngineV2`, `Chat`

## Code Style

**Formatting:**
- No explicit linter detected (no .pylintrc, .flake8, pyproject.toml with linting config)
- Code follows PEP 8 general style conventions
- Imports organized but no strict enforcement visible
- Mixed indentation in some evaluation files (4 spaces standard)

**Linting:**
- No linter configuration file detected
- Code appears to follow conventions organically through developer practice

## Import Organization

**Order:**
1. Standard library imports (`import json`, `import sys`, `from pathlib import Path`)
2. Third-party imports (`import pandas as pd`, `import streamlit as st`, `import polars as pl`)
3. Local application imports (`from classes.data_source import CountryStats`, `from utils.basic_stats.core.config import get_model`)

**Path Aliases:**
- No path aliases detected in tsconfig or Python configuration
- Full relative paths used: `from utils.basic_stats.core.query_planner import QueryPlanner`
- Imports from custom modules use `.utils` prefix consistently

**Example from `eval_runner_v5.py`:**
```python
import argparse
import json
import re
import sys
from collections import defaultdict
from copy import deepcopy
from datetime import datetime
from pathlib import Path

sys.path.insert(0, ".")

from utils.basic_stats.core.llm_query_engine_v2 import (
    LLMQueryEngineV2,
    _question_subject_entity,
)
```

## Error Handling

**Patterns:**
- Specific exception types caught when available: `except ValidationError as e`
- Generic `except Exception as e` for fallback/logging cases
- Errors printed to console: `print("ValidationError:", e)`
- Validation errors from Pydantic handled with try/except block (see `query_planner.py` lines 1400-1406)

**ValueError for validation:**
- Domain validation raises `ValueError` with descriptive messages:
  ```python
  raise ValueError(f"Invalid table_scope: {plan.table_scope}")
  raise ValueError(f"Unsupported agg '{agg}' for summary scope")
  ```

**Graceful fallback pattern:**
- Try/except blocks used to attempt operations and fall back silently (line 706-708 in `llm_query_engine_v2.py`)
- Exception details logged to console when needed

## Logging

**Framework:** Console print statements (no logging module detected)

**Patterns:**
- Debug output via `print()` with formatted strings: `print(f"Text: {text}")`
- Expanders for debugging transcripts: `st.expander("Chat transcript", expanded=False).write(messages)`
- JSON output for structured data: `print(json.dumps(plan_dict, indent=2, ensure_ascii=False))`
- Status updates: `print(f"PLANNER SCORE: {passed}/{len(TEST_CASES)}")`

**No centralized logging** - each module manages its own diagnostic output.

## Comments

**When to Comment:**
- Docstrings for classes explaining purpose: `"""Get, process, and manage various forms of data."""`
- Inline comments for complex regex patterns and extraction logic
- Comments above constant definitions explaining domain concepts: `# Dataframe specs: ...`
- Section comments for major workflow steps

**JSDoc/TSDoc:**
- Not used in Python codebase
- Pydantic Field descriptions used instead for data models:
  ```python
  class MetricResolution(BaseModel):
      metric: str = Field(description="Exact column name to sort by")
      descending: bool = Field(description="True for most/highest/best...")
      table: str = Field(description="'players' or 'teams'")
  ```

**Docstring examples from codebase:**
```python
class Data:
    """
    Get, process, and manage various forms of data.
    """

def get_raw_data(self) -> pd.DataFrame:
    raise NotImplementedError("Child class must implement get_raw_data(self)")
```

## Function Design

**Size:** Small focused functions (typically 5-30 lines)
- Text extraction functions like `_extract_numeric_ordinal()` are 10 lines
- Processing pipelines broken into steps: `_normalize_text()`, `_extract_top_rank_bucket()`
- Main entry points can be larger (50+ lines in `resolve()` methods)

**Parameters:**
- Single responsibility pattern - functions accept specific inputs for single task
- Type hints provided for clarity: `def check_expected(plan_dict: dict, expected: dict) -> list[str]:`
- Keyword arguments for optional configuration in Streamlit/API calls

**Return Values:**
- Consistent return types documented via type hints
- Multiple values returned as tuple when needed: `tuple[bool, dict]`
- Dictionaries used for complex return structures with multiple fields
- Pydantic models for data contracts

**Example function pattern:**
```python
def check_expected(plan_dict: dict, expected: dict) -> list[str]:
    errors = []

    if "table_scope" in expected and plan_dict["table_scope"] != expected["table_scope"]:
        errors.append(f"table_scope -> expected {expected['table_scope']}, got {plan_dict['table_scope']}")

    return errors
```

## Module Design

**Exports:**
- Main classes and functions exported implicitly by being defined at module level
- Helper functions prefixed with underscore to indicate internal use
- No explicit `__all__` declarations observed

**Barrel Files:**
- No barrel files (index.py) pattern used
- Direct imports from specific modules: `from utils.basic_stats.core.query_planner import QueryPlanner`

**Module organization in `utils/basic_stats/core/`:**
- Separate concerns across modules: `query_planner.py`, `duckdb_manager.py`, `llm_query_engine_v2.py`, `models.py`, `config.py`
- Configuration centralized in `config.py` with paths and factory functions
- Data models isolated in `models.py` using Pydantic
- No monolithic files; clear separation by responsibility

---

*Convention analysis: 2026-03-26*
