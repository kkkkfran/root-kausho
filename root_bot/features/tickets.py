from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass
from io import BytesIO
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from ..config import Settings


logger = logging.getLogger("root-bot.tickets")


@dataclass(frozen=True)
class TicketOption:
    key: str
    label: str
    description: str
    emoji: str


TICKET_OPTIONS = (
    TicketOption("soporte", "Soporte tecnico", "Ayuda con un bot, sistema o configuracion.", "\U0001F6E0"),
    TicketOption("compra", "Comprar o cotizar", "Solicitar un bot, web, panel o automatizacion.", "\U0001F4BC"),
    TicketOption("idea", "Proponer una idea", "Presentar una idea de proyecto o mejora.", "\U0001F4A1"),
    TicketOption("bot", "Bot de Discord", "Crear, mejorar o reparar un bot.", "\U0001F916"),
    TicketOption("web", "Pagina web o panel", "Sitios, dashboards o paneles administrativos.", "\U0001F310"),
    TicketOption("automatizacion", "Automatizacion", "Automatizar tareas para servidores o comunidades.", "\U00002699"),
    TicketOption("general", "Ayuda general", "Consultas que no entran en otra categoria.", "\U00002753"),
)
OPTION_BY_KEY = {option.key: option for option in TICKET_OPTIONS}
CHANNEL_SAFE = re.compile(r"[^a-z0-9-]+")
SERVICE_TICKET_TYPES = {"compra", "bot", "web", "automatizacion"}


TERMS_TEXT = (
    "Antes de continuar debes aceptar estas condiciones para mantener el proceso claro y ordenado:\n\n"
    "**1. Alcance del pedido**\n"
    "Todo pedido debe quedar definido dentro del ticket: objetivo, funciones, precio, plazos, entregables y cambios incluidos.\n\n"
    "**2. Pagos y reembolsos**\n"
    "Los trabajos personalizados, configuraciones, bots, paginas web, automatizaciones, reservas o adelantos no son reembolsables "
    "una vez confirmado el pedido e iniciado el trabajo, salvo que la ley aplicable exija otra cosa o que el servicio no pueda ser entregado por causa atribuible al proveedor.\n\n"
    "**3. Cambios fuera de alcance**\n"
    "Funciones nuevas, cambios grandes o requisitos no acordados inicialmente pueden requerir nueva cotizacion, pago adicional o nuevo plazo.\n\n"
    "**4. Informacion y accesos**\n"
    "El cliente debe entregar informacion correcta y accesos necesarios. Retrasos por falta de informacion pueden mover fechas de entrega.\n\n"
    "**5. Disputas y comunicacion**\n"
    "Antes de abrir reclamos externos o disputas de pago, se debe intentar resolver el problema dentro del ticket con evidencia clara, capturas, acuerdos y estado del trabajo.\n\n"
    "**6. Respeto**\n"
    "El soporte se entrega con orden. Insultos, amenazas, spam o mala fe pueden terminar en cierre del ticket y bloqueo del servicio.\n\n"
    "Pulsa **Acepto** para continuar o **Rechazo** para cerrar este ticket."
)


def slugify(value: str) -> str:
    normalized = value.lower().strip().replace(" ", "-")
    normalized = CHANNEL_SAFE.sub("", normalized)
    return normalized[:18] or "usuario"


def ticket_topic(owner_id: int, ticket_type: str, accepted: bool = False) -> str:
    state = "accepted" if accepted else "pending"
    return f"ticket_owner={owner_id};ticket_type={ticket_type};terms={state}"


def parse_topic(topic: str | None) -> dict[str, str]:
    data: dict[str, str] = {}
    if not topic:
        return data

    for part in topic.split(";"):
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        data[key.strip()] = value.strip()

    return data


def should_log_ticket(topic_data: dict[str, str]) -> bool:
    return topic_data.get("ticket_type") in SERVICE_TICKET_TYPES and topic_data.get("terms") == "accepted"


def user_can_manage_ticket(interaction: discord.Interaction, owner_id: int | None) -> bool:
    if interaction.user.id == owner_id:
        return True

    if isinstance(interaction.user, discord.Member):
        return interaction.user.guild_permissions.manage_guild or interaction.user.guild_permissions.manage_channels

    return False


