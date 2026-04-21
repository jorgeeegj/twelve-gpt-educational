import sys

sys.path.insert(0, ".")

from src.basic_stats.agent import BasicStatsAgent

QUESTIONS = [
    (
        "Which teams finished in the top 4 this season?",
        ["Liverpool", "Arsenal", "Manchester City", "Chelsea"],
    ),
    (
        "Which teams were relegated from the Premier League in 2024-25?",
        ["Leicester", "Ipswich", "Southampton"],
    ),
    (
        "Who are the Big Six clubs in the Premier League?",
        ["Arsenal", "Chelsea", "Liverpool", "Manchester City", "Manchester United", "Tottenham"],
    ),
    (
        "Which teams qualified for the Champions League this season?",
        ["Newcastle"],
    ),
    (
        "Which team finished 7th and what European competition did they qualify for?",
        ["Nottingham Forest", "Europa"],
    ),
    (
        "How many points did the champions finish with this season?",
        ["84"],
    ),
]

if __name__ == "__main__":
    passed = 0

    for question, keywords in QUESTIONS:
        agent = BasicStatsAgent()
        answer = agent.ask(question)
        answer_lower = answer.lower()
        all_found = all(kw.lower() in answer_lower for kw in keywords)
        status = "PASS" if all_found else "FAIL"
        if all_found:
            passed += 1
        print(f"[{status}] {question}")
        if not all_found:
            missing = [kw for kw in keywords if kw.lower() not in answer_lower]
            print(f"       Missing keywords: {missing}")
            print(f"       Answer: {answer[:200]}")

    total = len(QUESTIONS)
    print(f"\n{passed}/{total} questions passed")
    sys.exit(0 if passed >= 5 else 1)
