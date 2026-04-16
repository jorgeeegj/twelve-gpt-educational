# Phase 4: Extract & Clean — PLAN.md

**Phase:** 4 — Extract & Clean
**Requirements:** INFRA-01, INFRA-02, INFRA-03, INFRA-04, INFRA-05, CTX-02 (tail), FUNC-04 (tail)
**Benchmark invariant:** 61/61 must pass after EVERY task that touches live code
**Tasks:** 9 (7 core + 2 tail)

---

## Prerequisites

Before starting Task 1:

- You are on branch `feature/refactor-v2`
- `python eval_runner_v6.py` from project root returns `61/61` (confirm this first)
- `uv` is available: `uv --version` returns `0.10.6` or higher
- Working directory for all commands: `/Users/ricardoheredia/Twelve-GPT-Educational`

---

## Task 1 — pyproject.toml + Dev Tools Install

**Requirement:** INFRA-03

**Purpose:** Establish the project manifest with pinned deps and install ruff/pre-commit/pytest before any file moves. Run ruff on the existing code so it is clean before restructuring.

### Files to create/edit:

- `pyproject.toml` (create)

### Steps:

1. Create `pyproject.toml` at the project root with this exact content:

```toml
[project]
name = "twelve-gpt-educational"
version = "0.1.0"
description = "TwelveGPT Educational — data-driven football chatbot framework"
requires-python = ">=3.12"
dependencies = [
    "fastapi==0.104.1",
    "uvicorn==0.24.0.post1",
    "pandas>=2.2.0",
    "requests==2.29.0",
    "streamlit==1.31.0",
    "numpy>=1.26.3",
    "openai==2.15.0",
    "google-generativeai==0.7.2",
    "tiktoken",
    "python-jose==3.3.0",
    "polars>=1.0.0",
    "pyarrow",
    "duckdb>=1.0.0",
    "pydantic>=2.0.0",
    "pyyaml",
]

[project.optional-dependencies]
dev = [
    "ruff>=0.9.0",
    "pre-commit>=3.7.0",
    "pytest>=8.0.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.core"

[tool.hatch.build.targets.wheel]
packages = ["src"]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "W"]
ignore = [
    "E501",
    "F401",
]

[tool.ruff.format]
quote-style = "double"
indent-style = "space"

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_functions = ["test_*", "run_*"]
```

2. Install dev tools into the venv:
   ```bash
   uv add --dev ruff pre-commit pytest
   ```

3. Run ruff auto-fix on the existing codebase (before any file moves):
   ```bash
   .venv/bin/ruff check --fix .
   .venv/bin/ruff format .
   ```
   Expect ruff to modify import order and whitespace. Stage all ruff-modified files.

4. Run benchmark to confirm no regressions:
   ```bash
   python eval_runner_v6.py
   ```
   **Gate: must show 61/61.**

### Verification:
```bash
python -c "import tomllib; t = tomllib.load(open('pyproject.toml','rb')); print(t['project']['name'])"
# Expected: twelve-gpt-educational

.venv/bin/ruff --version
# Expected: ruff 0.9.x or higher

python eval_runner_v6.py
# Expected: 61/61
```

### Commit:
```
chore: add pyproject.toml with ruff config and pinned deps
```

---

## Task 2 — Create src/ Skeleton

**Requirement:** INFRA-01

**Purpose:** Create the empty directory structure and `__init__.py` files that make `src.basic_stats.*` imports resolvable. No files are moved here — this is scaffolding only.

### Files to create:

- `src/__init__.py` (empty)
- `src/basic_stats/__init__.py` (empty)
- `src/basic_stats/prompts/` (directory only, no files yet)
- `src/shared/__init__.py` (empty placeholder — shared utils stay in `utils/` for now)
- `tests/__init__.py` (empty)
- `evals/.gitkeep` (directory marker)

### Steps:

```bash
mkdir -p src/basic_stats/prompts src/shared tests evals
touch src/__init__.py src/basic_stats/__init__.py src/shared/__init__.py tests/__init__.py evals/.gitkeep
```

### Verification:
```bash
python -c "import src; import src.basic_stats; print('skeleton ok')"
# Expected: skeleton ok (no ImportError)

ls src/ src/basic_stats/ tests/ evals/
# Expected: directories and __init__.py files present
```

