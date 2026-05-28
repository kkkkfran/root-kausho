from __future__ import annotations

from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from ..config import Settings


def ticket_mention(settings: Settings) -> str:
    if settings.ticket_channel_id is None:
        return "el canal de tickets"

    return f"<#{settings.ticket_channel_id}>"


def build_about_embed(guild: discord.Guild, settings: Settings) -> discord.Embed:
    ticket_text = ticket_mention(settings)
    embed = discord.Embed(
        title="kaush@root | Desarrollo, bots y automatizacion",
        description=(
            "Este servidor reune proyectos, soporte y servicios enfocados en programacion, "
            "bots de Discord, paginas web y automatizaciones utiles para comunidades.\n\n"
            f"Si quieres cotizar, pedir soporte o conversar una idea, crea un ticket en {ticket_text}."
        ),
        color=discord.Color(settings.about_embed_color),
        timestamp=discord.utils.utcnow(),
    )

    if guild.icon is not None:
        embed.set_thumbnail(url=guild.icon.url)

    embed.add_field(
        name="Sobre mi",
        value=(
            "Soy Ingeniero en Informatica, con fuerte enfoque en programacion, desarrollo de bots, "
            "automatizacion de tareas y sistemas pensados para ahorrar tiempo y ordenar comunidades."
        ),
        inline=False,
    )
    embed.add_field(
        name="Lo que hago",
        value=(
            "• Bots de Discord a medida\n"
            "• Sistemas de tickets y soporte\n"
            "• Paginas web y paneles administrativos\n"
            "• Automatizaciones para servidores y comunidades\n"
            "• Sistemas de anuncios largos y herramientas de voz/TTS\n"
            "• Sistemas de roles y flujos para equipos"
        ),
        inline=False,
    )
    embed.add_field(
        name="Proyectos y experiencia",
        value=(
            "He creado varios bots y sistemas, incluyendo **Fossil**, un bot de videojuegos conocido por muchas comunidades; "
            "bots para musica, TTS y anuncios largos que superan limites habituales de Discord; sistemas para ARK y Path of Titans; "
            "y herramientas con funciones utiles para la administracion de servidores."
        ),
        inline=False,
    )
    embed.add_field(
        name="Proximamente",
        value=(
            "Estoy mejorando el sistema de roles para que las personas puedan autoasignarse roles de forma ordenada, "
            "sin depender de pedirlos manualmente, siempre respetando la organizacion de lideres y equipos."
        ),
        inline=False,
    )
    embed.add_field(
        name="Servicios",
        value=(
            f"Si buscas aprovechar mis servicios, crear un bot, mejorar tu servidor o automatizar alguna tarea, "
            f"abre un ticket en {ticket_text}. Ahi podemos revisar tu idea, requisitos y el mejor camino para construirlo."
        ),
        inline=False,
    )
    embed.set_footer(text="root@kausho | Soluciones a medida para comunidades")
    return embed


class TicketLinkView(discord.ui.View):
    def __init__(self, settings: Settings) -> None:
        super().__init__(timeout=None)
        self.add_item(
            discord.ui.Button(
                label="Crear ticket",
                style=discord.ButtonStyle.link,
                url=settings.ticket_url,
            )
        )


class AboutCog(commands.Cog):
    def __init__(self, bot: commands.Bot, settings: Settings) -> None:
        self.bot = bot
        self.settings = settings

    @app_commands.command(name="servidor", description="Publica de que va el servidor y los servicios disponibles.")
    @app_commands.describe(canal="Canal donde publicar la presentacion. Si lo dejas vacio, usa este canal.")
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.guild_only()
    async def server_info(
        self,
        interaction: discord.Interaction,
        canal: Optional[discord.TextChannel] = None,
    ) -> None:
        if interaction.guild is None:
            await interaction.response.send_message("Este comando solo funciona dentro de un servidor.", ephemeral=True)
            return

        target = canal or interaction.channel
        if not isinstance(target, discord.TextChannel):
            await interaction.response.send_message("Usa este comando en un canal de texto normal.", ephemeral=True)
            return

        me = interaction.guild.me
        if me is not None:
            permissions = target.permissions_for(me)
            if not permissions.view_channel or not permissions.send_messages or not permissions.embed_links:
                await interaction.response.send_message(
                    f"No tengo permisos para publicar embeds en {target.mention}.",
                    ephemeral=True,
                )
                return

        await target.send(embed=build_about_embed(interaction.guild, self.settings), view=TicketLinkView(self.settings))
        await interaction.response.send_message(f"Presentacion publicada en {target.mention}.", ephemeral=True)

    @server_info.error
    async def server_info_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
        if isinstance(error, app_commands.MissingPermissions):
            message = "Necesitas permiso de **Manage Server** para publicar esta presentacion."
            if interaction.response.is_done():
                await interaction.followup.send(message, ephemeral=True)
            else:
                await interaction.response.send_message(message, ephemeral=True)
            return

        raise error
