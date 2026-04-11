# Domain Pitfalls: Brownfield LLM Refactor (v2.0)

**Project:** Basic Stats Analyst v2.0 Refactor  
**Domain:** Migrating regex-based query planning to function calling, adding conversation memory, reorganizing repository, introducing quality tooling  
**Researched:** 2026-04-12  
**Severity Levels:** CRITICAL (blocks benchmark), HIGH (causes regressions/rewrites), MEDIUM (impacts testing/dev velocity), LOW (cosmetic/efficiency)

---

## Function Calling Migration Pitfalls

### Pitfall 1: Silent Behavior Change During Tool Migration (CRITICAL)

**What goes wrong:**
- Old regex+LLM planner produces canonicalized query objects (e.g., `table_scope`, `filters_applied`) via ~680 lines of post-processing
- New function calling tools define strict schemas (Pydantic models) but developer assumes "close enough" behavior carries over
- LLM produces valid JSON conforming to schema, but the semantic interpretation subtly differs
- Benchmark tests pass rows but with wrong implicit semantics (e.g., `p90` metric applied without team clustering, or player position filter silently drops some entities)
- **Result:** 61/61 benchmark shows green but real user questions fail silently with incorrect answers

**Why it happens:**
- Current system has ~400 lines of implicit canonicalization rules sprinkled across `_canonicalize_raw_plan()` and various extractors
- Function schema is explicit but doesn't capture all implicit assumptions (e.g., "top 5 players" assumes per-position normalization)
- LLM doesn't know about the implicit rules, only the schema; valid schema ≠ semantically correct

**Consequences:**
- Grounded answers become ungrounded when implicit filtering rules aren't preserved
- Benchmark may show false positives (correct rows happen to be returned despite wrong logic)
- Hard to detect until comparing results side-by-side or running live questions
- Rollback required, wasting phase time

**Prevention (Phase 1: Extract & Clean):**
- Before writing a single function tool, document every canonicalization rule in `query_canonicalization.md`
  - Include: what rule does, where it's applied, what happens if omitted
  - Explicitly list semantic assumptions (e.g., "p90 metrics require team context", "position filter must normalize position strings")
- Create unit tests for each canonicalization rule in isolation
  - Test input: raw planner output; Output: canonicalized query; Assert: specific semantic rule applied
  - Example: `test_position_filter_normalizes_full_back_variants()` should verify "LB, RB, WB" all map to single matcher
- When designing function schemas in Phase 2, add required fields and validation that capture these rules
  - Example: `position: str` with constraint `Pattern("^(goalkeeper|defender|midfielder|forward)$")` instead of free text

**Detection:**
- Eval runner returns 61/61 but manual spot-check of 3-5 questions shows off-topic rows in results
- New test suite in Phase 1 fails when canonicalization rules aren't captured
- Benchmark queries return "correct" rows by coincidence, not by rule

---

### Pitfall 2: LLM Tool Hallucination on Unfamiliar Filters (HIGH)

**What goes wrong:**
- Current system has ~200 implicit filters: `top_n_bucket`, `bottom_rank_bucket`, `mid_table`, `recent_window`, `opponent_strength`
- When migrating to explicit tools, developer defines tools for 90% of cases
- LLM sees a question like "who scored the most in the last 3 weeks against teams outside the top 6?"
- LLM can't express "teams outside top 6" in existing tool schema (only `top_6`, `bottom_5`, etc.)
- LLM invents a filter or uses closest matching tool with wrong parameters
- Result passes rows (because DuckDB query is generic) but answer is semantically wrong

