"""
Smoke tests for the dual-bucket comparison execution path.

These tests make real LLM + DuckDB calls.  Run them with:

    python -m utils.basic_stats.core.test_dual_bucket_hardening

Pass criteria:
  T1  goals regression   — answer uses dual_bucket_comparison engine
  T2  assists variant    — answer uses dual_bucket_comparison engine
  T3  unknown player     — answer does NOT use dual_bucket_comparison engine
                           (falls through to normal path)
"""

# NOTE: These tests require live LLM credentials (GPT_KEY) and DuckDB data.
# Run manually: python tests/test_dual_bucket_hardening.py
# Do NOT add to pre-commit hooks.

import sys

from src.basic_stats.llm_query_engine_v2 import LLMQueryEngineV2


def _engine_label(result: dict) -> str:
    return result.get("debug", {}).get("engine", "unknown")


def run_smoke_tests():
    engine = LLMQueryEngineV2()
    passed = 0
    total = 4

    print("=" * 80)
    print("DUAL-BUCKET HARDENING SMOKE TESTS (live LLM + DuckDB)")
    print("=" * 80)

    # ------------------------------------------------------------------
    # T1: goals regression — "Has E. Haaland scored more goals against
    #     top 5 teams or bottom 5 teams?"
    # Expected: engine == "dual_bucket_comparison"
    # ------------------------------------------------------------------
    q1 = "Has E. Haaland scored more goals against top 5 teams or bottom 5 teams?"
    print(f"\nT1: {q1}")
    try:
        r1 = engine.ask(q1)
        eng1 = _engine_label(r1)
        ok1 = eng1 == "dual_bucket_comparison"
        content1 = r1.get("content", "").encode("ascii", errors="replace").decode()
        print(f"  engine  : {eng1}")
        print(f"  content : {content1}")
        print(f"  T1: {'PASS' if ok1 else 'FAIL -- expected dual_bucket_comparison'}")
        if ok1:
            passed += 1
    except Exception as e:
        print(f"  T1: ERROR -- {repr(e)}")

    # ------------------------------------------------------------------
    # T2: second subject — M. Salah with goals, confirming the comparison
    #     path works for a different player (not hard-coded to Haaland),
    #     using top-6 vs bottom-6 buckets to exercise a different bucket size.
    # Expected: engine == "dual_bucket_comparison"
    # ------------------------------------------------------------------
    q2 = "Has M. Salah scored more goals against top 6 teams or bottom 6 teams?"
    print(f"\nT2: {q2}")
    try:
        r2 = engine.ask(q2)
        eng2 = _engine_label(r2)
        ok2 = eng2 == "dual_bucket_comparison"
        content2 = r2.get("content", "").encode("ascii", errors="replace").decode()
        print(f"  engine  : {eng2}")
        print(f"  content : {content2}")
        print(f"  T2: {'PASS' if ok2 else 'FAIL -- expected dual_bucket_comparison'}")
        if ok2:
            passed += 1
    except Exception as e:
        print(f"  T2: ERROR -- {repr(e)}")

    # ------------------------------------------------------------------
    # T3: unknown player — comparison must NOT fire
    # "Has ZZNONEXISTENTPLAYER scored more goals against top 5 or bottom 5 teams?"
    # Expected: engine != "dual_bucket_comparison"  (falls through to normal path)
    # ------------------------------------------------------------------
    q3 = "Has ZZNONEXISTENTPLAYER scored more goals against top 5 teams or bottom 5 teams?"
    print(f"\nT3: {q3}")
    try:
        r3 = engine.ask(q3)
        eng3 = _engine_label(r3)
        ok3 = eng3 != "dual_bucket_comparison"
        content3 = r3.get("content", "").encode("ascii", errors="replace").decode()
        print(f"  engine  : {eng3}")
        print(f"  content : {content3[:120]}")
        print(
            f"  T3: {'PASS' if ok3 else 'FAIL -- dual_bucket_comparison fired for unknown entity'}"
        )
        if ok3:
            passed += 1
    except Exception as e:
        print(f"  T3: ERROR -- {repr(e)}")

    # ------------------------------------------------------------------
    # T4: Issue B regression — last name only (no initial)
    # "Has Haaland scored more goals against top 5 teams or bottom 5 teams?"
    # Should resolve "Haaland" → "E. Haaland" and route to dual_bucket_comparison.
    # Expected: engine == "dual_bucket_comparison"
    # ------------------------------------------------------------------
    q4 = "Has Haaland scored more goals against top 5 teams or bottom 5 teams?"
    print(f"\nT4: {q4}")
    try:
        r4 = engine.ask(q4)
        eng4 = _engine_label(r4)
        ok4 = eng4 == "dual_bucket_comparison"
        content4 = r4.get("content", "").encode("ascii", errors="replace").decode()
        print(f"  engine  : {eng4}")
        print(f"  content : {content4}")
        print(f"  T4: {'PASS' if ok4 else 'FAIL -- expected dual_bucket_comparison'}")
        if ok4:
            passed += 1
    except Exception as e:
        print(f"  T4: ERROR -- {repr(e)}")

    print("\n" + "=" * 80)
    print(f"SMOKE SCORE: {passed}/{total}")
    print("=" * 80)
    return passed == total


if __name__ == "__main__":
    ok = run_smoke_tests()
    sys.exit(0 if ok else 1)
