from __future__ import annotations

import asyncio
import json
import logging
import random
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from ..config import Settings


logger = logging.getLogger("root-bot.giveaways")
FALLBACK_GIFT_EMOJI = "\U0001F381"
DEFAULT_REACTION_EMOJI = "\U0001F381"
CLAIM_SECONDS = 10


@dataclass
class GiveawayRecord:
    guild_id: int
    channel_id: int
    message_id: int
    host_id: int
    prize: str
    winners_count: int
    ends_at: float
    reaction_emoji: str
    gift_emoji: str
    claim_channel_id: int


def format_duration(seconds: int) -> str:
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        minutes, rest = divmod(seconds, 60)
        return f"{minutes}m {rest}s" if rest else f"{minutes}m"

    hours, rest = divmod(seconds, 3600)
    minutes = rest // 60
    return f"{hours}h {minutes}m" if minutes else f"{hours}h"


def resolve_named_emoji(guild: discord.Guild, name: str, fallback: str) -> str:
    emoji = discord.utils.get(guild.emojis, name=name)
    if emoji is None:
        return fallback

    return str(emoji)


def build_progress_bar(remaining: int, total: int = CLAIM_SECONDS) -> str:
    clamped = max(0, min(total, remaining))
    return "[" + ("#" * clamped) + ("-" * (total - clamped)) + "]"


def build_giveaway_embed(
    record: GiveawayRecord,
    *,
    guild: discord.Guild,
    color: int,
    status: str = "Activo",
) -> discord.Embed:
    ends_at = int(record.ends_at)
    host_mention = f"<@{record.host_id}>"
    embed = discord.Embed(
        title=f"{record.gift_emoji} Sorteo oficial",
        description=(
            f"**Premio**\n{record.prize}\n\n"
            f"{record.reaction_emoji} Reacciona en este mensaje para participar.\n"
            f"El ganador tendra **{CLAIM_SECONDS}s** para reclamar su premio."
        ),
        color=discord.Color(color),
        timestamp=discord.utils.utcnow(),
    )
    embed.add_field(name="Estado", value=status, inline=True)
    embed.add_field(name="Ganadores", value=str(record.winners_count), inline=True)
    embed.add_field(name="Organizador", value=host_mention, inline=True)
    embed.add_field(name="Finaliza", value=f"<t:{ends_at}:R>\n<t:{ends_at}:F>", inline=True)
    embed.add_field(name="Reclamo", value=f"Mencionar al organizador en <#{record.claim_channel_id}>.", inline=True)
    embed.add_field(name="Validacion", value="El bot ignora reacciones de bots.", inline=True)
    if guild.icon is not None:
        embed.set_author(name=guild.name, icon_url=guild.icon.url)
    if guild.icon is not None:
        embed.set_thumbnail(url=guild.icon.url)

    embed.set_footer(text="root@kausho | Sorteo oficial")
    return embed


def build_no_winner_embed(record: GiveawayRecord, guild: discord.Guild, *, color: int) -> discord.Embed:
    embed = discord.Embed(
        title=f"{record.gift_emoji} Sorteo finalizado",
        description=f"El sorteo de **{record.prize}** termino sin participantes validos.",
        color=discord.Color(color),
        timestamp=discord.utils.utcnow(),
    )
    if guild.icon is not None:
        embed.set_thumbnail(url=guild.icon.url)
    embed.set_footer(text="No hubo ganador")
    return embed