**Why it happens:**
- Tool schemas are defined statically; the world of possible filters grows
- LLM's "fill in the closest matching tool" strategy fails on edge cases
- Current regex extractors are forgiving (return None if pattern doesn't match); function calls require explicit handling

**Consequences:**
- Benchmark regresses on new question patterns (not in training data)
- False positives in eval runner mask the problem (rows returned, but for wrong reason)
- Requires adding new tools mid-refactor, breaking Phase 2 stability

**Prevention (Phase 2: Function Calling Core):**
- Design tool schemas with explicit "fallback" or "error" modes
  - Include a `filter_description` field (string) that LLM can use to express novel filters
  - When LLM fills this field, log a warning and route to manual review or fallback planner
  - Example: `"filter_description": "top 6 teams by xG, excluding teams with <5 matches"`
- Create comprehensive docstring for each tool that lists all supported filter values
  - Tool docs should say: "Supported metrics: [list]", "Supported filters: [list]", "If your question uses X, use tool Y"
- Add validation layer that rejects "impossible" filter combinations
  - Example: reject `{position: "goalkeeper", metric: "goals"}` before query reaches DuckDB
  - Raise clear error that propagates to eval runner as "unsupported" (not "no rows")

**Detection:**
- Eval runner shows regression on questions with novel filter patterns (e.g., "against mid-table or lower")
- LLM tool calls start using `filter_description` field frequently (sign of tool schema inadequacy)
- Manual inspection of failed questions reveals "filled closest matching tool" pattern

---

### Pitfall 3: Function Call Parameter Order Sensitivity (MEDIUM)

**What goes wrong:**
- Current system is loosely ordered: planner produces dict, order doesn't matter
- New function calls have strict parameter order (especially for Azure OpenAI SDK 0.28.1, which is older and stricter)
- Developer defines tool with params: `[metric, table, filters, limit]`
- LLM calls tool with params in different order or with extra params
- SDK silently drops extra params or reorders them
- Query semantics change (e.g., limit=10 becomes limit=1000 if param reordering happens)

**Why it happens:**
- Function calling specs (OpenAI JSON Schema) define parameter order, but LLM doesn't always respect it
- Legacy Azure SDK 0.28.1 has inconsistent parameter handling compared to modern API
- Pydantic models auto-reorder params, masking the real issue

**Consequences:**
- Intermittent benchmark failures that vary by LLM response variation
- Hard to reproduce (same question, different answer some runs)
- Phase 2 gets blocked on "flaky" test failures

**Prevention (Phase 2: Function Calling Core):**
- Use Pydantic `model_validate()` instead of manual dict unpacking
  - This ensures parameter order is normalized
  - Example: Validate raw LLM JSON against schema before passing to DuckDB
- Add assertion in tool implementation that checks parameter presence and type
  ```python
  def resolve_metric_tool(metric: str, table: str, filters: dict = None, limit: int = 100):
    assert isinstance(metric, str), f"metric must be str, got {type(metric)}"
    assert table in ["players", "teams"], f"table must be 'players' or 'teams', got {table}"
    # ... proceed
  ```
- Test with intentionally reordered params to verify robustness
  - Create test that calls function with kwargs in reverse order
  - Assert behavior is identical

**Detection:**
- Benchmark passes 59/61 today, then 56/61 tomorrow on unchanged questions
- `eval_runner` output shows same question with different correct/incorrect results across runs
- Tool call logs show parameter type mismatches

---

### Pitfall 4: Loss of Graceful Fallback During Full Migration (HIGH)

**What goes wrong:**
- Current system has graceful fallback: if QueryPlanner fails, LLMQueryEngineV2 has hardcoded summary fallback paths
- During migration, developer removes old planner code incrementally
- At some point (Phase 2 end), old planner is disabled but new function calling tools are incomplete
- Question arrives that old planner handled gracefully; new tools can't handle it
- No fallback exists; system returns `[PLANNER ERROR]` instead of answering
- Benchmark regresses hard (e.g., 61/61 → 40/61)

**Why it happens:**
- Parallel implementation strategy (old + new side-by-side) requires careful switchover
- Developer disables old planner too early, before new tools cover all cases
- Test coverage doesn't require "new tools must handle every old planner case"

**Consequences:**
- Phase 2 completion is blocked until tool coverage = 100%
- Large rework required to re-enable fallback mid-phase
- Team loses confidence in refactor strategy

**Prevention (Phase 2: Function Calling Core):**
- Implement "graceful degradation" mode, not hard switchover
  - Keep old planner enabled with a `use_function_calling` flag
  - Default to function calling; on tool validation error, fall back to old planner
  - Log each fallback with detailed reason
- Add explicit coverage requirement to Phase 2 success criteria
  - "All 61 benchmark questions must be answerable by function calling tools without fallback"
  - Run benchmark with fallback disabled 2 days before Phase 2 close
  - If any question routes to fallback, add a new tool
- Create a "tool coverage matrix" that maps each benchmark question to the tool that should handle it
  - Before Phase 2 ends, verify every question is covered
  - Example:
    ```
    Q1 "who scored most" → metric_ranking tool
    Q2 "top 5 vs bottom 5" → comparative_buckets tool
    Q3 "last 3 weeks" → temporal_window tool
    ```

**Detection:**
- Benchmark suddenly drops from 61/61 to 50/61 when old planner is disabled
- Tool validation errors logged frequently
- Questions marked `[PLANNER ERROR]` are not regression tests (old system handled them)

---

## Conversation Memory Pitfalls

### Pitfall 5: State Pollution from Follow-Up Questions (HIGH)

**What goes wrong:**
- Phase 3 adds `ConversationState` to track context across turns
- User: "Who scored the most?" → System: "Haaland with 20 goals"
- User: "Against top-6 teams?" → System should understand this as "Who scored the most against top-6 teams?"
- Developer caches `metric=total_goals` and `table=players_summary` from turn 1
- Turn 2 just filters existing results by "top-6 opponent" without re-planning
- But the filter logic is wrong: it filters Haaland's rows by opponent strength, not by "goals scored against top-6"
- Result: Benchmark question that was correct in turn 1 becomes wrong when used in turn 2 context

**Why it happens:**
- State management assumes context is fully captured in filters
- Some context is implicit in the original question's phrasing (e.g., "against top-6" implies a different ranking set, not just filtering)
- Memory module caches too aggressively, reusing contexts that don't apply

**Consequences:**
- Turn 1 questions still pass benchmark (61/61 if you only test first turn)
- Turn 2 questions fail silently because expected rows are filtered incorrectly
- Multi-turn test suite not part of existing benchmark, so regressions aren't caught
- Phase 3 completion looks good, but feature is broken

**Prevention (Phase 3: Conversation Memory):**
- Design `ConversationState` with explicit "valid context scope"
  - Track which fields are reusable: `metric`, `table` (yes); `recent_window`, `opponent_strength` (context-dependent, maybe no)
  - Document the boundary: "Context X is valid for follow-ups if question contains pattern Y"
- Create a "multi-turn test suite" before implementing memory
  - Define 10-15 realistic conversation flows
  - Example:
    ```
    Turn 1: "Who has the most assists?"
    Expected T1: [Top 10 players by assists, all matches]
    
    Turn 2: "Among strikers?"
    Expected T2: [Top 10 strikers by assists]
    
    Turn 3: "In the last 5 matchdays?"
    Expected T3: [Top 10 strikers by assists, last 5 matchdays only]
    ```
  - Create evaluation harness that tests multi-turn conversations, not single questions
- Implement "context validation" before applying cached state
  - Before reusing `metric` from Turn 1 in Turn 2, check: does Turn 2 question mention a different metric or filter?
  - Example: if Turn 1 is "best defenders" and Turn 2 is "among left-backs", validate that position filter is compatible with metric
  - If incompatible, re-plan instead of reusing

**Detection:**
- Single-turn benchmark passes (61/61), but manual testing of multi-turn conversations shows wrong answers
- Turn 2 results are subsets of Turn 1 results, indicating aggressive filtering instead of re-planning
- No regression test suite for multi-turn conversations exists

---

### Pitfall 6: Memory Growth and Token Budget Overflow (MEDIUM)

**What goes wrong:**
- Phase 3 adds `ConversationState` that grows with each turn
- By turn 10-15 in a long conversation, `ConversationState` contains 10 queries, 10 results, 10 verbalization summaries
- LLM system prompt: "You are a stats analyst with conversation history: [full state JSON, ~5KB]"
- By turn 15, system prompt + history + context = 7KB before user's new question
- With Azure OpenAI token budget (2K context window in this project), only ~1KB remains for question + reasoning
- LLM's answers become truncated or incoherent
- Benchmark doesn't test long conversations, so this isn't caught until Phase 3 review

**Why it happens:**
- Developer naively appends entire `ConversationState` to system prompt without summarization
- Token budget not checked during Phase 3 design
- No multi-turn stress test (e.g., 20-turn conversation)

**Consequences:**
- Feature works for 3-5 turn conversations but breaks at 10+
- Phase 3 passes tests (which are short) but fails in production
- Requires redesign of how context is stored/retrieved (expensive refactor mid-milestone)

**Prevention (Phase 3: Conversation Memory):**
- Design memory as "sliding window" not "full history"
  - Keep only last 3-5 turns in active state
  - Summarize older turns into a "conversation summary" (e.g., "User asked about 5 players, focused on assists metric")
  - Store full history for audit, but only feed recent turns to LLM
- Add token counting to Phase 3 success criteria
  - Before every LLM call, count tokens in system prompt + context + question
  - Assert: `total_tokens < 1500` (leaving 500 token buffer)
  - Example:
    ```python
    state_tokens = count_tokens(conversation_state)
    system_tokens = count_tokens(system_prompt)
    question_tokens = count_tokens(user_question)
    total = state_tokens + system_tokens + question_tokens
    assert total < 1500, f"Token budget exceeded: {total} > 1500"
    ```
- Test with 20-turn conversation to verify memory doesn't degrade
  - Create synthetic 20-turn conversation (alternating broad questions and follow-ups)
  - Run eval_runner_v4 on all 20 turns
  - Assert: quality doesn't degrade from turn 1 to turn 20

**Detection:**
- Benchmark passes, but manual 10-turn conversation shows truncated/incoherent answers at turn 8-10
- Token count warnings logged when system prompt is constructed
- Phase 3 review reveals memory design doesn't account for long conversations

---

### Pitfall 7: Context Ambiguity in Follow-Ups (MEDIUM)

**What goes wrong:**
- User: "Top scorers this season?" → System returns Top 10 players
- User: "What about the previous season?" → Ambiguous: does "previous" refer to last season (2024-25) or last question's set?
- Memory module interprets this as "change season filter, keep players_summary table" (reasonable)
- But user might have meant "show previous season's data for the same players" (different interpretation)
- System correctly queries 2024-25 but returns different players (because different season = different rankings)
- User: "I meant the same 10 from before" → Now system must backtrack and clarify
- This edge case isn't in benchmark, so no regression signal

**Why it happens:**
- Natural language is inherently ambiguous
- Memory module tries to infer intent, but without a clarification flow, it guesses
- Benchmark doesn't include ambiguous follow-ups (it's designed for unambiguous questions)

