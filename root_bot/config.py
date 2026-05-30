from __future__ import annotations

import os
from dataclasses import dataclass

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
DEFAULT_DM_MESSAGE = "Gracias por entrar a {server}, {username}. Lee las reglas y ponte comodo/a."
DEFAULT_WELCOME_AUTO_ROLE_ID = 1267198449355460700
DEFAULT_TICKET_CHANNEL_ID = 1509405048629755914
DEFAULT_TICKET_CATEGORY_ID = 1509407852681367632
DEFAULT_TICKET_LOG_CHANNEL_ID = 1509411767250583613
DEFAULT_TICKET_URL = "https://discord.com/channels/1267197911498887332/1509405048629755914"
DEFAULT_MOD_LOG_CHANNEL_ID = 1509748290110095471
DEFAULT_GIVEAWAY_CLAIM_CHANNEL_ID = 1507802013851717822


@dataclass(frozen=True)
class Settings:
    token: str
    guild_id: int | None
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
    welcome_auto_role_id: int | None
    welcome_ping_outside_embed: bool
    welcome_dm_enabled: bool
    welcome_dm_message: str
    rules_embed_color: int
    about_embed_color: int
    ticket_channel_id: int | None
    ticket_category_id: int | None
    ticket_log_channel_id: int | None
    ticket_staff_role_id: int | None
    ticket_panel_embed_color: int
    ticket_terms_embed_color: int
    ticket_url: str
    automod_enabled: bool
    automod_block_invites: bool
    automod_block_links: bool
    automod_allowed_domains: tuple[str, ...]
    automod_exempt_role_id: int | None
    automod_spam_max_messages: int
    automod_spam_window_seconds: int
    automod_timeout_seconds: int
    automod_warning_delete_seconds: int
    mod_log_channel_id: int | None
    mod_log_embed_color: int
    giveaway_claim_channel_id: int | None
    giveaway_embed_color: int
    giveaway_data_file: str
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


def parse_int(name: str, default: int) -> int:
    value = os.getenv(name, "").strip()
    if not value:
        return default

    try:
        return int(value)
    except ValueError as exc:
        raise RuntimeError(f"{name} debe ser un numero, pero recibio: {value}") from exc


def parse_hex_color(name: str, default: str) -> int:
    value = os.getenv(name, default).strip().removeprefix("#")
    try:
        color = int(value, 16)
    except ValueError as exc:
        raise RuntimeError(f"{name} debe ser un color HEX, por ejemplo FF0000.") from exc

    if not 0 <= color <= 0xFFFFFF:
        raise RuntimeError(f"{name} debe estar entre 000000 y FFFFFF.")

    return color


def load_template(name: str, default: str) -> str:
    return os.getenv(name, default).replace("\\n", "\n")


def load_csv(name: str) -> tuple[str, ...]:
    value = os.getenv(name, "").strip()
    if not value:
        return ()

    return tuple(item.strip().lower() for item in value.split(",") if item.strip())


