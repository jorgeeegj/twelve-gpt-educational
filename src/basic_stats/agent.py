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

    def __init__(self, in_memory: bool = False) -> None:
        self.duck = DuckDBManager(in_memory=in_memory)
        self.client = get_llm_client()
        self.model = get_model()
        self.duck.set_embedding_client(self.client, get_embeddings_model())
        self.system_prompt = build_system_prompt(self.duck)
        self._tool_map = _build_tool_map(self.duck)
        self._history: list[dict] = []
        self.last_telemetry: dict[str, Any] = {}

    def reset(self) -> None:
        """Clear conversation state (e.g. when user clicks 'Clear chat')."""
        self._history = []
        self.last_telemetry = {}

    def ask(self, question: str, history: list[dict] | None = None) -> str:
        """
        Answer a question and return a natural language string.

        Conversation state is maintained via previous_response_id — the API
        carries forward the full context automatically. Pass history=[] on the
        first turn for backwards compatibility; it is ignored when
        previous_response_id is already set.
        """
        # First turn seeds history with system prompt; follow-ups append to it.
        if not self._history:
            self._history = [{"role": "system", "content": self.system_prompt}]
        self._history.append({"role": "user", "content": question})

        tool_calls: list[dict[str, Any]] = []
        iterations_used = 0
        # input_messages tracks the current turn's message chain (may grow with
        # tool call/output pairs within this turn)
        input_messages: list[dict] = list(self._history)
        prior_call_hashes: frozenset[tuple[str, str]] = frozenset()

        for iteration in range(_MAX_ITERATIONS):
            iterations_used = iteration + 1
            kwargs: dict[str, Any] = {
                "model": self.model,
                "input": input_messages,
                "tools": ALL_AGENT_TOOLS,
                "tool_choice": "auto",
            }

            response = self.client.responses.create(**kwargs)

            # Collect all function calls — the model may request multiple tools in
            # parallel. Every call_id must have a matching function_call_output in
            # the next request or the API raises "No tool output found".
            fc_items = [item for item in response.output if item.type == "function_call"]

            if not fc_items:
                # No tool call — final answer; persist full turn (including any
                # tool call/output pairs) to history so the next turn's input
                # remains consistent with Responses-API call_id tracking.
                answer = (response.output_text or "").strip()
                if not answer:
                    logger.warning("Agent returned empty content on iteration %d", iteration)
                    return _FALLBACK_MESSAGE
                self._history = input_messages + list(response.output)
                self.last_telemetry = {
                    "iterations_used": iterations_used,
                    "tool_calls": tool_calls,
                    "hit_max_iterations": False,
                }
                return answer

            # Livelock guard: same (tool, args) as last iteration means the model
            # is stuck. Return an error for every repeated call_id so the API
            # doesn't complain about missing outputs, then let the model reconsider.
            current_call_hashes = frozenset((fc.name, fc.arguments) for fc in fc_items)
            if current_call_hashes & prior_call_hashes:
                livelock_outputs = [
                    {
                        "type": "function_call_output",
                        "call_id": fc.call_id,
                        "output": json.dumps(
                            {
                                "error": "Repeated call with identical arguments. Try different parameters or state that you cannot answer this question."
                            }
                        ),
                    }
                    for fc in fc_items
                ]
                input_messages = input_messages + list(response.output) + livelock_outputs
                prior_call_hashes = current_call_hashes
                continue
            prior_call_hashes = current_call_hashes

            # Execute every tool call and build one output entry per call_id.
            fco_entries: list[dict] = []
            for fc_item in fc_items:
                tool_result = self._execute_tool(fc_item.name, fc_item.arguments)
                tool_calls.append(
                    {
                        "name": fc_item.name,
                        "arguments": fc_item.arguments,
                        "resolved_entities": tool_result.get("resolved_entities")
                        if isinstance(tool_result, dict)
                        else None,
                        "note": tool_result.get("note") if isinstance(tool_result, dict) else None,
                        "error": tool_result.get("error")
                        if isinstance(tool_result, dict)
                        else None,
                    }
                )
                fco_entries.append(
                    {
                        "type": "function_call_output",
                        "call_id": fc_item.call_id,
                        "output": json.dumps(tool_result, ensure_ascii=False, default=str),
                    }
                )
            input_messages = input_messages + list(response.output) + fco_entries

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