No benchmark run needed — no source files touched.

### Commit:
```
chore: create src/ skeleton with __init__.py files for restructure
```

---

## Task 3 — Move Core Files + Update All Imports Atomically

**Requirement:** INFRA-01

**Purpose:** Copy the 7 source files from `utils/basic_stats/core/` to `src/basic_stats/`, update every import reference in one batch, verify benchmark with the NEW paths, then delete the originals.

**This is the highest-risk task. Do not split it.**

### Files to move (copy first, delete after benchmark passes):

Source → Destination:
- `utils/basic_stats/core/agent.py` → `src/basic_stats/agent.py`
- `utils/basic_stats/core/config.py` → `src/basic_stats/config.py`
- `utils/basic_stats/core/duckdb_manager.py` → `src/basic_stats/duckdb_manager.py`
- `utils/basic_stats/core/knowledge_base.py` → `src/basic_stats/knowledge_base.py`
- `utils/basic_stats/core/llm_query_engine_v2.py` → `src/basic_stats/llm_query_engine_v2.py`
- `utils/basic_stats/core/models.py` → `src/basic_stats/models.py`
- `utils/basic_stats/core/query_planner.py` → `src/basic_stats/query_planner.py`

Prompts directory:
- `utils/basic_stats/prompts/resolve_query_intent.yaml` → `src/basic_stats/prompts/resolve_query_intent.yaml`
- `utils/basic_stats/prompts/resolve_metric.yaml` → `src/basic_stats/prompts/resolve_metric.yaml`
- `utils/basic_stats/prompts/verbalize.yaml` → `src/basic_stats/prompts/verbalize.yaml`

### Steps:

**Step A — Copy files:**
```bash
cp utils/basic_stats/core/agent.py src/basic_stats/agent.py
cp utils/basic_stats/core/config.py src/basic_stats/config.py
cp utils/basic_stats/core/duckdb_manager.py src/basic_stats/duckdb_manager.py
cp utils/basic_stats/core/knowledge_base.py src/basic_stats/knowledge_base.py
cp utils/basic_stats/core/llm_query_engine_v2.py src/basic_stats/llm_query_engine_v2.py
cp utils/basic_stats/core/models.py src/basic_stats/models.py
cp utils/basic_stats/core/query_planner.py src/basic_stats/query_planner.py
cp utils/basic_stats/prompts/*.yaml src/basic_stats/prompts/
```

**Step B — Update imports inside moved files:**

In `src/basic_stats/agent.py` — change:
```python
# FROM:
from utils.basic_stats.core.knowledge_base import KnowledgeBase
from utils.basic_stats.core.llm_query_engine_v2 import LLMQueryEngineV2
# TO:
from src.basic_stats.knowledge_base import KnowledgeBase
from src.basic_stats.llm_query_engine_v2 import LLMQueryEngineV2
```

In `src/basic_stats/config.py` — change:
```python
# FROM:
BASE = Path(__file__).resolve().parents[3]
PROMPTS_DIR = BASE / "utils" / "basic_stats" / "prompts"
# TO:
BASE = Path(__file__).resolve().parents[2]
PROMPTS_DIR = BASE / "src" / "basic_stats" / "prompts"
```

In `src/basic_stats/duckdb_manager.py` — change:
```python
# FROM:
BASE = Path(__file__).resolve().parents[3]
# TO:
BASE = Path(__file__).resolve().parents[2]
```

In `src/basic_stats/knowledge_base.py` — change:
```python
# FROM:
BASE = Path(__file__).resolve().parents[3]
# TO:
BASE = Path(__file__).resolve().parents[2]
```

In `src/basic_stats/llm_query_engine_v2.py` — change all `utils.basic_stats.core.*` imports to `src.basic_stats.*`:
```python
# FROM (lines 20-29, all variants):
from utils.basic_stats.core.config import ...
from utils.basic_stats.core.models import ...
from utils.basic_stats.core.query_planner import ...
from utils.basic_stats.core.duckdb_manager import ...
from utils.basic_stats.core.knowledge_base import ...
# TO (replace utils.basic_stats.core with src.basic_stats throughout):
from src.basic_stats.config import ...
from src.basic_stats.models import ...
from src.basic_stats.query_planner import ...
from src.basic_stats.duckdb_manager import ...
from src.basic_stats.knowledge_base import ...
```

