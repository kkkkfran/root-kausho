from __future__ import annotations

import logging

import discord
from discord.ext import commands

from .config import Settings, load_settings
from .features.about import AboutCog
from .features.rules import RulesCog
from .features.welcome import WelcomeCog


logger = logging.getLogger("root-bot")


class RootBot(commands.Bot):
    def __init__(self, settings: Settings) -> None:
        intents = discord.Intents.default()
        intents.members = True

        super().__init__(command_prefix="!", intents=intents)
        self.settings = settings
        self._presence_ready = False

    async def setup_hook(self) -> None:
        await self.add_cog(WelcomeCog(self, self.settings))
        await self.add_cog(RulesCog(self, self.settings))
        await self.add_cog(AboutCog(self, self.settings))

        if self.settings.guild_id is not None:
            guild = discord.Object(id=self.settings.guild_id)
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
            logger.info("Slash commands sincronizados en guild %s: %s", self.settings.guild_id, len(synced))
            self.tree.clear_commands(guild=None)
            cleared = await self.tree.sync()
            logger.info("Slash commands globales limpiados para evitar duplicados: %s", len(cleared))
            return

        synced = await self.tree.sync()
        logger.info("Slash commands globales sincronizados: %s", len(synced))

    async def on_ready(self) -> None:
        if not self._presence_ready and self.settings.bot_status:
            await self.change_presence(
                activity=discord.Activity(
                    type=discord.ActivityType.watching,
                    name=self.settings.bot_status,
                )
            )
            self._presence_ready = True

        logger.info("Conectado como %s (ID: %s)", self.user, self.user.id if self.user else "desconocido")


def run() -> None:
    settings = load_settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    bot = RootBot(settings)
    bot.run(settings.token)
