# Codebase Concerns

**Analysis Date:** 2026-03-26

## Tech Debt

**Incomplete dependency declaration:**
- Issue: `setup.py` line 11 has TODO marker noting dependencies are incomplete — only lists `streamlit`, `pandas`, `tiktoken` but `requirements.txt` has 14+ packages
- Files: `setup.py`
- Impact: Installation via setup.py will fail or be incomplete; developers should use requirements.txt directly
- Fix approach: Complete the install_requires list in setup.py to match requirements.txt, or remove setup.py if requirements.txt is the source of truth

**Hardcoded API endpoint:**
- Issue: Azure OpenAI endpoint hardcoded to `https://twelve-courses.openai.azure.com` instead of using environment variable
- Files: `utils/basic_stats/core/config.py` line 15
- Impact: Endpoint cannot be changed without code modification; configuration is non-portable
- Fix approach: Move endpoint to `st.secrets["AZURE_ENDPOINT"]` or similar, with fallback default

**Overlapping OpenAI SDK versions:**
- Issue: `requirements.txt` specifies both `openai==0.28.1` (legacy) and `openai[embeddings]==0.28.1`, but code imports `AzureOpenAI` from newer openai 1.0+ API
- Files: `utils/embeddings_utils.py`, `classes/description.py`, `utils/basic_stats/core/config.py`
- Impact: Version mismatch will cause runtime ImportError or API incompatibility
- Fix approach: Align openai package version — upgrade to `openai>=1.0.0` and update all code to new API

**Legacy code directory not cleaned:**
- Issue: `utils/basic_stats/legacy/` contains 6 unused files from previous implementations never imported
- Files: `utils/basic_stats/legacy/*` (~271 lines unused)
- Impact: Dead code increases maintenance burden and confusion about which code is actually used
- Fix approach: Archive or remove legacy directory; document migration path if code is needed

**Multiple eval_runner iterations:**
- Issue: 5 versions of eval_runner exist (`eval_runner.py` through `eval_runner_v5.py`); unclear which is current
- Files: `eval_runner.py`, `eval_runner_v2.py`, `eval_runner_v3.py`, `eval_runner_v4.py`, `eval_runner_v5.py`
- Impact: Confusion about which version to run; potential for running stale benchmarks
- Fix approach: Keep only active eval_runner, archive/delete others, or structure as versioned modules

## Known Bugs

**Async/sync mismatch in embedding clients:**
- Issue: `utils/embeddings_utils.py` calls `_get_azure_embedding_client()` in async function `aget_embedding()` but only `_get_embedding_client()` exists (no async variant defined)
- Files: `utils/embeddings_utils.py` lines 49–66
- Impact: Async embedding functions will fail at runtime with AttributeError
- Workaround: Only use synchronous `get_embedding()` or `get_embeddings()`
- Fix: Define `_get_azure_embedding_client()` or use unified client initialization

**Missing method in async embeddings:**
- Issue: `aget_embeddings()` calls undefined `_get_azure_embedding_client()` while sync version uses different client factory
- Files: `utils/embeddings_utils.py` line 107
- Impact: Async batch embeddings will crash
- Fix: Align client factory names or use unified client initialization

**Gemini SDK usage uncertainty:**
- Issue: Gemini embedding calls marked with FIXME comments indicating uncertainty about correctness
- Files: `utils/embeddings_utils.py` lines 32, 79
- Impact: Gemini embedding pathway may return incorrect format or fail silently
- Fix: Test Gemini path thoroughly and document expected response format; resolve FIXME comments

## Security Considerations

**Secrets in Streamlit config dependency:**
- Risk: Code assumes `st.secrets` is always populated; if running outside Streamlit context (tests, CLI), missing secrets will crash
- Files: `utils/basic_stats/core/config.py` lines 13–15, `test_embeddings.py` lines 5–10
- Recommendations: Use environment variables as fallback; implement configuration validation; handle missing secrets gracefully

**API key exposure in legacy test code:**
- Risk: `test_embeddings.py` uses deprecated `openai.Embedding.create()` with direct key assignment — outdated Azure auth pattern
- Files: `test_embeddings.py` lines 30–34
- Recommendations: Remove legacy auth pattern; use modern OpenAI client initialization

**Hardcoded Azure endpoint:**
- Risk: Endpoint is visible in source code; production endpoint may be exposed if repo is public
- Files: `utils/basic_stats/core/config.py` line 15
- Recommendations: Move to environment variable or secrets manager

## Performance Bottlenecks

**Large monolithic query planner:**
- Problem: `utils/basic_stats/core/query_planner.py` is ~1405 lines; difficult to test and maintain
- Cause: Query planning logic not modularized; pattern matching, extraction, and orchestration mixed
- Improvement path: Break into focused modules (extractors.py, validators.py, orchestrator.py); add targeted unit tests

