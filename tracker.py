"""Core presence tracking logic."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Dict, Iterable, Optional, Tuple

from .database import Database

try:  # pragma: no cover - optional import for typing convenience
    import discord
except Exception:  # pragma: no cover
    discord = None  # type: ignore

TrackedStatus = Tuple[str, ...]


@dataclass(slots=True)
class ActiveSession:
    """Represents an in-memory session that has not yet closed."""

    row_id: int
    started_at: datetime
    status: str


class PresenceTracker:
    """Tracks presence transitions and persists them in the database."""

    TRACKED_STATUSES: TrackedStatus = ("online", "idle", "dnd")

    def __init__(self, database: Database) -> None:
        self._database = database
        self._active_sessions: Dict[tuple[int, int], ActiveSession] = {}

    async def setup(self) -> None:
        """Ensure the database schema exists and clean up stale sessions."""

        now = datetime.now(tz=UTC)
        await self._database.initialize()
        await self._database.close_open_sessions(now)

    async def bootstrap_member(self, guild_id: int, user_id: int, status: object) -> None:
        """Start an active session for members currently online when the bot boots."""

        normalized = self._normalize_status(status)
        if not self._is_tracked(normalized):
            return
        key = (guild_id, user_id)
        if key in self._active_sessions:
            return
        started_at = datetime.now(tz=UTC)
        row_id = await self._database.insert_session(
            guild_id=guild_id,
            user_id=user_id,
            status=normalized,
            started_at=started_at,
        )
        self._active_sessions[key] = ActiveSession(row_id=row_id, started_at=started_at, status=normalized)

    async def handle_presence_update(
        self,
        guild_id: int,
        user_id: int,
        before_status: object,
        after_status: object,
        timestamp: Optional[datetime] = None,
    ) -> None:
        """Record status changes for the provided member."""

        timestamp = timestamp or datetime.now(tz=UTC)
        before = self._normalize_status(before_status)
        after = self._normalize_status(after_status)
        key = (guild_id, user_id)
        active = self._active_sessions.get(key)

        before_tracked = self._is_tracked(before)
        after_tracked = self._is_tracked(after)

        if before_tracked and active and (not after_tracked or after != active.status):
            await self._close_session(key, timestamp)
            active = None

        if after_tracked:
            if active is None:
                row_id = await self._database.insert_session(guild_id, user_id, after, timestamp)
                self._active_sessions[key] = ActiveSession(row_id=row_id, started_at=timestamp, status=after)
            elif active.status != after:
                # we have already closed the previous session, start a new one
                row_id = await self._database.insert_session(guild_id, user_id, after, timestamp)
                self._active_sessions[key] = ActiveSession(row_id=row_id, started_at=timestamp, status=after)
        elif active and not after_tracked:
            # Ensure no lingering sessions for non-tracked statuses
            await self._close_session(key, timestamp)

    async def _close_session(self, key: tuple[int, int], ended_at: datetime) -> None:
        session = self._active_sessions.pop(key, None)
        if session is None:
            return
        await self._database.complete_session(session.row_id, ended_at)

    async def get_total_duration(
        self,
        guild_id: int,
        user_id: int,
        statuses: Optional[Iterable[str]] = None,
        now: Optional[datetime] = None,
    ) -> timedelta:
        """Compute total duration across stored sessions."""

        now = now or datetime.now(tz=UTC)
        statuses_tuple = self._normalize_statuses(statuses)
        sessions = await self._database.fetch_sessions(guild_id, user_id, statuses_tuple)
        total = timedelta()
        for session in sessions:
            end = session.ended_at or now
            total += end - session.started_at
        key = (guild_id, user_id)
        active = self._active_sessions.get(key)
        if active and active.status in statuses_tuple:
            total += now - active.started_at
        return total

    def format_timedelta(self, delta: timedelta) -> str:
        """Return a human readable representation of a duration."""

        total_seconds = int(delta.total_seconds())
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        parts = []
        if hours:
            parts.append(f"{hours}h")
        if minutes:
            parts.append(f"{minutes}m")
        if seconds or not parts:
            parts.append(f"{seconds}s")
        return " ".join(parts)

    def _normalize_status(self, status: object) -> str:
        if status is None:
            return "offline"
        if discord and isinstance(status, discord.Status):  # pragma: no cover - requires discord package
            return status.value
        return str(status).lower()

    def _normalize_statuses(self, statuses: Optional[Iterable[str]]) -> TrackedStatus:
        if statuses is None:
            return self.TRACKED_STATUSES
        normalized = tuple(self._normalize_status(status) for status in statuses)
        return tuple(status for status in normalized if self._is_tracked(status)) or self.TRACKED_STATUSES

    def _is_tracked(self, status: str) -> bool:
        return status in self.TRACKED_STATUSES

    @property
    def active_sessions(self) -> Dict[tuple[int, int], ActiveSession]:
        """Expose active sessions for introspection/testing."""

        return dict(self._active_sessions)