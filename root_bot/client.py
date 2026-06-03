from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands

from .config import Settings, load_settings
from .features.about import AboutCog
from .features.automod import AutoModCog
from .features.giveaways import GiveawayCog
from .features.rules import RulesCog
from .features.tickets import TicketCloseView, TicketCog, TicketPanelView, TicketTermsView
from .features.welcome import WelcomeCog


logger = logging.getLogger("root-bot")


class OwnerOnlyCommandTree(app_commands.CommandTree):
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        settings = getattr(self.client, "settings", None)
        owner_id = getattr(settings, "bot_owner_id", None)
        if owner_id is None or interaction.user.id == owner_id:
            return True

        message = "Este bot es privado. Solo el owner puede usar sus comandos."
        try:
            if interaction.response.is_done():
                await interaction.followup.send(message, ephemeral=True)
            else:
                await interaction.response.send_message(message, ephemeral=True)
        except discord.DiscordException:
            logger.warning("No pude responder bloqueo de comando para usuario %s.", interaction.user.id)

        return False


class RootBot(commands.Bot):
    def __init__(self, settings: Settings) -> None:
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True

        super().__init__(command_prefix="!", intents=intents, tree_cls=OwnerOnlyCommandTree)
        self.settings = settings
        self._presence_ready = False

    async def setup_hook(self) -> None:
        self.add_view(TicketPanelView(self.settings))
        self.add_view(TicketTermsView(self.settings))
        self.add_view(TicketCloseView(self.settings))

        await self.add_cog(WelcomeCog(self, self.settings))
        await self.add_cog(RulesCog(self, self.settings))
        await self.add_cog(AboutCog(self, self.settings))
        await self.add_cog(TicketCog(self, self.settings))
        await self.add_cog(AutoModCog(self, self.settings))
        await self.add_cog(GiveawayCog(self, self.settings))

        if self.settings.guild_id is not None:
            guild = discord.Object(id=self.settings.guild_id)
            self.tree.clear_commands(guild=guild)
            cleared_guild = await self.tree.sync(guild=guild)
            logger.info("Slash commands especificos de guild %s limpiados: %s", self.settings.guild_id, len(cleared_guild))

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
