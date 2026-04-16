# Phase 4: Extract & Clean — Research

**Researched:** 2026-04-12
**Domain:** Python repo restructure, pyproject.toml/uv, ruff, pre-commit, DuckDB views
**Confidence:** HIGH (all findings verified by direct file inspection of the live codebase)

---

## Summary

This phase is a pure structural refactor: move source code from `utils/basic_stats/core/` to `src/basic_stats/`, delete dead files, introduce `pyproject.toml` with ruff, configure `.pre-commit-config.yaml`, and rename the eval runner. No logic changes. The critical risk is import breakage — every file using `utils.basic_stats.core.*` must be updated in one atomic step and verified immediately against the benchmark.

The codebase is **not installed as a package** in the venv. All imports resolve because Streamlit and eval runners run from the project root with `sys.path.insert(0, ".")` or implicit PYTHONPATH. The restructure must preserve this convention: `src/__init__.py` and `src/basic_stats/__init__.py` must exist so `src.basic_stats.*` imports resolve without a package install.

A critical pre-existing discrepancy exists: `eval_runner_v6.py` saves to `docs/evals/latest_eval_results_v6.json`, but `pages/basic_stats.py` checks for `docs/evals/latest_eval_results.json`. The rename task must fix the save filename. Also: the `league_table` DuckDB view **already exists** in `duckdb_manager.py` (built from `player_match_stats`). The tail task wants a `league_standings` view built from `team_match_stats` instead — this is a net-new, cleaner view alongside the existing one.

**Primary recommendation:** Execute the restructure in this exact order: (1) pyproject.toml + ruff, (2) move files + update imports, (3) run benchmark immediately, (4) delete dead code, (5) configure pre-commit, (6) rename evals, (7) add league_standings view.

---

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| INFRA-01 | Repo reorganized to `src/basic_stats/`, `src/shared/`, `tests/`, `evals/` — all imports verified working, 61/61 benchmark passing after restructure | Import graph fully mapped below; path anchoring verified |
| INFRA-02 | Dead code deleted: legacy/, v0–v5 runners, old benchmarks, test_embeddings.py, .lnk, miniprueba.py, setup.py, egg-info/ | All dead files confirmed not imported by any live code |
| INFRA-03 | `pyproject.toml` with ruff config, pinned deps, uv as package manager | uv 0.10.6 installed; openai 2.15.0 already in venv; full dep list verified |
| INFRA-04 | `.pre-commit-config.yaml` with ruff + basic hooks, passes on first commit | ruff/pre-commit not yet installed; need `uv add --dev` |
| INFRA-05 | `evals/eval_runner.py` + `evals/questions_benchmark.json` — single source of truth, 61/61 confirmed | Path changes mapped; BENCHMARK_PATH must use `Path(__file__).parent`; output filename must change from `v6` to plain |
| CTX-02 (tail) | `league_standings` DuckDB view from `team_match_stats` data | Schema confirmed; `team_match_stats` has all needed columns; SQL template provided below |

---

## Standard Stack

### Core (already installed in .venv)
| Library | Version (actual) | Purpose |
|---------|-----------------|---------|
| openai | 2.15.0 | LLM API — already correct in venv, wrong in requirements.txt |
| duckdb | 1.5.1 | Analytical queries over parquet |
| polars | 1.39.0 | DataFrame ops in query planner |
| pydantic | 2.12.5 | Model schemas |
| streamlit | 1.31.0 | UI framework |
| pandas | 2.3.3 | Eval runner DataFrames |
| pyarrow | 23.0.1 | Parquet reads |

### Dev Tools (not yet installed)
| Tool | Recommended Version | Purpose |
|------|-------------------|---------|
| ruff | >=0.9.0 (latest stable) | Linter + formatter, replaces flake8/black/isort |
| pre-commit | >=3.7.0 | Git hook management |
| pytest | >=8.0.0 | Test runner for unit tests |

**Installation via uv:**
```bash
uv add --dev ruff pre-commit pytest
```

---

## Architecture Patterns

