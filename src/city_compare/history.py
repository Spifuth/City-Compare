"""Comparison history storage and retrieval."""

import json
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from .xdg import get_history_db_path


@dataclass
class HistoryEntry:
    """A single comparison history entry."""

    id: int
    timestamp: str
    cities: list[str]
    winner: str
    scores: dict[str, float]
    profile: str
    rules: str
    details: dict[str, Any] | None = None


class ComparisonHistory:
    """Manages comparison history storage in SQLite."""

    def __init__(self, db_path: Path | None = None) -> None:
        """
        Initialize history storage.

        Args:
            db_path: Path to SQLite database. Uses XDG default if not specified.
        """
        self.db_path = db_path or get_history_db_path()
        self._init_db()

    def _init_db(self) -> None:
        """Initialize the database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    cities TEXT NOT NULL,
                    winner TEXT NOT NULL,
                    scores TEXT NOT NULL,
                    profile TEXT NOT NULL,
                    rules TEXT NOT NULL,
                    details TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_timestamp ON history(timestamp)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_winner ON history(winner)
                """
            )
            conn.commit()

    def add(
        self,
        cities: list[str],
        winner: str,
        scores: dict[str, float],
        profile: str,
        rules: str,
        details: dict[str, Any] | None = None,
    ) -> int:
        """
        Add a comparison to history.

        Args:
            cities: List of compared cities.
            winner: The winning city.
            scores: Dict mapping city names to scores.
            profile: Profile file used.
            rules: Rules file used.
            details: Optional additional details.

        Returns:
            ID of the new history entry.
        """
        timestamp = datetime.now().isoformat()

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                INSERT INTO history (timestamp, cities, winner, scores, profile, rules, details)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    timestamp,
                    json.dumps(cities),
                    winner,
                    json.dumps(scores),
                    profile,
                    rules,
                    json.dumps(details) if details else None,
                ),
            )
            conn.commit()
            return cursor.lastrowid or 0

    def get(self, entry_id: int) -> HistoryEntry | None:
        """
        Get a specific history entry by ID.

        Args:
            entry_id: The entry ID.

        Returns:
            HistoryEntry or None if not found.
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM history WHERE id = ?",
                (entry_id,),
            )
            row = cursor.fetchone()

            if row is None:
                return None

            return HistoryEntry(
                id=row["id"],
                timestamp=row["timestamp"],
                cities=json.loads(row["cities"]),
                winner=row["winner"],
                scores=json.loads(row["scores"]),
                profile=row["profile"],
                rules=row["rules"],
                details=json.loads(row["details"]) if row["details"] else None,
            )

    def list_recent(self, limit: int = 20) -> list[HistoryEntry]:
        """
        List recent comparison history.

        Args:
            limit: Maximum number of entries to return.

        Returns:
            List of HistoryEntry objects, most recent first.
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM history ORDER BY timestamp DESC LIMIT ?",
                (limit,),
            )

            return [
                HistoryEntry(
                    id=row["id"],
                    timestamp=row["timestamp"],
                    cities=json.loads(row["cities"]),
                    winner=row["winner"],
                    scores=json.loads(row["scores"]),
                    profile=row["profile"],
                    rules=row["rules"],
                    details=json.loads(row["details"]) if row["details"] else None,
                )
                for row in cursor.fetchall()
            ]

    def search(
        self,
        city: str | None = None,
        winner: str | None = None,
        from_date: str | None = None,
        to_date: str | None = None,
        limit: int = 50,
    ) -> list[HistoryEntry]:
        """
        Search history with filters.

        Args:
            city: Filter by city (any city in comparison).
            winner: Filter by winner.
            from_date: Filter from date (ISO format).
            to_date: Filter to date (ISO format).
            limit: Maximum results.

        Returns:
            List of matching HistoryEntry objects.
        """
        query = "SELECT * FROM history WHERE 1=1"
        params: list[Any] = []

        if city:
            query += " AND cities LIKE ?"
            params.append(f"%{city}%")

        if winner:
            query += " AND winner = ?"
            params.append(winner)

        if from_date:
            query += " AND timestamp >= ?"
            params.append(from_date)

        if to_date:
            query += " AND timestamp <= ?"
            params.append(to_date)

        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(query, params)

            return [
                HistoryEntry(
                    id=row["id"],
                    timestamp=row["timestamp"],
                    cities=json.loads(row["cities"]),
                    winner=row["winner"],
                    scores=json.loads(row["scores"]),
                    profile=row["profile"],
                    rules=row["rules"],
                    details=json.loads(row["details"]) if row["details"] else None,
                )
                for row in cursor.fetchall()
            ]

    def get_stats(self) -> dict[str, Any]:
        """
        Get statistics about comparison history.

        Returns:
            Dict with various statistics.
        """
        with sqlite3.connect(self.db_path) as conn:
            # Total comparisons
            total = conn.execute("SELECT COUNT(*) FROM history").fetchone()[0]

            # Winner counts
            winner_counts = dict(
                conn.execute(
                    """
                    SELECT winner, COUNT(*) as count
                    FROM history
                    GROUP BY winner
                    ORDER BY count DESC
                    LIMIT 10
                    """
                ).fetchall()
            )

            # Most compared cities
            all_cities: dict[str, int] = {}
            for (cities_json,) in conn.execute("SELECT cities FROM history"):
                for city in json.loads(cities_json):
                    all_cities[city] = all_cities.get(city, 0) + 1

            most_compared = sorted(all_cities.items(), key=lambda x: -x[1])[:10]

            # Recent activity
            recent_count = conn.execute(
                """
                SELECT COUNT(*) FROM history
                WHERE timestamp >= datetime('now', '-7 days')
                """
            ).fetchone()[0]

            return {
                "total_comparisons": total,
                "top_winners": winner_counts,
                "most_compared_cities": dict(most_compared),
                "comparisons_last_7_days": recent_count,
            }

    def delete(self, entry_id: int) -> bool:
        """
        Delete a history entry.

        Args:
            entry_id: ID of entry to delete.

        Returns:
            True if deleted, False if not found.
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "DELETE FROM history WHERE id = ?",
                (entry_id,),
            )
            conn.commit()
            return cursor.rowcount > 0

    def clear(self) -> int:
        """
        Clear all history.

        Returns:
            Number of entries deleted.
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("DELETE FROM history")
            conn.commit()
            return cursor.rowcount

    def export_json(self) -> str:
        """Export all history as JSON."""
        entries = self.list_recent(limit=10000)
        return json.dumps([asdict(e) for e in entries], indent=2, ensure_ascii=False)

    def import_json(self, json_data: str) -> int:
        """
        Import history from JSON.

        Args:
            json_data: JSON string with history entries.

        Returns:
            Number of entries imported.
        """
        entries = json.loads(json_data)
        count = 0

        for entry in entries:
            self.add(
                cities=entry["cities"],
                winner=entry["winner"],
                scores=entry["scores"],
                profile=entry["profile"],
                rules=entry["rules"],
                details=entry.get("details"),
            )
            count += 1

        return count