**Consequences:**
- Feature works for unambiguous multi-turn conversations
- Edge cases cause poor UX (user confusion, need for clarification)
- Phase 3 looks good until real users test it

**Prevention (Phase 3: Conversation Memory):**
- Design memory with "clarification mode"
  - When context is ambiguous, log a warning and ask user to clarify before proceeding
  - Example: `"Did you mean 'top scorers in 2024-25' or 'the same players as before'?"`
  - Only apply this in Phase 3 to avoid over-engineering
- Create "ambiguity test cases" alongside multi-turn suite
  - Example ambiguous sequence:
    ```
    T1: "Top 10 scorers"
    T2: "Last season?" (ambiguous: previous season or previous set?)
    T2b: "No, the same 10 players" (clarification)
    ```
  - Document expected behavior for each case
- Add human review checkpoint before Phase 3 close
  - Have Agust (product expert) test 5-10 multi-turn conversations
  - If >20% involve clarifications or wrong interpretations, add clarification mode to Phase 3

**Detection:**
- No automated detection (requires human testing)
- Manual testing of multi-turn conversations reveals frequent clarification needs
- Phase 3 review notes show "memory interpretation wrong X times out of Y"

---

## Repository Restructure Pitfalls

### Pitfall 8: Broken Imports During Directory Migration (HIGH)

