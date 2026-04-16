"""
Tests for src/basic_stats/config.py
Run with: python -m pytest tests/test_config.py -v
"""

from src.basic_stats.config import get_embeddings_model, get_model


def test_get_model_returns_string():
    result = get_model()
    assert isinstance(result, str)
    assert len(result) > 0


def test_get_embeddings_model_returns_string():
    result = get_embeddings_model()
    assert isinstance(result, str)
    assert len(result) > 0


def test_get_embeddings_model_is_different_from_chat_model():
    assert get_embeddings_model() != get_model()
