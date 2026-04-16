"""
Tests for DuckDB VSS stub methods (Phase 6 placeholders).
Run with: python -m pytest tests/test_duckdb_vss_stubs.py -v
"""

import pytest

from src.basic_stats.duckdb_manager import DuckDBManager


@pytest.fixture(scope="module")
def duck():
    return DuckDBManager()


def test_store_entity_embeddings_raises_not_implemented(duck):
    with pytest.raises(NotImplementedError):
        duck.store_entity_embeddings()


def test_fuzzy_resolve_entity_raises_not_implemented(duck):
    with pytest.raises(NotImplementedError):
        duck.fuzzy_resolve_entity("Salah", "player")


def test_fuzzy_resolve_entity_raises_not_implemented_for_team(duck):
    with pytest.raises(NotImplementedError):
        duck.fuzzy_resolve_entity("Man City", "team")


def test_existing_query_dicts_still_works(duck):
    """Smoke check: no existing method signatures broken."""
    rows = duck.query_dicts("SELECT 1 AS val")
    assert rows == [{"val": 1}]


def test_existing_table_counts_still_works(duck):
    counts = duck.table_counts()
    assert "players_summary" in counts
    assert counts["players_summary"] > 0