def build_ticket_panel_embed(guild: discord.Guild, settings: Settings) -> discord.Embed:
    embed = discord.Embed(
        title="Centro de tickets",
        description=(
            "Selecciona el tipo de solicitud que necesitas abrir. "
            "El bot creara un canal privado para mantener todo ordenado y darle seguimiento.\n\n"
            "**Usa tickets para soporte, compras, ideas, bots, paginas web o automatizaciones.**"
        ),
        color=discord.Color(settings.ticket_panel_embed_color),
        timestamp=discord.utils.utcnow(),
    )

    if guild.icon is not None:
        embed.set_thumbnail(url=guild.icon.url)

    embed.add_field(
        name="Antes de abrir",
        value=(
            "Ten claro que dentro del ticket deberas aceptar terminos de uso antes de continuar. "
            "Esto protege el orden del proceso y deja registro de acuerdos, pagos, alcances y entregas."
        ),
        inline=False,
    )
    embed.add_field(
        name="Opciones disponibles",
        value="\n".join(f"{option.emoji} **{option.label}** - {option.description}" for option in TICKET_OPTIONS),
        inline=False,
    )
    embed.set_footer(text="Selecciona una opcion para crear tu ticket")
    return embed


def build_terms_embed(user: discord.abc.User, option: TicketOption, settings: Settings) -> discord.Embed:
    embed = discord.Embed(
        title="Terminos de uso del ticket",
        description=TERMS_TEXT,
        color=discord.Color(settings.ticket_terms_embed_color),
        timestamp=discord.utils.utcnow(),
    )
    embed.add_field(name="Solicitante", value=user.mention, inline=True)
    embed.add_field(name="Tipo de ticket", value=f"{option.emoji} {option.label}", inline=True)
    embed.set_footer(text="Aceptar estos terminos habilita la atencion del ticket")
    return embed


def build_ready_embed(user: discord.abc.User, option: TicketOption) -> discord.Embed:
    embed = discord.Embed(
        title="Ticket habilitado",
        description=(
            f"{user.mention}, gracias por aceptar los terminos.\n\n"
            "Ahora puedes explicar tu solicitud con la mayor cantidad de detalles posible: objetivo, presupuesto, fechas, ejemplos, "
            "links, capturas o cualquier dato que ayude a entender lo que necesitas."
        ),
        color=discord.Color.from_rgb(255, 255, 255),
        timestamp=discord.utils.utcnow(),
    )
    embed.add_field(name="Tipo", value=f"{option.emoji} {option.label}", inline=False)
    embed.set_footer(text="Un miembro del staff revisara el ticket cuando pueda")
    return embed


async def get_ticket_category(guild: discord.Guild, settings: Settings) -> discord.CategoryChannel | None:
    if settings.ticket_category_id is None:
        return None

    category = guild.get_channel(settings.ticket_category_id)
    if category is None:
        try:
            category = await guild.fetch_channel(settings.ticket_category_id)
        except discord.DiscordException as exc:
            logger.warning("No pude encontrar TICKET_CATEGORY_ID=%s: %s", settings.ticket_category_id, exc)
            return None

    if not isinstance(category, discord.CategoryChannel):
        logger.warning("TICKET_CATEGORY_ID=%s no es una categoria.", settings.ticket_category_id)
        return None

    return category


async def get_ticket_log_channel(guild: discord.Guild, settings: Settings) -> discord.TextChannel | None:
    if settings.ticket_log_channel_id is None:
        return None

    channel = guild.get_channel(settings.ticket_log_channel_id)
    if channel is None:
        try:
            channel = await guild.fetch_channel(settings.ticket_log_channel_id)
        except discord.DiscordException as exc:
            logger.warning("No pude encontrar TICKET_LOG_CHANNEL_ID=%s: %s", settings.ticket_log_channel_id, exc)
            return None

    if not isinstance(channel, discord.TextChannel):
        logger.warning("TICKET_LOG_CHANNEL_ID=%s no es un canal de texto.", settings.ticket_log_channel_id)
        return None

    return channel


async def find_open_ticket(
    guild: discord.Guild,
    settings: Settings,
    user_id: int,
) -> discord.TextChannel | None:
    category = await get_ticket_category(guild, settings)
    if category is None:
        return None

    for channel in category.text_channels:
        topic_data = parse_topic(channel.topic)
        if topic_data.get("ticket_owner") == str(user_id):
            return channel

    return None


