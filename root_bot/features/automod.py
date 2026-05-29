from __future__ import annotations

import logging
import re
from collections import defaultdict, deque
from datetime import timedelta

import discord
from discord import app_commands
from discord.ext import commands

from ..config import Settings


logger = logging.getLogger("root-bot.automod")

DISCORD_INVITE_PATTERN = re.compile(
    r"(?:https?://)?(?:www\.)?(?:discord\.gg|discord(?:app)?\.com/invite)/[a-zA-Z0-9-]+",
    re.IGNORECASE,
)
URL_PATTERN = re.compile(r"https?://(?:www\.)?([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})(?:/[^\s]*)?", re.IGNORECASE)


class AutoModCog(commands.Cog):
    def __init__(self, bot: commands.Bot, settings: Settings) -> None:
        self.bot = bot
        self.settings = settings
        self.enabled = settings.automod_enabled
        self.user_messages: dict[tuple[int, int], deque[float]] = defaultdict(deque)

    def is_exempt(self, member: discord.Member) -> bool:
        if member.bot:
            return True

        if member.guild_permissions.manage_messages or member.guild_permissions.manage_guild:
            return True

        if self.settings.automod_exempt_role_id is not None:
            return any(role.id == self.settings.automod_exempt_role_id for role in member.roles)

        return False

    def has_blocked_invite(self, content: str) -> bool:
        return self.settings.automod_block_invites and DISCORD_INVITE_PATTERN.search(content) is not None

    def has_blocked_link(self, content: str) -> bool:
        if not self.settings.automod_block_links:
            return False

        for match in URL_PATTERN.finditer(content):
            domain = match.group(1).lower().removeprefix("www.")
            if any(domain == allowed or domain.endswith(f".{allowed}") for allowed in self.settings.automod_allowed_domains):
                continue

            return True

        return False

    def is_spam(self, message: discord.Message) -> bool:
        now = message.created_at.timestamp()
        key = (message.guild.id, message.author.id) if message.guild else (0, message.author.id)
        history = self.user_messages[key]
        window = self.settings.automod_spam_window_seconds

        while history and now - history[0] > window:
            history.popleft()

        history.append(now)
        return len(history) > self.settings.automod_spam_max_messages

    async def warn_user(self, message: discord.Message, reason: str) -> None:
        try:
            warning = await message.channel.send(
                f"{message.author.mention}, {reason}",
                allowed_mentions=discord.AllowedMentions(users=True),
            )
        except discord.HTTPException:
            return

        try:
            await warning.delete(delay=self.settings.automod_warning_delete_seconds)
        except discord.HTTPException:
            pass

    async def apply_timeout(self, message: discord.Message, reason: str) -> None:
        if not isinstance(message.author, discord.Member):
            return

        if self.settings.automod_timeout_seconds <= 0:
            return

        try:
            await message.author.timeout(
                timedelta(seconds=self.settings.automod_timeout_seconds),
                reason=reason,
            )
        except discord.Forbidden:
            logger.warning("No tengo permisos para aplicar timeout a %s.", message.author)
        except discord.HTTPException as exc:
            logger.warning("Discord rechazo el timeout para %s: %s", message.author, exc)

    async def delete_message(self, message: discord.Message, reason: str) -> bool:
        try:
            await message.delete()
        except discord.Forbidden:
            logger.warning("No tengo permisos para borrar mensajes en #%s.", message.channel)
            return False
        except discord.HTTPException as exc:
            logger.warning("No pude borrar mensaje automod: %s", exc)
            return False

        await self.warn_user(message, reason)
        return True

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if not self.enabled or message.guild is None:
            return

        if not isinstance(message.author, discord.Member) or self.is_exempt(message.author):
            return

        content = message.content or ""
        if self.has_blocked_invite(content):
            deleted = await self.delete_message(message, "no se permiten invitaciones de Discord ni promociones sin permiso.")
            if deleted:
                await self.apply_timeout(message, "AutoMod: envio de invitacion Discord bloqueada")
            return

        if self.has_blocked_link(content):
            deleted = await self.delete_message(message, "no se permiten links externos sin autorizacion del staff.")
            if deleted:
                await self.apply_timeout(message, "AutoMod: envio de link externo bloqueado")
            return

        if self.is_spam(message):
            deleted = await self.delete_message(message, "evita spamear mensajes. El sistema puede silenciarte automaticamente.")
            if deleted:
                await self.apply_timeout(message, "AutoMod: spam de mensajes")

    @app_commands.command(name="automod", description="Revisa o cambia el estado del sistema anti spam/links.")
    @app_commands.describe(accion="Accion a ejecutar")
    @app_commands.choices(
        accion=[
            app_commands.Choice(name="estado", value="estado"),
            app_commands.Choice(name="activar", value="activar"),
            app_commands.Choice(name="desactivar", value="desactivar"),
        ]
    )
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.guild_only()
    async def automod(self, interaction: discord.Interaction, accion: app_commands.Choice[str]) -> None:
        if accion.value == "activar":
            self.enabled = True
        elif accion.value == "desactivar":
            self.enabled = False

        embed = discord.Embed(
            title="AutoMod",
            description="Sistema anti invitaciones, links externos y spam.",
            color=discord.Color.from_rgb(255, 255, 255),
            timestamp=discord.utils.utcnow(),
        )
        embed.add_field(name="Estado", value="Activo" if self.enabled else "Desactivado", inline=True)
        embed.add_field(name="Invites Discord", value="Bloqueados" if self.settings.automod_block_invites else "Permitidos", inline=True)
        embed.add_field(name="Links externos", value="Bloqueados" if self.settings.automod_block_links else "Permitidos", inline=True)
        embed.add_field(
            name="Spam",
            value=f"{self.settings.automod_spam_max_messages} mensajes / {self.settings.automod_spam_window_seconds}s",
            inline=True,
        )
        embed.add_field(name="Timeout", value=f"{self.settings.automod_timeout_seconds}s", inline=True)
        allowed = ", ".join(self.settings.automod_allowed_domains) or "Sin dominios permitidos"
        embed.add_field(name="Dominios permitidos", value=allowed, inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @automod.error
    async def automod_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
        if isinstance(error, app_commands.MissingPermissions):
            message = "Necesitas permiso de **Manage Server** para usar AutoMod."
            if interaction.response.is_done():
                await interaction.followup.send(message, ephemeral=True)
            else:
                await interaction.response.send_message(message, ephemeral=True)
            return

        raise error
