import sys

sys.path.insert(0, ".")

from src.basic_stats.agent import BasicStatsAgent

turns = [
    "How many goals has Haaland scored this season?",
    "But against top 6 teams?",
    "Is that more than the rest of his goals?",
    "What about per 90?",
]

agent = BasicStatsAgent()
failed = False

for i, question in enumerate(turns, 1):
    print(f"\nTurn {i}: {question}")
    answer = agent.ask(question)
    print(f"→ {answer}")
    if not answer or "wasn't able to answer" in answer.lower():
        print("  [FAIL]")
        failed = True

sys.exit(1 if failed else 0)
