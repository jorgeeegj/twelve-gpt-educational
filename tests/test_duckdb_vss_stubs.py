"""
Tests for DuckDB VSS methods (implemented in Phase 6).
Run with: python -m pytest tests/test_duckdb_vss_stubs.py -v
"""

import pytest

from src.basic_stats.duckdb_manager import DuckDBManager


@pytest.fixture(scope="module")
def duck():
    return DuckDBManager()


def test_store_entity_embeddings_is_callable(duck):
    # Method is now implemented — verify it exists and accepts (client, model) args.
    # Full execution requires Azure credentials; tested in test_fuzzy_resolve.py.
    import inspect

    sig = inspect.signature(duck.store_entity_embeddings)
    assert "client" in sig.parameters
    assert "model" in sig.parameters


def test_fuzzy_resolve_entity_passthrough_without_client(duck):
    # Without a client, fuzzy_resolve_entity returns the input unchanged (safe fallback).
    result = duck.fuzzy_resolve_entity("Salah", "player")
    assert result == "Salah"


def test_fuzzy_resolve_entity_passthrough_for_team_without_client(duck):
    result = duck.fuzzy_resolve_entity("Man City", "team")
    assert result == "Man City"


def test_existing_query_dicts_still_works(duck):
    """Smoke check: no existing method signatures broken."""
    rows = duck.query_dicts("SELECT 1 AS val")
    assert rows == [{"val": 1}]


def test_existing_table_counts_still_works(duck):
    counts = duck.table_counts()
    assert "players_summary" in counts
    assert counts["players_summary"] > 0


def test_p90_agg_produces_correct_sql(duck):
    """_match_value_expr with agg='p90' should produce a ratio expression."""
    expr = duck._match_value_expr("goals", "p90", "pms")
    assert "minutes_played" in expr
    assert "NULLIF" in expr
    assert "90" in expr
