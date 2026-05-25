from __future__ import annotations

import logging
import os
from dataclasses import dataclass

import discord
from dotenv import load_dotenv


load_dotenv()

DEFAULT_WELCOME_MESSAGE = (
    "Hola {member}, bienvenido/a a **{server}**. Ya somos **{total}** miembros."
)
DEFAULT_DM_MESSAGE = (
    "Gracias por entrar a {server}, {username}. Lee las reglas y ponte comodo/a."
)
CHANNEL_FALLBACKS = ("bienvenida", "bienvenidas", "welcome", "general")


@dataclass(frozen=True)
class Settings:
    token: str
    welcome_channel_id: int | None
    welcome_message: str
    welcome_dm_enabled: bool
    welcome_dm_message: str
    bot_status: str
    log_level: str


def parse_bool(value: str | None, default: bool = False) -> bool:
    if value is None or value.strip() == "":
        return default

    return value.strip().lower() in {"1", "true", "yes", "y", "si", "on"}


def parse_optional_int(name: str) -> int | None:
    value = os.getenv(name, "").strip()
    if not value:
        return None

    try:
        return int(value)
    except ValueError as exc:
        raise RuntimeError(f"{name} debe ser un numero, pero recibio: {value}") from exc


def load_settings() -> Settings:
    token = os.getenv("DISCORD_TOKEN", "").strip()
    if not token:
        raise RuntimeError("Falta DISCORD_TOKEN. Pegalo en el archivo .env antes de iniciar el bot.")

    return Settings(
        token=token,
        welcome_channel_id=parse_optional_int("WELCOME_CHANNEL_ID"),
        welcome_message=os.getenv("WELCOME_MESSAGE", DEFAULT_WELCOME_MESSAGE),
        welcome_dm_enabled=parse_bool(os.getenv("WELCOME_DM_ENABLED"), default=False),
        welcome_dm_message=os.getenv("WELCOME_DM_MESSAGE", DEFAULT_DM_MESSAGE),
        bot_status=os.getenv("BOT_STATUS", "dando la bienvenida"),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
    )


settings = load_settings()
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("welcome-bot")


def guild_total(member: discord.Member) -> str:
    if member.guild.member_count is not None:
        return str(member.guild.member_count)

    return "?"


def format_member_template(template: str, member: discord.Member, fallback: str) -> str:
    values = {
        "member": member.mention,
        "username": member.display_name,
        "tag": str(member),
        "server": member.guild.name,
        "total": guild_total(member),
    }

    try:
        return template.format(**values)
    except (KeyError, ValueError) as exc:
        logger.warning("Plantilla invalida en .env: %s. Usando mensaje por defecto.", exc)
        return fallback.format(**values)


def can_send_in(channel: discord.TextChannel | discord.Thread) -> bool:
    me = channel.guild.me
    if me is None:
        return True

    permissions = channel.permissions_for(me)
    return permissions.view_channel and permissions.send_messages


async def fetch_configured_channel(
    guild: discord.Guild,
) -> discord.TextChannel | discord.Thread | None:
    if settings.welcome_channel_id is None:
        return None

    channel = guild.get_channel(settings.welcome_channel_id)
    if channel is None:
        try:
            channel = await guild.fetch_channel(settings.welcome_channel_id)
        except discord.DiscordException as exc:
            logger.warning("No pude encontrar WELCOME_CHANNEL_ID=%s: %s", settings.welcome_channel_id, exc)
            return None

    if not isinstance(channel, (discord.TextChannel, discord.Thread)):
        logger.warning("WELCOME_CHANNEL_ID=%s no es un canal de texto.", settings.welcome_channel_id)
        return None

    if not can_send_in(channel):
        logger.warning("No tengo permisos para enviar mensajes en #%s.", channel.name)
        return None

    return channel


async def resolve_welcome_channel(guild: discord.Guild) -> discord.TextChannel | discord.Thread | None:
    configured_channel = await fetch_configured_channel(guild)
    if configured_channel is not None:
        return configured_channel

    if settings.welcome_channel_id is not None:
        return None

    if guild.system_channel is not None and can_send_in(guild.system_channel):
        return guild.system_channel

    for channel_name in CHANNEL_FALLBACKS:
        channel = discord.utils.get(guild.text_channels, name=channel_name)
        if channel is not None and can_send_in(channel):
            return channel

    return None


def build_welcome_embed(member: discord.Member) -> discord.Embed:
    embed = discord.Embed(
        title=f"Bienvenido/a a {member.guild.name}",
        description=(
            f"{member.mention}, nos alegra tenerte aqui.\n"
            "Pasa por las reglas, presentate y disfruta el servidor."
        ),
        color=discord.Color.from_rgb(88, 101, 242),
    )
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="Usuario", value=member.display_name, inline=True)
    embed.add_field(name="Miembro", value=f"#{guild_total(member)}", inline=True)
    embed.add_field(
        name="Cuenta creada",
        value=discord.utils.format_dt(member.created_at, style="R"),
        inline=False,
    )
    embed.set_footer(text=f"Servidor: {member.guild.name}")
    return embed


async def send_welcome_dm(member: discord.Member) -> None:
    message = format_member_template(
        settings.welcome_dm_message,
        member,
        DEFAULT_DM_MESSAGE,
    )

    try:
        await member.send(message)
    except discord.Forbidden:
        logger.info("No pude enviar DM a %s; probablemente tiene DMs cerrados.", member)
    except discord.HTTPException as exc:
        logger.warning("Discord rechazo el DM para %s: %s", member, exc)


class WelcomeClient(discord.Client):
    def __init__(self, *, intents: discord.Intents) -> None:
        super().__init__(intents=intents)
        self._presence_ready = False

    async def on_ready(self) -> None:
        if not self._presence_ready and settings.bot_status:
            await self.change_presence(
                activity=discord.Activity(
                    type=discord.ActivityType.watching,
                    name=settings.bot_status,
                )
            )
            self._presence_ready = True

        logger.info("Conectado como %s (ID: %s)", self.user, self.user.id if self.user else "desconocido")

    async def on_member_join(self, member: discord.Member) -> None:
        channel = await resolve_welcome_channel(member.guild)
        if channel is None:
            logger.warning("No encontre canal de bienvenida para %s.", member.guild.name)
            return

        content = format_member_template(
            settings.welcome_message,
            member,
            DEFAULT_WELCOME_MESSAGE,
        )

        try:
            await channel.send(content=content, embed=build_welcome_embed(member))
        except discord.Forbidden:
            logger.warning("No tengo permisos para enviar bienvenidas en #%s.", channel.name)
            return
        except discord.HTTPException as exc:
            logger.warning("Discord rechazo la bienvenida para %s: %s", member, exc)
            return

        logger.info("Bienvenida enviada para %s en %s.", member, member.guild.name)

        if settings.welcome_dm_enabled:
            await send_welcome_dm(member)


def main() -> None:
    intents = discord.Intents.default()
    intents.members = True

    client = WelcomeClient(intents=intents)
    client.run(settings.token)


if __name__ == "__main__":
    main()
