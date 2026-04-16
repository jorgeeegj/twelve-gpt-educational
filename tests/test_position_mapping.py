"""
Tests for normalize_position() in agent_tools.py.

Run manually: python -m pytest tests/test_position_mapping.py -v
"""

import pytest

from src.basic_stats.agent_tools import normalize_position


class TestNormalizePosition:
    def test_central_defender_aliases(self):
        assert normalize_position("CB") == "Central Defender"
        assert normalize_position("cb") == "Central Defender"
        assert normalize_position("center back") == "Central Defender"
        assert normalize_position("Centre back") == "Central Defender"
        assert normalize_position("defender") == "Central Defender"

    def test_full_back_aliases(self):
        assert normalize_position("fullback") == "Full Back"
        assert normalize_position("lb") == "Full Back"
        assert normalize_position("rb") == "Full Back"
        assert normalize_position("right back") == "Full Back"

    def test_goalkeeper_aliases(self):
        assert normalize_position("keeper") == "Goalkeeper"
        assert normalize_position("GK") == "Goalkeeper"
        assert normalize_position("goalie") == "Goalkeeper"

    def test_midfielder_aliases(self):
        assert normalize_position("mid") == "Midfielder"
        assert normalize_position("CDM") == "Midfielder"
        assert normalize_position("cam") == "Midfielder"
        assert normalize_position("central midfielder") == "Midfielder"

    def test_striker_aliases(self):
        assert normalize_position("striker") == "Striker"
        assert normalize_position("forward") == "Striker"
        assert normalize_position("CF") == "Striker"
        assert normalize_position("centre forward") == "Striker"

    def test_winger_aliases(self):
        assert normalize_position("winger") == "Winger"
        assert normalize_position("LW") == "Winger"
        assert normalize_position("rw") == "Winger"
        assert normalize_position("wide") == "Winger"

    def test_canonical_passthrough(self):
        assert normalize_position("Striker") == "Striker"
        assert normalize_position("Goalkeeper") == "Goalkeeper"
        assert normalize_position("Central Defender") == "Central Defender"

    def test_unknown_passthrough(self):
        assert normalize_position("attacking midfield") == "attacking midfield"

    def test_none_returns_none(self):
        assert normalize_position(None) is None
