"""Static regression tests for prompt rules and league-context doc.

These tests read YAML/Markdown files and assert key substrings are present or absent.
They require no DuckDB connection and run fast.
"""

from pathlib import Path

import yaml

PROMPT_PATH = Path("src/basic_stats/prompts/agent_system.yaml")
LEAGUE_CTX_PATH = Path("docs/premier_league_2024_25_context.md")


def _load_prompt() -> str:
    raw = yaml.safe_load(PROMPT_PATH.read_text(encoding="utf-8"))
    return raw["system"]


def _load_league_ctx() -> str:
    return LEAGUE_CTX_PATH.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Numeric grounding
# ---------------------------------------------------------------------------


def test_numeric_grounding_rule_present():
    prompt = _load_prompt()
    assert "NUMERIC GROUNDING" in prompt, "NUMERIC GROUNDING section must be present"
    assert "Never compute, sum, or reconcile numbers in your head" in prompt
    assert "total_metric_value" in prompt, (
        "Prompt must mention total_metric_value so LLM knows to use it"
    )


# ---------------------------------------------------------------------------
# Language rule
# ---------------------------------------------------------------------------


def test_language_rule_mentions_latest_user_message():
    prompt = _load_prompt()
    # The rule must reference "latest" to clarify it's the current message, not history
    assert "LATEST user message" in prompt or "latest user message" in prompt, (
        "LANGUAGE rule must specify 'latest user message', not just 'the user's question'"
    )


# ---------------------------------------------------------------------------
# Follow-up / topic reset
# ---------------------------------------------------------------------------


def test_followup_topic_reset_rule_present():
    prompt = _load_prompt()
    assert "TOPIC RESET" in prompt, "TOPIC RESET rule must be present in prompt"
    assert "fresh question" in prompt or "fresh topic" in prompt or "completely fresh" in prompt, (
        "Topic reset rule must mention treating new questions as fresh"
    )
    assert "anaphoric" in prompt or "and …" in prompt or "what about …" in prompt, (
        "Topic reset rule must distinguish anaphoric follow-ups from new topics"
    )


# ---------------------------------------------------------------------------
# Future prediction / out of scope
# ---------------------------------------------------------------------------


def test_future_prediction_out_of_scope_has_outcome_ban():
    prompt = _load_prompt()
    assert "OUT OF SCOPE" in prompt
    # The ban must explicitly call out outcome-shaped sentences
    assert "likely outcome" in prompt, (
        "OUT OF SCOPE must ban 'likely outcome' sentences"
    )
    assert "I can't predict" in prompt or "I cannot know" in prompt or "can't predict" in prompt, (
        "OUT OF SCOPE must include a worked example with a clear refusal phrase"
    )


# ---------------------------------------------------------------------------
# Top 6 vs Big Six label rule
# ---------------------------------------------------------------------------


def test_top6_bigsix_label_rule_present():
    prompt = _load_prompt()
    # The absolute label rule must be present
    assert "CRITICAL ANSWER LABEL RULE" in prompt or "label rule is absolute" in prompt, (
        "Prompt must contain a hard rule on Big Six vs top-six labelling"
    )
    assert ("Never say" in prompt or "never say" in prompt) and "Big Six" in prompt, (
        "Rule must explicitly say never use 'Big Six' unless user wrote it verbatim"
    )


# ---------------------------------------------------------------------------
# Player name rule
# ---------------------------------------------------------------------------


def test_player_name_rule_uses_canonical_full_name():
    prompt = _load_prompt()
    assert "first_name" in prompt and "last_name" in prompt, (
        "PLAYER NAMES rule must reference first_name and last_name fields from tool"
    )
    assert "full canonical" in prompt or "canonical name" in prompt, (
        "PLAYER NAMES rule must instruct LLM to use the full canonical name"
    )


# ---------------------------------------------------------------------------
# League context doc — must not conflate top-6 with Big Six
# ---------------------------------------------------------------------------


