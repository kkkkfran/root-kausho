from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

import aiohttp
import discord
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps


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
DEFAULT_WELCOME_BANNER_FILE = "assets/welcome.jpg"
DEFAULT_DM_MESSAGE = (
    "Gracias por entrar a {server}, {username}. Lee las reglas y ponte comodo/a."
)
CHANNEL_FALLBACKS = ("bienvenida", "bienvenidas", "welcome", "general")
CARD_SIZE = (1200, 760)
MARKDOWN_LINK_PATTERN = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")


@dataclass(frozen=True)
class Settings:
    token: str
    welcome_channel_id: int | None
    welcome_mode: str
    welcome_title: str
    welcome_intro: str
    welcome_message: str
    welcome_links: str
    welcome_decoration: str
    welcome_embed_color: int
    welcome_card_accent_color: int
    welcome_card_background: int
    welcome_card_text_color: int
    welcome_card_muted_color: int
    welcome_card_link_color: int
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


def parse_mode() -> str:
    mode = os.getenv("WELCOME_MODE", "card").strip().lower()
    if mode not in {"card", "embed"}:
        raise RuntimeError("WELCOME_MODE debe ser 'card' o 'embed'.")

    return mode


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
        welcome_mode=parse_mode(),
        welcome_title=load_template("WELCOME_TITLE", DEFAULT_WELCOME_TITLE),
        welcome_intro=load_template("WELCOME_INTRO", DEFAULT_WELCOME_INTRO),
        welcome_message=load_template("WELCOME_MESSAGE", DEFAULT_WELCOME_MESSAGE),
        welcome_links=load_template("WELCOME_LINKS", DEFAULT_WELCOME_LINKS),
        welcome_decoration=load_template("WELCOME_DECORATION", DEFAULT_WELCOME_DECORATION),
        welcome_embed_color=parse_hex_color("WELCOME_EMBED_COLOR", "FFFFFF"),
        welcome_card_accent_color=parse_hex_color("WELCOME_CARD_ACCENT_COLOR", "F2A7C6"),
        welcome_card_background=parse_hex_color("WELCOME_CARD_BACKGROUND", "111318"),
        welcome_card_text_color=parse_hex_color("WELCOME_CARD_TEXT_COLOR", "F4F4F5"),
        welcome_card_muted_color=parse_hex_color("WELCOME_CARD_MUTED_COLOR", "C9CDD6"),
        welcome_card_link_color=parse_hex_color("WELCOME_CARD_LINK_COLOR", "4DA3FF"),
        welcome_thumbnail_url=os.getenv("WELCOME_THUMBNAIL_URL", "").strip(),
        welcome_banner_url=os.getenv("WELCOME_BANNER_URL", "").strip(),
        welcome_banner_file=os.getenv("WELCOME_BANNER_FILE", DEFAULT_WELCOME_BANNER_FILE).strip(),
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


def int_to_rgb(color: int) -> tuple[int, int, int]:
    return (color >> 16 & 255, color >> 8 & 255, color & 255)


def with_alpha(color: int, alpha: int) -> tuple[int, int, int, int]:
    red, green, blue = int_to_rgb(color)
    return red, green, blue, alpha


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


def visual_member_text(text: str, member: discord.Member) -> str:
    return text.replace(member.mention, f"@{member.display_name}")


def strip_visual_markdown(text: str) -> str:
    text = MARKDOWN_LINK_PATTERN.sub(r"\1", text)
    for marker in ("**", "__", "~~", "`"):
        text = text.replace(marker, "")

    return text


def format_card_template(
    template: str,
    member: discord.Member,
    fallback: str,
    extra: dict[str, str] | None = None,
) -> str:
    formatted = format_member_template(template, member, fallback, extra)
    return strip_visual_markdown(visual_member_text(formatted, member))


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