In `src/basic_stats/query_planner.py` — change:
```python
# FROM:
from utils.basic_stats.core.config import ...
# TO:
from src.basic_stats.config import ...
```

**Step C — Update external callers:**

In `pages/basic_stats.py` line 8:
```python
# FROM:
from utils.basic_stats.core.agent import BasicStatsAgent
# TO:
from src.basic_stats.agent import BasicStatsAgent
```

In `eval_runner_v6.py` line 30:
```python
# FROM:
from utils.basic_stats.core.llm_query_engine_v2 import LLMQueryEngineV2
# TO:
from src.basic_stats.llm_query_engine_v2 import LLMQueryEngineV2
```

**Step D — Verify benchmark with new imports (originals still present as fallback):**
```bash
python eval_runner_v6.py
```
**Gate: must show 61/61 before proceeding.**

**Step E — Delete originals (only after 61/61 confirmed):**
```bash
rm utils/basic_stats/core/agent.py
rm utils/basic_stats/core/config.py
rm utils/basic_stats/core/duckdb_manager.py
rm utils/basic_stats/core/knowledge_base.py
rm utils/basic_stats/core/llm_query_engine_v2.py
rm utils/basic_stats/core/models.py
rm utils/basic_stats/core/query_planner.py
```

**Step F — Run benchmark one more time to confirm originals are not needed:**
```bash
python eval_runner_v6.py
```
**Gate: must show 61/61.**

### Verification:
```bash
# No remaining utils.basic_stats.core imports in live code:
grep -r "from utils.basic_stats.core" pages/ eval_runner_v6.py src/
# Expected: no output

# parents depth is correct:
grep -n "parents\[" src/basic_stats/config.py src/basic_stats/duckdb_manager.py src/basic_stats/knowledge_base.py
# Expected: all show parents[2], not parents[3]

# PROMPTS_DIR points to new location:
grep "PROMPTS_DIR" src/basic_stats/config.py
# Expected: BASE / "src" / "basic_stats" / "prompts"

python eval_runner_v6.py
# Expected: 61/61
```

### Commit:
```
refactor(INFRA-01): move core files to src/basic_stats/ and update all imports
```

---

## Task 4 — Delete Dead Code

**Requirement:** INFRA-02

**Purpose:** Remove all files confirmed as dead by the import graph scan. None of these are imported by any live code path.

### Files to delete:

**Old eval runners and their benchmark files:**
```bash
rm eval_runner.py
rm eval_runner_v2.py
rm eval_runner_v3.py
rm eval_runner_v4.py
rm eval_runner_v5.py
rm eval_llm_engine.py
rm questions_benchmark_raw.json
rm questions_benchmark_v4.json
rm questions_benchmark_v5.json
```

**Legacy utils/basic_stats dead files:**
```bash
rm -rf utils/basic_stats/legacy/
rm utils/basic_stats/verbal_model.py
rm utils/basic_stats/aliases_para_ricardo.json
```

**Root-level orphans:**
```bash
rm test_embeddings.py
rm miniprueba.py
rm setup.py
rm -rf twelve_gpt_educational.egg-info/
```

**Windows shortcut (if present):**
```bash
rm "twelve-gpt-educational - Shortcut.lnk" 2>/dev/null || true
```

**Verify no live code imports any of these before deleting:**
```bash
grep -r "from eval_runner" . --include="*.py" | grep -v "__pycache__"
grep -r "from utils.basic_stats.verbal_model" . --include="*.py"
grep -r "from utils.basic_stats.legacy" . --include="*.py"
# All expected: no output
```

### Verification:
```bash
# Confirm dead files are gone:
ls eval_runner.py eval_runner_v2.py eval_runner_v3.py eval_runner_v4.py eval_runner_v5.py 2>&1
# Expected: No such file

ls utils/basic_stats/legacy/ 2>&1
# Expected: No such file or directory

ls twelve_gpt_educational.egg-info/ 2>&1
# Expected: No such file or directory

# Confirm eval_runner_v6.py still works:
python eval_runner_v6.py
# Expected: 61/61
```

### Commit:
```
chore(INFRA-02): delete dead eval runners, legacy utils, and setup artifacts
```

---

