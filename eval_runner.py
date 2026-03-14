import json
import sys
sys.path.insert(0, ".")

from utils.basic_stats.agent import BasicStatsAgent

agent = BasicStatsAgent()

with open("questions_benchmark_raw.json") as f:
    benchmark = json.load(f)

for q in benchmark:
    print(f"\n{'='*60}")
    print(f"{q['id']} | {q['question']}")
    print(f"EXPECTED: {q['answer']}")
    print(f"AGENT:    {agent.ask(q['question'])}")
