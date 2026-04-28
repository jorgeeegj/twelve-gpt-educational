# Synthetic UAT Fixtures

Discovery infrastructure for Phase 10 (Self-Generated Robustness / Synthetic UAT).

## Files

- `seed_questions.json` — hand-authored seed fixture covering all 12 failure categories (see `.planning/phases/10-self-generated-robustness-synthetic-uat/10-SPEC.md` section 2).
- `__init__.py` — Python package marker so `evals.synthetic_runner` can import.

## Schema

Every entry MUST have:

| Field | Type | Notes |
|-------|------|-------|
| `id` | string | `SYN_<NNN>` zero-padded 3 digits |
| `category` | string | One of the 12 enum values from 10-SPEC.md section 2 |
| `language` | string | `en` or `es` |
| `question` | string | NL question. Multi-turn chains use `\|` as turn separator (no spaces) |
| `expected_behavior` | string | `answerable` \| `refuse` \| `ambiguous_clarify` |
| `expected_values` | object \| null | Mirrors `evals/questions_benchmark.json` shape; null when not answerable or list-typed |
| `notes` | string | Optional rationale or edge-case marker |

## How to add a question

1. Pick a category from the 12 enum values.
2. Append a new entry to `seed_questions.json` with the next sequential `SYN_<NNN>` id.
3. Validate JSON: `python -c "import json; json.load(open('evals/synthetic/seed_questions.json'))"`.
4. Run the synthetic runner (Plan 03) to confirm the entry executes.
5. Do NOT modify production code (`src/basic_stats/*`) as part of adding a question — that is out of scope for Phase 10.

## Run outputs

Run outputs land in `evals/runs/<timestamp>__synthetic_<label>/` and are gitignored.
Do NOT stage them.

## See also

- `.planning/phases/10-self-generated-robustness-synthetic-uat/10-SPEC.md` — full contract
- `evals/questions_benchmark.json` — reference for `expected_values` shape
- `evals/random_questions.json` — demo-style question reference
