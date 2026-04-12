# Canonicalization Rules — `QueryPlanner`

> **Source of truth:** `src/basic_stats/query_planner.py`
> **Purpose:** Document every deterministic rule applied after LLM raw plan extraction.
> This document is a prerequisite for Phase 5 (FUNC-04).

---

## Overview

The planner pipeline has three stages:

```
LLM raw JSON → _canonicalize_raw_plan() → _post_process_plan() → QueryPlan
```

`_canonicalize_raw_plan` applies broad structural normalization.
`_post_process_plan` validates via Pydantic, then applies name enrichment and coherence guards.

---

## 1. Text normalization

All question strings are lowercased and accent-stripped before rule matching:

```python
q = _normalize_text(question)   # lower + unidecode
```

---

## 2. Entity / subject detection

Two helper functions determine whether the question is about a player or a team:

| Function | Triggers |
|---|---|
| `_targets_player_subject(q)` | "player", "footballer", "striker", "midfielder", "forward", "defender", "goalkeeper", "winger", "scorer", "who scored", "which player", "jugador", "delantero", "mediocampista", "portero", "defensa", "extremo", "goleador" |
| `_targets_team_subject(q)` | "team", "club", "side", "squad", "equipo", "club de fútbol", "which team", "qué equipo" |

**Priority order (highest to lowest):**
1. Matched known player name → `entity_type = "player"`
2. `position` filter is set → `entity_type = "player"`
3. `_targets_player_subject(q)` → `entity_type = "player"`
4. `_targets_team_subject(q)` → `entity_type = "team"`

---

## 3. Player name resolution

Resolution happens in two passes:

**Pass 1 — known name scan:**
`_match_known_name(question, player_names)` — case-insensitive substring scan of all player names in the DB.

**Pass 2 — alias map:**
`_match_player_alias(question)` — scans `_build_player_alias_map()` which derives aliases from DB names:
- Last name only: "Haaland" → "E. Haaland"
- First initial + last name (already canonical form)
- Full first name + last name: "Erling Haaland" → "E. Haaland"

**Pass 3 — suffix resolver:**
`_resolve_player_suffix(name)` — used when LLM returns a partial name (e.g. "Haaland"); finds the first DB player whose name ends with that suffix.

**Temporal-window fallback:**
When `matchday_start` is set but no player was found, scan question tokens word-by-word through the suffix resolver.

**Override rule:** deterministic name scan always overrides LLM-extracted player name.

---

## 4. Team name resolution

- `_match_known_name(question, team_names)` scans all team names in DB.
- `_extract_own_team_hint(question)` — looks for "for [team]", "by [team]" patterns.
- `_extract_opponent_team_hint(question)` — looks for "against [team]", "vs [team]", "versus [team]", "contra [team]" patterns.

**Assignment priority:**
1. `own_team_hint` → `filters.team_name` (when unset)
2. `opponent_team_hint` → `filters.opponent_team_name` (when unset)
3. `matched_team` → `filters.team_name` only when both team fields are unset, entity is team, and no "against/vs/versus/contra" in question

**Coherence guard:** if `team_name == opponent_team_name`, `team_name` is cleared to None.

---

## 5. Aggregation normalization

| Raw value | Canonical value |
|---|---|
| `"count"` | `"count_matches_positive"` |
| `"mean"` / `"average"` | `"avg"` |
| `"per_90"` / `"per90"` | left as-is (triggers legacy `_resolve_metric` path) |

**Aggregation inference from question wording** (when aggregation is None or "sum"):

| Question contains | Canonical aggregation |
|---|---|
| "won the most points", "most points against", "mas puntos", "más puntos" | `"points"` |
| "won the most matches", "most wins", "mas victorias", "más victorias" | `"wins"` |
| "goal difference", "diferencia de goles" | `"goal_difference"` |
| metric == "points" | `"points"` |

---

## 6. Metric aliases (scope-aware)

`METRIC_ALIASES` maps generic metric names to scope-specific canonical names:

| Alias | `players_summary` / `teams_summary` | `player_match` | `team_match` |
|---|---|---|---|
| `"goals_scored"` | `"goals"` | `"goals"` | `"team_score"` |
| `"total_goals"` | `"goals"` | `"goals"` | `"team_score"` |
| `"goals_conceded"` | `"goals_conceded"` | — | `"opponent_score"` |
| `"assists_total"` | `"assists"` | `"assists"` | — |
| `"minutes"` | `"minutes_played"` | `"minutes_played"` | — |

Applied in `_canonicalize_raw_plan` after scope is set.

---

## 7. Metric-to-canonical-name normalization

`_normalize_metric_key(metric)` resolves natural-language metric names to DB column names:

| Pattern | Canonical |
|---|---|
| "progressive pass" | `"progressive_passes"` |
| "key pass" | `"key_passes"` |
| "shot assist" | `"shot_assists"` |
| "touch.*box" / "box touch" | `"touches_in_box"` |
| "dribble" | `"dribbles_completed"` |
| "tackle" | `"tackles_won"` |
| "interception" | `"interceptions"` |
| "aerial" / "duel" | `"aerial_duels_won"` |
| "clearance" | `"clearances"` |
| "save" | `"saves"` |
| "cross" | `"crosses"` |
| "foul commit" | `"fouls_committed"` |
| "foul drawn" | `"fouls_drawn"` |
| "yellow" | `"yellow_card"` |
| "red" | `"red_card"` |
| "xG" / "expected goal" | `"xg"` |
| "action.*z3" | `"actions_z3"` |
| "away goal" | `"away_goals"` |

---

## 8. Scope inference (`_infer_scope_from_question`)

Decision tree applied after initial metric/entity assignment:

1. **Explicit match context present** (`is_home`, `opponent_rank_*`, `matchday_*`, `opponent_team_name`):
   - player entity + match-level metric → `player_match`
   - player entity + event metric → `player_match_event`
   - team entity → `team_match`

2. **Match-like question wording** (`_has_match_like_question`):
   - "matches", "games", "gameweeks", "matchdays", "rounds", "in a game", "partidos", "jornadas"

3. **Metric catalog lookup:**
   - metric in `player_match_event` catalog → `player_match_event`
   - metric in `player_match` catalog → `player_match`
   - metric in `team_match` catalog → `team_match`

4. **Entity fallback:**
   - player entity → `players_summary`
   - team entity → `teams_summary`

---

## 9. Opponent rank filters

All three rank filter types are mutually exclusive. Last write wins within `_canonicalize_raw_plan`:

| Question pattern | Filter set |
|---|---|
| "top-N teams", "top N sides" | `opponent_rank_lte = N` |
| "bottom-N teams" | `opponent_rank_gte = 21 - N` |
| "mid-table" (`MID_TABLE_RANGE = (8, 14)`) | `opponent_rank_between = [8, 14]`, clears others |
| "big six" / "big6" / "big 6" | `opponent_is_big6 = True` |
| "top-6" / "top 6" | `opponent_rank_lte = 6`, clears `opponent_is_big6` |

---

## 10. Home/away filters

| Question contains | Filter set |
|---|---|
| "away" / "fuera de casa" | `is_home = False` (if not already set) |
| "at home" / "home " / "en casa" | `is_home = True` (if not already set) |

---

## 11. Matchday window filters

**Explicit range:**
- `"between matchdays? N and M"` → `matchday_start = min, matchday_end = max`
- `"entre jornadas? N y M"` → same

**Relative window** (fires only when no explicit range is set):
- `_extract_recent_window(q)` matches "last N gameweeks/rounds/matchdays/jornadas"
- Sets `matchday_end = max_matchday` (loaded from DB), `matchday_start = max_matchday - N + 1`

---

## 12. Ranking normalization

| Condition | Action |
|---|---|
| Ordinal detected in question (e.g. "3rd", "second") | `mode = "ordinal"`, `ordinal = N`, `n = None` |
| `mode == "top_n"` and `n is None` | `n = 1` |
| `mode == "ordinal"` and `ordinal is None` | re-extract from question |