### Proposed New Structure
```
project_root/
├── src/
│   ├── __init__.py              # Required for "src.basic_stats.*" imports to work
│   └── basic_stats/
│       ├── __init__.py          # Required
│       ├── agent.py             # from utils/basic_stats/core/
│       ├── config.py
│       ├── duckdb_manager.py
│       ├── knowledge_base.py
│       ├── llm_query_engine_v2.py
│       ├── models.py
│       ├── query_planner.py
│       └── prompts/
│           ├── resolve_query_intent.yaml
│           ├── resolve_metric.yaml
│           └── verbalize.yaml
├── tests/
│   ├── __init__.py
│   ├── test_query_planner.py    # from utils/basic_stats/core/
│   └── test_dual_bucket_hardening.py
├── evals/
│   ├── eval_runner.py           # renamed from eval_runner_v6.py
│   └── questions_benchmark.json # renamed from questions_benchmark_v6.json
├── pages/
│   └── basic_stats.py           # import changes: src.basic_stats.agent
├── utils/                       # KEEP as-is (shared, used by other pages)
│   ├── __init__.py
│   ├── page_components.py
│   ├── utils.py
│   ├── embeddings_utils.py
│   ├── sentences.py
│   ├── font_helpers.py
│   ├── gemini.py
│   └── datalib/
├── pyproject.toml
├── .pre-commit-config.yaml
├── app.py
└── settings.py
```

**Note on `src/shared/`:** The INFRA-01 requirement mentions `src/shared/`. However, the shared utilities (`utils/page_components.py`, `utils/utils.py`, etc.) are used by ALL pages (not just basic_stats). Moving them to `src/shared/` would require updating every page. Recommend: create `src/shared/` as an empty placeholder for Phase 4, or move only files with no cross-page references. See Open Questions.

---

## Complete Import Graph (verified by codebase scan)

### Files that import `utils.basic_stats.core.*` — MUST BE UPDATED

| File | Current Import | New Import |
|------|---------------|------------|
| `pages/basic_stats.py:8` | `from utils.basic_stats.core.agent import BasicStatsAgent` | `from src.basic_stats.agent import BasicStatsAgent` |
| `eval_runner_v6.py:30` | `from utils.basic_stats.core.llm_query_engine_v2 import LLMQueryEngineV2` | `from src.basic_stats.llm_query_engine_v2 import LLMQueryEngineV2` |
| `utils/basic_stats/core/agent.py:1` | `from utils.basic_stats.core.knowledge_base import KnowledgeBase` | `from src.basic_stats.knowledge_base import KnowledgeBase` |
| `utils/basic_stats/core/agent.py:2` | `from utils.basic_stats.core.llm_query_engine_v2 import LLMQueryEngineV2` | `from src.basic_stats.llm_query_engine_v2 import LLMQueryEngineV2` |
| `utils/basic_stats/core/llm_query_engine_v2.py:20–29` | `from utils.basic_stats.core.config import ...` etc. | `from src.basic_stats.config import ...` etc. |
| `utils/basic_stats/core/query_planner.py:11` | `from utils.basic_stats.core.config import ...` | `from src.basic_stats.config import ...` |
| `tests/test_query_planner.py` (was core/) | `from utils.basic_stats.core.query_planner import ...` | `from src.basic_stats.query_planner import ...` |
| `tests/test_dual_bucket_hardening.py` (was core/) | `from utils.basic_stats.core.llm_query_engine_v2 import ...` | `from src.basic_stats.llm_query_engine_v2 import LLMQueryEngineV2` |

### Files that are DEAD — safe to delete without updating

| File | Reason Safe |
|------|-------------|
| `eval_runner.py` | Imports `utils.basic_stats.agent` (non-existent path already broken) |
| `eval_runner_v2.py` | Imports `utils.basic_stats.llm_query_engine_v2` (non-existent) |
| `eval_runner_v3.py` | Imports `utils.basic_stats.core.llm_query_engine_v2` (could work but is v3 dead) |
| `eval_runner_v4.py` | Superseded by v6 |
| `eval_runner_v5.py` | Superseded by v6 |
| `eval_llm_engine.py` | Imports non-existent `utils.basic_stats.llm_query_engine_v2` path |
| `utils/basic_stats/legacy/*.py` | Not imported anywhere in live code |
| `utils/basic_stats/core/miniprueba.py` | One-off debug script |
| `test_embeddings.py` (root) | Not connected to basic_stats pipeline |
| `setup.py` | Superseded by pyproject.toml |
| `twelve_gpt_educational.egg-info/` | Stale build artifact from setup.py install |
| `twelve-gpt-educational - Shortcut.lnk` | Windows desktop shortcut, not code |
| `questions_benchmark_raw.json` | Superseded by v6 |
| `questions_benchmark_v4.json` | Superseded by v6 |
| `questions_benchmark_v5.json` | Superseded by v6 |

