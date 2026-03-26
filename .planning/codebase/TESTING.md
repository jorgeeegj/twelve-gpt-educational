# Testing Patterns

**Analysis Date:** 2026-03-26

## Test Framework

**Runner:**
- Manual Python test runners (no pytest/unittest framework detected)
- Test scripts execute via `if __name__ == "__main__": main()`
- No test configuration file (pytest.ini, setup.cfg, tox.ini) present

**Assertion Library:**
- Custom assertion logic implemented in test functions
- Pydantic ValidationError caught and inspected directly
- Dictionary comparison for expected vs actual results

**Run Commands:**
```bash
python utils/basic_stats/core/test_query_planner.py
python eval_runner_v5.py --bench  # Comprehensive evaluation
python eval_runner_v5.py --focus <ids>  # Focused test run
python -m pytest                  # Not used - no pytest setup
```

## Test File Organization

**Location:**
- Co-located pattern: `test_query_planner.py` in same directory as code (`utils/basic_stats/core/`)
- Eval scripts at root level: `eval_runner_v5.py`, `eval_runner_v4.py`
- No separate `tests/` directory structure

**Naming:**
- Test files: `test_*.py` pattern
- Test functions: `def main():` as entry point, not individual test functions
- Test cases: Lists of dictionaries with structure `{"id": "P01", "question": "...", "expected": {...}}`

**Structure:**
```
utils/basic_stats/core/
├── test_query_planner.py      # Test cases for QueryPlanner
└── (source files)

./ (root)
├── eval_runner_v5.py          # Comprehensive evaluation runner
├── eval_runner_v4.py          # Previous version
└── questions_benchmark_v5.json # Test data
```

## Test Structure

**Suite Organization:**
```python
# From test_query_planner.py
TEST_CASES = [
    {
        "id": "P01",
        "question": "Who has scored the most goals this season?",
        "expected": {
            "table_scope": "players_summary",
            "entity_type": "player",
            "metric": "total_goals",
            "aggregation": "sum",
            "ranking_mode": "top_n",
        },
    },
    # ... more cases
]

def check_expected(plan_dict: dict, expected: dict) -> list[str]:
    errors = []
    # ... validation logic
    return errors

def main():
    planner = QueryPlanner()
    passed = 0

    for case in TEST_CASES:
        print("=" * 100)
        print(case["id"])
        print(case["question"])

        try:
            plan = planner.resolve(case["question"])
            plan_dict = planner.to_debug_dict(plan)
            print(json.dumps(plan_dict, indent=2, ensure_ascii=False))

            errors = check_expected(plan_dict, case["expected"])
            ok = len(errors) == 0

            if ok:
                passed += 1
                print("PASS: True")
            else:
                print("PASS: False")
                for err in errors:
                    print(" -", err)

        except Exception as e:
            print("PASS: False")
            print("ERROR:", repr(e))

    print("\n" + "#" * 100)
    print(f"PLANNER SCORE: {passed}/{len(TEST_CASES)}")
```

**Patterns:**
- Setup: Create instance of class under test in main loop
- Execution: Call method and convert to debug dictionary for inspection
- Verification: Use helper function `check_expected()` to compare fields
- Assertion: Track passed/failed counts; no assertions, manual pass/fail logic
- Teardown: None (stateless test cases)

## Mocking

**Framework:** No mocking library detected (no unittest.mock, pytest-mock)

**Patterns:**
- Literal test data used directly in test definitions
- No mock objects or patches
- DuckDB in-memory database used for actual data (real dependencies)

**What to Mock:**
- LLM calls would ideally be mocked but currently test against real models
- External API calls (OpenAI, Gemini) not mocked in test suites

**What NOT to Mock:**
- DuckDB database queries - test with real data
- QueryPlanner logic - should execute end-to-end
- Data transformations - verify actual outputs

## Fixtures and Factories

**Test Data:**
```python
# From test_query_planner.py - inline test cases
TEST_CASES = [
    {
        "id": "P01",
        "question": "Who has scored the most goals this season?",
        "expected": {
            "table_scope": "players_summary",
            "entity_type": "player",
            "metric": "total_goals",
            ...
        },
    },
    # 11 more test cases defined as dictionaries
]
```

