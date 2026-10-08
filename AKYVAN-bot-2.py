import os
import time
import json
from pathlib import Path
from collections import defaultdict, deque

import discord
from discord.ext import commands
from discord import app_commands

TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN is not set.")

DATA_FILE = Path("security_data.json")

def load_data():
    try:
        return json.loads(DATA_FILE.read_text())
    except Exception:
        return {"guilds": {}}

data = load_data()

def save_data():
    DATA_FILE.write_text(json.dumps(data, indent=2))

def cfg(guild_id):
    gid = str(guild_id)
    if gid not in data["guilds"]:
        data["guilds"][gid] = {
            "antinuke": True,
            "antiraid": True,
            "raid_joins": 8,
            "raid_seconds": 10,
            "whitelist": []
        }
        save_data()
    return data["guilds"][gid]

intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.message_content = True
intents.presences = True

bot = commands.Bot(command_prefix="!", intents=intents)
join_times = defaultdict(deque)
recent = {}

async def whitelisted(guild, user_id):
    return user_id == guild.owner_id or user_id in cfg(guild.id)["whitelist"]

async def audit_executor(guild, action, target_id):
    try:
        async for entry in guild.audit_logs(limit=10, action=action):
            if entry.target and getattr(entry.target, "id", None) == target_id:
                if (discord.utils.utcnow() - entry.created_at).total_seconds() < 15:
                    return entry.user
    except Exception as e:
        print("Audit log error:", e)
    return None

async def punish(guild, user, reason):
    if not user or await whitelisted(guild, user.id) or (bot.user and user.id == bot.user.id):
        return
    member = guild.get_member(user.id)
    if not member:
        return
    try:
        await member.edit(roles=[], reason="AKYVAN: " + reason)
    except Exception:
        pass
    try:
        await guild.ban(member, reason="AKYVAN: " + reason, delete_message_seconds=0)
        print(f"AKYVAN banned {user} in {guild.name}: {reason}")
    except Exception as e:
        print("Could not ban executor:", e)

async def protect(guild, action, target_id, reason, key):
    c = cfg(guild.id)
    if not c["antinuke"]:
        return
    user = await audit_executor(guild, action, target_id)
    if not user:
        return
    stamp = time.time()
    if stamp - recent.get((guild.id, user.id, key), 0) < 3:
        return
    recent[(guild.id, user.id, key)] = stamp
    await punish(guild, user, reason)

@bot.event
async def on_ready():
    try:
        synced = await bot.tree.sync()
        print(f"AKYVAN online as {bot.user}")
        print(f"Synced {len(synced)} slash commands.")
    except Exception as e:
        print("Sync error:", e)

@bot.event
async def on_member_join(member):
    c = cfg(member.guild.id)
    if not c["antiraid"] or member.bot:
        return
    now = time.time()
    q = join_times[member.guild.id]
    q.append(now)
    while q and now - q[0] > c["raid_seconds"]:
        q.popleft()
    if len(q) >= c["raid_joins"]:
        try:
            await member.kick(reason="AKYVAN Anti-Raid: join rate exceeded")
            print("Anti-Raid kicked", member)
        except Exception as e:
            print("Anti-Raid error:", e)

@bot.event
async def on_guild_channel_delete(channel):
    await protect(channel.guild, discord.AuditLogAction.channel_delete, channel.id,
                   "unauthorized channel deletion", "channel_delete")

@bot.event
async def on_guild_role_delete(role):
    await protect(role.guild, discord.AuditLogAction.role_delete, role.id,
                   "unauthorized role deletion", "role_delete")

@bot.event
async def on_member_ban(guild, user):
    await protect(guild, discord.AuditLogAction.member_ban_add, user.id,
                   "unauthorized member ban", "ban")

@bot.event
async def on_member_remove(member):
    await protect(member.guild, discord.AuditLogAction.member_kick, member.id,
                   "unauthorized member kick", "kick")

@bot.event
async def on_guild_update(before, after):
    if before.name != after.name or before.icon != after.icon:
        await protect(after, discord.AuditLogAction.guild_update, after.id,
                       "unauthorized server change", "guild_update")

def admin():
    return app_commands.checks.has_permissions(administrator=True)

