"""Tests for the NLP-01 raw-key guard and label-violation guard."""
from __future__ import annotations

import pytest
from evals.raw_key_guard import find_label_violations, find_violations, load_forbidden_tokens


@pytest.fixture(scope="module")
def forb():
    return load_forbidden_tokens()


class TestForbiddenTokenLoad:
    def test_contains_known_columns(self, forb):
        assert "total_goals" in forb
        assert "xg_total_p90" in forb
        assert "pass_accuracy_pct" in forb
        assert "metric_value" in forb
        assert "opponent_is_big6" in forb

    def test_excludes_prose_nouns(self, forb):
        assert "goals" not in forb
        assert "assists" not in forb
        assert "minutes" not in forb

    def test_nonempty(self, forb):
        assert len(forb) >= 30  # current AVAILABLE STATS has well over this


class TestFindViolations:
    def test_clean_natural_answer(self):
        assert find_violations("Haaland has scored 5 goals against the Big Six.") == []

    def test_raw_column_caught(self):
        hits = find_violations("Haaland total_goals = 5 across 8 appearances")
        assert "total_goals" in hits

    def test_p90_column_caught(self):
        hits = find_violations("xg_total_p90 was 0.473 vs Big Six")
        assert "xg_total_p90" in hits

    def test_filter_key_caught(self):
        # opponent_is_big6 is a filter key, not a stat — still robotic
        assert "opponent_is_big6" in find_violations("filter opponent_is_big6=true used")

    def test_case_insensitive(self):
        assert "total_goals" in find_violations("TOTAL_GOALS = 5")

    def test_word_boundary(self):
        # "subtotal_goals" should not flag "total_goals"
        assert find_violations("That subtotal_goalsmith dribbled past") == []

    def test_multiple_distinct(self):
        hits = find_violations("returned total_goals=5 and xg_total=3.44")
        assert "total_goals" in hits and "xg_total" in hits

    def test_total_metric_value_caught(self):
        hits = find_violations("Haaland total_metric_value 22 goals")
        assert "total_metric_value" in hits

    def test_first_name_caught(self):
        hits = find_violations("player first_name is Jacob")
        assert "first_name" in hits

    def test_last_name_caught(self):
        hits = find_violations("use last_name field to identify")
        assert "last_name" in hits


class TestFindLabelViolations:
    def test_no_violation_when_user_wrote_big_six(self):
        # User explicitly said "Big Six" — answer may use it
        assert find_label_violations(
            "How many goals did Haaland score against the Big Six?",
            "Haaland scored 5 goals against the Big Six this season.",
        ) == []

    def test_violation_when_user_said_top_6_but_answer_says_big_six(self):
        # UAT regression: user said "top 6 teams", answer must not say "Big Six"
        violations = find_label_violations(
            "How many minutes has Salah played against top 6 teams?",
            "Mohamed Salah has played 890 minutes against the Big Six this season.",
        )
        assert len(violations) == 1
        assert "Big Six" in violations[0]

    def test_no_violation_when_answer_uses_correct_top_six_label(self):
        violations = find_label_violations(
            "How many minutes has Salah played against top 6 teams?",
            "Mohamed Salah has played 890 minutes against the top six teams this season.",
        )
        assert violations == []

    def test_case_insensitive_big_six_detection(self):
        violations = find_label_violations(
            "goals against top six",
            "He scored 5 against the big six.",
        )
        assert len(violations) == 1

    def test_no_violation_when_big_six_absent_from_answer(self):
        assert find_label_violations(
            "How did Salah do against the top six?",
            "Salah scored 6 goals against the top six teams this season.",
        ) == []
