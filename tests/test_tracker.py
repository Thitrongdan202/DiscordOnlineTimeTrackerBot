from __future__ import annotations

import asyncio
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from discord_online_tracker.database import Database
from discord_online_tracker.tracker import PresenceTracker


def test_presence_cycle(tmp_path) -> None:
    db_path = tmp_path / "tracker.sqlite"
    tracker = PresenceTracker(Database(db_path))

    async def scenario() -> timedelta:
        await tracker.setup()
        start = datetime(2024, 1, 1, 12, 0, tzinfo=UTC)
        mid = start + timedelta(hours=2)
        end = mid + timedelta(hours=1)

        await tracker.handle_presence_update(1, 42, "offline", "online", timestamp=start)
        assert (1, 42) in tracker.active_sessions

        await tracker.handle_presence_update(1, 42, "online", "idle", timestamp=mid)
        await tracker.handle_presence_update(1, 42, "idle", "offline", timestamp=end)

        return await tracker.get_total_duration(1, 42)

    total = asyncio.run(scenario())
    assert total == timedelta(hours=3)


def test_ignore_untracked_status(tmp_path) -> None:
    db_path = tmp_path / "tracker.sqlite"
    tracker = PresenceTracker(Database(db_path))

    async def scenario() -> timedelta:
        await tracker.setup()
        start = datetime(2024, 1, 2, 12, 0, tzinfo=UTC)
        end = start + timedelta(minutes=30)

        await tracker.handle_presence_update(1, 99, "offline", "streaming", timestamp=start)
        assert tracker.active_sessions == {}

        await tracker.handle_presence_update(1, 99, "streaming", "online", timestamp=start)
        await tracker.handle_presence_update(1, 99, "online", "offline", timestamp=end)

        return await tracker.get_total_duration(1, 99)

    total = asyncio.run(scenario())
    assert total == timedelta(minutes=30)


def test_formatting() -> None:
    db = Database("/tmp/example.sqlite")
    tracker = PresenceTracker(db)
    formatted = tracker.format_timedelta(timedelta(hours=2, minutes=5, seconds=9))
    assert formatted == "2h 5m 9s"