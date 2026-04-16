"""
Tests for src/basic_stats/agent_tool_schemas.py — Step 3 (Responses API flat format).
Run with: python -m pytest tests/test_agent_tool_schemas.py -v
"""

from src.basic_stats.agent_tool_schemas import ALL_AGENT_TOOLS


def test_four_tools_defined():
    assert len(ALL_AGENT_TOOLS) == 4


def test_schemas_use_flat_responses_api_format():
    for tool in ALL_AGENT_TOOLS:
        assert "function" not in tool, f"Tool {tool.get('name')} still uses nested format"
        assert "name" in tool
        assert "description" in tool
        assert "parameters" in tool


def test_no_strict_field():
    # strict=True is Chat Completions only — invalid in Responses API
    for tool in ALL_AGENT_TOOLS:
        assert "strict" not in tool, f"Tool {tool.get('name')} has 'strict' field"


def test_tool_names_are_correct():
    names = {t["name"] for t in ALL_AGENT_TOOLS}
    assert names == {
        "query_player_stats",
        "query_team_stats",
        "query_ranking",
        "get_league_standings",
    }


def test_all_schemas_have_additionalproperties_false():
    for tool in ALL_AGENT_TOOLS:
        params = tool["parameters"]
        assert params.get("additionalProperties") is False, (
            f"{tool['name']} missing additionalProperties: false"
        )


def test_query_player_stats_required_fields():
    schema = next(t for t in ALL_AGENT_TOOLS if t["name"] == "query_player_stats")
    required = set(schema["parameters"]["required"])
    assert "player_name" in required
    assert "filters" in required
    assert "stat" in required
    assert "match_conditions" in required
    assert "last_n_gameweeks" in required
    assert "opponent_teams" in required


def test_query_team_stats_required_fields():
    schema = next(t for t in ALL_AGENT_TOOLS if t["name"] == "query_team_stats")
    required = set(schema["parameters"]["required"])
    assert "stat" in required
    assert "filters" in required
    assert "rank_mode" in required
    assert "descending" in required
    assert "limit" in required


def test_query_ranking_entity_type_is_enum():
    schema = next(t for t in ALL_AGENT_TOOLS if t["name"] == "query_ranking")
    entity_type_prop = schema["parameters"]["properties"]["entity_type"]
    assert "enum" in entity_type_prop
    assert set(entity_type_prop["enum"]) == {"player", "team"}


def test_query_ranking_required_fields():
    schema = next(t for t in ALL_AGENT_TOOLS if t["name"] == "query_ranking")
    required = set(schema["parameters"]["required"])
    assert "entity_type" in required
    assert "rank_mode" in required
    assert "entities" in required
    assert "stat" in required
    assert "filters" in required
    assert "limit" in required
    assert "descending" in required
    assert "match_conditions" in required


def test_get_league_standings_has_no_required_params():
    schema = next(t for t in ALL_AGENT_TOOLS if t["name"] == "get_league_standings")
    assert schema["parameters"]["required"] == []
    assert schema["parameters"]["properties"] == {}


def test_all_tools_have_type_function():
    for tool in ALL_AGENT_TOOLS:
        assert tool["type"] == "function", f"{tool.get('name')} has wrong type"


def test_filters_schema_has_required_fields():
    """Verify _FILTERS_SCHEMA is correctly embedded in at least one tool."""
    schema = next(t for t in ALL_AGENT_TOOLS if t["name"] == "query_player_stats")
    filters = schema["parameters"]["properties"]["filters"]
    assert "properties" in filters
    props = set(filters["properties"].keys())
    assert "opponent_team" in props
    assert "is_home" in props
    assert "opponent_is_big6" in props
    assert "player_team" in props
    assert "position" in props
