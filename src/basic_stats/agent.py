"""
agent.py — BasicStatsAgent: tool-calling agent for Premier League 2024-25 stats.

The LLM owns semantic interpretation (which stat, which entity, which filter)
and verbalization (writing the final answer). Code owns data access only.
No if/else heuristics.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from src.basic_stats.agent_prompt import build_system_prompt
from src.basic_stats.agent_tool_schemas import ALL_AGENT_TOOLS
from src.basic_stats.agent_tools import (
    ToolError,
    compare_entities,
    count_matches_where,
    get_league_standings,
    get_player_stat,
    get_stat_over_window,
    get_stat_vs_opponent_group,
    get_team_stat,
    rank_players,
    rank_teams,
)
from src.basic_stats.config import get_llm_client, get_model
from src.basic_stats.duckdb_manager import DuckDBManager

logger = logging.getLogger(__name__)

_MAX_ITERATIONS = 6
_FALLBACK_MESSAGE = (
    "I wasn't able to answer that question with the available data. "
    "Try rephrasing or ask a more specific question about a player, team, or stat."
)


def _build_tool_map(duck: DuckDBManager) -> dict[str, Any]:
    return {
        "get_player_stat": lambda **kw: get_player_stat(duck, **kw),
        "get_team_stat": lambda **kw: get_team_stat(duck, **kw),
        "rank_players": lambda **kw: rank_players(duck, **kw),
        "rank_teams": lambda **kw: rank_teams(duck, **kw),
        "compare_entities": lambda **kw: compare_entities(duck, **kw),
        "count_matches_where": lambda **kw: count_matches_where(duck, **kw),
        "get_stat_over_window": lambda **kw: get_stat_over_window(duck, **kw),
        "get_league_standings": lambda **kw: get_league_standings(duck, **kw),
        "get_stat_vs_opponent_group": lambda **kw: get_stat_vs_opponent_group(duck, **kw),
    }


class BasicStatsAgent:
    """
    Premier League 2024-25 stats agent.

    Usage:
        agent = BasicStatsAgent()
        answer = agent.ask("Who has scored the most goals this season?")

        # Follow-ups with history (Phase 6):
        history = []
        a1 = agent.ask("How many goals has Haaland scored?", history=history)
        history += [{"role": "user", "content": "How many goals has Haaland scored?"},
                    {"role": "assistant", "content": a1}]
        a2 = agent.ask("What about against top 6 teams?", history=history)
    """

    def __init__(self) -> None:
        self.duck = DuckDBManager()
        self.client = get_llm_client()
        self.model = get_model()
        self.system_prompt = build_system_prompt(self.duck)
        self._tool_map = _build_tool_map(self.duck)

    def ask(self, question: str, history: list[dict] | None = None) -> str:
        """
        Answer a question and return a natural language string.

        history: list of {role, content} dicts from prior turns.
                 Pass [] on first turn, append each question+answer pair,
                 and pass the accumulated list on follow-up turns.
                 Wiring the Streamlit UI to maintain state is Phase 6's job.
        """
        messages: list[dict] = [{"role": "system", "content": self.system_prompt}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": question})

        for iteration in range(_MAX_ITERATIONS):
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=ALL_AGENT_TOOLS,
                tool_choice="auto",
            )
            message = response.choices[0].message

            if not message.tool_calls:
                answer = (message.content or "").strip()
                if not answer:
                    logger.warning("Agent returned empty content on iteration %d", iteration)
                    return _FALLBACK_MESSAGE
                return answer

            messages.append(message)

            for tool_call in message.tool_calls:
                tool_name = tool_call.function.name
                try:
                    args = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError as exc:
                    tool_result: dict = {"error": f"Failed to parse tool arguments: {exc}"}
                else:
                    tool_result = self._execute_tool(tool_name, args)

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(tool_result, ensure_ascii=False, default=str),
                    }
                )

        logger.warning(
            "Agent loop exhausted after %d iterations for: %r", _MAX_ITERATIONS, question
        )
        return _FALLBACK_MESSAGE

    def _execute_tool(self, tool_name: str, args: dict) -> dict:
        fn = self._tool_map.get(tool_name)
        if fn is None:
            return {"error": f"Unknown tool: {tool_name!r}"}
        try:
            return fn(**args)
        except ToolError as exc:
            return {"error": str(exc)}
        except Exception as exc:
            logger.exception("Unexpected error in tool %r with args %r", tool_name, args)
            return {"error": f"Tool {tool_name!r} failed: {exc}"}
