"""
campaign_generator.py — Template-based targeted campaign generator.

Implements Phase 11 SPEC §6: file-based, reviewable, zero OpenAI cost by default.
Generated questions conform to the seed_questions.json schema (10-SPEC.md §3) so the
existing synthetic_runner consumes them unchanged.
No coupling to src.basic_stats.* or openai.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

CAMPAIGNS_DIR = Path(__file__).parent / "campaigns"

# Template strings keyed by 12-category taxonomy enum from 10-SPEC.md §2.
_TEMPLATES: dict[str, list[str]] = {
    "DIRECT_STATS": [
        "How many {metric} has {player} scored this season?",
        "What is {player}'s {metric} count this season?",
    ],
    "RANKINGS": [
        "Top {N} {entity_type} by {metric} this season?",
        "Who has the most {metric} this season?",
    ],
    "COMPARISONS": [
        "Has {player_a} scored more {metric} than {player_b} this season?",
        "Which player has more {metric} this season: {player_a} or {player_b}?",
    ],
    "FOLLOW_UPS": [
        "How many {metric} has {player} scored?|But against top 6?",
        "What is {player}'s {metric} tally?|How does that compare away from home?",
    ],
    "TOP6_VS_BIG6": [
        "How many {metric} has {player} scored against the top 6?",
        "How many {metric} has {player} scored against the Big Six?",
    ],
    "CHAMPIONS_LEAGUE": [
        "Which Premier League teams played in the Champions League this season?",
        "How many {metric} did {player} score in the Champions League this season?",
    ],
    "P90_METRICS": [
        "What is {player}'s {metric} per 90 against the top 6?",
        "What is {player}'s {metric} per 90 this season?",
    ],
    "HOME_AWAY": [
        "Has {player} scored more {metric} at home or away this season?",
        "What is {player}'s home vs away {metric} split this season?",
    ],
    "SPANISH_ENGLISH": [
        "¿Cuántos {metric_es} ha conseguido {player} esta temporada?",
        "¿Quién tiene más {metric_es} esta temporada?",
    ],
    "UNSUPPORTED_FUTURE": [
        "Will {player} score against {opponent} next matchday?",
        "What will the final standings be at the end of the season?",
    ],
    "AMBIGUOUS": [
        "Tell me about {player}.",
        "What can you say about {player} this season?",
    ],
    "DEMO_RANDOM": [
        "Surprise me with a stat about {player}.",
        "Give me an interesting fact about {player}.",
    ],
}

# Small parameter pool (concrete strings — not random; chosen for stability).
_PARAM_POOL: dict[str, list[str]] = {
    "player": ["Mohamed Salah", "Erling Haaland", "Bukayo Saka"],
    "player_a": ["Mohamed Salah"],
    "player_b": ["Erling Haaland"],
    "metric": ["goals", "assists", "shots"],
    "metric_es": ["goles", "asistencias"],
    "entity_type": ["players", "teams"],
    "N": ["3", "5"],
    "opponent": ["Arsenal", "Liverpool"],
}

_BEHAVIOR_MAP: dict[str, str] = {
    "UNSUPPORTED_FUTURE": "refuse",
    "AMBIGUOUS": "ambiguous_clarify",
}

_LANGUAGE_MAP: dict[str, str] = {
    "SPANISH_ENGLISH": "es",
}


def _sanitise_name(name: str) -> str:
    """Lower-case, replace non-alphanumeric runs with '_', collapse repeats, trim to 64."""
    s = re.sub(r"[^a-z0-9]+", "_", name.lower())
    s = re.sub(r"_+", "_", s).strip("_")
    return s[:64]


def _new_id(name: str, index: int) -> str:
    """Return CAMP_<sanitised_name>_<NNN> (zero-padded to 3 digits)."""
    return f"CAMP_{name}_{index + 1:03d}"


def _fill_template(template: str, index: int) -> str:
    """Substitute {placeholder} tokens using _PARAM_POOL with modulo rotation."""
    def _replace(match: re.Match) -> str:
        key = match.group(1)
        pool = _PARAM_POOL.get(key, [key])
        return pool[index % len(pool)]
    return re.sub(r"\{(\w+)\}", _replace, template)


def generate_from_category(category: str, count: int = 4, language: str = "en") -> list[dict]:
    """Emit `count` template-based questions in the given category.

    Each emitted dict conforms to the seed_questions.json schema:
      {id, category, language, question, expected_behavior, expected_values, notes}.

    expected_behavior defaults to:
      - 'refuse'             for UNSUPPORTED_FUTURE
      - 'ambiguous_clarify'  for AMBIGUOUS
      - 'answerable'         otherwise
    expected_values is None (manual review path).
    """
    templates = _TEMPLATES.get(category)
    if templates is None:
        raise ValueError(f"Unknown category: {category!r}")

    behavior = _BEHAVIOR_MAP.get(category, "answerable")
    lang = _LANGUAGE_MAP.get(category, language)
    name = _sanitise_name(category)

    questions = []
    for i in range(count):
        tmpl = templates[i % len(templates)]
        questions.append({
            "id": _new_id(name, i),
            "category": category,
            "language": lang,
            "question": _fill_template(tmpl, i),
            "expected_behavior": behavior,
            "expected_values": None,
            "notes": None,
        })
    return questions


def generate_from_cluster(backlog_entry: dict, count: int = 4) -> list[dict]:
    """Emit a campaign targeting the cluster's category.

    Reuses the cluster's category to call generate_from_category(category, count).
    Adds a notes field on each entry: 'Generated from backlog entry <id> (signature <sig>)'.
    """
    category = backlog_entry.get("category", "")
    questions = generate_from_category(category, count)
    entry_id = backlog_entry.get("id", "?")
    sig = backlog_entry.get("failure_signature", "?")
    note = f"Generated from backlog entry {entry_id} (signature {sig})"
    for q in questions:
        q["notes"] = note
    return questions


def write_campaign(questions: list[dict], name: str) -> Path:
    """Write the questions list to evals/discovery/campaigns/<name>.json.

    name is sanitised: lowercase, alphanumerics+underscore, max 64 chars.
    Returns the absolute Path written.
    Creates the campaigns/ directory if missing.
    """
    safe = _sanitise_name(name) or "campaign"
    CAMPAIGNS_DIR.mkdir(parents=True, exist_ok=True)
    path = CAMPAIGNS_DIR / f"{safe}.json"
    path.write_text(json.dumps(questions, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def generate_with_llm(category: str, count: int = 4, use_llm: bool = False) -> list[dict]:
    """Opt-in LLM-assisted generation. LLM mode is deferred in v1.

    When use_llm=False (default), delegates to generate_from_category.
    When use_llm=True, raises NotImplementedError.
    """
    if use_llm:
        raise NotImplementedError("LLM-assisted generation deferred — use template mode")
    return generate_from_category(category, count)