## Task 5 — Move Test Files to tests/

**Requirement:** INFRA-01

**Purpose:** Move the two test files from `utils/basic_stats/core/` to `tests/` and update their imports to use `src.basic_stats.*`.

**Note:** These tests require a live LLM connection (`GPT_KEY`) and a loaded DuckDB. They are NOT added to pre-commit hooks. They are manual smoke tests.

### Files to move:

- `utils/basic_stats/core/test_query_planner.py` → `tests/test_query_planner.py`
- `utils/basic_stats/core/test_dual_bucket_hardening.py` → `tests/test_dual_bucket_hardening.py`

### Steps:

1. Copy files:
   ```bash
   cp utils/basic_stats/core/test_query_planner.py tests/test_query_planner.py
   cp utils/basic_stats/core/test_dual_bucket_hardening.py tests/test_dual_bucket_hardening.py
   ```

2. In `tests/test_query_planner.py` — update imports:
   ```python
   # FROM:
   from utils.basic_stats.core.query_planner import ...
   # TO:
   from src.basic_stats.query_planner import ...
   ```

3. In `tests/test_dual_bucket_hardening.py` — update imports:
   ```python
   # FROM:
   from utils.basic_stats.core.llm_query_engine_v2 import ...
   # TO:
   from src.basic_stats.llm_query_engine_v2 import LLMQueryEngineV2
   ```

4. Add a comment at the top of each test file:
   ```python
   # NOTE: These tests require live LLM credentials (GPT_KEY) and DuckDB data.
   # Run manually: python -m pytest tests/test_query_planner.py -v
   # Do NOT add to pre-commit hooks.
   ```

5. Delete originals:
   ```bash
   rm utils/basic_stats/core/test_query_planner.py
   rm utils/basic_stats/core/test_dual_bucket_hardening.py
   ```

6. Remove `utils/basic_stats/core/` directory if now empty:
   ```bash
   rmdir utils/basic_stats/core/ 2>/dev/null || ls utils/basic_stats/core/
   ```

7. If `utils/basic_stats/` is now empty (all files removed), remove it too:
   ```bash
   rmdir utils/basic_stats/ 2>/dev/null || ls utils/basic_stats/
   ```

### Verification:
```bash
# Imports resolve correctly (syntax check only, no LLM call):
python -c "import ast; ast.parse(open('tests/test_query_planner.py').read()); print('syntax ok')"
python -c "import ast; ast.parse(open('tests/test_dual_bucket_hardening.py').read()); print('syntax ok')"

# No remaining old test files in utils/:
ls utils/basic_stats/core/test_*.py 2>&1
# Expected: No such file

# utils/basic_stats/core/ is gone (or empty):
ls utils/basic_stats/core/ 2>&1
# Expected: No such file or directory
```

### Commit:
```
refactor(INFRA-01): move test files to tests/ and update imports
```

---

## Task 6 — Configure Pre-commit

**Requirement:** INFRA-04

**Purpose:** Install `.pre-commit-config.yaml` with ruff hooks and basic safety checks. Verify it passes on the cleaned codebase.

### Files to create:

- `.pre-commit-config.yaml`

### Steps:

1. Create `.pre-commit-config.yaml` at project root:

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.9.0
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format

  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.6.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files
        args: ['--maxkb=1000']
      - id: debug-statements
```

2. Install git hooks:
   ```bash
   .venv/bin/pre-commit install
   ```

3. Run against all files (expect ruff to auto-fix some things):
   ```bash
   .venv/bin/pre-commit run --all-files
   ```

4. If ruff modified files (non-zero exit is expected on first run due to `--fix`), stage the changes and run again:
   ```bash
   git add -A
   .venv/bin/pre-commit run --all-files
   ```
   Second run must exit 0.

5. Confirm benchmark still passes:
   ```bash
   python eval_runner_v6.py
   ```
   **Gate: must show 61/61.**

### Verification:
```bash
# Hooks are installed:
cat .git/hooks/pre-commit | head -3
# Expected: "#!/usr/bin/env python" (pre-commit shebang)

# Clean run:
.venv/bin/pre-commit run --all-files
# Expected: exit code 0