def format_message_for_transcript(message: discord.Message) -> str:
    created_at = message.created_at.strftime("%Y-%m-%d %H:%M:%S UTC")
    author = f"{message.author} ({message.author.id})"
    parts = [
        f"[{created_at}] {author}",
        f"Jump: {message.jump_url}",
    ]

    if message.content:
        parts.append(message.content)

    for attachment in message.attachments:
        parts.append(f"Attachment: {attachment.filename} | {attachment.url}")

    for embed in message.embeds:
        if embed.title:
            parts.append(f"Embed title: {embed.title}")
        if embed.description:
            parts.append(f"Embed description: {embed.description}")
        for field in embed.fields:
            parts.append(f"Embed field - {field.name}: {field.value}")

    if len(parts) == 2:
        parts.append("[Mensaje sin texto visible]")

    return "\n".join(parts)


async def build_ticket_transcript_file(
    channel: discord.TextChannel,
    topic_data: dict[str, str],
) -> tuple[discord.File, int]:
    lines = [
        "TRANSCRIPT DE TICKET",
        "=" * 80,
        f"Servidor: {channel.guild.name} ({channel.guild.id})",
        f"Canal: #{channel.name} ({channel.id})",
        f"Categoria: {channel.category.name if channel.category else 'Sin categoria'}",
        f"Topic: {channel.topic or 'Sin topic'}",
        f"Owner ID: {topic_data.get('ticket_owner', 'desconocido')}",
        f"Tipo: {topic_data.get('ticket_type', 'desconocido')}",
        f"Terminos: {topic_data.get('terms', 'desconocido')}",
        f"Creado: {channel.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}",
        f"Generado: {discord.utils.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}",
        "=" * 80,
        "",
    ]

    message_count = 0
    async for message in channel.history(limit=None, oldest_first=True):
        message_count += 1
        lines.append(format_message_for_transcript(message))
        lines.append("-" * 80)

    transcript = "\n".join(lines)
    buffer = BytesIO(transcript.encode("utf-8"))
    filename = f"ticket-log-{channel.name}-{channel.id}.txt"
    return discord.File(buffer, filename=filename), message_count


def build_ticket_log_embed(
    channel: discord.TextChannel,
    topic_data: dict[str, str],
    closed_by: discord.abc.User,
    message_count: int,
) -> discord.Embed:
    option = OPTION_BY_KEY.get(topic_data.get("ticket_type", "general"), OPTION_BY_KEY["general"])
    owner_id = topic_data.get("ticket_owner", "desconocido")
    embed = discord.Embed(
        title="Log de ticket de servicio",
        description="Transcript generado automaticamente antes de cerrar el ticket.",
        color=discord.Color.from_rgb(255, 255, 255),
        timestamp=discord.utils.utcnow(),
    )
    embed.add_field(name="Ticket", value=f"#{channel.name}\n`{channel.id}`", inline=True)
    embed.add_field(name="Cliente", value=f"<@{owner_id}>\n`{owner_id}`", inline=True)
    embed.add_field(name="Tipo", value=f"{option.emoji} {option.label}", inline=True)
    embed.add_field(name="Cerrado por", value=f"{closed_by.mention}\n`{closed_by.id}`", inline=True)
    embed.add_field(name="Mensajes", value=str(message_count), inline=True)
    embed.add_field(name="Terminos", value=topic_data.get("terms", "desconocido"), inline=True)
    embed.set_footer(text="Guardar este archivo como evidencia en caso de disputa")
    return embed


async def send_ticket_log(
    channel: discord.TextChannel,
    settings: Settings,
    closed_by: discord.abc.User,
    topic_data: dict[str, str],
) -> bool:
    if channel.guild is None:
        return False

    log_channel = await get_ticket_log_channel(channel.guild, settings)
    if log_channel is None:
        return False

    me = channel.guild.me
    if me is not None:
        permissions = log_channel.permissions_for(me)
        if not permissions.view_channel or not permissions.send_messages or not permissions.attach_files or not permissions.embed_links:
            logger.warning("No tengo permisos suficientes para enviar logs en #%s.", log_channel.name)
            return False

    transcript_file, message_count = await build_ticket_transcript_file(channel, topic_data)
    embed = build_ticket_log_embed(channel, topic_data, closed_by, message_count)
    await log_channel.send(embed=embed, file=transcript_file)
    return True


