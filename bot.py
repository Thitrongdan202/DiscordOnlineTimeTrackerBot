"""Bot implementation wiring Discord events to the tracker."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Optional

import discord
from discord.ext import commands

from .config import BotConfig
from .database import Database
from .tracker import PresenceTracker


class OnlineTrackerBot(commands.Bot):
    """Discord bot that records online time for guild members."""

    def __init__(self, config: BotConfig) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.presences = True
        super().__init__(command_prefix="!", intents=intents)

        self.config = config
        self.database = Database(config.database_path)
        self.tracker = PresenceTracker(self.database)

    async def setup_hook(self) -> None:
        await self.tracker.setup()
        await self._bootstrap_guilds()

    async def _bootstrap_guilds(self) -> None:
        for guild in self.guilds:
            await self._bootstrap_guild(guild)

    async def _bootstrap_guild(self, guild: discord.Guild) -> None:
        for member in guild.members:
            await self.tracker.bootstrap_member(guild.id, member.id, member.status)

    async def on_guild_join(self, guild: discord.Guild) -> None:  # pragma: no cover - requires discord runtime
        await self._bootstrap_guild(guild)

    async def on_presence_update(  # pragma: no cover - requires discord runtime
        self, before: discord.Member, after: discord.Member
    ) -> None:
        await self.tracker.handle_presence_update(
            guild_id=after.guild.id,
            user_id=after.id,
            before_status=before.status,
            after_status=after.status,
        )

    async def on_ready(self) -> None:  # pragma: no cover - requires discord runtime
        if self.user:
            print(f"Logged in as {self.user} (ID: {self.user.id})")

    def run_bot(self) -> None:
        super().run(self.config.token)

    def add_commands(self) -> None:
        @self.command(name="online")
        async def online(ctx: commands.Context, member: Optional[discord.Member] = None, status: Optional[str] = None) -> None:
            target = member or ctx.author
            if target is None:
                await ctx.send("Unable to resolve member.")
                return

            statuses = None
            if status is not None:
                normalized = self.tracker._normalize_status(status)
                if not self.tracker._is_tracked(normalized):
                    await ctx.send("Status must be one of: online, idle, dnd.")
                    return
                statuses = (normalized,)

            now = datetime.now(tz=UTC)
            total = await self.tracker.get_total_duration(ctx.guild.id, target.id, statuses, now=now)
            formatted = self.tracker.format_timedelta(total)
            await ctx.send(f"{target.display_name} has been {status or 'online'} for {formatted}.")

        @self.command(name="presence-status")
        async def presence_status(ctx: commands.Context) -> None:
            active = self.tracker.active_sessions
            if not active:
                await ctx.send("No active sessions currently tracked.")
                return
            lines = []
            for (guild_id, user_id), session in active.items():
                lines.append(
                    f"Guild {guild_id} | User {user_id} -> {session.status} since {session.started_at.astimezone(UTC).isoformat()}"
                )
            await ctx.send("\n".join(lines))

    async def start_bot(self) -> None:
        self.add_commands()
        await self.start(self.config.token)


async def run_from_env(env_file: Optional[str] = None) -> None:
    config = BotConfig.load(Path(env_file) if env_file else None)
    bot = OnlineTrackerBot(config)
    bot.add_commands()
    await bot.start(config.token)


def main() -> None:
    config = BotConfig.load()
    bot = OnlineTrackerBot(config)
    bot.add_commands()
    bot.run_bot()


if __name__ == "__main__":  # pragma: no cover - manual execution
    main()