### Files that STAY in `utils/` — do NOT move

| File | Reason |
|------|--------|
| `utils/page_components.py` | Used by app.py and ALL pages (about, embedder, football_scout, shots, own_page, personality_test, quality_builder, wvs_chat) |
| `utils/utils.py` | Used by pages/embedder, football_scout, own_page, shots, wvs_chat |
| `utils/embeddings_utils.py` | Used by classes/embeddings.py |
| `utils/sentences.py` | Used by classes/visual.py |
| `utils/font_helpers.py` | Shared util |
| `utils/gemini.py` | Used by classes/chat.py and classes/description.py |
| `utils/datalib/` | Independent utility |

### `aliases_para_ricardo.json`
Not imported by any Python file (verified via grep). **Safe to delete or leave.** It is in `utils/basic_stats/` but has zero references. Recommend: delete with dead code (INFRA-02).

### `utils/basic_stats/verbal_model.py` (at package root, not core/)
Used only by legacy runners and the old `eval_runner.py`. Not imported by any live code path. **Safe to delete.**

---

## Path Anchoring: Critical Changes Required

### config.py — parents depth changes
```python
# CURRENT (utils/basic_stats/core/config.py):
BASE = Path(__file__).resolve().parents[3]      # utils/basic_stats/core -> root (3 hops up)
PROMPTS_DIR = BASE / "utils" / "basic_stats" / "prompts"

# NEW (src/basic_stats/config.py):
BASE = Path(__file__).resolve().parents[2]      # src/basic_stats -> root (2 hops up)
PROMPTS_DIR = BASE / "src" / "basic_stats" / "prompts"
```

### duckdb_manager.py — parents depth changes
```python
# CURRENT (utils/basic_stats/core/duckdb_manager.py):
BASE = Path(__file__).resolve().parents[3]      # 3 hops to root

# NEW (src/basic_stats/duckdb_manager.py):
BASE = Path(__file__).resolve().parents[2]      # 2 hops to root
```

### knowledge_base.py — parents depth changes
```python
# CURRENT (utils/basic_stats/core/knowledge_base.py):
BASE = Path(__file__).resolve().parents[3]

# NEW (src/basic_stats/knowledge_base.py):
BASE = Path(__file__).resolve().parents[2]
```

**All three use `BASE / "output" / ...` and `BASE / "data" / ...` — these paths stay valid because output/ and data/ remain at project root.**

---

## eval_runner.py Changes After Rename

Three changes needed in `eval_runner_v6.py` → `evals/eval_runner.py`:

1. **BENCHMARK_PATH** — change from relative-to-cwd to relative-to-file:
   ```python
   # OLD:
   BENCHMARK_PATH = "questions_benchmark_v6.json"
   # NEW:
   BENCHMARK_PATH = str(Path(__file__).parent / "questions_benchmark.json")
   ```

2. **Import path** — after src restructure:
   ```python
   # OLD:
   from utils.basic_stats.core.llm_query_engine_v2 import LLMQueryEngineV2
   # NEW:
   from src.basic_stats.llm_query_engine_v2 import LLMQueryEngineV2
   ```

3. **Output filenames** — strip `_v6` suffix so UI picks it up:
   ```python
   # OLD:
   latest_path = OUTPUT_DIR / "latest_eval_results_v6.json"
   dated_path  = OUTPUT_DIR / f"{timestamp}_eval_results_v6.json"
   # NEW:
   latest_path = OUTPUT_DIR / "latest_eval_results.json"
   dated_path  = OUTPUT_DIR / f"{timestamp}_eval_results.json"
   ```
   Also update argparse description and any docstring references to "v6".

