from __future__ import annotations

import logging
from pathlib import Path

import discord
from discord.ext import commands

from ..config import DEFAULT_DM_MESSAGE, DEFAULT_WELCOME_INTRO, DEFAULT_WELCOME_MESSAGE, DEFAULT_WELCOME_TITLE, Settings


logger = logging.getLogger("root-bot.welcome")
CHANNEL_FALLBACKS = ("bienvenida", "bienvenidas", "welcome", "general")


def guild_total(member: discord.Member) -> str:
    if member.guild.member_count is not None:
        return str(member.guild.member_count)

    return "?"


def template_values(
    settings: Settings,
    member: discord.Member,
    extra: dict[str, str] | None = None,
) -> dict[str, str]:
    values = {
        "member": member.mention,
        "username": member.display_name,
        "tag": str(member),
        "server": member.guild.name,
        "total": guild_total(member),
        "decoration": settings.welcome_decoration,
    }
    if extra is not None:
        values.update(extra)

    return values


def format_member_template(
    settings: Settings,
    template: str,
    member: discord.Member,
    fallback: str,
    extra: dict[str, str] | None = None,
) -> str:
    try:
        return template.format(**template_values(settings, member, extra))
    except (KeyError, ValueError) as exc:
        logger.warning("Plantilla invalida: %s. Usando mensaje por defecto.", exc)
        return fallback.format(**template_values(settings, member, extra))


def render_welcome_links(settings: Settings, member: discord.Member) -> str:
    lines: list[str] = []
    for raw_line in settings.welcome_links.splitlines():
        raw_line = raw_line.strip()
        if not raw_line:
            continue

        line = format_member_template(settings, raw_line, member, raw_line)
        if "|" in line:
            label, target = [part.strip() for part in line.split("|", 1)]
            if target.startswith(("http://", "https://")):
                line = f"[{label}]({target})"
            elif target:
                line = f"{label} {target}"
            else:
                line = label

        lines.append(f"{settings.welcome_decoration} {line}")

    return "\n".join(lines)


def can_send_in(channel: discord.TextChannel | discord.Thread) -> bool:
    me = channel.guild.me
    if me is None:
        return True

    permissions = channel.permissions_for(me)
    return permissions.view_channel and permissions.send_messages


class WelcomeCog(commands.Cog):
    def __init__(self, bot: commands.Bot, settings: Settings) -> None:
        self.bot = bot
        self.settings = settings

    async def fetch_configured_channel(
        self,
        guild: discord.Guild,
    ) -> discord.TextChannel | discord.Thread | None:
        if self.settings.welcome_channel_id is None:
            return None

        channel = guild.get_channel(self.settings.welcome_channel_id)
        if channel is None:
            try:
                channel = await guild.fetch_channel(self.settings.welcome_channel_id)
            except discord.DiscordException as exc:
                logger.warning("No pude encontrar WELCOME_CHANNEL_ID=%s: %s", self.settings.welcome_channel_id, exc)
                return None

        if not isinstance(channel, (discord.TextChannel, discord.Thread)):
            logger.warning("WELCOME_CHANNEL_ID=%s no es un canal de texto.", self.settings.welcome_channel_id)
            return None

        if not can_send_in(channel):
            logger.warning("No tengo permisos para enviar mensajes en #%s.", channel.name)
            return None

        return channel

    async def resolve_welcome_channel(self, guild: discord.Guild) -> discord.TextChannel | discord.Thread | None:
        configured_channel = await self.fetch_configured_channel(guild)
        if configured_channel is not None:
            return configured_channel

        if self.settings.welcome_channel_id is not None:
            return None

        if guild.system_channel is not None and can_send_in(guild.system_channel):
            return guild.system_channel

        for channel_name in CHANNEL_FALLBACKS:
            channel = discord.utils.get(guild.text_channels, name=channel_name)
            if channel is not None and can_send_in(channel):
                return channel

        return None

    def resolve_banner_file(self) -> discord.File | None:
        if not self.settings.welcome_banner_file:
            return None

        file_path = Path(self.settings.welcome_banner_file)
        if not file_path.exists() or not file_path.is_file():
            logger.warning("WELCOME_BANNER_FILE no existe o no es un archivo: %s", file_path)
            return None

        return discord.File(file_path, filename=file_path.name)

    def build_welcome_embed(self, member: discord.Member, banner_file: discord.File | None = None) -> discord.Embed:
        links = render_welcome_links(self.settings, member)
        title = format_member_template(
            self.settings,
            self.settings.welcome_title,
            member,
            DEFAULT_WELCOME_TITLE,
        )
        intro = format_member_template(
            self.settings,
            self.settings.welcome_intro,
            member,
            DEFAULT_WELCOME_INTRO,
        )
        description = format_member_template(
            self.settings,
            self.settings.welcome_message,
            member,
            DEFAULT_WELCOME_MESSAGE,
            extra={"links": links},
        )

        embed = discord.Embed(
            title=title,
            description=f"{intro}\n\n{description}",
            color=discord.Color(self.settings.welcome_embed_color),
            timestamp=discord.utils.utcnow(),
        )

        if member.guild.icon is not None:
            embed.set_author(name=member.guild.name, icon_url=member.guild.icon.url)
        else:
            embed.set_author(name=member.guild.name)

        thumbnail_url = self.settings.welcome_thumbnail_url or member.display_avatar.url
        embed.set_thumbnail(url=thumbnail_url)

        if banner_file is not None:
            embed.set_image(url=f"attachment://{banner_file.filename}")
        elif self.settings.welcome_banner_url:
            embed.set_image(url=self.settings.welcome_banner_url)

        embed.set_footer(text=f"Member #{guild_total(member)}")
        return embed

    async def send_welcome_dm(self, member: discord.Member) -> None:
        message = format_member_template(
            self.settings,
            self.settings.welcome_dm_message,
            member,
            DEFAULT_DM_MESSAGE,
        )

        try:
            await member.send(message)
        except discord.Forbidden:
            logger.info("No pude enviar DM a %s; probablemente tiene DMs cerrados.", member)
        except discord.HTTPException as exc:
            logger.warning("Discord rechazo el DM para %s: %s", member, exc)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        channel = await self.resolve_welcome_channel(member.guild)
        if channel is None:
            logger.warning("No encontre canal de bienvenida para %s.", member.guild.name)
            return

        content = member.mention if self.settings.welcome_ping_outside_embed else None
        banner_file = self.resolve_banner_file()

        send_kwargs = {
            "content": content,
            "embed": self.build_welcome_embed(member, banner_file),
        }
        if banner_file is not None:
            send_kwargs["file"] = banner_file

        try:
            await channel.send(**send_kwargs)
        except discord.Forbidden:
            logger.warning("No tengo permisos para enviar bienvenidas en #%s.", channel.name)
            return
        except discord.HTTPException as exc:
            logger.warning("Discord rechazo la bienvenida para %s: %s", member, exc)
            return

        logger.info("Bienvenida enviada para %s en %s.", member, member.guild.name)

        if self.settings.welcome_dm_enabled:
            await self.send_welcome_dm(member)
