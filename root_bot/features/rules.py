from __future__ import annotations

from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from ..config import Settings


RULES = (
    (
        "1. Respeto obligatorio",
        "No insultos, acoso, amenazas, discriminacion, burlas pesadas ni ataques personales. Trata a todos como quieres que te traten.",
    ),
    (
        "2. Cero toxicidad y drama",
        "No vengas a provocar, pelear, humillar, buscar problemas o arrastrar conflictos de otros servidores. Si algo pasa, reportalo al staff.",
    ),
    (
        "3. Usa bien los canales",
        "Cada canal tiene su proposito. Evita desorden, flood, spam, mensajes repetidos, menciones innecesarias y contenido fuera de lugar.",
    ),
    (
        "4. Contenido seguro",
        "Prohibido NSFW, gore, contenido ilegal, estafas, phishing, malware, pirateria, doxxing o cualquier cosa que ponga en riesgo a la comunidad.",
    ),
    (
        "5. Publicidad con permiso",
        "No invites a otros servidores, autopromocion, ventas, sorteos externos ni links sospechosos sin autorizacion del staff.",
    ),
    (
        "6. Identidad y perfiles",
        "No suplantes usuarios, staff, bots o marcas. Nombres, avatares y estados ofensivos pueden ser moderados.",
    ),
    (
        "7. Privacidad",
        "No compartas datos personales, conversaciones privadas, fotos o informacion de otros sin permiso claro.",
    ),
    (
        "8. Comunidad ordenada",
        "Ayuda a mantener buen ambiente. No hagas backseat moderating, no alimentes peleas y usa tickets/reportes cuando sea necesario.",
    ),
    (
        "9. Staff y sanciones",
        "Las decisiones del staff se respetan. Saltarse reglas puede terminar en advertencia, mute, kick o ban segun la gravedad.",
    ),
    (
        "10. Sentido comun",
        "Si algo parece mala idea, probablemente lo es. El objetivo es convivir, pasarla bien y cuidar el servidor.",
    ),
)


def build_rules_embed(guild: discord.Guild, settings: Settings) -> discord.Embed:
    embed = discord.Embed(
        title=f"Reglas oficiales de {guild.name}",
        description=(
            "Esta comunidad es para compartir, convivir y pasarla bien con orden. "
            "No buscamos toxicidad, peleas ni gente que venga a romper el ambiente.\n\n"
            "**Al permanecer en el servidor aceptas estas reglas.**"
        ),
        color=discord.Color(settings.rules_embed_color),
        timestamp=discord.utils.utcnow(),
    )

    if guild.icon is not None:
        embed.set_thumbnail(url=guild.icon.url)

    for title, text in RULES:
        embed.add_field(name=title, value=text, inline=False)

    embed.set_footer(text="Staff | Comunidad oficial")
    return embed


class RulesCog(commands.Cog):
    def __init__(self, bot: commands.Bot, settings: Settings) -> None:
        self.bot = bot
        self.settings = settings

    @app_commands.command(name="reglas", description="Publica las reglas oficiales del servidor.")
    @app_commands.describe(canal="Canal donde publicar las reglas. Si lo dejas vacio, usa este canal.")
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.guild_only()
    async def rules(
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

        await target.send(embed=build_rules_embed(interaction.guild, self.settings))
        await interaction.response.send_message(f"Reglas publicadas en {target.mention}.", ephemeral=True)

    @rules.error
    async def rules_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
        if isinstance(error, app_commands.MissingPermissions):
            message = "Necesitas permiso de **Manage Server** para publicar las reglas."
            if interaction.response.is_done():
                await interaction.followup.send(message, ephemeral=True)
            else:
                await interaction.response.send_message(message, ephemeral=True)
            return

        raise error