**What goes wrong:**
- Phase 1 reorganizes `utils/basic_stats/` from flat structure to modular structure
- Old: `utils/basic_stats/{query_planner.py, llm_query_engine_v2.py, ...}`
- New: `utils/basic_stats/core/{query_planner.py, engine.py, ...}` + `utils/basic_stats/memory/` + `utils/basic_stats/tools/`
- Developer moves files and updates imports in the moved files
- But `eval_runner_v4.py` (in project root) still imports from old paths
- Plus 5 other places import from old paths (agent.py, pages/basic_stats.py, etc.)
- Developers update some imports, miss others
- When Phase 1 is done, eval_runner_v4 breaks: `ImportError: cannot import name 'QueryPlanner' from 'utils.basic_stats.core.query_planner'`
- Benchmark runs, shows 0/61 passing, appears to be total regression
- Actually, it's just broken imports

**Why it happens:**
- Large codebase has ~30-40 import points for basic_stats modules
- IDE refactoring tools miss non-obvious import points (e.g., dynamic imports, string-based imports in YAML config)
- No "import validation" step in Phase 1 process
- Tests aren't run before Phase 1 close, so import errors aren't caught

**Consequences:**
- Phase 1 looks complete but code is broken
- Phase 2 can't start (no working baseline to refactor from)
- Team has to debug import issues before refactoring can proceed (lost time)
- Confidence in refactor plan drops

**Prevention (Phase 1: Extract & Clean):**
- Create explicit "import manifest" before moving files
  - Document all import points: where each module is imported from
  - Example: `query_planner` imported from: `{eval_runner_v4.py:10, agent.py:5, test_query_planner.py:3}`
  - Use grep to find all: `grep -r "from utils.basic_stats" /Users/ricardoheredia/Twelve-GPT-Educational --include="*.py"`
  - Store manifest in `.planning/IMPORTS.md`
- Add import validation script that runs after directory moves
  - Script walks all .py files and validates each import resolves
  - Example:
    ```python
    import importlib
    import sys
    
    imports_to_check = [
        "utils.basic_stats.core.QueryPlanner",
        "utils.basic_stats.core.LLMQueryEngineV2",
        # ... all imports
    ]
    
    failed = []
    for imp in imports_to_check:
        try:
            importlib.import_module(imp)
        except ImportError as e:
            failed.append((imp, str(e)))
    
    if failed:
        print("IMPORT VALIDATION FAILED:")
        for imp, err in failed:
            print(f"  {imp}: {err}")
        sys.exit(1)
    ```
- Run this validation as part of Phase 1 success criteria
  - Success criteria: "All imports resolve without error" (not just "files moved")
  - Run `python scripts/validate_imports.py` before closing Phase 1

**Detection:**
- `eval_runner_v4.py` crashes immediately with ImportError
- Benchmark shows 0/61 (not regression, just broken imports)
- Import validation script output shows >5 failed imports

---

### Pitfall 9: Circular Import Chains from New Module Organization (MEDIUM)

**What goes wrong:**
- Phase 1 creates new structure with dedicated modules: `core`, `memory`, `tools`, `engine`
- Each module imports from `config.py` (settings)
- `config.py` imports from `models.py` (Pydantic models)
- `models.py` needs to import from `tools` module (to reference tool schemas)
- `tools` module imports from `models` (to use Pydantic models)
- Python hits circular import: `models` → `tools` → `models`
- At runtime, when eval_runner imports LLMQueryEngineV2, it gets NameError on second import
- Benchmark fails with cryptic error: `NameError: name 'MetricResolution' is not defined`

**Why it happens:**
- New modular structure creates more potential import chains
- Developer wasn't aware of circular dependency while reorganizing
- No circular import detection tool run during Phase 1