def build_claim_embed(
    record: GiveawayRecord,
    winner: discord.abc.User,
    *,
    color: int,
    remaining: int,
    claimed: bool = False,
    lost: bool = False,
) -> discord.Embed:
    if claimed:
        title = f"{record.gift_emoji} Premio reclamado"
        description = f"{winner.mention} reclamo el premio correctamente."
        status = "Reclamado"
    elif lost:
        title = f"{record.gift_emoji} Recompensa perdida"
        description = f"{winner.mention} no menciono al organizador a tiempo y perdio la recompensa."
        status = "Perdido"
    else:
        title = f"{record.gift_emoji} Ganador seleccionado"
        description = (
            f"Felicidades {winner.mention}, ganaste **{record.prize}**.\n\n"
            f"Debes mencionar a <@{record.host_id}> en <#{record.claim_channel_id}> para reclamar."
        )
        status = f"{remaining}s restantes"

    embed_color = discord.Color(color)
    if claimed:
        embed_color = discord.Color.green()
    elif lost:
        embed_color = discord.Color.red()

    timer = "`00:00`"
    progress = build_progress_bar(0)
    if not claimed and not lost:
        timer = f"`00:{remaining:02d}`"
        progress = build_progress_bar(remaining)

    embed = discord.Embed(title=title, description=description, color=embed_color, timestamp=discord.utils.utcnow())
    embed.add_field(name="Temporizador", value=f"{timer}\n`{progress}`", inline=True)
    embed.add_field(name="Estado", value=status, inline=True)
    embed.add_field(name="Canal de reclamo", value=f"<#{record.claim_channel_id}>", inline=True)
    embed.set_footer(text="El reclamo debe hacerse dentro del tiempo indicado")
    return embed


