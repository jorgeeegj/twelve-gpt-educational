---
phase: 11-iterative-synthetic-discovery-loop-v1
plan: "04"
subsystem: testing
tags: [campaign-generator, discovery-loop, synthetic-uat, phase11]

# Dependency graph
requires:
  - phase: 11-01
    provides: "11-SPEC.md locked — §6 campaign generator contract"
provides:
  - "evals/discovery/campaign_generator.py — generate_from_category / generate_from_cluster / write_campaign / generate_with_llm stub"
  - "evals/discovery/campaigns/.gitkeep — directory placeholder"
  - "evals/discovery/CAMPAIGNS.md — usage guide with worked example"
  - "13 unit tests covering all required cases + 3 bonus (12-category sweep, unique IDs, llm=False delegation)"
affects: ["11-05", "11-06", "11-07"]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Stable ID generation: CAMP_<sanitised_category>_<NNN> via modulo index"
    - "Template cycling: i % len(templates) for count > available templates"
    - "Parameter rotation: _PARAM_POOL[key][index % len(pool)] — deterministic, no random"
    - "CAMPAIGNS_DIR monkeypatching via module attribute for test isolation"

key-files:
  created:
    - evals/discovery/campaign_generator.py
    - evals/discovery/campaigns/.gitkeep
    - evals/discovery/CAMPAIGNS.md
    - tests/test_campaign_generator.py
  modified: []

key-decisions:
  - "SPANISH_ENGLISH hardcoded to language='es' regardless of caller's language kwarg — the template is Spanish and _validate_fixture enforces language in {'en','es'}"
  - "generate_with_llm(use_llm=True) raises NotImplementedError — not imported in v1, gating real OpenAI cost"
  - "write_campaign uses module-level CAMPAIGNS_DIR; tests monkeypatch cg.CAMPAIGNS_DIR to tmp_path — avoids polluting real campaigns/ dir"

patterns-established:
  - "All 12 taxonomy categories covered in _TEMPLATES — _validate_fixture passes on generated output"
  - "generate_from_cluster adds notes referencing entry id and signature for traceability"

requirements-completed: [LOOP-04]

# Metrics
duration: 10min
completed: 2026-04-30
---

# Phase 11 Plan 04: Targeted Campaign Generator Summary

**Template-based campaign generator with 12-category coverage, write_campaign helper, CAMPAIGNS.md guide, and 13 unit tests — zero OpenAI cost in default mode**

## Performance

- **Duration:** ~10 min
- **Started:** 2026-04-30T00:40:00Z
- **Completed:** 2026-04-30T00:50:00Z
- **Tasks:** 3
- **Files created:** 4

## Accomplishments

- `evals/discovery/campaign_generator.py` — 5 public functions per 11-SPEC.md §6. All 12 taxonomy categories templated. Generated questions pass `_validate_fixture` unchanged.
- `evals/discovery/campaigns/.gitkeep` — directory placeholder committed.
- `evals/discovery/CAMPAIGNS.md` — usage guide with template-based default, LLM stub note, `iteration_runner` forward reference, naming convention, and Phase-10-grounded worked example.
- `tests/test_campaign_generator.py` — 13 tests (10 required + 3 bonus). All 230 project tests pass.

## Task Commits

1. **Tasks 1-3** — `11c503f` (feat)

## Files Created/Modified

- `evals/discovery/campaign_generator.py`
- `evals/discovery/campaigns/.gitkeep`
- `evals/discovery/CAMPAIGNS.md`
- `tests/test_campaign_generator.py`

## Decisions Made

- `SPANISH_ENGLISH` hardcodes `language="es"` regardless of the `language` kwarg — the Spanish template would fail `_validate_fixture`'s `language in {"en","es"}` check only if language were set to something else, but the semantics are also cleaner.
- `write_campaign` references module-level `CAMPAIGNS_DIR` so tests can `monkeypatch.setattr(cg, "CAMPAIGNS_DIR", tmp_path)` for isolation without touching real campaign files.
- `generate_with_llm` does NOT import `openai` — it raises `NotImplementedError` immediately, keeping the v1 bundle free of the `openai` dependency.

## Deviations from Plan

None. 13 tests (10 required + 3 bonus: 12-category sweep, unique IDs, llm=False delegation).

## Issues Encountered

Minor: `CAMPAIGNS.md` heading "Template-based mode" uses Title Case; the acceptance criterion `grep -q 'template-based'` is case-sensitive. Fixed by adding one lowercase occurrence in the intro sentence.

## Known Stubs

- `generate_with_llm(..., use_llm=True)` raises `NotImplementedError` — LLM-assisted generation deferred to a future phase per 11-SPEC.md §6.

## Next Phase Readiness

- Plan 11-05 (Iteration Runner) can `from evals.discovery.campaign_generator import generate_from_category, write_campaign` directly.
- `CAMPAIGNS_DIR = Path(__file__).parent / "campaigns"` is the canonical campaigns output directory.
- All 230 project tests pass; baseline suite (184) unaffected.

---
*Phase: 11-iterative-synthetic-discovery-loop-v1*
*Completed: 2026-04-30*