python eval_runner_v6.py
# Expected: 61/61
```

### Commit:
```
chore(INFRA-04): add .pre-commit-config.yaml with ruff and safety hooks
```

---

## Task 7 — Rename Evals to Single Source of Truth

**Requirement:** INFRA-05

**Purpose:** Move `eval_runner_v6.py` → `evals/eval_runner.py` and `questions_benchmark_v6.json` → `evals/questions_benchmark.json`. Apply 3 targeted changes to the eval runner. Confirm 61/61 with the new path.

### Files to create/modify/delete:

- Create: `evals/eval_runner.py` (renamed from `eval_runner_v6.py` with changes)
- Create: `evals/questions_benchmark.json` (copy of `questions_benchmark_v6.json`)
- Delete: `eval_runner_v6.py`
- Delete: `questions_benchmark_v6.json`

### Steps:

1. Copy eval runner:
   ```bash
   cp eval_runner_v6.py evals/eval_runner.py
   ```

2. Apply these 3 changes to `evals/eval_runner.py`:

   **Change 1 — BENCHMARK_PATH (portability fix):**
   ```python
   # FROM:
   BENCHMARK_PATH = "questions_benchmark_v6.json"
   # TO:
   BENCHMARK_PATH = str(Path(__file__).parent / "questions_benchmark.json")
   ```

   **Change 2 — Import path (after src restructure):**
   ```python
   # FROM:
   from utils.basic_stats.core.llm_query_engine_v2 import LLMQueryEngineV2
   # TO:
   from src.basic_stats.llm_query_engine_v2 import LLMQueryEngineV2
   ```

   **Change 3 — Output filenames (strip _v6 suffix so UI reads them):**
   ```python
   # FROM:
   latest_path = OUTPUT_DIR / "latest_eval_results_v6.json"
   dated_path  = OUTPUT_DIR / f"{timestamp}_eval_results_v6.json"
   # TO:
   latest_path = OUTPUT_DIR / "latest_eval_results.json"
   dated_path  = OUTPUT_DIR / f"{timestamp}_eval_results.json"
   ```
   Also update argparse description and any docstring references to remove "v6".

   **Keep as-is:** `sys.path.insert(0, ".")` — required for imports to resolve when run as `python evals/eval_runner.py` from project root.

3. Copy benchmark JSON:
   ```bash
   cp questions_benchmark_v6.json evals/questions_benchmark.json
   ```

4. Run benchmark from the new path:
   ```bash
   python evals/eval_runner.py
   ```
   **Gate: must show 61/61.**

5. Verify output file was written to the correct path:
   ```bash
   ls -la docs/evals/latest_eval_results.json
   # Expected: file exists and was just updated (not latest_eval_results_v6.json)
   ```

6. Delete the old files:
   ```bash
   rm eval_runner_v6.py
   rm questions_benchmark_v6.json
   ```

7. Run benchmark one final time to confirm deletions did not break anything:
   ```bash
   python evals/eval_runner.py
   ```
   **Gate: must show 61/61.**

### Verification:
```bash
# New files exist:
ls evals/eval_runner.py evals/questions_benchmark.json
# Expected: both files present

# Old files are gone:
ls eval_runner_v6.py questions_benchmark_v6.json 2>&1
# Expected: No such file

# No _v6 references remain in output save logic:
grep "_v6" evals/eval_runner.py
# Expected: no output (or only in comments/changelog)

# Benchmark uses correct path:
grep "BENCHMARK_PATH" evals/eval_runner.py
# Expected: Path(__file__).parent / "questions_benchmark.json"

python evals/eval_runner.py
# Expected: 61/61

