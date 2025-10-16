"""Entry point for running the Discord Online Tracker bot."""

from __future__ import annotations

import asyncio
from pathlib import Path

from discord_online_tracker.bot import run_from_env


def main() -> None:
    env_file = Path(".env")
    if env_file.exists():
        asyncio.run(run_from_env(str(env_file)))
    else:
        asyncio.run(run_from_env())


if __name__ == "__main__":
    main()