@bot.tree.command(name="security", description="Show AKYVAN security status")
@app_commands.guild_only()
async def security(interaction):
    c = cfg(interaction.guild.id)
    e = discord.Embed(title="🛡️ AKYVAN Security", color=discord.Color.blurple())
    e.add_field(name="Anti-Nuke", value="🟢 ON" if c["antinuke"] else "🔴 OFF")
    e.add_field(name="Anti-Raid", value="🟢 ON" if c["antiraid"] else "🔴 OFF")
    e.add_field(name="Raid limit", value=f"{c['raid_joins']} joins / {c['raid_seconds']} sec")
    e.add_field(name="Whitelist", value=str(len(c["whitelist"])))
    await interaction.response.send_message(embed=e, ephemeral=True)

@bot.tree.command(name="antinuke", description="Enable or disable Anti-Nuke")
@app_commands.guild_only()
@admin()
async def antinuke(interaction, enabled: bool):
    cfg(interaction.guild.id)["antinuke"] = enabled
    save_data()
    await interaction.response.send_message(f"🛡️ Anti-Nuke: **{'ON' if enabled else 'OFF'}**", ephemeral=True)

@bot.tree.command(name="antiraid", description="Enable or disable Anti-Raid")
@app_commands.guild_only()
@admin()
async def antiraid(interaction, enabled: bool):
    cfg(interaction.guild.id)["antiraid"] = enabled
    save_data()
    await interaction.response.send_message(f"🚨 Anti-Raid: **{'ON' if enabled else 'OFF'}**", ephemeral=True)

@bot.tree.command(name="raidlimit", description="Set Anti-Raid join limit")
@app_commands.guild_only()
@admin()
async def raidlimit(interaction, joins: int, seconds: int):
    if not 2 <= joins <= 50 or not 3 <= seconds <= 60:
        await interaction.response.send_message("Use joins 2-50 and seconds 3-60.", ephemeral=True)
        return
    c = cfg(interaction.guild.id)
    c["raid_joins"] = joins
    c["raid_seconds"] = seconds
    save_data()
    await interaction.response.send_message(f"🚨 Anti-Raid: **{joins} joins / {seconds} seconds**", ephemeral=True)

@bot.tree.command(name="whitelist", description="Add or remove a trusted user")
@app_commands.guild_only()
@admin()
@app_commands.choices(action=[app_commands.Choice(name="add", value="add"), app_commands.Choice(name="remove", value="remove")])
async def whitelist(interaction, user: discord.Member, action: app_commands.Choice[str]):
    c = cfg(interaction.guild.id)
    if action.value == "add":
        if user.id not in c["whitelist"]:
            c["whitelist"].append(user.id)
        msg = f"✅ {user.mention} added to whitelist."
    else:
        if user.id in c["whitelist"]:
            c["whitelist"].remove(user.id)
        msg = f"✅ {user.mention} removed from whitelist."
    save_data()
    await interaction.response.send_message(msg, ephemeral=True)

@bot.tree.command(name="lockdown", description="Lock all text channels")
@app_commands.guild_only()
@admin()
async def lockdown(interaction):
    await interaction.response.send_message("🔒 Lockdown starting...", ephemeral=True)
    count = 0
    for channel in interaction.guild.text_channels:
        try:
            ow = channel.overwrites_for(interaction.guild.default_role)
            ow.send_messages = False
            await channel.set_permissions(interaction.guild.default_role, overwrite=ow, reason="AKYVAN lockdown")
            count += 1
        except Exception:
            pass
    await interaction.followup.send(f"🔒 Locked **{count}** text channels.", ephemeral=True)

@bot.tree.command(name="unlock", description="Remove AKYVAN lockdown")
@app_commands.guild_only()
@admin()
async def unlock(interaction):
    await interaction.response.send_message("🔓 Unlocking...", ephemeral=True)
    count = 0
    for channel in interaction.guild.text_channels:
        try:
            ow = channel.overwrites_for(interaction.guild.default_role)
            ow.send_messages = None
            await channel.set_permissions(interaction.guild.default_role, overwrite=ow, reason="AKYVAN unlock")
            count += 1
        except Exception:
            pass
    await interaction.followup.send(f"🔓 Updated **{count}** text channels.", ephemeral=True)

@bot.tree.error
async def command_error(interaction, error):
    if isinstance(error, app_commands.errors.MissingPermissions):
        msg = "❌ Administrator permission required."
    else:
        print("Command error:", error)
        msg = "❌ Command failed. Check the bot console."
    if interaction.response.is_done():
        await interaction.followup.send(msg, ephemeral=True)
    else:
        await interaction.response.send_message(msg, ephemeral=True)

bot.run(TOKEN)