async def create_ticket_channel(
    interaction: discord.Interaction,
    settings: Settings,
    option: TicketOption,
) -> discord.TextChannel:
    if interaction.guild is None or not isinstance(interaction.user, discord.Member):
        raise RuntimeError("Los tickets solo pueden crearse dentro de un servidor.")

    category = await get_ticket_category(interaction.guild, settings)
    if category is None:
        raise RuntimeError("No encontre la categoria configurada para tickets.")

    bot_member = interaction.guild.me
    overwrites: dict[discord.abc.Snowflake, discord.PermissionOverwrite] = {
        interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
        interaction.user: discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True,
            attach_files=True,
            embed_links=True,
        ),
    }

    if bot_member is not None:
        overwrites[bot_member] = discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True,
            manage_channels=True,
            embed_links=True,
        )

    if settings.ticket_staff_role_id is not None:
        role = interaction.guild.get_role(settings.ticket_staff_role_id)
        if role is not None:
            overwrites[role] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                attach_files=True,
                embed_links=True,
                manage_messages=True,
            )

    channel_name = f"ticket-{option.key}-{slugify(interaction.user.display_name)}"
    return await interaction.guild.create_text_channel(
        name=channel_name,
        category=category,
        overwrites=overwrites,
        topic=ticket_topic(interaction.user.id, option.key),
        reason=f"Ticket {option.label} creado por {interaction.user}",
    )


