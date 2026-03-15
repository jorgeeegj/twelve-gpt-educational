import json
import sys
sys.path.insert(0, ".")

from utils.basic_stats.llm_query_engine_v2 import LLMQueryEngineV2

engine = LLMQueryEngineV2()

with open("questions_benchmark_raw.json") as f:
    benchmark = json.load(f)

for q in benchmark:
    print(f"\n{'='*60}")
    print(f"{q['id']} | {q['question']}")
    print(f"EXPECTED : {q['answer']}")
    result = engine.ask(q["question"])
    print(f"AGENT    : {result['content']}")
    d = result["debug"]
    print(f"DEBUG    : table={d['table']} | metric={d['metric']} | filters={d['filters']}")