def load_settings() -> Settings:
    token = os.getenv("DISCORD_TOKEN", "").strip()
    if not token:
        raise RuntimeError("Falta DISCORD_TOKEN. Pegalo en .env o en Railway Variables.")

    return Settings(
        token=token,
        guild_id=parse_optional_int("DISCORD_GUILD_ID"),
        welcome_channel_id=parse_optional_int("WELCOME_CHANNEL_ID"),
        welcome_title=load_template("WELCOME_TITLE", DEFAULT_WELCOME_TITLE),
        welcome_intro=load_template("WELCOME_INTRO", DEFAULT_WELCOME_INTRO),
        welcome_message=load_template("WELCOME_MESSAGE", DEFAULT_WELCOME_MESSAGE),
        welcome_links=load_template("WELCOME_LINKS", DEFAULT_WELCOME_LINKS),
        welcome_decoration=load_template("WELCOME_DECORATION", DEFAULT_WELCOME_DECORATION),
        welcome_embed_color=parse_hex_color("WELCOME_EMBED_COLOR", "FFFFFF"),
        welcome_thumbnail_url=os.getenv("WELCOME_THUMBNAIL_URL", "").strip(),
        welcome_banner_url=os.getenv("WELCOME_BANNER_URL", "").strip(),
        welcome_banner_file=os.getenv("WELCOME_BANNER_FILE", "").strip(),
        welcome_auto_role_id=parse_optional_int("WELCOME_AUTO_ROLE_ID") or DEFAULT_WELCOME_AUTO_ROLE_ID,
        welcome_ping_outside_embed=parse_bool(os.getenv("WELCOME_PING_OUTSIDE_EMBED"), default=False),
        welcome_dm_enabled=parse_bool(os.getenv("WELCOME_DM_ENABLED"), default=False),
        welcome_dm_message=load_template("WELCOME_DM_MESSAGE", DEFAULT_DM_MESSAGE),
        rules_embed_color=parse_hex_color("RULES_EMBED_COLOR", "E53935"),
        about_embed_color=parse_hex_color("ABOUT_EMBED_COLOR", "111111"),
        ticket_channel_id=parse_optional_int("TICKET_CHANNEL_ID") or DEFAULT_TICKET_CHANNEL_ID,
        ticket_category_id=parse_optional_int("TICKET_CATEGORY_ID") or DEFAULT_TICKET_CATEGORY_ID,
        ticket_log_channel_id=parse_optional_int("TICKET_LOG_CHANNEL_ID") or DEFAULT_TICKET_LOG_CHANNEL_ID,
        ticket_staff_role_id=parse_optional_int("TICKET_STAFF_ROLE_ID"),
        ticket_panel_embed_color=parse_hex_color("TICKET_PANEL_EMBED_COLOR", "111111"),
        ticket_terms_embed_color=parse_hex_color("TICKET_TERMS_EMBED_COLOR", "111111"),
        ticket_url=os.getenv("TICKET_URL", DEFAULT_TICKET_URL).strip() or DEFAULT_TICKET_URL,
        automod_enabled=parse_bool(os.getenv("AUTOMOD_ENABLED"), default=True),
        automod_block_invites=parse_bool(os.getenv("AUTOMOD_BLOCK_INVITES"), default=True),
        automod_block_links=parse_bool(os.getenv("AUTOMOD_BLOCK_LINKS"), default=True),
        automod_allowed_domains=load_csv("AUTOMOD_ALLOWED_DOMAINS"),
        automod_exempt_role_id=parse_optional_int("AUTOMOD_EXEMPT_ROLE_ID"),
        automod_spam_max_messages=parse_int("AUTOMOD_SPAM_MAX_MESSAGES", 5),
        automod_spam_window_seconds=parse_int("AUTOMOD_SPAM_WINDOW_SECONDS", 8),
        automod_timeout_seconds=parse_int("AUTOMOD_TIMEOUT_SECONDS", 300),
        automod_warning_delete_seconds=parse_int("AUTOMOD_WARNING_DELETE_SECONDS", 8),
        mod_log_channel_id=parse_optional_int("MOD_LOG_CHANNEL_ID") or DEFAULT_MOD_LOG_CHANNEL_ID,
        mod_log_embed_color=parse_hex_color("MOD_LOG_EMBED_COLOR", "111111"),
        giveaway_claim_channel_id=parse_optional_int("GIVEAWAY_CLAIM_CHANNEL_ID") or DEFAULT_GIVEAWAY_CLAIM_CHANNEL_ID,
        giveaway_embed_color=parse_hex_color("GIVEAWAY_EMBED_COLOR", "FFFFFF"),
        giveaway_data_file=os.getenv("GIVEAWAY_DATA_FILE", "data/giveaways.json").strip() or "data/giveaways.json",
        bot_status=os.getenv("BOT_STATUS", "dando la bienvenida"),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
    )