class TicketPanelSelect(discord.ui.Select):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        options = [
            discord.SelectOption(
                label=option.label,
                value=option.key,
                description=option.description,
                emoji=option.emoji,
            )
            for option in TICKET_OPTIONS
        ]
        super().__init__(
            custom_id="root_ticket_panel_select",
            placeholder="Selecciona el motivo del ticket",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None:
            await interaction.response.send_message("Los tickets solo funcionan dentro del servidor.", ephemeral=True)
            return

        option = OPTION_BY_KEY[self.values[0]]

        existing_ticket = await find_open_ticket(interaction.guild, self.settings, interaction.user.id)
        if existing_ticket is not None:
            await interaction.response.send_message(
                f"Ya tienes un ticket abierto: {existing_ticket.mention}",
                ephemeral=True,
            )
            return

        try:
            channel = await create_ticket_channel(interaction, self.settings, option)
        except RuntimeError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return
        except discord.Forbidden:
            await interaction.response.send_message("No tengo permisos para crear el canal del ticket.", ephemeral=True)
            return
        except discord.HTTPException as exc:
            logger.warning("Discord rechazo la creacion del ticket: %s", exc)
            await interaction.response.send_message("No pude crear el ticket. Intenta nuevamente mas tarde.", ephemeral=True)
            return

        await channel.send(
            content=interaction.user.mention,
            embed=build_terms_embed(interaction.user, option, self.settings),
            view=TicketTermsView(self.settings),
        )
        await interaction.response.send_message(f"Ticket creado: {channel.mention}", ephemeral=True)


class TicketPanelView(discord.ui.View):
    def __init__(self, settings: Settings) -> None:
        super().__init__(timeout=None)
        self.add_item(TicketPanelSelect(settings))


class TicketTermsView(discord.ui.View):
    def __init__(self, settings: Settings) -> None:
        super().__init__(timeout=None)
        self.settings = settings

    @discord.ui.button(
        label="Acepto",
        style=discord.ButtonStyle.success,
        custom_id="root_ticket_terms_accept",
    )
    async def accept(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        if not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message("Este boton solo funciona dentro del ticket.", ephemeral=True)
            return

        topic_data = parse_topic(interaction.channel.topic)
        owner_id = int(topic_data.get("ticket_owner", "0") or "0")
        option = OPTION_BY_KEY.get(topic_data.get("ticket_type", "general"), OPTION_BY_KEY["general"])

        if interaction.user.id != owner_id:
            await interaction.response.send_message("Solo quien creo el ticket puede aceptar estos terminos.", ephemeral=True)
            return

        await interaction.channel.edit(topic=ticket_topic(owner_id, option.key, accepted=True))
        await interaction.response.edit_message(view=None)
        await interaction.channel.send(embed=build_ready_embed(interaction.user, option), view=TicketCloseView(self.settings))

    @discord.ui.button(
        label="Rechazo",
        style=discord.ButtonStyle.danger,
        custom_id="root_ticket_terms_reject",
    )
    async def reject(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        if not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message("Este boton solo funciona dentro del ticket.", ephemeral=True)
            return

        topic_data = parse_topic(interaction.channel.topic)
        owner_id = int(topic_data.get("ticket_owner", "0") or "0")
        if interaction.user.id != owner_id:
            await interaction.response.send_message("Solo quien creo el ticket puede rechazar estos terminos.", ephemeral=True)
            return

        await interaction.response.edit_message(view=None)
        await interaction.channel.send(
            f"{interaction.user.mention}, rechazaste los terminos. Este ticket se cerrara en 10 segundos."
        )
        await asyncio.sleep(10)
        await interaction.channel.delete(reason=f"Ticket cerrado por rechazo de terminos: {interaction.user}")


class TicketCloseView(discord.ui.View):
    def __init__(self, settings: Settings) -> None:
        super().__init__(timeout=None)
        self.settings = settings

    @discord.ui.button(
        label="Cerrar ticket",
        style=discord.ButtonStyle.danger,
        custom_id="root_ticket_close",
    )
    async def close(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        if not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message("Este boton solo funciona dentro del ticket.", ephemeral=True)
            return

        topic_data = parse_topic(interaction.channel.topic)
        owner_id = int(topic_data.get("ticket_owner", "0") or "0")
        if not user_can_manage_ticket(interaction, owner_id):
            await interaction.response.send_message("No puedes cerrar este ticket.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        await interaction.channel.send(f"Ticket cerrado por {interaction.user.mention}. Se cerrara en 5 segundos.")

        if should_log_ticket(topic_data):
            try:
                logged = await send_ticket_log(interaction.channel, self.settings, interaction.user, topic_data)
            except discord.HTTPException as exc:
                logger.warning("No pude enviar log del ticket %s: %s", interaction.channel.id, exc)
                logged = False

            if not logged:
                await interaction.followup.send(
                    "No pude guardar el log descargable. No cerre el ticket para no perder evidencia.",
                    ephemeral=True,
                )
                return

        await interaction.followup.send("Ticket cerrado correctamente.", ephemeral=True)
        await asyncio.sleep(5)
        await interaction.channel.delete(reason=f"Ticket cerrado por {interaction.user}")


class TicketCog(commands.Cog):
    def __init__(self, bot: commands.Bot, settings: Settings) -> None:
        self.bot = bot
        self.settings = settings

    @app_commands.command(name="panel-ticket", description="Publica el panel para crear tickets.")
    @app_commands.describe(canal="Canal donde publicar el panel. Si lo dejas vacio, usa el canal configurado.")
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.guild_only()
    async def panel_ticket(
        self,
        interaction: discord.Interaction,
        canal: Optional[discord.TextChannel] = None,
    ) -> None:
        if interaction.guild is None:
            await interaction.response.send_message("Este comando solo funciona dentro de un servidor.", ephemeral=True)
            return

        target = canal
        if target is None and self.settings.ticket_channel_id is not None:
            channel = interaction.guild.get_channel(self.settings.ticket_channel_id)
            if isinstance(channel, discord.TextChannel):
                target = channel

        if target is None:
            target = interaction.channel if isinstance(interaction.channel, discord.TextChannel) else None

        if target is None:
            await interaction.response.send_message("No encontre un canal valido para publicar el panel.", ephemeral=True)
            return

        me = interaction.guild.me
        if me is not None:
            permissions = target.permissions_for(me)
            if not permissions.view_channel or not permissions.send_messages or not permissions.embed_links:
                await interaction.response.send_message(
                    f"No tengo permisos para publicar el panel en {target.mention}.",
                    ephemeral=True,
                )
                return

        await target.send(embed=build_ticket_panel_embed(interaction.guild, self.settings), view=TicketPanelView(self.settings))
        await interaction.response.send_message(f"Panel de tickets publicado en {target.mention}.", ephemeral=True)

    @panel_ticket.error
    async def panel_ticket_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
        if isinstance(error, app_commands.MissingPermissions):
            message = "Necesitas permiso de **Manage Server** para publicar el panel de tickets."
            if interaction.response.is_done():
                await interaction.followup.send(message, ephemeral=True)
            else:
                await interaction.response.send_message(message, ephemeral=True)
            return

        raise error