def render_card_links(member: discord.Member) -> list[list[tuple[str, int]]]:
    lines: list[list[tuple[str, int]]] = []
    for raw_line in settings.welcome_links.splitlines():
        raw_line = raw_line.strip()
        if not raw_line:
            continue

        line = visual_member_text(format_member_template(raw_line, member, raw_line), member)
        if "|" in line:
            label, _target = [part.strip() for part in line.split("|", 1)]
            line = label

        segments: list[tuple[str, int]] = []
        cursor = 0
        for match in MARKDOWN_LINK_PATTERN.finditer(line):
            prefix = strip_visual_markdown(line[cursor : match.start()])
            if prefix:
                segments.append((prefix, settings.welcome_card_text_color))

            segments.append((strip_visual_markdown(match.group(1)), settings.welcome_card_link_color))
            cursor = match.end()

        suffix = strip_visual_markdown(line[cursor:])
        if suffix:
            segments.append((suffix, settings.welcome_card_text_color))

        if segments:
            lines.append(segments)

    return lines


def font_candidates(bold: bool = False) -> tuple[str, ...]:
    if bold:
        return (
            "C:/Windows/Fonts/segoeuib.ttf",
            "C:/Windows/Fonts/arialbd.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
        )

    return (
        "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    )


def load_font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for candidate in font_candidates(bold=bold):
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size=size)

    return ImageFont.load_default()


def text_width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> int:
    left, _top, right, _bottom = draw.textbbox((0, 0), text, font=font)
    return right - left


