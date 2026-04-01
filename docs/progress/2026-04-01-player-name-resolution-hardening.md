---
date: 2026-04-01
author: Jorge
scope: Basic Stats Analyst
status: stable — planner alias resolution verified; benchmark confirmed 61/61 after name-resolution fix
---

# Progress Log — 2026-04-01

## Context

Continues directly from:

- `docs/progress/2026-03-30-phase3-contextual-enrichment_verbalization-polish.md`

This is a narrow hardening pass. No new analytics capabilities were added. The only changes are in deterministic player-name resolution within the planner layer.

---

## Scope

All changes in this log are in:

- `utils/basic_stats/core/query_planner.py` — alias map construction, alias matching, normalization

No changes to `llm_query_engine_v2.py`, DuckDB routing logic, benchmark JSON, or eval runner beyond what was already confirmed in prior sessions.

---

## What Was Fixed

### 1. Deterministic player alias resolution

Previously, player-name matching in `_post_process_plan` only scanned the question for `short_name` substrings (e.g. `"e. haaland"`, `"k. walker"`). User queries that used full or partial real names were passed to `_resolve_player_suffix` as a fallback only when the LLM had already set `player_name`. This missed cases where the LLM set a non-canonical name that didn't suffix-match.

**Fix:** Added `_build_player_alias_map()` and `_match_player_alias()` to `QueryPlanner`.

The alias map is built at init from `first_name` / `last_name` columns in `player_full_stats.parquet`. Three alias types per player:

1. `first_name + last_name` (full name)
2. `first_name + last word of last_name` (for multi-word surnames only)
3. unique last-word surname alone (only where that surname maps to exactly one player; ambiguous surnames excluded)

Matching is longest-first substring search in the normalized question. The deterministic alias match always overrides the LLM-extracted `player_name`.

**Examples now resolving correctly:**

| User mention | Resolves to |
|---|---|
| `Haaland` | `E. Haaland` |
| `Erling Haaland` | `E. Haaland` |
| `Erling Braut Haaland` | `E. Haaland` |
| `Kyle Walker` | `K. Walker` |
| `Alexander Isak` | `A. Isak` |
| `Carlos Henrique Casemiro` | `Casemiro` |

### 2. Apostrophe / smart-quote normalization

**Issue:** The alias map stores names from the dataset, which use ASCII apostrophe U+0027 (e.g. `N. O'Reilly`, `last_name = "O'Reilly"`). User queries typed on modern keyboards or copy-pasted from web inputs may use U+2019 (RIGHT SINGLE QUOTATION MARK, the "smart quote"). After `_normalize_text`, the two characters remained distinct, causing substring match to fail silently — the query fell through to a generic `top_n=1` result instead of an entity-value query for the named player.

**Fix:** One line added to `_normalize_text`:

```python
text = re.sub(r"[\u2018\u2019\u02bc]", "'", text)  # smart quotes → ASCII apostrophe
```

Applied after NFKD combining-char removal. Covers:
- U+2018 LEFT SINGLE QUOTATION MARK
- U+2019 RIGHT SINGLE QUOTATION MARK
- U+02BC MODIFIER LETTER APOSTROPHE

Because both alias keys and query text pass through `_normalize_text`, normalization is symmetric — no asymmetry edge cases.

**Examples fixed:**

| User mention | Resolves to |
|---|---|
| `Nico O'Reilly` (U+2019) | `N. O'Reilly` |
| `Nico O'Reilly` (U+0027) | `N. O'Reilly` (already worked) |

---

## Why The Issues Existed

**Alias gap:** The pre-existing `_match_known_name` only matched `short_name` values directly. There was no layer converting full or partial real-name mentions to `short_name`. The LLM sometimes set `player_name` to a full name, but `_resolve_player_suffix` only fired as a fallback and used a weaker suffix heuristic.

**Override ordering bug (now fixed):** The original condition `if matched_player and not plan.filters.player_name:` skipped the alias override when the LLM had already populated `player_name`. Changed to `if matched_player: plan.filters.player_name = matched_player` — deterministic scan always wins.

**Apostrophe gap:** `_normalize_text` stripped diacritics via NFKD but left all other punctuation intact. Unicode typographic apostrophes (U+2019) are structurally unrelated to U+0027 and survived the normalization pass unchanged.

---

## Validation

- **Planner smoke test:** `_match_player_alias` called directly on all named examples above — all resolved to correct canonical `short_name`.
- **Apostrophe fix:** `_normalize_text("Nico O\u2019Reilly")` → `"nico o'reilly"` (U+0027); substring match confirmed `True`.
- **Ambiguity check:** 8 aliases in the map contain apostrophe; all are either full first+last or unique single-surname entries. No new ambiguous aliases introduced.
- **Benchmark:** `eval_runner_v6.py` confirmed **61/61** after the name-resolution pass (run label: `Name_resolution_robustness_fix_v2`). The apostrophe fix was validated at the planner level; a full benchmark rerun with apostrophe-name cases is a sensible follow-up.

---

## Explicitly Out of Scope

- No fuzzy matching added
- No changes to planner routing or DuckDB SQL
- No new analytics paths
- Benchmark JSON not extended with apostrophe-name test cases (intentionally deferred)
- No changes to `llm_query_engine_v2.py` or `eval_runner_v6.py`

---

## Next Step

Add one or two apostrophe-name benchmark entries to `questions_benchmark_v6.json` (e.g. a `carry_meters_gained` query for `N. O'Reilly`) and rerun `eval_runner_v6.py` to lock in the fix at the eval level.