# Output goes to correct file (not v6 filename):
ls docs/evals/latest_eval_results.json
# Expected: file exists
```

### Commit:
```
refactor(INFRA-05): rename eval runner to evals/eval_runner.py as single source of truth
```

---

## Tail Task A — league_standings DuckDB View

**Requirement:** CTX-02 (needed by Phase 7)

**Purpose:** Add `league_standings` view to `DuckDBManager._register_base_views()`. This is additive — do NOT modify or remove the existing `league_table` view.

### Files to edit:

- `src/basic_stats/duckdb_manager.py`

### Steps:

1. Open `src/basic_stats/duckdb_manager.py` and locate `_register_base_views()`.

2. After the existing `league_table` CREATE statement, add:

```python
self.con.execute("""
    CREATE OR REPLACE VIEW league_standings AS
    WITH season AS (
        SELECT
            team_id,
            team_name,
            COUNT(*)                                           AS matches_played,
            SUM(CASE WHEN is_win  THEN 1 ELSE 0 END)          AS wins,
            SUM(CASE WHEN is_draw THEN 1 ELSE 0 END)          AS draws,
            SUM(CASE WHEN is_loss THEN 1 ELSE 0 END)          AS losses,
            SUM(team_score)                                    AS goals_for,
            SUM(opponent_score)                                AS goals_against,
            SUM(team_score) - SUM(opponent_score)             AS goal_difference,
            SUM(points)                                        AS points
        FROM team_match_stats
        GROUP BY team_id, team_name
    )
    SELECT
        team_id,
        team_name,
        matches_played,
        wins,
        draws,
        losses,
        goals_for,
        goals_against,
        goal_difference,
        points,
        ROW_NUMBER() OVER (
            ORDER BY points DESC, goal_difference DESC, goals_for DESC, team_name ASC
        ) AS position,
        CASE
            WHEN team_name IN (
                'Arsenal', 'Chelsea', 'Liverpool',
                'Manchester City', 'Manchester United', 'Tottenham Hotspur'
            ) THEN TRUE
            ELSE FALSE
        END AS is_big6
    FROM season
""")
```

3. Run benchmark to confirm no regression:
   ```bash
   python evals/eval_runner.py
   ```
   **Gate: must show 61/61.**

4. Run the smoke test to verify the view returns correct data:
   ```bash
   python -c "
   from src.basic_stats.duckdb_manager import DuckDBManager
   db = DuckDBManager()
   rows = db.query_dicts('SELECT position, team_name, points FROM league_standings ORDER BY position LIMIT 5')
   for r in rows: print(r)
   db.close()
   "
   ```
   **Expected output:** Liverpool at position 1 with 84 points.

### Verification:
```bash
# View is registered and returns rows:
python -c "
from src.basic_stats.duckdb_manager import DuckDBManager
db = DuckDBManager()
rows = db.query_dicts('SELECT position, team_name, points FROM league_standings ORDER BY position LIMIT 1')
assert rows[0]['team_name'] == 'Liverpool', f'Unexpected leader: {rows[0]}'
assert rows[0]['points'] == 84, f'Unexpected points: {rows[0][\"points\"]}'
print('league_standings view: PASS')
db.close()
"

# Existing league_table view still works (no regression):
python -c "
from src.basic_stats.duckdb_manager import DuckDBManager
db = DuckDBManager()
rows = db.query_dicts('SELECT * FROM league_table LIMIT 1')
print('league_table still works:', rows[0] if rows else 'empty')
db.close()
"

python evals/eval_runner.py
# Expected: 61/61
```

### Commit:
```
feat(CTX-02): add league_standings DuckDB view to duckdb_manager
```

---

## Tail Task B — canonicalization_rules.md

**Requirement:** FUNC-04 (prereq — Phase 5 cannot start without this)

**Purpose:** Document all implicit canonicalization rules from `query_planner.py` in `docs/canonicalization_rules.md`. This is the spec document Phase 5 will use to implement typed function calling tools.

### Files to create:

- `docs/canonicalization_rules.md`

### Steps:

1. Read `src/basic_stats/query_planner.py` in full — specifically:
   - `_canonicalize_raw_plan()` and all its sub-functions
   - All detector functions (`_detect_scope`, `_detect_entity_type`, etc.)
   - All alias/normalization dictionaries
   - All fallback and default behaviors

2. Create `docs/canonicalization_rules.md` documenting:

   **Section 1 — Entity Canonicalization**
   - How raw entity names from LLM are mapped to canonical player/team names
   - The alias lookup tables and normalization functions used
   - What happens on no-match (fallback behavior)

   **Section 2 — Metric Canonicalization**
   - How raw metric strings map to column names in DuckDB
   - All supported metric aliases
   - Per-scope metric availability (which metrics work in which scopes)

   **Section 3 — Scope Detection Rules**
   - How `scope` is determined from question type and entity type
   - Decision tree: what triggers `player_match_stats` vs `players_summary` vs `team_match_stats`
   - Precedence rules when multiple scopes could apply

   **Section 4 — Filter Canonicalization**
   - How `opponent`, `is_home`, `time_window` filters are detected and normalized
   - What raw LLM values look like vs. what the DuckDB query expects

   **Section 5 — Aggregation Rules**
   - How `aggregation` field is set (sum/avg/count/rank)
   - When ranking is used vs. direct value lookup
   - Default aggregation per metric type

   **Section 6 — Edge Cases and Fallbacks**
   - All `if X is None: default to Y` behaviors explicitly listed
   - Any known limitations that Phase 5 must preserve

3. Format: plain markdown with code examples showing before (raw LLM output) → after (canonicalized plan dict). No prose padding — spec quality only.

### Verification:
```bash
# File exists and is non-trivial:
wc -l docs/canonicalization_rules.md
# Expected: 80+ lines