def text_height(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> int:
    _left, top, _right, bottom = draw.textbbox((0, 0), text, font=font)
    return bottom - top


def draw_badged_text(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    text: str,
    font: ImageFont.ImageFont,
    fill: tuple[int, int, int, int],
    *,
    badge_font: ImageFont.ImageFont | None = None,
    badge_text: str | None = None,
) -> int:
    badge_font = badge_font or font
    cursor = x
    badge_text = badge_text or ""

    parts = text.split(badge_text) if badge_text else [text]
    for index, part in enumerate(parts):
        if part:
            draw.text((cursor, y), part, font=font, fill=fill)
            cursor += text_width(draw, part, font)

        if badge_text and index < len(parts) - 1:
            width = text_width(draw, badge_text, badge_font)
            height = text_height(draw, badge_text, badge_font)
            draw.rounded_rectangle(
                (cursor - 4, y + 2, cursor + width + 8, y + height + 8),
                radius=6,
                fill=(61, 70, 145, 210),
            )
            draw.text((cursor + 2, y), badge_text, font=badge_font, fill=(172, 184, 255, 255))
            cursor += width + 14

    return cursor


def draw_pink_detail(draw: ImageDraw.ImageDraw, x: int, y: int, size: int = 14) -> None:
    colors = ((255, 191, 214, 255), (244, 120, 170, 255), (255, 232, 239, 255))
    draw.ellipse((x, y + size // 2, x + size, y + size + size // 2), fill=colors[0])
    draw.ellipse((x + size // 2, y, x + size + size // 2, y + size), fill=colors[1])
    draw.ellipse((x + size, y + size // 2, x + size * 2, y + size + size // 2), fill=colors[0])
    draw.ellipse((x + size // 2, y + size, x + size + size // 2, y + size * 2), fill=colors[2])


def draw_glow_dot(draw: ImageDraw.ImageDraw, x: int, y: int) -> None:
    accent = int_to_rgb(settings.welcome_card_accent_color)
    draw.ellipse((x - 8, y - 8, x + 8, y + 8), fill=(*accent, 54))
    draw.ellipse((x - 4, y - 4, x + 4, y + 4), fill=(*accent, 235))
    draw.ellipse((x - 1, y - 1, x + 1, y + 1), fill=(255, 255, 255, 255))


def draw_segmented_text(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    segments: list[tuple[str, int]],
    font: ImageFont.ImageFont,
) -> None:
    cursor = x
    for text, color in segments:
        fill = with_alpha(color, 255)
        draw.text((cursor, y), text, font=font, fill=fill)
        cursor += text_width(draw, text, font)


async def fetch_image_from_url(url: str) -> Image.Image | None:
    if not url:
        return None

    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as response:
                if response.status != 200:
                    logger.warning("No pude descargar imagen %s: HTTP %s", url, response.status)
                    return None

                data = await response.read()
    except aiohttp.ClientError as exc:
        logger.warning("Error descargando imagen %s: %s", url, exc)
        return None

    try:
        with Image.open(BytesIO(data)) as image:
            return image.convert("RGBA")
    except OSError as exc:
        logger.warning("La URL no devolvio una imagen valida %s: %s", url, exc)
        return None


def load_local_image(path: str) -> Image.Image | None:
    if not path:
        return None

    file_path = Path(path)
    if not file_path.exists() or not file_path.is_file():
        logger.warning("No existe la imagen local: %s", file_path)
        return None

    try:
        with Image.open(file_path) as image:
            return image.convert("RGBA")
    except OSError as exc:
        logger.warning("No pude abrir la imagen local %s: %s", file_path, exc)
        return None


async def load_member_avatar(member: discord.Member) -> Image.Image | None:
    try:
        data = await member.display_avatar.with_size(256).read()
    except discord.DiscordException as exc:
        logger.warning("No pude leer el avatar de %s: %s", member, exc)
        return None

    try:
        with Image.open(BytesIO(data)) as image:
            return image.convert("RGBA")
    except OSError as exc:
        logger.warning("Discord devolvio un avatar invalido para %s: %s", member, exc)
        return None


async def load_card_thumbnail(member: discord.Member) -> Image.Image | None:
    if settings.welcome_thumbnail_url:
        thumbnail = await fetch_image_from_url(settings.welcome_thumbnail_url)
        if thumbnail is not None:
            return thumbnail

    return await load_member_avatar(member)


async def load_card_banner() -> Image.Image | None:
    banner = load_local_image(settings.welcome_banner_file)
    if banner is not None:
        return banner

    return await fetch_image_from_url(settings.welcome_banner_url)


def make_placeholder_avatar(member: discord.Member, size: int) -> Image.Image:
    image = Image.new("RGBA", (size, size), (61, 70, 145, 255))
    draw = ImageDraw.Draw(image)
    font = load_font(size // 2, bold=True)
    initial = (member.display_name[:1] or "?").upper()
    width = text_width(draw, initial, font)
    height = text_height(draw, initial, font)
    draw.text(((size - width) // 2, (size - height) // 2 - 4), initial, font=font, fill=(255, 255, 255, 255))
    return image


def fit_cover(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    return ImageOps.fit(image.convert("RGBA"), size, method=Image.Resampling.LANCZOS)


def rounded_mask(size: tuple[int, int], radius: int) -> Image.Image:
    mask = Image.new("L", size, 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.rounded_rectangle((0, 0, size[0], size[1]), radius=radius, fill=255)
    return mask


def paste_rounded(
    base: Image.Image,
    image: Image.Image,
    box: tuple[int, int, int, int],
    *,
    radius: int,
) -> None:
    x, y, width, height = box
    fitted = fit_cover(image, (width, height))
    base.paste(fitted, (x, y), rounded_mask((width, height), radius))


def build_empty_card() -> Image.Image:
    width, height = CARD_SIZE
    base = Image.new("RGBA", CARD_SIZE, (0, 0, 0, 0))
    shadow = Image.new("RGBA", CARD_SIZE, (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow)
    shadow_draw.rounded_rectangle((12, 16, width - 12, height - 10), radius=22, fill=(0, 0, 0, 125))
    base.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(8)))

    draw = ImageDraw.Draw(base)
    draw.rounded_rectangle(
        (10, 10, width - 10, height - 18),
        radius=20,
        fill=with_alpha(settings.welcome_card_background, 255),
        outline=(53, 58, 70, 255),
        width=2,
    )
    return base


async def build_welcome_card_file(member: discord.Member) -> discord.File:
    card = build_empty_card()
    draw = ImageDraw.Draw(card)

    text_color = with_alpha(settings.welcome_card_text_color, 255)
    muted_color = with_alpha(settings.welcome_card_muted_color, 255)
    divider_color = (54, 59, 70, 255)

    small_font = load_font(24)
    body_font = load_font(25)
    body_bold_font = load_font(26, bold=True)
    title_font = load_font(42, bold=True)
    intro_font = load_font(25, bold=True)

    left = 58
    right = CARD_SIZE[0] - 58
    member_badge = f"@{member.display_name}"

    top_line = format_card_template(settings.welcome_title, member, DEFAULT_WELCOME_TITLE)
    draw_badged_text(draw, left, 42, top_line, small_font, text_color, badge_text=member_badge)
    draw.line((left, 100, right, 100), fill=divider_color, width=2)

    title = format_card_template(settings.welcome_title, member, DEFAULT_WELCOME_TITLE)
    title_end = draw_badged_text(draw, left, 126, title, title_font, text_color, badge_text=member_badge)
    draw_pink_detail(draw, title_end + 10, 129, size=13)
    draw.line((left, 190, right, 190), fill=divider_color, width=2)

    intro = format_card_template(settings.welcome_intro, member, DEFAULT_WELCOME_INTRO)
    draw_badged_text(draw, left, 220, intro, intro_font, text_color, badge_text=member_badge)

    thumbnail = await load_card_thumbnail(member)
    if thumbnail is None:
        thumbnail = make_placeholder_avatar(member, 160)

    thumb_box = (right - 170, 218, 150, 150)
    draw.rounded_rectangle(
        (thumb_box[0] - 2, thumb_box[1] - 2, thumb_box[0] + thumb_box[2] + 2, thumb_box[1] + thumb_box[3] + 2),
        radius=18,
        outline=(73, 78, 90, 255),
        width=2,
    )
    paste_rounded(card, thumbnail, thumb_box, radius=16)

    message = format_card_template(
        settings.welcome_message,
        member,
        DEFAULT_WELCOME_MESSAGE,
        extra={"links": "{links}"},
    )
    before_links, _separator, after_links = message.partition("{links}")

    y = 286
    for line in before_links.strip().splitlines():
        if not line.strip():
            continue

        draw.text((left, y), line.strip(), font=body_bold_font, fill=text_color)
        y += 38

    y += 6
    for segments in render_card_links(member):
        draw_glow_dot(draw, left + 18, y + 16)
        draw_segmented_text(draw, left + 42, y, segments, body_font)
        y += 31

    y += 18
    closing = after_links.strip() or f"Thank you for joining us, have fun"
    closing = closing.replace(settings.welcome_decoration, "").strip()
    draw_pink_detail(draw, left, y - 4, size=11)
    draw.text((left + 34, y), closing, font=body_font, fill=muted_color)
    closing_width = text_width(draw, closing, body_font)
    draw_pink_detail(draw, left + closing_width + 48, y - 4, size=11)

    banner = await load_card_banner()
    if banner is not None:
        banner_box = (left, 528, right - left, 172)
        draw.rounded_rectangle(
            (banner_box[0] - 2, banner_box[1] - 2, banner_box[0] + banner_box[2] + 2, banner_box[1] + banner_box[3] + 2),
            radius=18,
            outline=(73, 78, 90, 255),
            width=2,
        )
        paste_rounded(card, banner, banner_box, radius=16)
    else:
        draw.text((left, 524), f"Member #{guild_total(member)}", font=small_font, fill=muted_color)

    buffer = BytesIO()
    card.save(buffer, format="PNG", optimize=True)
    buffer.seek(0)
    return discord.File(buffer, filename="welcome-card.png")


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

        if settings.welcome_mode == "card":
            try:
                await channel.send(content=content, file=await build_welcome_card_file(member))
            except discord.Forbidden:
                logger.warning("No tengo permisos para enviar bienvenidas en #%s.", channel.name)
                return
            except discord.HTTPException as exc:
                logger.warning("Discord rechazo la bienvenida para %s: %s", member, exc)
                return

            logger.info("Bienvenida enviada para %s en %s.", member, member.guild.name)

            if settings.welcome_dm_enabled:
                await send_welcome_dm(member)

            return

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
