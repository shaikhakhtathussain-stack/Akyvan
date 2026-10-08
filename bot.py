import os
from datetime import timedelta
import discord
from discord.ext import commands
from discord import app_commands

TOKEN = os.getenv("DISCORD_TOKEN")

if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN is not set.")

intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.message_content = True
intents.presences = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    try:
        synced = await bot.tree.sync()
        print(f"AKYVAN online as {bot.user}")
        print(f"Synced {len(synced)} slash commands.")
    except Exception as e:
        print(f"Command sync error: {e}")

@bot.tree.command(name="ping", description="Check whether AKYVAN is online.")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message(
        f"🛡️ AKYVAN is online! Ping: {round(bot.latency * 1000)}ms"
    )

@bot.tree.command(name="serverinfo", description="Show basic server information.")
@app_commands.checks.has_permissions(manage_guild=True)
async def serverinfo(interaction: discord.Interaction):
    guild = interaction.guild
    if guild is None:
        return await interaction.response.send_message("This command can only be used in a server.")
    embed = discord.Embed(title=f"🛡️ {guild.name}", color=discord.Color.blue())
    embed.add_field(name="Members", value=str(guild.member_count))
    embed.add_field(name="Channels", value=str(len(guild.channels)))
    embed.add_field(name="Roles", value=str(len(guild.roles)))
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="clear", description="Delete messages from the current channel.")
@app_commands.describe(amount="Number of messages to delete (1-100)")
@app_commands.checks.has_permissions(manage_messages=True)
async def clear(interaction: discord.Interaction, amount: app_commands.Range[int, 1, 100]):
    if not isinstance(interaction.channel, discord.TextChannel):
        return await interaction.response.send_message("This command can only be used in a text channel.")
    await interaction.response.defer(ephemeral=True)
    deleted = await interaction.channel.purge(limit=amount)
    await interaction.followup.send(f"🧹 Deleted {len(deleted)} messages.", ephemeral=True)

@bot.tree.command(name="kick", description="Kick a member.")
@app_commands.describe(member="Member to kick", reason="Reason")
@app_commands.checks.has_permissions(kick_members=True)
async def kick(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
    if member == interaction.user:
        return await interaction.response.send_message("You cannot kick yourself.", ephemeral=True)
    try:
        await member.kick(reason=f"{reason} | By {interaction.user}")
        await interaction.response.send_message(f"👢 Kicked **{member}**. Reason: {reason}")
    except discord.Forbidden:
        await interaction.response.send_message("❌ I don't have permission to kick that member.", ephemeral=True)

@bot.tree.command(name="ban", description="Ban a member.")
@app_commands.describe(member="Member to ban", reason="Reason")
@app_commands.checks.has_permissions(ban_members=True)
async def ban(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
    if member == interaction.user:
        return await interaction.response.send_message("You cannot ban yourself.", ephemeral=True)
    try:
        await member.ban(reason=f"{reason} | By {interaction.user}")
        await interaction.response.send_message(f"🔨 Banned **{member}**. Reason: {reason}")
    except discord.Forbidden:
        await interaction.response.send_message("❌ I don't have permission to ban that member.", ephemeral=True)

@bot.tree.command(name="timeout", description="Timeout a member.")
@app_commands.describe(member="Member to timeout", minutes="Timeout length in minutes", reason="Reason")
@app_commands.checks.has_permissions(moderate_members=True)
async def timeout(interaction: discord.Interaction, member: discord.Member, minutes: app_commands.Range[int, 1, 40320], reason: str = "No reason provided"):
    if member == interaction.user:
        return await interaction.response.send_message("You cannot timeout yourself.", ephemeral=True)
    try:
        duration = discord.utils.utcnow() + timedelta(minutes=minutes)
        await member.timeout(duration, reason=f"{reason} | By {interaction.user}")
        await interaction.response.send_message(f"⏳ Timed out **{member}** for {minutes} minutes.")
    except discord.Forbidden:
        await interaction.response.send_message("❌ I don't have permission to timeout that member.", ephemeral=True)

@bot.tree.command(name="lock", description="Lock the current channel.")
@app_commands.checks.has_permissions(manage_channels=True)
async def lock(interaction: discord.Interaction):
    channel = interaction.channel
    if not isinstance(channel, discord.TextChannel):
        return await interaction.response.send_message("Text channel only.", ephemeral=True)
    overwrite = channel.overwrites_for(interaction.guild.default_role)
    overwrite.send_messages = False
    await channel.set_permissions(interaction.guild.default_role, overwrite=overwrite)
    await interaction.response.send_message("🔒 Channel locked.")

@bot.tree.command(name="unlock", description="Unlock the current channel.")
@app_commands.checks.has_permissions(manage_channels=True)
async def unlock(interaction: discord.Interaction):
    channel = interaction.channel
    if not isinstance(channel, discord.TextChannel):
        return await interaction.response.send_message("Text channel only.", ephemeral=True)
    overwrite = channel.overwrites_for(interaction.guild.default_role)
    overwrite.send_messages = None
    await channel.set_permissions(interaction.guild.default_role, overwrite=overwrite)
    await interaction.response.send_message("🔓 Channel unlocked.")

@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.errors.MissingPermissions):
        message = "❌ You don't have permission to use this command."
    else:
        message = "❌ Something went wrong while running that command."
        print(repr(error))
    if interaction.response.is_done():
        await interaction.followup.send(message, ephemeral=True)
    else:
        await interaction.response.send_message(message, ephemeral=True)

bot.run(TOKEN)
