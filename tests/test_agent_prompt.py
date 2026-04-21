from src.basic_stats.agent_prompt import build_system_prompt
from src.basic_stats.duckdb_manager import DuckDBManager


def test_build_system_prompt_structure():
    duck = DuckDBManager()
    prompt = build_system_prompt(duck)

    assert "2024/25 Final Standings" in prompt
    assert "Champions League Qualifiers" in prompt
    assert "Nottingham Forest" in prompt
    assert "LEAGUE TIER CONVENTIONS" not in prompt
    assert "Big Six: Arsenal" not in prompt
    assert "opponent_is_big6" in prompt
    assert len(prompt) > 3000
