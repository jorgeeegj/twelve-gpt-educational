---
phase: 10-self-generated-robustness-synthetic-uat
plan: "02"
subsystem: evals/synthetic
tags: [synthetic-uat, fixtures, seed-questions, phase10]
dependency_graph:
  requires: [10-01-PLAN (10-SPEC.md)]
  provides: [evals/synthetic/seed_questions.json, evals/synthetic/__init__.py, evals/synthetic/README.md]
  affects: [10-03-PLAN (runner), 10-04-PLAN (clusterer)]
tech_stack:
  added: []
  patterns: [JSON fixture array, Python package marker]
key_files:
  created:
    - evals/synthetic/__init__.py
    - evals/synthetic/seed_questions.json
    - evals/synthetic/README.md
  modified: []
decisions:
  - "Used exact 24-entry fixture specified in plan — no extra entries added (plan was fully self-contained)"
  - "expected_values set to null for entries where numeric ground truth is not pinned at fixture-time (judge_faithfulness skips null entries per Plan 03 contract)"
  - "Multi-turn chains encoded with pipe separator in question field (SYN_007, SYN_008)"
metrics:
  duration_seconds: 178
  completed_date: "2026-04-28"
  tasks_completed: 2
  files_created: 3
---

# Phase 10 Plan 02: Seed Synthetic Fixture Summary

Hand-authored 24-question seed fixture for Phase 10 synthetic UAT, covering all 12 failure-taxonomy categories with Spanish entries, multi-turn chains, and known edge cases (Tottenham Europa League, Top 6 vs Big Six, contextual p90).

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Seed fixture + package marker | 1a350c8 | evals/synthetic/__init__.py, evals/synthetic/seed_questions.json |
| 2 | README — schema, how-to-add, links | e596a00 | evals/synthetic/README.md |

## Files Committed

3 files total:

1. `evals/synthetic/__init__.py` — Python package marker with docstring "Synthetic UAT fixture package — Phase 10."
2. `evals/synthetic/seed_questions.json` — 24 hand-authored seed questions (see breakdown below)
3. `evals/synthetic/README.md` — schema table, 5-step how-to-add guide, links to 10-SPEC.md

## Question Count and Per-Category Breakdown

Total: **24 questions**

| Category | Count | IDs |
|----------|-------|-----|
| DIRECT_STATS | 2 | SYN_001, SYN_002 |
| RANKINGS | 2 | SYN_003, SYN_004 |
| COMPARISONS | 2 | SYN_005, SYN_006 |
| FOLLOW_UPS | 2 | SYN_007, SYN_008 |
| TOP6_VS_BIG6 | 2 | SYN_009, SYN_010 |
| CHAMPIONS_LEAGUE | 2 | SYN_011, SYN_012 |
| P90_METRICS | 2 | SYN_013, SYN_014 |
| HOME_AWAY | 2 | SYN_015, SYN_016 |
| SPANISH_ENGLISH | 2 | SYN_017 (es), SYN_018 (es) |
| UNSUPPORTED_FUTURE | 2 | SYN_019, SYN_020 |
| AMBIGUOUS | 2 | SYN_021, SYN_022 |
| DEMO_RANDOM | 2 | SYN_023, SYN_024 |

## Edge Cases Included

- **Tottenham Europa League Champions League qualification**: SYN_011 (all-routes, must include Tottenham) and SYN_012 (strictly via league position, should exclude Tottenham)
- **Top 6 vs Big Six distinction**: SYN_009 ("top 6 teams" = standings rank 1–6) vs SYN_010 ("Big Six" = canonical static set)
- **Contextual p90 regression**: SYN_014 (Salah xG per 90 against Big Six — closed by WI-2 hotfix)
- **Spanish away-wins**: SYN_017 ("¿Cuántos partidos ha ganado Liverpool fuera de casa?") — known prior friction
- **Multi-turn chains**: SYN_007 (Haaland 4-turn: goals → vs top6 → comparison → per90), SYN_008 (Arsenal top scorer → Liverpool → per90)
- **Future-tense refusals**: SYN_019 (next matchday), SYN_020 (next season)
- **Ambiguous cold-start**: SYN_021 ("How is he doing?"), SYN_022 ("What about the rest?")

## Pending

- Plan 03 (runner): consumes this fixture via `json.load(open('evals/synthetic/seed_questions.json'))`
- Plan 04 (clusterer): groups entries by `category` field
- Plan 05 (regression scaffold): `tests/test_synthetic_regressions.py`
- Plan 06 (verification + STATE update)

## Deviations from Plan

None — plan executed exactly as written. The 24 entries were fully specified in the plan body; no additions or modifications were needed.

## Self-Check: PASSED

Files exist:
- FOUND: evals/synthetic/__init__.py
- FOUND: evals/synthetic/seed_questions.json
- FOUND: evals/synthetic/README.md

Commits exist:
- FOUND: 1a350c8 (feat(10-02): add synthetic fixture package)
- FOUND: e596a00 (docs(10-02): add README.md)

Verification results:
- 24 questions, 12 categories: PASS
- Spanish entries present: PASS
- All required fields present: PASS
- All expected_behavior values valid: PASS
- Tottenham CL edge case in notes: PASS
- src/basic_stats/ untouched: PASS