def test_league_context_does_not_conflate_top6_and_bigsix():
    ctx = _load_league_ctx()
    # The old conflating sentence must be gone
    assert (
        '"Top 6" in Premier League context traditionally refers to' not in ctx
    ), (
        "League context must not contain the old sentence that conflates 'Top 6' with Big Six"
    )
    # The replacement must clarify both concepts
    assert "Big Six" in ctx and "historical" in ctx, (
        "League context must define Big Six as a historical-identity grouping"
    )
    assert "not the same group" in ctx or "not treat them interchangeably" in ctx, (
        "League context must explicitly state Big Six and top six are different groups"
    )


# ---------------------------------------------------------------------------
# Champions League team group — all routes vs league-position
# ---------------------------------------------------------------------------


def test_league_context_cl_all_routes_group_present():
    ctx = _load_league_ctx()
    assert "Champions League-qualified teams (all routes)" in ctx, (
        "League context must define the all-routes Champions League group explicitly"
    )
    assert "Tottenham Hotspur" in ctx.split("Champions League-qualified teams (all routes)")[1].split("\n")[1], (
        "All-routes CL group must include Tottenham Hotspur"
    )


def test_league_context_league_position_cl_group_distinct():
    ctx = _load_league_ctx()
    assert "League-position Champions League Qualifiers" in ctx or "league-position" in ctx.lower(), (
        "League context must define a distinct league-position CL qualifier group"
    )


def test_league_context_cl_notes_include_tottenham_rule():
    ctx = _load_league_ctx()
    notes_section = ctx.split("Notes for LLM Usage")[1] if "Notes for LLM Usage" in ctx else ctx
    assert "Tottenham Hotspur" in notes_section, (
        "Notes for LLM Usage must mention Tottenham Hotspur in the Champions League teams rule"
    )


def test_prompt_cl_teams_rule_includes_tottenham():
    prompt = _load_prompt()
    assert "Tottenham" in prompt, (
        "Prompt must mention Tottenham Hotspur in the Champions League teams wording rule"
    )
    assert "Europa League" in prompt, (
        "Prompt must mention Europa League as Tottenham's CL qualification route"
    )


# ---------------------------------------------------------------------------
# Comparison direction — MANDATORY SELF-CHECK rule (UAT regression)
# ---------------------------------------------------------------------------


def test_comparison_direction_rule_has_mandatory_self_check():
    prompt = _load_prompt()
    assert "MANDATORY SELF-CHECK" in prompt or "self-check" in prompt.lower(), (
        "COMPARISON DIRECTION rule must include a mandatory self-check directive"
    )
    # The rule must explicitly state the arithmetic condition for Yes/No
    assert "prior > X" in prompt or "prior < X" in prompt or "prior >" in prompt, (
        "Self-check must state the arithmetic inequality that governs Yes/No"
    )
    # The wrong-answer example must show the specific 5 < 17 / 'Yes' contradiction
    assert '"Yes"' in prompt or "Yes" in prompt, (
        "Rule must include a WRONG example showing 'Yes' with contradicting numbers"
    )
    # The right answer must demonstrate the 'No' opening
    assert '"No"' in prompt or "No —" in prompt, (
        "Rule must include a RIGHT example starting with 'No'"
    )


# ---------------------------------------------------------------------------
# Bucket answer label — must not substitute 'Big Six' for 'top 6' (UAT regression)
# ---------------------------------------------------------------------------


def test_bucket_answer_rule_forbids_big_six_for_top6_input():
    prompt = _load_prompt()
    # The HOW TO WRITE YOUR ANSWER section must reflect the label rule
    how_to_write = prompt.split("HOW TO WRITE YOUR ANSWER")[1] if "HOW TO WRITE YOUR ANSWER" in prompt else prompt
    assert 'user said "top 6 teams"' in how_to_write or "top 6" in how_to_write.lower(), (
        "HOW TO WRITE YOUR ANSWER must address top-6 label explicitly"
    )
    # Must not instruct the LLM to always use 'the Big Six' as bucket label (no longer valid)
    # Check that the *only* explicit example using "the Big Six" as bucket label is under
    # the condition that user said "Big Six".
    assert 'user said "Big Six"' in how_to_write or "user wrote" in how_to_write.lower(), (
        "HOW TO WRITE YOUR ANSWER bucket rule must condition 'Big Six' label on user input"
    )
