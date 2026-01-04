"""Local cache for API responses (geocoding, weather)."""

import json
import sqlite3
import time
from pathlib import Path
from typing import Any


class LocalCache:
    """SQLite-based local cache for API responses."""

    def __init__(self, db_path: Path = Path("data/cache.db")):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        """Initialize database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cache (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    ttl_seconds INTEGER DEFAULT NULL
                )
            """)
            conn.commit()

    def get(self, key: str) -> Any | None:
        """Get value from cache, returns None if not found or expired."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT value, created_at, ttl_seconds FROM cache WHERE key = ?",
                (key,),
            )
            row = cursor.fetchone()

            if row is None:
                return None

            value, created_at, ttl = row

            # Check expiration if TTL is set
            if ttl is not None and time.time() - created_at > ttl:
                conn.execute("DELETE FROM cache WHERE key = ?", (key,))
                conn.commit()
                return None

            return json.loads(value)

    def set(self, key: str, value: Any, ttl_seconds: int | None = None) -> None:
        """Store value in cache."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO cache (key, value, created_at, ttl_seconds)
                VALUES (?, ?, ?, ?)
                """,
                (key, json.dumps(value), time.time(), ttl_seconds),
            )
            conn.commit()

    def clear(self) -> None:
        """Clear all cache entries."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM cache")
            conn.commit()

    def delete(self, key: str) -> None:
        """Delete a specific cache entry."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM cache WHERE key = ?", (key,))
            conn.commit()