4. **sys.path.insert(0, ".")** — keep this line; it ensures imports work when run as `python evals/eval_runner.py` from project root.

---

## pyproject.toml Structure

Python 3.12.8, uv 0.10.6 confirmed installed. No `pyproject.toml` exists yet. Recommended structure:

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
    "E501",  # line too long (handled by formatter)
    "F401",  # unused imports (will be cleaned up incrementally)
]

[tool.ruff.format]
quote-style = "double"
indent-style = "space"

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_functions = ["test_*", "run_*"]
```

**Note on `openai[embeddings]==0.28.1`:** The current `requirements.txt` has two conflicting openai lines. The venv already has `openai==2.15.0` which is correct. The `pyproject.toml` pins `openai==2.15.0` only, dropping the old `[embeddings]` extra (no longer needed with the v2 API).

**Note on `google-generativeai==0.7.2`:** Kept as pinned; not part of basic_stats but used by `utils/gemini.py`.

---

## .pre-commit-config.yaml Structure

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

**Installation:**
```bash
uv add --dev pre-commit
.venv/bin/pre-commit install
```

**First-run behavior:** ruff will auto-fix trailing whitespace, import order, and basic style issues. The `--fix` flag means the first commit will likely modify files — this is expected. Commit the ruff-fixed files as part of the pyproject.toml setup task.

**What ruff will flag in the existing code (anticipate):**
- Import order in several files (will auto-fix with `--fix`)
- F-string in SQL (will NOT flag — these are intentional, not ruff's concern)
- Possibly `E711` comparison to None patterns in some test files

---

## league_standings DuckDB View

The `league_table` view already exists in `duckdb_manager.py` (line 128) and is built from `player_match_stats` via a complex grouping. It works and is used in all three query methods via `LEFT JOIN league_table`.

The tail task requires a `league_standings` view built **directly from `team_match_stats`**, which is the more correct and efficient source. This should be added as an **additional** view alongside `league_table` (do not replace `league_table` yet — all existing JOINs reference it).

The `team_match_stats` parquet confirmed schema:
- `team_id`, `team_name`, `opponent_team_id`, `opponent_team_name`
- `is_home`, `team_score`, `opponent_score`
- `points` (pre-computed: 3/1/0), `is_win`, `is_draw`, `is_loss`
- `goal_difference` (pre-computed)

**Proposed SQL for `_register_base_views()` addition:**
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

**Sample standings output (verified against actual data):**
Liverpool 84 pts, Arsenal 74 pts, Manchester City 71 pts, Chelsea 69 pts, Aston Villa 66 pts (confirmed correct for 38-game season, 20 teams).

**Relationship to existing `league_table` view:** `league_standings` is a strict superset — it adds `matches_played`, `wins`, `draws`, `losses`, and renames `final_rank` to `position`. The `league_table` view and all its JOINs remain untouched in Phase 4. `league_standings` is created in addition.

---

## Safe Order of Operations

This is the highest-risk section. Execute in this exact order to minimize time with broken state:

### Step 1 — pyproject.toml + ruff install (no import changes)
1. Create `pyproject.toml` with deps and ruff config
2. `uv add --dev ruff pre-commit pytest` to install dev tools
3. Run `ruff check --fix .` on the existing codebase (auto-fix imports/style before moving files)
4. Commit: `chore: add pyproject.toml with ruff config and pinned deps`
5. Benchmark: still passes 61/61 (no code moved yet)

### Step 2 — Create src/ skeleton
1. `mkdir -p src/basic_stats/prompts tests evals`
2. Create `src/__init__.py` and `src/basic_stats/__init__.py` (empty)
3. Create `tests/__init__.py` (empty)
4. Do NOT move any files yet

### Step 3 — Move and update imports atomically
Move all 7 source files at once, update all imports in one batch:
1. Copy (don't delete yet) `utils/basic_stats/core/*.py` → `src/basic_stats/`
2. Copy `utils/basic_stats/prompts/*.yaml` → `src/basic_stats/prompts/`
3. In each moved file: update `parents[3]` → `parents[2]`, update `utils.basic_stats.core` → `src.basic_stats`
4. In `config.py`: update `PROMPTS_DIR` path to `BASE / "src" / "basic_stats" / "prompts"`
5. Update `pages/basic_stats.py` import
6. Run benchmark: `python eval_runner_v6.py` — must still be 61/61 (still uses old utils path)
7. NOW delete originals from `utils/basic_stats/core/`
8. Run benchmark again with the new imports: confirm 61/61

### Step 4 — Delete dead code
Delete in this order (least risk to most risk):
1. `utils/basic_stats/legacy/` (confirmed no live imports)
2. `utils/basic_stats/verbal_model.py` (no live imports)
3. `utils/basic_stats/aliases_para_ricardo.json` (no imports at all)
4. `eval_runner.py`, `eval_runner_v2.py`, `eval_runner_v3.py`, `eval_runner_v4.py`, `eval_runner_v5.py`, `eval_llm_engine.py`
5. `questions_benchmark_raw.json`, `questions_benchmark_v4.json`, `questions_benchmark_v5.json`
6. `test_embeddings.py`, `miniprueba.py` (already moved from core/)
7. `setup.py`, `twelve_gpt_educational.egg-info/`, `twelve-gpt-educational - Shortcut.lnk`
8. Run `python eval_runner_v6.py` — confirm 61/61 still

### Step 5 — Move tests to tests/
1. Move `utils/basic_stats/core/test_query_planner.py` → `tests/test_query_planner.py`
2. Move `utils/basic_stats/core/test_dual_bucket_hardening.py` → `tests/test_dual_bucket_hardening.py`
3. Update imports in both test files to `src.basic_stats.*`
4. Run `python -m pytest tests/test_query_planner.py` from project root (note: these are smoke tests requiring LLM, may be manual-only in CI)

### Step 6 — Configure pre-commit
1. Create `.pre-commit-config.yaml`
2. `pre-commit install`
3. `pre-commit run --all-files` — fix any ruff findings
4. Make a test commit to verify hooks pass

### Step 7 — Rename evals
1. Copy `eval_runner_v6.py` → `evals/eval_runner.py`, apply 3 changes (BENCHMARK_PATH, import, output filenames)
2. Copy `questions_benchmark_v6.json` → `evals/questions_benchmark.json`
3. Delete `eval_runner_v6.py` and `questions_benchmark_v6.json`
4. Run `python evals/eval_runner.py` from project root — confirm 61/61
5. Verify `docs/evals/latest_eval_results.json` is updated (not `latest_eval_results_v6.json`)

### Step 8 — Add league_standings view (tail task)
1. Add `league_standings` CREATE statement to `DuckDBManager._register_base_views()` in `src/basic_stats/duckdb_manager.py`
2. Run benchmark: 61/61 (this view is additive, no existing behavior changes)
3. Manual verification: `python -c "from src.basic_stats.duckdb_manager import DuckDBManager; db=DuckDBManager(); print(db.query_dicts('SELECT * FROM league_standings ORDER BY position LIMIT 5'))"`

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead |
|---------|-------------|-------------|
| Linting + formatting | Custom scripts | ruff (handles both, replaces flake8+black+isort) |
| Git hooks | Shell scripts | pre-commit |
| Dependency pinning | requirements.txt editing | pyproject.toml + uv |
| Path resolution across Python versions | os.path gymnastics | `Path(__file__).resolve().parents[N]` |

---

## Common Pitfalls

### Pitfall 1: Missing `__init__.py` in src/
**What goes wrong:** `from src.basic_stats.agent import ...` raises `ModuleNotFoundError: No module named 'src'`
**Why it happens:** Python only traverses `__init__.py` chains. `utils/` has `__init__.py`; a new `src/` directory does not automatically get one.
**How to avoid:** Create `src/__init__.py` AND `src/basic_stats/__init__.py` before running any imports.
**Warning signs:** Import error mentions `src` not `basic_stats`

### Pitfall 2: Wrong `parents[N]` depth after move
**What goes wrong:** `config.py` and `duckdb_manager.py` use `Path(__file__).resolve().parents[3]` to find the project root. After moving from `utils/basic_stats/core/` (3 levels deep) to `src/basic_stats/` (2 levels deep), `parents[3]` would point one directory ABOVE the project root.
**Why it happens:** File depth changes from 3 to 2.
**How to avoid:** Change `parents[3]` to `parents[2]` in all three files: `config.py`, `duckdb_manager.py`, `knowledge_base.py`.
**Warning signs:** FileNotFoundError on parquet paths or DuckDB connect fails

### Pitfall 3: BENCHMARK_PATH relative to cwd vs. file location
**What goes wrong:** `eval_runner.py` currently uses `BENCHMARK_PATH = "questions_benchmark_v6.json"` — a path relative to the current working directory. When moved to `evals/`, the file `evals/questions_benchmark.json` won't be found unless called from project root AND the path is updated.
**Why it happens:** `Path("evals/questions_benchmark.json")` and `Path(__file__).parent / "questions_benchmark.json"` are equivalent only when cwd is project root.
**How to avoid:** Use `Path(__file__).parent / "questions_benchmark.json"` for portability.

### Pitfall 4: Pre-commit ruff fails on first run due to auto-fix
**What goes wrong:** `pre-commit run` exits with non-zero because ruff modified files (auto-fixed imports/whitespace). The commit is rejected — but the changes are correct.
**Why it happens:** Pre-commit hooks with `--fix` modify files and exit non-zero to signal the working tree changed.
**How to avoid:** After `pre-commit run --all-files`, stage the ruff-fixed changes and commit again. This is expected behavior.

### Pitfall 5: `eval_runner_v6.py` output overwrites `latest_eval_results_v6.json` but UI checks `latest_eval_results.json`
**What goes wrong:** Pages/basic_stats.py benchmark status shows "unavailable" because no file matches `docs/evals/latest_eval_results.json`.
**Why it happens:** The save_results function in v6 writes `_v6.json`. The UI was written to check the v4 filename or a plain name.
**How to avoid:** When renaming to `evals/eval_runner.py`, change the output filename to `latest_eval_results.json`.

### Pitfall 6: Deleting `utils/basic_stats/` before updating OTHER pages
**What goes wrong:** If `utils/basic_stats/core/` is deleted before `pages/basic_stats.py` is updated, Streamlit hot-reloads fail immediately.
**Why it happens:** Streamlit imports all page modules at startup.
**How to avoid:** Follow Step-by-Step order above: update pages/ BEFORE deleting originals.

### Pitfall 7: `config.py` PROMPTS_DIR still points to old location
**What goes wrong:** LLM calls fail with `FileNotFoundError` for yaml prompt files because `PROMPTS_DIR` still resolves to `utils/basic_stats/prompts/` after the move.
**Why it happens:** `PROMPTS_DIR = BASE / "utils" / "basic_stats" / "prompts"` is hardcoded.
**How to avoid:** Update to `PROMPTS_DIR = BASE / "src" / "basic_stats" / "prompts"`. The yaml files move with the rest of `src/basic_stats/`.

---

## Runtime State Inventory

| Category | Items Found | Action Required |
|----------|-------------|-----------------|
| Stored data | DuckDB file at `db/basic_stats.duckdb` — views are registered at connect time, not persisted | No data migration; views recreate automatically each connect |
| Live service config | Streamlit `docs/evals/latest_eval_results.json` and `latest_eval_results_v4.json` exist; UI reads them at startup | Rename output in `save_results()` only; existing files can stay |
| OS-registered state | None — no Task Scheduler, pm2, or launchd config found | None |
| Secrets/env vars | Streamlit secrets: `GPT_KEY`, `GPT_VERSION`, `GPT_CHAT_MODEL` — code renames only, no key names change | None |
| Build artifacts | `twelve_gpt_educational.egg-info/` — stale from `pip install -e .` run against old `setup.py`; project NOT in venv pip list | Delete as part of INFRA-02; no reinstall needed (project not installed) |

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | All | ✓ | 3.12.8 | — |
| uv | pyproject.toml, package management | ✓ | 0.10.6 | pip |
| ruff | INFRA-03, INFRA-04 | ✗ (not in venv) | — | `uv add --dev ruff` |
| pre-commit | INFRA-04 | ✗ (not in venv) | — | `uv add --dev pre-commit` |
| pytest | tests/ | ✗ (not in venv) | — | `uv add --dev pytest` |
| openai 2.15.0 | LLM calls | ✓ (in venv) | 2.15.0 | — |
| duckdb 1.5.1 | All queries | ✓ (in venv) | 1.5.1 | — |
| polars 1.39.0 | Query planner | ✓ (in venv) | 1.39.0 | — |

**Missing with no fallback:** None — all missing tools install via `uv add --dev`.

---

## Validation Architecture

`nyquist_validation` is set to `false` in `.planning/config.json`. Skipping formal test matrix per config. However, the benchmark is the de-facto acceptance gate for this phase:

**Benchmark gate (mandatory at each step):**
```bash
# From project root
python eval_runner_v6.py   # Steps 1–4 (before eval rename)
python evals/eval_runner.py # Steps 7–8 (after eval rename)
```
Pass criteria: `61/61` in summary output.

**Smoke test for league_standings:**
```bash
python -c "
from src.basic_stats.duckdb_manager import DuckDBManager
db = DuckDBManager()
rows = db.query_dicts('SELECT position, team_name, points FROM league_standings ORDER BY position LIMIT 5')
for r in rows: print(r)
db.close()
"
```
Expected: Liverpool position=1 points=84.

---

## Open Questions

1. **Should `src/shared/` contain anything in Phase 4?**
   - What we know: INFRA-01 mentions `src/shared/` but all shared utils (`utils/page_components.py`, etc.) are used by non-basic_stats pages. Moving them would require updating 8+ page files.
   - What's unclear: Is the intent to create an empty `src/shared/` as a placeholder, or to actually migrate shared utils?
   - Recommendation: Create empty `src/shared/__init__.py` as a placeholder. Do not migrate shared utils until Phase 5+ when the scope is clearer.

2. **Should the test files in `tests/` run in CI without LLM credentials?**
   - What we know: `test_dual_bucket_hardening.py` makes live LLM + DuckDB calls (requires `GPT_KEY` secret). `test_query_planner.py` also calls LLM functions.
   - What's unclear: Are Streamlit secrets available in the CI environment where pre-commit runs?
   - Recommendation: For Phase 4, move the test files but do NOT add them to pre-commit hooks. Mark them as manual-only smoke tests in comments. Phase 5 can introduce a mock/fixture layer.

3. **`eval_runner_v3.py` — dead or alive?**
   - What we know: It imports `from utils.basic_stats.core.llm_query_engine_v2 import LLMQueryEngineV2` — a valid path that currently works.
   - What's unclear: Is it used by anyone? No page or other file imports it.
   - Recommendation: Treat as dead code (standalone script, superseded by v6). Delete in INFRA-02.

---

## Sources

### Primary (HIGH confidence — direct codebase inspection)
- `/Users/ricardoheredia/Twelve-GPT-Educational/utils/basic_stats/core/*.py` — all 7 active source files read and import graph mapped
- `/Users/ricardoheredia/Twelve-GPT-Educational/eval_runner_v6.py` — full file read
- `/Users/ricardoheredia/Twelve-GPT-Educational/pages/basic_stats.py` — full file read
- `/Users/ricardoheredia/Twelve-GPT-Educational/requirements.txt` — full file read
- `grep -rn "from utils.basic_stats"` — exhaustive import scan
- DuckDB parquet schema — verified via `pyarrow.parquet.read_schema()`
- `pip list` in `.venv` — actual installed versions verified

### Secondary (MEDIUM confidence)
- uv documentation pattern for `pyproject.toml` with `[tool.hatch.build]` — standard src-layout pyproject pattern
- ruff default rule selection (E, F, I, W) — well-established minimal viable ruleset
- pre-commit ruff integration from `astral-sh/ruff-pre-commit` — official recommended approach

---

## Metadata

**Confidence breakdown:**
- Import graph: HIGH — verified by grep scan of all .py files
- Path anchoring: HIGH — verified by Python computation
- Parquet schema: HIGH — read directly from binary
- pyproject.toml structure: MEDIUM — standard pattern, exact ruff version from PyPI query failed (use `>=0.9.0`)
- pre-commit config: MEDIUM — standard ruff integration, versions approximate

**Research date:** 2026-04-12
**Valid until:** 2026-05-12 (stable domain, no fast-moving dependencies)
