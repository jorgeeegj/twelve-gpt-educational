# Regression test for BUG-PARALLEL-TOOLS:
# When response.output contains multiple function_call items, the loop must
# produce one function_call_output per call_id so the next API request is valid.
# No LLM credentials or DuckDB files required.

from unittest.mock import MagicMock, call, patch


def _make_fc(name: str, call_id: str, arguments: str = "{}") -> MagicMock:
    """Minimal function_call output item stub."""
    item = MagicMock()
    item.type = "function_call"
    item.name = name
    item.call_id = call_id
    item.arguments = arguments
    return item


def _make_text_response(text: str) -> MagicMock:
    """Minimal final-answer response stub."""
    resp = MagicMock()
    fc_msg = MagicMock()
    fc_msg.type = "message"
    resp.output = [fc_msg]
    resp.output_text = text
    return resp


def _make_tool_call_response(*fc_items) -> MagicMock:
    """Response stub with one or more function_call items."""
    resp = MagicMock()
    resp.output = list(fc_items)
    resp.output_text = ""
    return resp


@patch("src.basic_stats.agent.build_system_prompt", return_value="sys")
@patch("src.basic_stats.agent.get_embeddings_model", return_value="emb-model")
@patch("src.basic_stats.agent.get_model", return_value="gpt-test")
@patch("src.basic_stats.agent.get_llm_client")
@patch("src.basic_stats.agent.DuckDBManager")
def test_parallel_tool_calls_produce_two_outputs(
    MockDuck, MockClient, mock_gm, mock_gem, mock_bsp
):
    """Two function_call items in response.output → two function_call_outputs sent."""
    from src.basic_stats.agent import BasicStatsAgent

    # --- tool map: each call returns a trivial dict ---
    duck_instance = MockDuck.return_value
    duck_instance.set_embedding_client.return_value = None

    client_instance = MockClient.return_value
    mock_responses = client_instance.responses

    fc_a = _make_fc("query_player_stats", "call_aaa", '{"player_name": "E. Haaland"}')
    fc_b = _make_fc("query_player_stats", "call_bbb", '{"player_name": "M. Salah"}')

    # Turn 1: first call returns two function_calls; second call returns answer.
    first_response = _make_tool_call_response(fc_a, fc_b)
    second_response = _make_text_response("Haaland 0.8, Salah 0.7 per 90.")

    mock_responses.create.side_effect = [first_response, second_response]

    # Patch tool dispatchers to avoid real DuckDB
    with patch("src.basic_stats.agent.query_player_stats", return_value={"value": 1}) as mock_tool, \
         patch("src.basic_stats.agent.query_team_stats", return_value={}), \
         patch("src.basic_stats.agent.query_ranking", return_value={}), \
         patch("src.basic_stats.agent.get_league_standings", return_value={}):

        agent = BasicStatsAgent()
        answer = agent.ask("What about per 90?")

    assert answer == "Haaland 0.8, Salah 0.7 per 90."
    assert mock_responses.create.call_count == 2

    # Inspect the second responses.create call
    second_call_kwargs = mock_responses.create.call_args_list[1]
    input_sent = second_call_kwargs.kwargs.get("input") or second_call_kwargs.args[0]

    fco_entries = [item for item in input_sent if isinstance(item, dict) and item.get("type") == "function_call_output"]

    assert len(fco_entries) == 2, (
        f"Expected 2 function_call_output entries, got {len(fco_entries)}: {fco_entries}"
    )
    call_ids_sent = {e["call_id"] for e in fco_entries}
    assert call_ids_sent == {"call_aaa", "call_bbb"}


@patch("src.basic_stats.agent.build_system_prompt", return_value="sys")
@patch("src.basic_stats.agent.get_embeddings_model", return_value="emb-model")
@patch("src.basic_stats.agent.get_model", return_value="gpt-test")
@patch("src.basic_stats.agent.get_llm_client")
@patch("src.basic_stats.agent.DuckDBManager")
def test_single_tool_call_unchanged(
    MockDuck, MockClient, mock_gm, mock_gem, mock_bsp
):
    """Single function_call still works — regression guard for existing behavior."""
    from src.basic_stats.agent import BasicStatsAgent

    duck_instance = MockDuck.return_value
    duck_instance.set_embedding_client.return_value = None
    client_instance = MockClient.return_value
    mock_responses = client_instance.responses

    fc = _make_fc("query_player_stats", "call_ccc", '{"player_name": "E. Haaland"}')
    mock_responses.create.side_effect = [
        _make_tool_call_response(fc),
        _make_text_response("Haaland scored 27 goals."),
    ]

    with patch("src.basic_stats.agent.query_player_stats", return_value={"value": 27}), \
         patch("src.basic_stats.agent.query_team_stats", return_value={}), \
         patch("src.basic_stats.agent.query_ranking", return_value={}), \
         patch("src.basic_stats.agent.get_league_standings", return_value={}):

        agent = BasicStatsAgent()
        answer = agent.ask("How many goals has Haaland scored?")

    assert answer == "Haaland scored 27 goals."
    second_input = mock_responses.create.call_args_list[1].kwargs.get("input") or \
                   mock_responses.create.call_args_list[1].args[0]
    fco_entries = [i for i in second_input if isinstance(i, dict) and i.get("type") == "function_call_output"]
    assert len(fco_entries) == 1
    assert fco_entries[0]["call_id"] == "call_ccc"