**Redundant metric/column definitions:**
- Problem: `NEGATIVE_METRICS`, `PLAYER_COLS`, `TEAM_COLS` defined in multiple places
- Files: `utils/basic_stats/core/llm_query_engine_v2.py` lines 32–73, `utils/basic_stats/core/duckdb_manager.py` lines 21–28
- Improvement path: Create `utils/basic_stats/core/constants.py` as single source of truth

**Polars vs Pandas inconsistency:**
- Problem: Some files use `polars` (`query_planner.py`), others use `pandas` (`data_source.py`, `description.py`) without clear rationale
- Improvement path: Establish data framework standard; document performance tradeoffs

## Fragile Areas

**QueryPlanner NLP fragility:**
- Files: `utils/basic_stats/core/query_planner.py`
- Why fragile: Regex-based pattern extraction is brittle to question variations; LLM-based planner has no unit test suite
- Safe modification: Add test cases for each new question pattern before modifying extraction logic; use eval_runner to validate all benchmark questions before merging
- Test coverage: `test_query_planner.py` has 20+ cases but integration tests still show failing cases (QV4_37, QV4_38, QV5_41)

**Streamlit singleton dependency:**
- Files: `classes/description.py` line 181, `utils/basic_stats/core/config.py` line 13, `test_embeddings.py` line 5
- Why fragile: Hard dependency on `streamlit` for configuration; non-Streamlit code paths (CLI, batch, tests) cannot run without workarounds
- Safe modification: Inject configuration object instead of reading from `st.secrets`

**Exception handling gaps:**
- Files: `classes/description.py` lines 142–144, 156–159
- Why fragile: FIXME comments indicate incomplete exception handling when merging training data; only catches FileNotFoundError
- Safe modification: Enumerate all possible exceptions; add logging for each case

## Scaling Limits

**DuckDB as single-node query engine:**
- Current capacity: Works for in-memory player/team statistics from parquet files; benchmark is 66 questions
- Limit: Query planner and execution are in-process; no distributed query support; DuckDB connection is per-instance
- Scaling path: Migrate to distributed query engine (Presto, Spark) if dataset grows; add caching layer

**LLM verbalization bottleneck:**
- Current capacity: Handles single query verbalization per user interaction; 2 LLM calls per question (planner + verbalize)
- Scaling path: Add request batching; implement result caching; consider retrieval-based answers before LLM generation

## Dependencies at Risk

**Outdated openai package:**
- Risk: `openai==0.28.1` is 2021-era legacy SDK; critical security and API bugs fixed since then
- Impact: Import errors, API incompatibility, security vulnerabilities
- Migration plan: Upgrade to `openai>=1.0.0` and update all code to new async-first API; test with eval_runner_v5

**google-generativeai unstable:**
- Risk: `google-generativeai==0.7.2` pinned to old version; Gemini API rapidly evolving; FIXME comments in code suggest implementation uncertainty
- Migration plan: Upgrade to latest; re-test Gemini paths; resolve FIXME comments

**tiktoken unpinned:**
- Risk: `tiktoken` has no version specified in requirements.txt — will install whatever is latest
- Impact: Reproducibility issues; token counting may vary between installations
- Fix: Pin to specific version (e.g., `tiktoken>=0.5.1`)

## Missing Critical Features

**No request rate limiting:**
- Problem: Code makes unlimited API calls to OpenAI/Gemini; no exponential backoff visible in active code paths
- Recommendation: Implement token bucket rate limiter; add configurable delay between API calls

**No local LLM fallback:**
- Problem: All LLM operations depend on cloud APIs; no offline mode
- Recommendation: Add support for local ollama/LLaMA models as fallback; cache common queries

**No query result caching:**
- Problem: Identical questions re-execute planner + database query + LLM verbalization every time
- Recommendation: Add in-memory or Redis caching layer; implement cache invalidation on data updates

## Test Coverage Gaps

**Core planner lacks unit tests — HIGH:**
- What's not tested: `QueryPlanner` class methods like `resolve_player_name()`, `resolve_metric()`, filter building logic
- Files: `utils/basic_stats/core/query_planner.py` (~1405 lines, no corresponding unit test file)
- Risk: Refactoring breaks hidden assumptions; bugs in filter building go undetected until eval_runner runs

**Async embedding functions broken and untested — CRITICAL:**
- What's not tested: `aget_embedding()`, `aget_embeddings()` in `utils/embeddings_utils.py` lines 49–113
- Risk: Code is broken (calls undefined function) and untestable; will crash at runtime if called

**Data source transformations untested — HIGH:**
- What's not tested: Z-score, rank, pct_rank calculations in `classes/data_source.py` lines 70–95
- Risk: Statistical calculations silently incorrect; player rankings may be wrong

**No tests for exception paths — MEDIUM:**
- What's not tested: FileNotFoundError, exception handling in `classes/description.py` `setup_messages()` lines 137–159
- Risk: Code crashes ungracefully when training data files missing

**Eval runner output not validated — MEDIUM:**
- What's not tested: Output JSON structure from `eval_runner_v5.py`; correctness of evaluation metrics
- Risk: Evaluation results may be incorrect; false positives/negatives in success metrics

---

*Concerns audit: 2026-03-26*