**Consequences:**
- Code appears correct but fails at import time
- Hard to debug (error message doesn't point to circular import)
- Requires restructuring module boundaries again (expensive in Phase 1)

**Prevention (Phase 1: Extract & Clean):**
- Use Python's import cycle detector before closing Phase 1
  - Install: `pip install pydeps` or write custom detector
  - Run: `pydeps utils/basic_stats --show-deps --no-external`
  - Review output for cycles; refactor if any found
- Apply "dependency inversion" pattern
  - High-level modules (engine, memory) should depend on low-level modules (config, models)
  - Low-level modules should NOT import from high-level modules
  - Example structure (good):
    ```
    config.py (no imports from basic_stats except models)
    models.py (no imports from basic_stats except config)
    tools.py (imports config, models, but NOT engine)
    engine.py (imports config, models, tools)
    ```
  - Example structure (bad):
    ```
    tools.py imports engine.py
    engine.py imports tools.py
    (circular!)
    ```
- Add a "layer diagram" to Phase 1 output
  - Document allowed imports by layer
  - Part of Phase 1 completion artifact

**Detection:**
- `python -c "import utils.basic_stats.core.llm_query_engine_v2"` fails with NameError
- `pydeps` output shows cycles in graph
- Phase 1 review shows import errors in test runs

---

### Pitfall 10: Test Suite Breaks From Import Path Changes (MEDIUM)

**What goes wrong:**
- Current tests import from old paths: `from utils.basic_stats.core.query_planner import QueryPlanner`
- Phase 1 moves `query_planner.py` to `utils/basic_stats/core/query_planner.py` (same path, but structure changes)
- But some tests use relative imports that assume old structure
- Example: `test_query_planner.py` does `from . import query_planner` (relative)
- After reorganization, this path is wrong
- Tests can't even be imported
- No test coverage for Phase 1 changes, so this isn't caught

**Why it happens:**
- Test structure wasn't migrated alongside code
- Relative imports are fragile to directory changes
- No test suite validation step in Phase 1

**Consequences:**
- Phase 1 complete, Phase 2 starts with no test coverage
- Phase 2 refactoring has no baseline tests to validate against
- Bugs in Phase 2 aren't caught because tests never run

**Prevention (Phase 1: Extract & Clean):**
- Use absolute imports everywhere (not relative)
  - Before Phase 1: scan test files for `from . import` or `from .module import`
  - Replace all with `from utils.basic_stats.core.module import`
  - Example: `from . import query_planner` → `from utils.basic_stats.core import query_planner`
- Add test discovery to Phase 1 success criteria
  - Run: `python -m pytest utils/basic_stats/ --collect-only`
  - Assert: all tests are discoverable (no import errors)
- Run full test suite at Phase 1 close
  - `pytest utils/basic_stats/core/test_*.py -v`
  - Assert: all tests pass (behavior unchanged, just reorganized)
  - If tests fail, it's a regression (fix before Phase 1 close)

**Detection:**
- Test discovery fails: `pytest --collect-only` shows 0 tests collected (should be 20+)
- Test import errors in Phase 1 review: `ModuleNotFoundError` or `ImportError`
- Phase 2 starts with no test baseline

---

## Quality Tooling Setup Pitfalls

### Pitfall 11: Pre-Commit Hooks Block Phase Commits (MEDIUM)

**What goes wrong:**
- Phase 1 task: "Add pre-commit + ruff configuration"
- Developer adds `.pre-commit-config.yaml` with ruff, black, and lint checks
- Ruff config specifies `line-length = 88`
- Existing code has lines with length >88 (some functions in query_planner are 120+ chars)
- Developer commits Phase 1 changes, and pre-commit hook blocks commit
- Error: "26 files have linting violations"
- Developer must fix all linting violations before committing Phase 1
- This creates "catch-22": can't commit reorganization without fixing style issues, but style fixes are outside Phase 1 scope

**Why it happens:**
- Pre-commit hooks are introduced with strict settings
- Existing code doesn't conform to new standards
- No "grace period" for legacy code

**Consequences:**
- Phase 1 is blocked until all style violations are fixed
- Scope creep: Phase 1 now includes linting all of basic_stats (not just reorganization)
- Takes extra 4-8 hours to fix style, delaying Phase 2

**Prevention (Phase 1: Extract & Clean → Before Phase 1 close):**
- Add pre-commit hooks with lenient settings, not strict
  - Use `--extend-exclude` to exclude files not being touched in Phase 1
  - Example `.pre-commit-config.yaml`:
    ```yaml
    - repo: https://github.com/astral-sh/ruff-pre-commit
      rev: v0.1.0
      hooks:
        - id: ruff
          args: [--extend-exclude=utils/basic_stats/legacy]
        - id: ruff-format
    ```
- Alternative: add pre-commit without enforcing on Phase 1
  - Set pre-commit to "warn, not block"
  - Document plan to fix violations in later phases
  - Example: `--fix` mode auto-fixes, commit happens, violations are tracked but don't block
- Create a "style migration plan" as separate task (Phase 2 or later)
  - Don't mix style fixes with functional refactoring
  - Phase 1: move files, organize code; Phase X: fix style

**Detection:**
- Pre-commit hook fails during Phase 1 commit
- Error message lists 26+ linting violations
- Phase 1 is blocked, waiting for style fixes

---

### Pitfall 12: Ruff Configuration Conflicts with Existing Formatters (MEDIUM)

**What goes wrong:**
- Existing code uses some `black` formatting (line breaks, spacing)
- Phase 1 adds ruff with `line-length = 88`
- Ruff also has format rules that conflict with black
- Example: ruff wants `from x import y` on one line; black wants multi-line for >4 imports
- Running ruff fixes conflicts in one direction, but black's format was intentional for readability
- Developer commits Phase 1, Phase 2 developer runs ruff again, changes revert/conflict
- Git history shows unnecessary style commits cluttering the log

**Why it happens:**
- Ruff and black have overlapping (but not identical) style rules
- Configuration wasn't coordinated with existing code practices
- No "style guide" documented before tooling was added

**Consequences:**
- Unnecessary git commits for style changes only
- Phase 2 developer experience is poor (constant auto-fixes)
- Confusion about what "correct" style is

**Prevention (Phase 1: Extract & Clean):**
- Coordinate ruff and black settings before committing Phase 1
  - If black is already in use, configure ruff to match black
  - Example `pyproject.toml`:
    ```toml
    [tool.ruff]
    line-length = 88
    
    [tool.ruff.format]
    quote-style = "double"
    
    [tool.black]
    line-length = 88
    ```
  - Run both tools on a sample file, verify no conflict
- Create `.style-guide.md` documenting choices
  - Why 88 char line limit?
  - Why this quote style?
  - When to break rules?
- Run both ruff and black before committing Phase 1
  - `ruff check . --fix && black . && ruff format .`
  - Verify no conflicts (run tools multiple times, should idempotent)

**Detection:**
- Phase 2 dev runs ruff, gets 5+ auto-fixes for Phase 1 code
- Git log shows consecutive style-only commits
- Team discusses "what's the right format?" without clear answer

---

### Pitfall 13: Missing Dependencies in pyproject.toml (MEDIUM)

**What goes wrong:**
- Phase 1 adds `pyproject.toml` with dependencies
- Requirements.txt has: `openai`, `polars`, `pydantic`, `yaml` (plus 10 others)
- Developer writes pyproject.toml with only direct imports: `openai`, `pydantic`
- Missing transitive dependencies: `polars`, `yaml`, `tiktoken`
- Dev environment has requirements.txt installed, so things work locally
- In clean environment (CI/CD or new machine), Phase 2 code fails: `ImportError: No module named 'polars'`
- Phase 2 is blocked waiting for dependency fixes

**Why it happens:**
- Pyproject.toml is new; developer wasn't familiar with all dependencies
- Relied on requirements.txt but didn't cross-reference
- No validation that pyproject.toml lists all needed packages

**Consequences:**
- Phase 2 code fails in CI/CD
- Requires debugging import errors before Phase 2 can proceed
- Takes 1-2 hours to identify and fix missing dependencies

**Prevention (Phase 1: Extract & Clean → Before Phase 1 close):**
- Use automated dependency checker
  - Install: `pip install pip-audit` or `pipdeptree`
  - Run on all .py files in Phase 1 code:
    ```bash
    pipdeptree -p openai,polars,pydantic,yaml,duckdb
    ```
  - Verify each dependency in code has entry in `pyproject.toml`
- Create a script to validate pyproject.toml completeness
  - Example:
    ```python
    import ast
    import re
    from pathlib import Path
    
    # Find all imports in basic_stats
    imports = set()
    for py_file in Path("utils/basic_stats").rglob("*.py"):
        tree = ast.parse(py_file.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.add(node.module.split(".")[0])
    
    # Check against pyproject.toml
    pyproject_content = Path("pyproject.toml").read_text()
    declared = set(re.findall(r'^\s*"([^"]+)"', pyproject_content, re.MULTILINE))
    
    missing = imports - declared - {"utils", "sys", "os", "json", "re", ...}  # stdlib
    if missing:
        print(f"Missing dependencies: {missing}")
        sys.exit(1)
    ```
- Add this to Phase 1 success criteria: "pyproject.toml contains all dependencies"

**Detection:**
- Phase 2 CI/CD fails with `ImportError: No module named 'polars'`
- Clean environment install from pyproject.toml fails
- Phase 1 review shows dependencies incomplete

---

### Pitfall 14: Benchmark Runner Fails Due to Tool Config Changes (MEDIUM)

**What goes wrong:**
- Phase 1 updates directory structure, adding new `pyproject.toml`
- Phase 1 adds pre-commit hooks, ruff config
- Existing `eval_runner_v4.py` (in project root) still works locally
- But CI/CD environment uses fresh install from pyproject.toml
- CI/CD runs eval_runner_v4, gets ModuleNotFoundError (missing config or paths)
- Benchmark shows 0/61
- Looks like total regression, actually just CI/CD issue

**Why it happens:**
- Eval runner has hardcoded paths: `sys.path.insert(0, ".")` to find modules
- In fresh environment, "." doesn't include venv or package paths
- Phase 1 changes broke implicit path assumptions

**Consequences:**
- Phase 1 CI/CD gate is broken
- Can't run automated benchmarks after Phase 1
- Phase 2 starts without automated testing (risky)

**Prevention (Phase 1: Extract & Clean):**
- Test eval_runner in fresh environment before Phase 1 close
  - Create fresh venv: `python -m venv /tmp/test_venv`
  - Install from pyproject.toml: `pip install -e .`
  - Run eval_runner: `python eval_runner_v4.py`
  - Assert: 61/61 pass (or at least same pass rate as before Phase 1)
- Update eval_runner to use proper module imports
  - Remove `sys.path.insert(0, ".")` hack
  - Use proper: `from utils.basic_stats.core import LLMQueryEngineV2`
  - Example:
    ```python
    # OLD (fragile):
    sys.path.insert(0, ".")
    from utils.basic_stats.core.llm_query_engine_v2 import LLMQueryEngineV2
    
    # NEW (robust):
    from utils.basic_stats.core.llm_query_engine_v2 import LLMQueryEngineV2
    ```
- Document eval_runner setup in `.planning/EVAL_SETUP.md`
  - How to run it
  - What paths it expects
  - How to troubleshoot

**Detection:**
- CI/CD fails at eval_runner step with ModuleNotFoundError
- Benchmark shows 0/61 (not regression, environment issue)
- Phase 1 review shows eval_runner wasn't tested in clean environment

---

## Critical Phase-Specific Pitfalls Summary

| Phase | Top 3 Pitfalls | Prevention Focus |
|-------|---|---|
| **Phase 1: Extract & Clean** | Broken imports (Pitfall 8), Circular imports (Pitfall 9), Test suite breaks (Pitfall 10) | Import manifest + validation script, dependency checker, test discovery |
| **Phase 2: Function Calling** | Silent behavior change (Pitfall 1), Tool hallucination (Pitfall 2), Loss of fallback (Pitfall 4) | Canonicalization docs, tool coverage matrix, graceful degradation flag |
| **Phase 3: Memory** | State pollution (Pitfall 5), Token overflow (Pitfall 6), Context ambiguity (Pitfall 7) | Multi-turn test suite, token counting assertion, clarification mode |
| **Phase 1→2: Tooling** | Pre-commit blocks (Pitfall 11), Ruff conflicts (Pitfall 12), Missing deps (Pitfall 13), Runner fails (Pitfall 14) | Lenient config initially, coordinate formatters, validate pyproject, test in fresh env |

---

## Prevention Strategies by Phase

### Phase 1: Extract & Clean (0-3 days)

**Before starting:**
- [ ] Run `grep -r "from utils.basic_stats" . --include="*.py"` to find all 40+ import points
- [ ] Document in `.planning/IMPORTS.md`: list of all import points and their current paths
- [ ] Create `scripts/validate_imports.py` (see Pitfall 8)

**During Phase 1:**
- [ ] After moving files, run import validation script
  - All imports must resolve without error
- [ ] Run `pytest --collect-only utils/basic_stats/core/test_*.py` to discover all tests
  - Must show ≥20 tests collected (not "0 collected")
- [ ] Run full test suite: `pytest utils/basic_stats/core/test_*.py -v`
  - All tests must pass (behavior unchanged)
- [ ] Check for circular imports: `pydeps utils/basic_stats --show-deps`
  - Must show no cycles in graph

**Tooling setup (Phase 1 tail):**
- [ ] Add `.pre-commit-config.yaml` with `--extend-exclude=utils/basic_stats/legacy`
  - Start lenient; don't enforce on existing code yet
- [ ] Create `pyproject.toml` with all dependencies from requirements.txt
  - Use validation script (Pitfall 13) to confirm completeness
- [ ] Create `.style-guide.md` documenting ruff + black rules
- [ ] Test in fresh environment:
  ```bash
  python -m venv /tmp/phase1_test
  source /tmp/phase1_test/bin/activate
  pip install -e .
  python eval_runner_v4.py
  ```
  - Assert: 61/61 pass (or same rate as before Phase 1)

**Phase 1 success criteria:**
- [ ] All imports resolve (validation script passes)
- [ ] All tests discoverable and passing
- [ ] No circular imports
- [ ] eval_runner passes in fresh environment
- [ ] `.planning/IMPORTS.md` documents all import points

---

### Phase 2: Function Calling Core (5-7 days)

**Before starting:**
- [ ] Create `docs/canonicalization_rules.md`
  - Document every rule from old `_canonicalize_raw_plan()`
  - Include: what rule does, where applied, what breaks if omitted
  - Example rules:
    - "Position filter normalizes 'LB', 'RB', 'WB' to 'full back' matcher"
    - "p90 metrics require team context for correct calculation"
    - "Top-N ranking must normalize position variations"
- [ ] Create "tool coverage matrix" in `.planning/TOOL_COVERAGE.md`
  - Map each of 61 benchmark questions to the tool that should handle it
  - Example:
    ```
    Q1 "Who scored most" → metric_ranking(metric=total_goals, table=players, limit=10)
    Q2 "Top 5 vs bottom 5" → comparative_buckets(metric=total_goals, top_bucket=5, bottom_bucket=5)
    ```
- [ ] Create unit tests for each canonicalization rule (Pitfall 1)
  - Test input: raw planner output; output: canonicalized query
  - Assert: specific rule applied correctly
- [ ] Design tool schemas with explicit fallback/error modes (Pitfall 2)
  - Include `filter_description: str` field in each tool
  - Document supported values in tool docstring

**During Phase 2:**
- [ ] Implement graceful degradation (Pitfall 4)
  - Keep old planner enabled with `use_function_calling` flag
  - Log each fallback with reason
  - Success: tools handle all 61 questions without fallback by Phase 2 end
- [ ] Validate tool parameters (Pitfall 3)
  - Use Pydantic `model_validate()` for all tool calls
  - Add assertions for type checking
  - Test with intentionally reordered params
- [ ] Test tool hallucination resistance (Pitfall 2)
  - Create 10 "edge case" questions with novel filter patterns
  - Assert: each either uses correct tool or falls back gracefully
  - Example edge case: "against teams outside top 6 by expected goals"

**Phase 2 success criteria:**
- [ ] All 61 benchmark questions answerable by function tools (no fallback)
- [ ] Tool coverage matrix 100% complete
- [ ] Canonicalization rules tests passing
- [ ] Zero silent behavior changes (tool outputs match old planner semantically)
- [ ] Edge case questions handled (either correct tool or error message, not hallucination)

---

### Phase 3: Conversation Memory (4-5 days)

**Before starting:**
- [ ] Create "multi-turn test suite" with 10-15 realistic conversations
  - Document expected output for each turn
  - Example:
    ```
    T1: "Who has the most assists?"
    Expected T1: Top 10 players by assists
    
    T2: "Among strikers?"
    Expected T2: Top 10 strikers by assists
    
    T3: "In the last 5 matchdays?"
    Expected T3: Top 10 strikers by assists, matchdays 34-38
    ```
- [ ] Create `scripts/test_multi_turn.py` to evaluate conversation flows
  - Input: multi-turn conversation (list of questions)
  - Output: pass/fail for each turn with expected rows

**During Phase 3:**
- [ ] Design `ConversationState` with explicit "valid context scope"
  - Document which fields are reusable (`metric`, `table` yes; `recent_window` context-dependent)
  - Include field for reason: `reason_cache_valid: str`
- [ ] Add token counting to every LLM call (Pitfall 6)
  - Assert: `total_tokens < 1500` before calling LLM
  - Example:
    ```python
    state_tokens = count_tokens(conversation_state)
    question_tokens = count_tokens(user_question)
    system_tokens = count_tokens(system_prompt)
    total = state_tokens + question_tokens + system_tokens
    assert total < 1500, f"Token budget exceeded: {total} > 1500"
    ```
- [ ] Implement context validation (Pitfall 5)
  - Before reusing cached context, validate compatibility with new question
  - If incompatible, re-plan instead of filtering
  - Example:
    ```python
    if turn_1_metric == "goals" and turn_2_asks_for_assists:
        re_plan()  # incompatible
    else:
        reuse_context()
    ```
- [ ] Test 20-turn conversation for memory degradation
  - Create synthetic 20-turn conversation
  - Assert: answer quality doesn't degrade from turn 1 to turn 20
- [ ] Design clarification mode for ambiguous follow-ups (Pitfall 7)
  - When context is ambiguous, ask user to clarify
  - Log clarification request
  - Document ambiguous pattern (e.g., "previous X" after multi-question context)

**Phase 3 success criteria:**
- [ ] Multi-turn test suite passing for all 15 conversations
- [ ] Token budget assertion included in all LLM calls
- [ ] 20-turn stress test shows no quality degradation
- [ ] Context validation prevents silent semantic errors
- [ ] Ambiguous follow-ups are handled (clarified, not guessed)
- [ ] No regressions in single-turn benchmark (still 61/61)

---

### Phase 4+: League Context & Polish (deferred)

**Setup (applies to Phases 4-6):**
- [ ] Continue running eval_runner_v4 after every phase (non-negotiable)
  - 61/61 pass is the regression gate
  - Any drop = phase is incomplete/broken
- [ ] Monitor token usage across all LLM calls
  - Track per-call tokens and total budget
  - Flag if trending upward
- [ ] Keep import validation and test discovery running in CI/CD
  - Prevent regressions to Phase 1

---

## Regression Detection Checklist

Use this checklist after each phase close:

- [ ] `eval_runner_v4.py` shows 61/61 pass (or same pass count as before phase)
- [ ] `pytest utils/basic_stats/core/test_*.py -v` shows all tests passing
- [ ] `python -m pytest --collect-only utils/basic_stats/` shows ≥20 tests collected
- [ ] Import validation script passes: `python scripts/validate_imports.py`
- [ ] No circular imports: `pydeps utils/basic_stats --show-deps` shows no cycles
- [ ] Token usage stable: average tokens per query didn't increase >10%
- [ ] No fallback routes taken: eval_runner logs show 0 fallback invocations (Phase 2+)
- [ ] Multi-turn test suite passing (Phase 3+): `python scripts/test_multi_turn.py` shows all turns passing
- [ ] Manual spot-check: run 3 questions manually, verify answers are grounded and correct

---

## Sources & References

**Based on:**
- Analysis of `/Users/ricardoheredia/Twelve-GPT-Educational/.planning/PROJECT.md` (1,405 line query planner, 1,933 line engine)
- Review of `.planning/codebase/CONCERNS.md` (tech debt: legacy SDK, broken async, ~400 lines implicit canonicalization)
- Examination of current codebase: `query_planner.py` (~1,500 lines regex), `llm_query_engine_v2.py` (tool-use pattern)
- Experience with LLM refactors: function calling migration patterns, conversation memory design
- Repository structure analysis: 6 eval_runner versions, multiple import points, pre-commit/tooling not yet in place

**Confidence:**
- CRITICAL and HIGH pitfalls: HIGH confidence (specific to this codebase structure)
- MEDIUM pitfalls: MEDIUM confidence (generic patterns, validate in Phase-specific research)
- Prevention strategies: MEDIUM confidence (tested patterns, but project-specific adaptation needed)

---

*Last updated: 2026-04-12*  
*For: Phase 1-6 planning of v2.0 milestone refactor*
