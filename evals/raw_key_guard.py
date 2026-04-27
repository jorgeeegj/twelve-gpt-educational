"""evals/raw_key_guard.py — NLP-01 guard.

Detects raw column/metric tokens leaking into LLM answers. The token list is
parsed from agent_system.yaml's AVAILABLE STATS block so it stays in sync as
new metrics are added.
"""
from __future__ import annotations

import re
import yaml
from pathlib import Path
from functools import lru_cache

PROMPT_PATH = Path(__file__).resolve().parents[1] / "src/basic_stats/prompts/agent_system.yaml"

# Tokens that are ALWAYS forbidden in answers regardless of the stats block.
# These are robotic patterns the LLM falls into even when not citing a column.
_HARDCODED_FORBIDDEN = frozenset({
    "metric_value",
    "total_metric_value",
    "team_score",
    "opponent_score",
    "is_home",
    "matchday_start",
    "matchday_end",
    "opponent_rank_lte",
    "opponent_rank_gte",
    "opponent_is_big6",
    "rank_mode",
    "min_minutes",
    "min_matches",
    "first_name",
    "last_name",
})

# Words to preserve even when they appear in the stats list — they are valid
# English/Spanish prose nouns when used naturally.
_PROSE_ALLOWLIST = frozenset({
    "goals", "assists", "shots", "minutes", "points", "wins",
    "saves", "interceptions", "clearances", "crosses", "recoveries",
    "passes", "fouls", "carries", "dribbles",
})


@lru_cache(maxsize=1)
def load_forbidden_tokens(prompt_path: Path = PROMPT_PATH) -> frozenset[str]:
    """Parse agent_system.yaml AVAILABLE STATS block, return forbidden tokens.

    Rule: include any token that contains '_' (snake_case columns) plus any
    token ending in '_pct', '_p90', or '_per_90'. Bare prose nouns are kept
    out via _PROSE_ALLOWLIST.
    """
    raw = yaml.safe_load(prompt_path.read_text(encoding="utf-8"))["system"]
    # Slice from "AVAILABLE STATS" header to the next ALL-CAPS header.
    # When loaded via yaml.safe_load the system string has no leading spaces.
    block = re.search(r"AVAILABLE STATS.*?(?=\n[A-Z][A-Z ]{3,}\n)", raw, re.DOTALL)
    text = block.group(0) if block else ""
    candidates = set(re.findall(r"\b[a-z][a-z0-9_]*\b", text))
    forbidden = {
        t for t in candidates
        if (("_" in t) or t.endswith(("_pct", "_p90")) or t.endswith("_per_90"))
        and t not in _PROSE_ALLOWLIST
    }
    return frozenset(forbidden | _HARDCODED_FORBIDDEN)


def find_label_violations(user_input: str, answer: str) -> list[str]:
    """Detect label substitutions that contradict the user's wording.

    Returns sorted list of violation strings. Currently checks:
    - 'Big Six' in answer when user did not write 'Big Six' verbatim.
    """
    violations = []
    if re.search(r"\bBig Six\b", answer, re.IGNORECASE) and not re.search(
        r"\bBig Six\b", user_input, re.IGNORECASE
    ):
        violations.append("label:Big Six used when user did not write 'Big Six'")
    return sorted(violations)


def find_violations(answer: str, forbidden: frozenset[str] | None = None) -> list[str]:
    """Return sorted list of raw tokens found in answer (case-insensitive, word-bounded)."""
    if forbidden is None:
        forbidden = load_forbidden_tokens()
    hits = []
    lowered = answer.lower()
    for tok in forbidden:
        if re.search(rf"\b{re.escape(tok)}\b", lowered):
            hits.append(tok)
    return sorted(set(hits))