ls docs/canonicalization_rules.md
# Expected: file present

# Check it covers the key sections:
grep -c "^## " docs/canonicalization_rules.md
# Expected: 6 or more section headers
```

### Commit:
```
docs(FUNC-04): document canonicalization rules from query_planner.py for Phase 5
```

---

## Verification Checklist

Map to success criteria from ROADMAP.md:

| # | Success Criterion | Verification Command |
|---|-------------------|----------------------|
| 1 | Repo reorganized, imports working | `grep -r "utils.basic_stats.core" pages/ src/ evals/ \| wc -l` → 0 |
| 2 | Dead code deleted | `ls eval_runner_v*.py utils/basic_stats/legacy/ setup.py 2>&1` → all "No such file" |
| 3 | pyproject.toml with openai==2.15.0 | `grep "openai==2.15.0" pyproject.toml` → match |
| 4 | pre-commit passes | `.venv/bin/pre-commit run --all-files` → exit 0 |
| 5 | evals/eval_runner.py, 61/61 | `python evals/eval_runner.py` → 61/61 |
| 6 | league_standings view works | smoke test in Tail Task A → Liverpool 84 pts |
| 7 | canonicalization_rules.md exists | `wc -l docs/canonicalization_rules.md` → 80+ lines |

**Final benchmark gate:**
```bash
python evals/eval_runner.py
# Required output: 61/61
```

---

## Guardrails

**Do NOT do these things in Phase 4:**

1. **Do not move `utils/page_components.py`, `utils/utils.py`, or any shared util** — they are imported by 8+ other pages. `src/shared/` is a placeholder only this phase.
2. **Do not modify any business logic** in the moved files — the only changes allowed are `parents[N]` depth, import paths, and `PROMPTS_DIR`.
3. **Do not add LLM-dependent tests to pre-commit hooks** — `test_dual_bucket_hardening.py` requires `GPT_KEY` and will break CI-style hooks.
4. **Do not delete `league_table` view** — all existing query methods JOIN against it. Only add `league_standings` alongside it.
5. **Do not run `pip install -e .`** — the project is NOT installed as a package; imports work via `sys.path`. Installing it could create a new stale egg-info.
6. **Do not commit with failing benchmark** — if any task step breaks 61/61, stop, diagnose, and fix before committing.
7. **Do not start Phase 5 before `canonicalization_rules.md` is complete** — FUNC-04 is a hard prerequisite per ROADMAP guardrails.
8. **Do not rename `questions_benchmark_v6.json` before updating BENCHMARK_PATH in the eval runner** — the file rename and the path fix must happen in the same task.

---

## Execution Order Summary

| Task | Requirement | Benchmark Gate |
|------|-------------|---------------|
| Task 1: pyproject.toml + ruff | INFRA-03 | After ruff auto-fix: 61/61 |
| Task 2: src/ skeleton | INFRA-01 | None needed |
| Task 3: Move files + update imports | INFRA-01 | Before delete: 61/61. After delete: 61/61 |
| Task 4: Delete dead code | INFRA-02 | After deletions: 61/61 |
| Task 5: Move tests to tests/ | INFRA-01 | None needed (no live path change) |
| Task 6: Configure pre-commit | INFRA-04 | After hooks pass: 61/61 |
| Task 7: Rename evals | INFRA-05 | Before delete: 61/61. After delete: 61/61 |
| Tail A: league_standings view | CTX-02 | After add: 61/61 |
| Tail B: canonicalization_rules.md | FUNC-04 | N/A (docs only) |
