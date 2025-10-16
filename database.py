"""Database helpers for storing presence sessions."""

from __future__ import annotations

import asyncio
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass(slots=True)
class PresenceSession:
    """Represents a single tracked session."""

    row_id: int
    guild_id: int
    user_id: int
    status: str
    started_at: datetime
    ended_at: Optional[datetime]


class Database:
    """SQLite-backed storage with asyncio-friendly helpers."""

    def __init__(self, database_path: Path) -> None:
        self._database_path = Path(database_path)
        self._lock = asyncio.Lock()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._database_path)
        conn.row_factory = sqlite3.Row
        return conn

    async def initialize(self) -> None:
        async with self._lock:
            await asyncio.to_thread(self._initialize_sync)

    def _initialize_sync(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS presence_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    ended_at TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_presence_sessions_lookup
                ON presence_sessions (guild_id, user_id, status)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_presence_sessions_open
                ON presence_sessions (guild_id, user_id, ended_at)
                """
            )
            conn.commit()

    async def close_open_sessions(self, closed_at: datetime) -> None:
        await asyncio.to_thread(self._close_open_sessions_sync, closed_at)

    def _close_open_sessions_sync(self, closed_at: datetime) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE presence_sessions
                SET ended_at = ?
                WHERE ended_at IS NULL
                """,
                (closed_at.isoformat(),),
            )
            conn.commit()

    async def insert_session(
        self,
        guild_id: int,
        user_id: int,
        status: str,
        started_at: datetime,
    ) -> int:
        return await asyncio.to_thread(
            self._insert_session_sync, guild_id, user_id, status, started_at
        )

    def _insert_session_sync(
        self, guild_id: int, user_id: int, status: str, started_at: datetime
    ) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO presence_sessions (guild_id, user_id, status, started_at)
                VALUES (?, ?, ?, ?)
                """,
                (guild_id, user_id, status, started_at.isoformat()),
            )
            conn.commit()
            return int(cursor.lastrowid)

    async def complete_session(self, row_id: int, ended_at: datetime) -> None:
        await asyncio.to_thread(self._complete_session_sync, row_id, ended_at)

    def _complete_session_sync(self, row_id: int, ended_at: datetime) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE presence_sessions
                SET ended_at = ?
                WHERE id = ?
                """,
                (ended_at.isoformat(), row_id),
            )
            conn.commit()

    async def fetch_sessions(
        self,
        guild_id: int,
        user_id: int,
        statuses: tuple[str, ...],
    ) -> list[PresenceSession]:
        return await asyncio.to_thread(self._fetch_sessions_sync, guild_id, user_id, statuses)

    def _fetch_sessions_sync(
        self,
        guild_id: int,
        user_id: int,
        statuses: tuple[str, ...],
    ) -> list[PresenceSession]:
        placeholders = ",".join("?" for _ in statuses)
        query = f"""
            SELECT id, guild_id, user_id, status, started_at, ended_at
            FROM presence_sessions
            WHERE guild_id = ? AND user_id = ? AND status IN ({placeholders})
            ORDER BY started_at ASC
        """
        with self._connect() as conn:
            cursor = conn.execute(query, (guild_id, user_id, *statuses))
            rows = cursor.fetchall()

        sessions: list[PresenceSession] = []
        for row in rows:
            started_at = datetime.fromisoformat(row["started_at"])
            ended_at = datetime.fromisoformat(row["ended_at"]) if row["ended_at"] else None
            sessions.append(
                PresenceSession(
                    row_id=int(row["id"]),
                    guild_id=int(row["guild_id"]),
                    user_id=int(row["user_id"]),
                    status=str(row["status"]),
                    started_at=started_at,
                    ended_at=ended_at,
                )
            )
        return sessions