**Benchmark data:**
```python
# From eval_runner_v5.py
BENCHMARK_PATH = "questions_benchmark_v5.json"  # External JSON file with questions and expected answers

FOCUS_IDS_DEFAULT = [
    "QV4_16",  # under-23 top scorer (fixed)
    "QV4_37",  # most goals vs top-6 (still failing)
    # ... tracked by ID for focused debugging
]
```

**Location:**
- Test data embedded in test files as Python literals (lists of dicts)
- External benchmark data in JSON files: `questions_benchmark_v5.json`
- No factory pattern or builder classes for test fixtures

## Coverage

**Requirements:** Not enforced
- No coverage configuration detected
- No coverage badges or requirements in documentation

**View Coverage:**
- Not currently tracked
- Coverage command not configured

## Test Types

**Unit Tests:**
- Scope: Individual functions like `check_expected()`, extraction functions
- Approach: Direct function calls with test data
- Example: `test_query_planner.py` validates QueryPlanner output structure
- Coverage: Core query planning logic, field extraction, text normalization

**Integration Tests:**
- Scope: End-to-end question → plan → query → result flow
- Approach: Full pipeline execution via `LLMQueryEngineV2`
- Example: `eval_runner_v5.py` tests complete question answering
- Coverage: Question parsing, plan generation, DuckDB query execution, result validation

**E2E Tests:**
- Framework: `eval_runner_v5.py` functions as comprehensive E2E test
- Approach: Questions executed through full pipeline, results validated against expected answers
- Stages tracked: baseline, sprint_1, sprint_2, sprint_3, sprint_4, sprint_5
- Metrics: Pass/fail ratio, detailed error analysis per question

## Common Patterns

**Test execution pattern:**
```python
if __name__ == "__main__":
    main()
```

**Exception handling in tests:**
```python
try:
    plan = planner.resolve(case["question"])
    plan_dict = planner.to_debug_dict(plan)
    errors = check_expected(plan_dict, case["expected"])
    ok = len(errors) == 0
except Exception as e:
    print("PASS: False")
    print("ERROR:", repr(e))
```

**Async Testing:**
Not used - codebase is synchronous Python.

**Error Testing:**
```python
# From eval_runner_v5.py
def explain_should_use(engine: LLMQueryEngineV2, question: str, plan) -> dict:
    """Validates whether a generated plan should be used for a question."""
    reasons = []
    should_use = True

    if subject_entity == "team" and plan.entity_type == "player":
        should_use = False
        reasons.append("subject_entity_team_but_plan_entity_is_player")

    return {
        "should_use": should_use,
        "reasons": reasons,
        "signals": {...}
    }
```

**Value validation pattern:**
```python
def row_matches_expected(row: dict, expected: dict) -> bool:
    for key, expected_value in expected.items():
        if key not in row:
            return False
        if normalize_value(row[key]) != normalize_value(expected_value):
            return False
    return True

def evaluate_rows(rows: list[dict], expected: dict) -> tuple[bool, dict]:
    if not rows:
        return False, {"reason": "no_rows", "matched_row": None}

    for row in rows:
        if row_matches_expected(row, expected):
            return True, {"reason": "matched", "matched_row": row}

    return False, {"reason": "no_matching_row", "matched_row": None}
```

**Debugging output:**
```python
# From test_query_planner.py
print("=" * 100)
print(case["id"])
print(case["question"])
print(json.dumps(plan_dict, indent=2, ensure_ascii=False))
print("PASS: True/False")
print(f"PLANNER SCORE: {passed}/{len(TEST_CASES)}")
```

## Test Execution Strategy

**Manual test runners:**
- Tests designed to be run manually via command line
- Output goes to stdout with human-readable format
- Test cases organized by ID for easy reference and debugging
- Focus mode allows testing subset of cases: `eval_runner_v5.py --focus QV4_16 QV4_37`

**Evaluation pipeline (`eval_runner_v5.py`):**
- Loads questions from JSON benchmark
- Executes through LLMQueryEngineV2 pipeline
- Compares results against expected answers
- Provides detailed error analysis with reasons
- Tracks improvement across "sprints" (versions)

---

*Testing analysis: 2026-03-26*
