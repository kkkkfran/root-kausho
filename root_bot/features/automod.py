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

    def sanitize_logged_content(self, content: str) -> str:
        content = DISCORD_INVITE_PATTERN.sub("[INVITACION DISCORD OCULTA]", content)
        content = URL_PATTERN.sub("[LINK OCULTO]", content)
        return content

    async def get_mod_log_channel(self, guild: discord.Guild) -> discord.TextChannel | None:
        if self.settings.mod_log_channel_id is None:
            return None

        channel = guild.get_channel(self.settings.mod_log_channel_id)
        if channel is None:
            try:
                channel = await guild.fetch_channel(self.settings.mod_log_channel_id)
            except discord.DiscordException as exc:
                logger.warning("No pude encontrar MOD_LOG_CHANNEL_ID=%s: %s", self.settings.mod_log_channel_id, exc)
                return None

        if not isinstance(channel, discord.TextChannel):
            logger.warning("MOD_LOG_CHANNEL_ID=%s no es un canal de texto.", self.settings.mod_log_channel_id)
            return None

        return channel

    async def send_mod_log(
        self,
        message: discord.Message,
        *,
        action: str,
        reason: str,
        timeout_applied: bool = False,
    ) -> None:
        if message.guild is None:
            return

        log_channel = await self.get_mod_log_channel(message.guild)
        if log_channel is None:
            return

        me = message.guild.me
        if me is not None:
            permissions = log_channel.permissions_for(me)
            if not permissions.view_channel or not permissions.send_messages or not permissions.embed_links:
                logger.warning("No tengo permisos para enviar mod logs en #%s.", log_channel.name)
                return

        content = self.sanitize_logged_content(message.content or "[Mensaje sin texto visible]")
        if len(content) > 900:
            content = f"{content[:900]}..."

        embed = discord.Embed(
            title="Registro de sancion automatica",
            description="AutoMod ejecuto una accion para proteger el servidor.",
            color=discord.Color(self.settings.mod_log_embed_color),
            timestamp=discord.utils.utcnow(),
        )
        embed.add_field(name="Usuario", value=f"{message.author.mention}\n`{message.author.id}`", inline=True)
        embed.add_field(name="Canal", value=f"{message.channel.mention}\n`{message.channel.id}`", inline=True)
        embed.add_field(name="Accion", value=action, inline=True)
        embed.add_field(name="Razon", value=reason, inline=False)
        embed.add_field(name="Aislamiento", value=f"{self.settings.automod_timeout_seconds}s" if timeout_applied else "No aplicado", inline=True)
        embed.add_field(name="Mensaje eliminado", value=content, inline=False)
        embed.set_footer(text="root@kausho AutoMod")

        if isinstance(message.author, discord.Member):
            embed.set_thumbnail(url=message.author.display_avatar.url)

        try:
            await log_channel.send(embed=embed)
        except discord.HTTPException as exc:
            logger.warning("No pude enviar mod log: %s", exc)

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

    async def apply_timeout(self, message: discord.Message, reason: str) -> bool:
        if not isinstance(message.author, discord.Member):
            return False

        if self.settings.automod_timeout_seconds <= 0:
            return False

        try:
            await message.author.timeout(
                timedelta(seconds=self.settings.automod_timeout_seconds),
                reason=reason,
            )
        except discord.Forbidden:
            logger.warning("No tengo permisos para aplicar timeout a %s.", message.author)
            return False
        except discord.HTTPException as exc:
            logger.warning("Discord rechazo el timeout para %s: %s", message.author, exc)
            return False

        return True

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
                reason = "AutoMod: envio de invitacion Discord bloqueada"
                timeout_applied = await self.apply_timeout(message, reason)
                await self.send_mod_log(
                    message,
                    action="Mensaje eliminado + aislamiento",
                    reason=reason,
                    timeout_applied=timeout_applied,
                )
            return

        if self.has_blocked_link(content):
            deleted = await self.delete_message(message, "no se permiten links externos sin autorizacion del staff.")
            if deleted:
                reason = "AutoMod: envio de link externo bloqueado"
                timeout_applied = await self.apply_timeout(message, reason)
                await self.send_mod_log(
                    message,
                    action="Mensaje eliminado + aislamiento",
                    reason=reason,
                    timeout_applied=timeout_applied,
                )
            return

        if self.is_spam(message):
            deleted = await self.delete_message(message, "evita spamear mensajes. El sistema puede silenciarte automaticamente.")
            if deleted:
                reason = "AutoMod: spam de mensajes"
                timeout_applied = await self.apply_timeout(message, reason)
                await self.send_mod_log(
                    message,
                    action="Mensaje eliminado + aislamiento",
                    reason=reason,
                    timeout_applied=timeout_applied,
                )

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
