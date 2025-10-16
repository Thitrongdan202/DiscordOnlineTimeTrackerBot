"""Discord Online Tracker package."""

from __future__ import annotations

from importlib import import_module
from typing import Any

__all__ = ["OnlineTrackerBot", "BotConfig", "PresenceTracker"]


def __getattr__(name: str) -> Any:  # pragma: no cover - simple passthrough
    if name == "OnlineTrackerBot":
        return import_module("discord_online_tracker.bot").OnlineTrackerBot
    if name == "BotConfig":
        return import_module("discord_online_tracker.config").BotConfig
    if name == "PresenceTracker":
        return import_module("discord_online_tracker.tracker").PresenceTracker
    raise AttributeError(name)