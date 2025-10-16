"""Configuration loading utilities for the Discord Online Tracker bot."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv


@dataclass(slots=True)
class BotConfig:
    """Runtime configuration for the bot."""

    token: str
    database_path: Path
    timezone: str = "UTC"

    @classmethod
    def load(cls, env_file: Optional[Path] = None) -> "BotConfig":
        """Load configuration from environment variables.

        Parameters
        ----------
        env_file:
            Optional path to a dotenv file to load before reading configuration.
        """

        if env_file is not None:
            load_dotenv(env_file)
        else:
            load_dotenv()

        token = os.getenv("DISCORD_TOKEN")
        if not token:
            raise RuntimeError("DISCORD_TOKEN is not set")

        database_path = Path(os.getenv("DATABASE_PATH", "online_tracker.db")).expanduser()
        timezone = os.getenv("TIMEZONE", "UTC")
        return cls(token=token, database_path=database_path, timezone=timezone)