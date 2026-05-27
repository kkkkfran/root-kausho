from __future__ import annotations

import logging
import os
from pathlib import Path
from dataclasses import dataclass

import discord
from dotenv import load_dotenv


load_dotenv()

DEFAULT_WELCOME_MESSAGE = (
    "**Glad to have you here**\n\n"
    "{links}\n\n"
    "{decoration} Thank you for joining us, have fun {decoration}"
)
DEFAULT_WELCOME_TITLE = "Welcome {member}"
DEFAULT_WELCOME_INTRO = "**Welcome {member} To {server}**"
DEFAULT_WELCOME_LINKS = (
    "Make sure to read the Server Rules\n"
    "Check our latest Updates\n"
    "For IP/Port Click Here\n"
    "Need Help? Check our Ticket Support"
)
DEFAULT_WELCOME_DECORATION = "\U0001F338"
DEFAULT_DM_MESSAGE = (
    "Gracias por entrar a {server}, {username}. Lee las reglas y ponte comodo/a."
)
CHANNEL_FALLBACKS = ("bienvenida", "bienvenidas", "welcome", "general")


@dataclass(frozen=True)
class Settings:
    token: str
    welcome_channel_id: int | None
    welcome_title: str
    welcome_intro: str
    welcome_message: str
    welcome_links: str
    welcome_decoration: str
    welcome_embed_color: int
    welcome_thumbnail_url: str
    welcome_banner_url: str
    welcome_banner_file: str
    welcome_ping_outside_embed: bool
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


def parse_hex_color(name: str, default: str) -> int:
    value = os.getenv(name, default).strip().removeprefix("#")
    try:
        color = int(value, 16)
    except ValueError as exc:
        raise RuntimeError(f"{name} debe ser un color HEX, por ejemplo 5865F2.") from exc

    if not 0 <= color <= 0xFFFFFF:
        raise RuntimeError(f"{name} debe estar entre 000000 y FFFFFF.")

    return color


def load_template(name: str, default: str) -> str:
    return os.getenv(name, default).replace("\\n", "\n")


def load_settings() -> Settings:
    token = os.getenv("DISCORD_TOKEN", "").strip()
    if not token:
        raise RuntimeError("Falta DISCORD_TOKEN. Pegalo en el archivo .env antes de iniciar el bot.")

    return Settings(
        token=token,
        welcome_channel_id=parse_optional_int("WELCOME_CHANNEL_ID"),
        welcome_title=load_template("WELCOME_TITLE", DEFAULT_WELCOME_TITLE),
        welcome_intro=load_template("WELCOME_INTRO", DEFAULT_WELCOME_INTRO),
        welcome_message=load_template("WELCOME_MESSAGE", DEFAULT_WELCOME_MESSAGE),
        welcome_links=load_template("WELCOME_LINKS", DEFAULT_WELCOME_LINKS),
        welcome_decoration=load_template("WELCOME_DECORATION", DEFAULT_WELCOME_DECORATION),
        welcome_embed_color=parse_hex_color("WELCOME_EMBED_COLOR", "F2A7C6"),
        welcome_thumbnail_url=os.getenv("WELCOME_THUMBNAIL_URL", "").strip(),
        welcome_banner_url=os.getenv("WELCOME_BANNER_URL", "").strip(),
        welcome_banner_file=os.getenv("WELCOME_BANNER_FILE", "").strip(),
        welcome_ping_outside_embed=parse_bool(os.getenv("WELCOME_PING_OUTSIDE_EMBED"), default=False),
        welcome_dm_enabled=parse_bool(os.getenv("WELCOME_DM_ENABLED"), default=False),
        welcome_dm_message=load_template("WELCOME_DM_MESSAGE", DEFAULT_DM_MESSAGE),
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


def template_values(member: discord.Member, extra: dict[str, str] | None = None) -> dict[str, str]:
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
    template: str,
    member: discord.Member,
    fallback: str,
    extra: dict[str, str] | None = None,
) -> str:
    try:
        return template.format(**template_values(member, extra))
    except (KeyError, ValueError) as exc:
        logger.warning("Plantilla invalida en .env: %s. Usando mensaje por defecto.", exc)
        return fallback.format(**template_values(member, extra))


def render_welcome_links(member: discord.Member) -> str:
    lines: list[str] = []
    for raw_line in settings.welcome_links.splitlines():
        raw_line = raw_line.strip()
        if not raw_line:
            continue

        line = format_member_template(raw_line, member, raw_line)
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


def resolve_banner_file() -> discord.File | None:
    if not settings.welcome_banner_file:
        return None

    file_path = Path(settings.welcome_banner_file)
    if not file_path.exists() or not file_path.is_file():
        logger.warning("WELCOME_BANNER_FILE no existe o no es un archivo: %s", file_path)
        return None

    return discord.File(file_path, filename=file_path.name)


def build_welcome_embed(member: discord.Member, banner_file: discord.File | None = None) -> discord.Embed:
    links = render_welcome_links(member)
    title = format_member_template(
        settings.welcome_title,
        member,
        DEFAULT_WELCOME_TITLE,
    )
    intro = format_member_template(
        settings.welcome_intro,
        member,
        DEFAULT_WELCOME_INTRO,
    )
    description = format_member_template(
        settings.welcome_message,
        member,
        DEFAULT_WELCOME_MESSAGE,
        extra={"links": links},
    )

    embed = discord.Embed(
        title=title,
        description=f"{intro}\n\n{description}",
        color=discord.Color(settings.welcome_embed_color),
        timestamp=discord.utils.utcnow(),
    )

    if member.guild.icon is not None:
        embed.set_author(name=member.guild.name, icon_url=member.guild.icon.url)
    else:
        embed.set_author(name=member.guild.name)

    thumbnail_url = settings.welcome_thumbnail_url or member.display_avatar.url
    embed.set_thumbnail(url=thumbnail_url)

    if banner_file is not None:
        embed.set_image(url=f"attachment://{banner_file.filename}")
    elif settings.welcome_banner_url:
        embed.set_image(url=settings.welcome_banner_url)

    embed.set_footer(text=f"Member #{guild_total(member)}")
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

        content = member.mention if settings.welcome_ping_outside_embed else None

        banner_file = resolve_banner_file()

        send_kwargs = {
            "content": content,
            "embed": build_welcome_embed(member, banner_file),
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

        if settings.welcome_dm_enabled:
            await send_welcome_dm(member)


def main() -> None:
    intents = discord.Intents.default()
    intents.members = True

    client = WelcomeClient(intents=intents)
    client.run(settings.token)


if __name__ == "__main__":
    main()