`_extract_numeric_ordinal(q)` matches: "1st", "2nd", "3rd", "4th"–"20th", word forms "first"–"twentieth".

---

## 13. Derived-metric match conditions

Two patterns produce `count_matches_positive` aggregation with `match_conditions`:

**Goal + assist matches:**
- Phrases: "matches with both a goal and an assist", "games with both a goal and an assist", "partidos con gol y asistencia"
- Produces: `aggregation = count_matches_positive`, `match_conditions = [{goals > 0}, {assists > 0}]`

**Multi-goal matches:**
- Phrases: "matches with 2 or more goals", "matches with two or more goals", "partidos con 2 o mas goles"
- Produces: `aggregation = count_matches_positive`, `match_conditions = [{goals >= 2}]`

Also triggered by LLM returning these metric names (normalized away):
- `matches_with_two_or_more_goals`, `two_goal_matches`, `matches_with_2_or_more_goals`
- `matches_with_goal_and_assist`, `matches_scored_and_assisted`, `goal_and_assist_matches`

---

## 14. Contextual strong overrides

Applied when specific metric+context combinations are detected:

| Condition | Override |
|---|---|
| goals + (rank_bucket or big6) + player subject | `scope=player_match`, `entity=player`, `metric=goals`, `agg=sum` |
| progressive_passes + rank_bucket + (position or player subject) | `scope=player_match_event`, `entity=player`, `metric=progressive_passes`, `agg=sum` |
| shot_assists + big6 | `scope=player_match_event`, `entity=player`, `metric=shot_assists`, `agg=sum`, `opponent_is_big6=True` |
| away_goals + team subject | `scope=team_match`, `entity=team`, `metric=team_score`, `agg=sum`, `is_home=False` |
| away_goals + player subject | `scope=player_match`, `entity=player`, `metric=goals`, `agg=sum`, `is_home=False` |
| actions_z3 + opponent_team_name + team subject | `scope=team_match`, `entity=team`, `metric=actions_z3`, `agg=sum` |
| points + big6 | `scope=team_match`, `entity=team`, `metric=team_score`, `agg=points`, `opponent_is_big6=True` |
| away_wins | `scope=team_match`, `entity=team`, `metric=team_score`, `agg=wins`, `is_home=False` |

---

## 15. Scope-level metric renames

Applied as scope is finalized, to ensure metric name matches actual DB column:

| Scope | Input metric | Canonical metric |
|---|---|---|
| `player_match` | `total_goals` | `goals` |
| `player_match` | `total_assists` | `assists` |
| `player_match` | `total_minutes` | `minutes_played` |
| `player_match` | `away_goals` | `goals` |
| `team_match` | `goals` / `total_goals` / `away_goals` | `team_score` |
| `team_match` | `total_goals_against` | `opponent_score` |
| `team_match` | `points` / `wins` / `goal_difference` | `team_score` |
| `team_match` | `actions_in_z3` / `z3_actions` | `actions_z3` |

---

## 16. Coherence guards (`_post_process_plan`)

- Team entity + position filter set → `position = None`
- Team entity + `player_match_event` scope → `scope = team_match`
- Team entity + `player_match` scope → `scope = team_match`, `goals` → `team_score`
- Player entity + `teams_summary` scope + no context → `scope = players_summary`
- Player entity + `teams_summary` scope + context → `scope = player_match_event` or `player_match`
- Team entity + `players_summary` scope → `scope = teams_summary` (no context) or `team_match` (with context)

---

## 17. `_validate_scope_and_metric`

Final gate: raises `ValueError` if `(table_scope, metric)` is not a recognized combination.
Falls back to the legacy `_resolve_metric` path for per-90 queries (those pass `per_90`/`per90` as aggregation and bypass this validator).

---

## Resolution entry point

```python
plan = planner.resolve(question)
# → _call_llm_for_plan(question)        # LLM extracts raw JSON
# → _canonicalize_raw_plan(question, raw)  # rules 2–14
# → _post_process_plan(question, canonical) # rules 1, 15–17 + Pydantic validation
```
