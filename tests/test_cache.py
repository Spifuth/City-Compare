"""Tests for the local cache."""

import time
from pathlib import Path

import pytest

from city_compare.cache import LocalCache


class TestLocalCache:
    """Test SQLite cache."""

    def test_set_and_get(self, tmp_path: Path):
        """Test basic set and get operations."""
        cache = LocalCache(tmp_path / "cache.db")
        
        cache.set("key1", {"value": 42})
        result = cache.get("key1")
        
        assert result == {"value": 42}

    def test_get_nonexistent_key(self, tmp_path: Path):
        """Test getting a key that doesn't exist."""
        cache = LocalCache(tmp_path / "cache.db")
        
        result = cache.get("nonexistent")
        
        assert result is None

    def test_overwrite_key(self, tmp_path: Path):
        """Test overwriting an existing key."""
        cache = LocalCache(tmp_path / "cache.db")
        
        cache.set("key1", "value1")
        cache.set("key1", "value2")
        result = cache.get("key1")
        
        assert result == "value2"

    def test_ttl_not_expired(self, tmp_path: Path):
        """Test that cache returns value before TTL expires."""
        cache = LocalCache(tmp_path / "cache.db")
        
        cache.set("key1", "value1", ttl_seconds=10)
        result = cache.get("key1")
        
        assert result == "value1"

    def test_ttl_expired(self, tmp_path: Path):
        """Test that cache returns None after TTL expires."""
        cache = LocalCache(tmp_path / "cache.db")
        
        cache.set("key1", "value1", ttl_seconds=1)
        time.sleep(1.1)
        result = cache.get("key1")
        
        assert result is None

    def test_delete(self, tmp_path: Path):
        """Test deleting a cache entry."""
        cache = LocalCache(tmp_path / "cache.db")
        
        cache.set("key1", "value1")
        cache.delete("key1")
        result = cache.get("key1")
        
        assert result is None

    def test_clear(self, tmp_path: Path):
        """Test clearing all cache entries."""
        cache = LocalCache(tmp_path / "cache.db")
        
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.clear()
        
        assert cache.get("key1") is None
        assert cache.get("key2") is None

    def test_complex_values(self, tmp_path: Path):
        """Test caching complex nested values."""
        cache = LocalCache(tmp_path / "cache.db")
        
        complex_value = {
            "list": [1, 2, 3],
            "nested": {"a": "b"},
            "float": 3.14,
            "null": None,
        }
        
        cache.set("complex", complex_value)
        result = cache.get("complex")
        
        assert result == complex_value
