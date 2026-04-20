"""
agent.py — BasicStatsAgent: tool-calling agent for Premier League 2024-25 stats.

The LLM owns semantic interpretation (which stat, which entity, which filter)
and verbalization (writing the final answer). Code owns data access only.
No if/else heuristics.

Uses the OpenAI Responses API (client.responses.create) with previous_response_id
for stateful multi-turn conversation — no message history to rebuild each turn.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from src.basic_stats.agent_prompt import build_system_prompt
from src.basic_stats.agent_tool_schemas import ALL_AGENT_TOOLS
from src.basic_stats.agent_tools import (
    ToolError,
    get_league_standings,
    query_player_stats,
    query_ranking,
    query_team_stats,
)
from src.basic_stats.config import get_embeddings_model, get_llm_client, get_model
from src.basic_stats.duckdb_manager import DuckDBManager

logger = logging.getLogger(__name__)

_MAX_ITERATIONS = 6
_FALLBACK_MESSAGE = (
    "I wasn't able to answer that question with the available data. "
    "Try rephrasing or ask a more specific question about a player, team, or stat."
)


def _build_tool_map(duck: DuckDBManager) -> dict[str, Any]:
    return {
        "query_player_stats": lambda **kw: query_player_stats(duck, **kw),
        "query_team_stats": lambda **kw: query_team_stats(duck, **kw),
        "query_ranking": lambda **kw: query_ranking(duck, **kw),
        "get_league_standings": lambda **kw: get_league_standings(duck, **kw),
    }


class BasicStatsAgent:
    """
    Premier League 2024-25 stats agent.

    Usage:
        agent = BasicStatsAgent()
        answer = agent.ask("Who has scored the most goals this season?")

        # Follow-ups via previous_response_id (stateful):
        a1 = agent.ask("How many goals has Haaland scored?")
        a2 = agent.ask("What about against top 6 teams?")  # agent remembers context
    """

    def __init__(self) -> None:
        self.duck = DuckDBManager()
        self.client = get_llm_client()
        self.model = get_model()
        self.duck.set_embedding_client(self.client, get_embeddings_model())
        self.system_prompt = build_system_prompt(self.duck)
        self._tool_map = _build_tool_map(self.duck)
        self._last_response_id: str | None = None
        self.last_telemetry: dict[str, Any] = {}

    def reset(self) -> None:
        """Clear conversation state (e.g. when user clicks 'Clear chat')."""
        self._last_response_id = None
        self.last_telemetry = {}

    def ask(self, question: str, history: list[dict] | None = None) -> str:
        """
        Answer a question and return a natural language string.

        Conversation state is maintained via previous_response_id — the API
        carries forward the full context automatically. Pass history=[] on the
        first turn for backwards compatibility; it is ignored when
        previous_response_id is already set.
        """
        # Build input: system prompt + question (history is handled server-side
        # via previous_response_id after the first turn)
        if self._last_response_id is None:
            # First turn — seed with system prompt
            input_messages: list[dict] | str = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": question},
            ]
        else:
            # Follow-up — server carries conversation context
            input_messages = [{"role": "user", "content": question}]

        # previous_response_id links this turn to prior conversation history.
        # We only pass it on the first API call of each turn; inside the tool
        # loop we chain via explicit input (response.output + tool output) so
        # Azure never sees a duplicate item.
        turn_response_id = self._last_response_id

        tool_calls: list[dict[str, Any]] = []
        iterations_used = 0

        for iteration in range(_MAX_ITERATIONS):
            iterations_used = iteration + 1
            kwargs: dict[str, Any] = {
                "model": self.model,
                "input": input_messages,
                "tools": ALL_AGENT_TOOLS,
                "tool_choice": "auto",
            }
            if iteration == 0 and turn_response_id is not None:
                kwargs["previous_response_id"] = turn_response_id

            response = self.client.responses.create(**kwargs)

            # Check for a function call in output items
            fc_item = next(
                (item for item in response.output if item.type == "function_call"),
                None,
            )

            if fc_item is None:
                # No tool call — final answer; save response id for next turn
                self._last_response_id = response.id
                self.last_telemetry = {
                    "iterations_used": iterations_used,
                    "tool_calls": tool_calls,
                    "hit_max_iterations": False,
                }
                answer = (response.output_text or "").strip()
                if not answer:
                    logger.warning("Agent returned empty content on iteration %d", iteration)
                    return _FALLBACK_MESSAGE
                return answer

            # Execute the tool and chain explicitly via input for next iteration
            tool_result = self._execute_tool(fc_item.name, fc_item.arguments)
            tool_calls.append(
                {
                    "name": fc_item.name,
                    "arguments": fc_item.arguments,
                    "resolved_entities": tool_result.get("resolved_entities")
                    if isinstance(tool_result, dict)
                    else None,
                    "note": tool_result.get("note") if isinstance(tool_result, dict) else None,
                    "error": tool_result.get("error") if isinstance(tool_result, dict) else None,
                }
            )
            input_messages = list(response.output) + [
                {
                    "type": "function_call_output",
                    "call_id": fc_item.call_id,
                    "output": json.dumps(tool_result, ensure_ascii=False, default=str),
                }
            ]

        logger.warning(
            "Agent loop exhausted after %d iterations for: %r", _MAX_ITERATIONS, question
        )
        self.last_telemetry = {
            "iterations_used": iterations_used,
            "tool_calls": tool_calls,
            "hit_max_iterations": True,
        }
        return _FALLBACK_MESSAGE

    def _execute_tool(self, tool_name: str, arguments: str) -> dict:
        fn = self._tool_map.get(tool_name)
        if fn is None:
            return {"error": f"Unknown tool: {tool_name!r}"}
        try:
            args = json.loads(arguments)
        except json.JSONDecodeError as exc:
            return {"error": f"Failed to parse tool arguments: {exc}"}
        try:
            return fn(**args)
        except ToolError as exc:
            return {"error": str(exc)}
        except Exception as exc:
            logger.exception("Unexpected error in tool %r with args %r", tool_name, args)
            return {"error": f"Tool {tool_name!r} failed: {exc}"}