class GiveawayStore:
    def __init__(self, path: str) -> None:
        self.path = Path(path)

    def load(self) -> dict[str, GiveawayRecord]:
        if not self.path.exists():
            return {}

        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("No pude leer giveaways: %s", exc)
            return {}

        records: dict[str, GiveawayRecord] = {}
        for key, value in data.items():
            try:
                records[key] = GiveawayRecord(**value)
            except TypeError as exc:
                logger.warning("Giveaway invalido en storage %s: %s", key, exc)

        return records

    def save(self, records: dict[str, GiveawayRecord]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {key: asdict(value) for key, value in records.items()}
        self.path.write_text(json.dumps(data, indent=2), encoding="utf-8")


class GiveawayCog(commands.Cog):
    giveaway = app_commands.Group(name="sorteo", description="Sistema de sorteos del servidor.")

    def __init__(self, bot: commands.Bot, settings: Settings) -> None:
        self.bot = bot
        self.settings = settings
        self.store = GiveawayStore(settings.giveaway_data_file)
        self.records = self.store.load()
        self.tasks: dict[str, asyncio.Task[None]] = {}

    async def cog_load(self) -> None:
        self.bot.loop.create_task(self.resume_giveaways())

    async def cog_unload(self) -> None:
        for task in self.tasks.values():
            task.cancel()

    async def resume_giveaways(self) -> None:
        await self.bot.wait_until_ready()
        for key, record in list(self.records.items()):
            self.schedule_giveaway(key, record)

    def schedule_giveaway(self, key: str, record: GiveawayRecord) -> None:
        old_task = self.tasks.pop(key, None)
        if old_task is not None:
            old_task.cancel()

        self.tasks[key] = self.bot.loop.create_task(self.finish_when_ready(key, record))

    def save_records(self) -> None:
        self.store.save(self.records)

    async def finish_when_ready(self, key: str, record: GiveawayRecord) -> None:
        delay = max(0, record.ends_at - discord.utils.utcnow().timestamp())
        await asyncio.sleep(delay)
        await self.finish_giveaway(key, record)

    async def fetch_giveaway_message(self, record: GiveawayRecord) -> tuple[discord.Guild, discord.TextChannel, discord.Message] | None:
        guild = self.bot.get_guild(record.guild_id)
        if guild is None:
            logger.warning("No encontre guild para sorteo %s.", record.message_id)
            return None

        channel = guild.get_channel(record.channel_id)
        if channel is None:
            try:
                channel = await guild.fetch_channel(record.channel_id)
            except discord.DiscordException as exc:
                logger.warning("No encontre canal de sorteo %s: %s", record.channel_id, exc)
                return None

        if not isinstance(channel, discord.TextChannel):
            logger.warning("Canal de sorteo %s no es texto.", record.channel_id)
            return None

        try:
            message = await channel.fetch_message(record.message_id)
        except discord.DiscordException as exc:
            logger.warning("No encontre mensaje de sorteo %s: %s", record.message_id, exc)
            return None

        return guild, channel, message

    async def collect_participants(self, message: discord.Message, record: GiveawayRecord) -> list[discord.abc.User]:
        participants: list[discord.abc.User] = []
        seen: set[int] = set()
        for reaction in message.reactions:
            if str(reaction.emoji) != record.reaction_emoji:
                continue

            async for user in reaction.users(limit=None):
                if user.bot or user.id in seen:
                    continue

                seen.add(user.id)
                participants.append(user)

        return participants

    async def finish_giveaway(self, key: str, record: GiveawayRecord) -> None:
        fetched = await self.fetch_giveaway_message(record)
        if fetched is None:
            self.records.pop(key, None)
            self.save_records()
            return

        guild, channel, message = fetched
        participants = await self.collect_participants(message, record)
        if not participants:
            await message.edit(content=None, embed=build_no_winner_embed(record, guild, color=self.settings.giveaway_embed_color))
            self.records.pop(key, None)
            self.save_records()
            return

        winners = random.sample(participants, k=min(record.winners_count, len(participants)))
        winner_mentions = ", ".join(winner.mention for winner in winners)
        ended_embed = build_giveaway_embed(
            record,
            guild=guild,
            color=self.settings.giveaway_embed_color,
            status="Finalizado",
        )
        ended_embed.add_field(name="Ganador(es)", value=winner_mentions, inline=False)
        await message.edit(content=None, embed=ended_embed)

        await asyncio.gather(*(self.run_claim_countdown(channel, record, winner) for winner in winners))

        self.records.pop(key, None)
        self.save_records()

    async def run_claim_countdown(
        self,
        source_channel: discord.TextChannel,
        record: GiveawayRecord,
        winner: discord.abc.User,
    ) -> None:
        claim_message = await source_channel.send(
            content=winner.mention,
            embed=build_claim_embed(
                record,
                winner,
                color=self.settings.giveaway_embed_color,
                remaining=CLAIM_SECONDS,
            ),
            allowed_mentions=discord.AllowedMentions(users=True),
        )

        claim_channel = source_channel.guild.get_channel(record.claim_channel_id)
        if claim_channel is None:
            try:
                claim_channel = await source_channel.guild.fetch_channel(record.claim_channel_id)
            except discord.DiscordException:
                claim_channel = source_channel

        if not isinstance(claim_channel, discord.TextChannel):
            claim_channel = source_channel

        def check(message: discord.Message) -> bool:
            if message.author.id != winner.id or message.channel.id != claim_channel.id:
                return False

            host_mentioned = any(user.id == record.host_id for user in message.mentions)
            return host_mentioned or f"<@{record.host_id}>" in message.content or f"<@!{record.host_id}>" in message.content

        wait_task = self.bot.loop.create_task(self.bot.wait_for("message", check=check, timeout=CLAIM_SECONDS))
        for remaining in range(CLAIM_SECONDS - 1, -1, -1):
            await asyncio.sleep(1)
            if wait_task.done():
                break
            await claim_message.edit(
                embed=build_claim_embed(
                    record,
                    winner,
                    color=self.settings.giveaway_embed_color,
                    remaining=remaining,
                )
            )

        try:
            await wait_task
        except asyncio.TimeoutError:
            await claim_message.edit(
                embed=build_claim_embed(
                    record,
                    winner,
                    color=self.settings.giveaway_embed_color,
                    remaining=0,
                    lost=True,
                )
            )
            return

        await claim_message.edit(
            embed=build_claim_embed(
                record,
                winner,
                color=self.settings.giveaway_embed_color,
                remaining=0,
                claimed=True,
            )
        )

    @giveaway.command(name="iniciar", description="Inicia un sorteo con reaccion para participar.")
    @app_commands.describe(
        premio="Premio del sorteo",
        duracion_minutos="Duracion del sorteo en minutos",
        ganadores="Cantidad de ganadores",
        canal="Canal donde publicar el sorteo",
    )
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.guild_only()
    async def start(
        self,
        interaction: discord.Interaction,
        premio: str,
        duracion_minutos: app_commands.Range[int, 1, 10080],
        ganadores: app_commands.Range[int, 1, 10] = 1,
        canal: Optional[discord.TextChannel] = None,
    ) -> None:
        if interaction.guild is None:
            await interaction.response.send_message("Este comando solo funciona dentro de un servidor.", ephemeral=True)
            return

        target = canal or interaction.channel
        if not isinstance(target, discord.TextChannel):
            await interaction.response.send_message("Usa este comando en un canal de texto normal.", ephemeral=True)
            return

        if len(premio) > 250:
            await interaction.response.send_message("El premio no puede superar 250 caracteres.", ephemeral=True)
            return

        me = interaction.guild.me
        if me is not None:
            permissions = target.permissions_for(me)
            required_permissions = {
                "View Channel": permissions.view_channel,
                "Send Messages": permissions.send_messages,
                "Embed Links": permissions.embed_links,
                "Add Reactions": permissions.add_reactions,
                "Read Message History": permissions.read_message_history,
                "Mention Everyone": permissions.mention_everyone,
            }
            missing_permissions = [name for name, has_permission in required_permissions.items() if not has_permission]
            if missing_permissions:
                await interaction.response.send_message(
                    f"No tengo permisos para publicar sorteos en {target.mention}: {', '.join(missing_permissions)}.",
                    ephemeral=True,
                )
                return

        gift_emoji = resolve_named_emoji(interaction.guild, "gift_1", FALLBACK_GIFT_EMOJI)
        reaction_emoji = resolve_named_emoji(interaction.guild, "react_gift", DEFAULT_REACTION_EMOJI)
        ends_at = discord.utils.utcnow().timestamp() + duracion_minutos * 60
        claim_channel_id = self.settings.giveaway_claim_channel_id or target.id
        record = GiveawayRecord(
            guild_id=interaction.guild.id,
            channel_id=target.id,
            message_id=0,
            host_id=interaction.user.id,
            prize=premio,
            winners_count=ganadores,
            ends_at=ends_at,
            reaction_emoji=reaction_emoji,
            gift_emoji=gift_emoji,
            claim_channel_id=claim_channel_id,
        )

        embed = build_giveaway_embed(record, guild=interaction.guild, color=self.settings.giveaway_embed_color)
        await interaction.response.defer(ephemeral=True)
        message = await target.send(
            content="||@everyone||",
            embed=embed,
            allowed_mentions=discord.AllowedMentions(everyone=True),
        )
        record.message_id = message.id

        try:
            await message.add_reaction(reaction_emoji)
        except discord.HTTPException:
            fallback_record = record
            fallback_record.reaction_emoji = DEFAULT_REACTION_EMOJI
            await message.add_reaction(DEFAULT_REACTION_EMOJI)
            await message.edit(
                embed=build_giveaway_embed(
                    fallback_record,
                    guild=interaction.guild,
                    color=self.settings.giveaway_embed_color,
                )
            )

        key = str(message.id)
        self.records[key] = record
        self.save_records()
        self.schedule_giveaway(key, record)

        await interaction.followup.send(
            f"Sorteo creado en {target.mention}. Termina en {format_duration(duracion_minutos * 60)}.",
            ephemeral=True,
        )

    @giveaway.error
    async def giveaway_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
        if isinstance(error, app_commands.MissingPermissions):
            message = "Necesitas permiso de **Manage Server** para administrar sorteos."
            if interaction.response.is_done():
                await interaction.followup.send(message, ephemeral=True)
            else:
                await interaction.response.send_message(message, ephemeral=True)
            return

        raise error
