"""
Mini eval runner for LLMQueryEngine.
Tests 5 questions that failed with the keyword-based engine.
"""
import json
import sys
sys.path.insert(0, ".")

from utils.basic_stats.llm_query_engine_v2 import LLMQueryEngineV2 as LLMQueryEngine

MINI_BENCHMARK = [
    {
        "id": "Q01",
        "question": "Who has scored the most goals this season?",
        "expected": "Mohamed Salah — 29 goals",
    },
    {
        "id": "Q05",
        "question": "Which player has the best goals per 90 minutes (minimum 10 appearances)?",
        "expected": "J. Durán (Aston Villa) — 0.85 goals/90",
    },
    {
        "id": "Q08",
        "question": "Which team wins the most aerial duels?",
        "expected": "Everton — 691 aerial duels won",
    },
    {
        "id": "Q12",
        "question": "Which player has the highest dribble success rate (minimum 10 appearances)?",
        "expected": "K. Walker (Manchester City) — 100%",
    },
    {
        "id": "Q15",
        "question": "Which defender wins the most aerial duels per 90?",
        "expected": "D. Burn (Newcastle United) — 3.95/90",
    },
]

engine = LLMQueryEngine()

print("=" * 65)
print("LLMQueryEngine v2 — Mini Eval (5 questions)")
print("=" * 65)

for item in MINI_BENCHMARK:
    print(f"\n{item['id']} | {item['question']}")
    print(f"  EXPECTED : {item['expected']}")

    result = engine.ask(item["question"])
    print(f"  AGENT    : {result['content']}")

    debug = result.get("debug", {})
    print(f"  DEBUG    : table={debug.get('table')} | metric={debug.get('metric')} | filters={debug.get('filters')}")

print("\n" + "=" * 65)
