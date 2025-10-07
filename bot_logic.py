# bot_logic.py
# Core logic, commands, and events for AURA Operational AI.

import os
import json
from datetime import datetime, timedelta
from discord.ext import commands, tasks
import discord
import asyncio
import time 
import collections 

# --- CONFIGURATION & SETUP ---

# Fetches the bot token from the environment variable (DISCORD_BOT_TOKEN)
TOKEN = os.environ.get('DISCORD_BOT_TOKEN')
COMMAND_PREFIX = '!'

# Filepaths
MOD_LOGS_FILE = 'permanent_record.json'
METRICS_FILE = 'operational_metrics.json'

# Role Names (ADJUST THESE TO MATCH YOUR SERVER'S ROLES)
MEMBER_ROLE_NAME = 'Agent' # Your primary member role
MUTED_ROLE_NAME = 'Muted' # Your mute role

# Channel IDs (PLACEHOLDERS - MUST BE UPDATED TO YOUR SERVER'S IDs)
MOD_ALERT_CHANNEL_ID = 1424585869909819392 # Your #root-log or staff alert channel
VERIFICATION_CHANNEL_ID = 1424581183999574127 # The channel where reaction verification happens
VERIFICATION_EMOJI = '✅'

# In-Memory Metric Trackers
ACTIVE_CHATTERS = set()
CHANNEL_ACTIVITY = collections.defaultdict(int)

# Global data containers and start time
MOD_LOGS = {'logs': []}
SERVER_METRICS = {}
BOT_START_TIME = time.time()

# Intents are mandatory for modern discord bots
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.presences = True
intents.reactions = True

# Initialize the bot client (AURA Operational AI)
bot = commands.Bot(command_prefix=COMMAND_PREFIX, intents=intents)

# --- HELPER FUNCTIONS FOR WEB DASHBOARD ---

def get_active_chatters():
    return ACTIVE_CHATTERS

# --- JSON HELPER FUNCTIONS (UNCHANGED) ---

def load_json(filepath, default_data={}):
    """Loads JSON data from a file, initializing with default data if necessary."""
    if not os.path.exists(filepath):
        print(f"File not found: {filepath}. Initializing with default structure.")
        try:
            with open(filepath, 'w') as f:
                json.dump(default_data, f, indent=4)
            return default_data
        except Exception as e:
            print(f"ERROR: Could not create {filepath}. {e}")
            return default_data
    
    try:
        with open(filepath, 'r') as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        print(f"ERROR: Error decoding JSON from {filepath}: {e}. Returning default data.")
        return default_data
    except Exception as e:
        print(f"ERROR: Failed to read {filepath}. {e}")
        return default_data

def save_json(filepath, data):
    """Saves data to a JSON file."""
    try:
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        print(f"ERROR: Failed to save data to {filepath}: {e}")

def load_initial_data():
    """Loads both moderation logs and server metrics upon bot startup."""
    global MOD_LOGS
    global SERVER_METRICS

    # 1. Load/Initialize Permanent Record
    MOD_LOGS = load_json(MOD_LOGS_FILE, default_data={'logs': []})
    
    # 2. Load/Initialize Operational Metrics
    default_metrics = {
        'members_joined': [], # List of timestamps
        'members_left': [],   # List of timestamps
        'messages_by_channel': {}, # {channel_id: count, ...} - Last saved state
        'monthly_summary': {
            'total_mutes': 0,
            'total_bans': 0,
            'total_kicks': 0,
            'last_reset': str(datetime.now().date())
        }
    }
    SERVER_METRICS = load_json(METRICS_FILE, default_metrics)
    # Restore last known channel activity from file to memory
    for k, v in SERVER_METRICS.get('messages_by_channel', {}).items():
        CHANNEL_ACTIVITY[int(k)] = v

load_initial_data() 

# --- METRICS & DATA MANAGEMENT FUNCTIONS (UNCHANGED) ---

def update_log_and_metrics(action, target_id, moderator_id, reason, guild_members=None):
    """Saves a log entry to permanent_record.json and updates the monthly metrics count."""
    timestamp = datetime.now().isoformat()
    target_username = ""
    # In a full setup, you'd try to get the target's username here from the cache/API
    
    log_entry = {
        'timestamp': timestamp,
        'action': action,
        'target_id': str(target_id),
        'moderator_id': str(moderator_id),
        'reason': reason,
        'target_username': target_username # Placeholder for now
    }
    
    MOD_LOGS['logs'].insert(0, log_entry) 
    save_json(MOD_LOGS_FILE, MOD_LOGS)
    
    # Update monthly metrics
    update_monthly_metric(f'total_{action.lower()}s')
    
    if guild_members:
        # Log member counts on every major action for historical reference
        SERVER_METRICS['monthly_summary']['member_count_at_action'] = len(guild_members)
    save_json(METRICS_FILE, SERVER_METRICS)


def update_monthly_metric(key):
    """Increments a counter in the SERVER_METRICS monthly_summary and saves."""
    global SERVER_METRICS
    
    today = datetime.now().date()
    last_reset_str = SERVER_METRICS['monthly_summary'].get('last_reset', str(today))
    last_reset_date = datetime.fromisoformat(last_reset_str).date()
    
    # Simple monthly reset logic
    if today.month != last_reset_date.month:
        print("INFO: Monthly metric reset triggered.")
        SERVER_METRICS['monthly_summary'] = {
            'total_mutes': 0,
            'total_bans': 0,
            'total_kicks': 0,
            'last_reset': str(today)
        }

    if key in SERVER_METRICS['monthly_summary']:
        SERVER_METRICS['monthly_summary'][key] += 1
        save_json(METRICS_FILE, SERVER_METRICS)


@tasks.loop(minutes=1.0)
async def metric_saver_loop():
    """Background loop to periodically save in-memory metrics to disk."""
    global SERVER_METRICS
    
    # Convert in-memory channel activity back to a standard dictionary for JSON
    SERVER_METRICS['messages_by_channel'] = {str(k): v for k, v in CHANNEL_ACTIVITY.items()}
    
    save_json(METRICS_FILE, SERVER_METRICS)


# --- DISCORD EVENTS (ADAPTED FOR AURA) ---

@bot.event
async def on_ready():
    """Confirms the bot is connected and starts the metric saver loop."""
    print('---------------------------------')
    print(f'AURA Operational AI is ONLINE. Logged in as: {bot.user.name}')
    print('---------------------------------')
    
    if not metric_saver_loop.is_running():
        metric_saver_loop.start()


@bot.event
async def on_member_join(member):
    """
    Handles ban evasion check and logs the join event for metrics.
    """
    # --- BAN EVASION CHECK (Auto-Eviction Enforcement) ---
    is_banned = any(log['target_id'] == str(member.id) and log['action'] == 'BAN' for log in MOD_LOGS['logs'])
    
    if is_banned:
        try:
            # Re-ban the user and notify staff
            await member.ban(reason="Auto-Eviction Enforcement: Detected prior BAN record in Permanent Record.")
            mod_channel = bot.get_channel(MOD_ALERT_CHANNEL_ID)
            if mod_channel:
                embed = discord.Embed(
                    title="🚫 AUTO-EVICTION PROTOCOL INITIATED",
                    description=f"Agent **{member.display_name}** (`{member.id}`) attempted to infiltrate but was **INSTANTLY RE-BANNED**.",
                    color=discord.Color.red()
                )
                embed.add_field(name="Protocol Reason", value="Detected prior BAN in permanent record.", inline=False)
                await mod_channel.send(embed=embed)
            return

        except Exception as e:
            print(f"ERROR: Failed to auto-ban {member.id}. {e}")

    # --- METRIC LOGGING ---
    SERVER_METRICS['members_joined'].append(datetime.now().isoformat())
    save_json(METRICS_FILE, SERVER_METRICS)


@bot.event
async def on_member_remove(member):
    """
    Logs the leave event for metrics (Churn tracking).
    """
    # --- METRIC LOGGING ---
    SERVER_METRICS['members_left'].append(datetime.now().isoformat())
    save_json(METRICS_FILE, SERVER_METRICS)


@bot.event
async def on_raw_reaction_add(payload):
    """Handles the automatic role assignment for verification."""
    if payload.channel_id == VERIFICATION_CHANNEL_ID and str(payload.emoji) == VERIFICATION_EMOJI:
        guild = bot.get_guild(payload.guild_id)
        if not guild: return

        member = guild.get_member(payload.user_id)
        if not member or member.bot: return

        member_role = discord.utils.get(guild.roles, name=MEMBER_ROLE_NAME)
        if member_role and member_role not in member.roles:
            try:
                await member.add_roles(member_role, reason="Protocol Verification.")
                print(f"ACTION: Granted {MEMBER_ROLE_NAME} to {member.display_name} via reaction.")
                
            except Exception as e:
                print(f"ERROR: Could not grant role to {member.display_name}: {e}")


@bot.event
async def on_message(message):
    """Handles content filtering and metric tracking."""
    
    # Ignore bot messages and empty messages
    if message.author.bot or not message.content:
        return

    # --- METRIC TRACKING ---
    user_id = str(message.author.id)
    if user_id not in ACTIVE_CHATTERS:
        ACTIVE_CHATTERS.add(user_id)
        
    CHANNEL_ACTIVITY[message.channel.id] += 1

    # --- CONTENT FILTERING (System Protocol Enforcement) ---
    
    # 1. Spam Link Filter
    suspicious_links = ['bit.ly', 'tinyurl.com', '.xyz', '.cc', 'discord.gg']
    if any(link in message.content.lower() for link in suspicious_links) and not message.author.guild_permissions.manage_messages:
        try:
            await message.delete()
            
            # Send temporary removal notice
            notice_message = await message.channel.send(
                f"**AURA System Protocol:** {message.author.mention}, unauthorized links are filtered for system security."
            )
            await asyncio.sleep(5)
            await notice_message.delete()
            return
        except discord.errors.Forbidden:
            pass
            
    # 2. Keyword Filter 
    prohibited_keywords = ['promotional-phrase', 'shill-content-example']
    if any(keyword in message.content.lower() for keyword in prohibited_keywords) and not message.author.guild_permissions.manage_messages:
        try:
            await message.delete()
            notice_message = await message.channel.send(
                f"**AURA System Protocol:** {message.author.mention}, certain keywords violate command protocol. Message deleted."
            )
            await asyncio.sleep(5)
            await notice_message.delete()
            return
        except discord.errors.Forbidden:
            pass
    
    # Process commands after all filters
    await bot.process_commands(message)


# --- STAFF AND MODERATION COMMANDS (ADAPTED FOR AURA) ---

def is_moderator(ctx):
    """Check if the user has permission to manage messages."""
    return ctx.author.guild_permissions.manage_messages

@bot.command(name='commands', help='[STAFF] Displays available Protocol commands.')
@commands.check(is_moderator)
async def list_commands(ctx):
    """Dynamically lists all moderator commands in an embed."""
    command_list = []
    
    for command in bot.commands:
        if command.hidden or not command.help:
            continue
        
        if any(check.__name__ == 'is_moderator' for check in command.checks):
            command_list.append(f"**{COMMAND_PREFIX}{command.name}** {command.signature or ''}\n> *{command.help}*")

    embed = discord.Embed(
        title="🛠️ AURA: Protocol Command Terminal",
        description="Authorized staff commands:",
        color=discord.Color.blue() # Changed color to match mascot
    )
    
    embed.add_field(name="OPERATIONAL COMMANDS", value="\n".join(command_list), inline=False)
    embed.set_footer(text=f"AURA Protocol | Prefix: {COMMAND_PREFIX}")
    
    await ctx.send(embed=embed)


@bot.command(name='say', help='[ADMIN] AURA broadcasts a message to a channel. Usage: !say #channel Your message here')
@commands.check(is_moderator)
async def say_command(ctx, channel: discord.TextChannel, *, message):
    try:
        await ctx.message.delete()
        await channel.send(message)
        await ctx.author.send(f"✅ Protocol Message sent to **#{channel.name}**:\n>>> {message}", delete_after=5)
    except Exception as e:
        await ctx.author.send(f"❌ AURA Error: {e}", delete_after=10)


@bot.command(name='purge', help='[STAFF] Cleans the data stream (deletes messages). Usage: !purge 10')
@commands.check(is_moderator)
async def purge_command(ctx, count: int):
    if count < 1:
        await ctx.send("Protocol requires a number greater than 0.")
        return
        
    try:
        deleted = await ctx.channel.purge(limit=count + 1)
        notice = await ctx.send(f"🧹 Data Stream Cleaned: Deleted **{len(deleted) - 1}** messages.", delete_after=5)
    except Exception as e:
        await ctx.send(f"❌ AURA Error during purge: {e}")


@bot.command(name='kick', help='[STAFF] Kicks a member (Eviction Notice). Usage: !kick @Member reason')
@commands.check(is_moderator)
async def kick_command(ctx, member: discord.Member, *, reason="No reason provided"):
    try:
        await member.kick(reason=reason)
        # We need member list for metrics, so we pass it from guild
        update_log_and_metrics('KICK', member.id, ctx.author.id, reason, ctx.guild.members) 
        
        embed = discord.Embed(
            title="👢 EVICTION NOTICE: KICK", 
            description=f"Agent {member.mention} was forcefully removed from the station.", 
            color=discord.Color.orange()
        )
        embed.add_field(name="Reason/Breach", value=reason, inline=False)
        
        mod_channel = bot.get_channel(MOD_ALERT_CHANNEL_ID)
        if mod_channel: await mod_channel.send(embed=embed)
        await ctx.send(f"✅ Kicked {member.mention}.", delete_after=5)
        
    except Exception as e:
        await ctx.send(f"❌ AURA Error: {e}")


@bot.command(name='ban', help='[ADMIN] Bans a member permanently (Permanent Eviction). Usage: !ban @Member reason')
@commands.check(is_moderator)
async def ban_command(ctx, member: discord.Member, *, reason="No reason provided"):
    try:
        await member.ban(reason=reason)
        update_log_and_metrics('BAN', member.id, ctx.author.id, reason, ctx.guild.members)

        embed = discord.Embed(
            title="⛔ PERMANENT EVICTION NOTICE: BAN", 
            description=f"Agent {member.mention} has been permanently blacklisted from the network.", 
            color=discord.Color.red()
        )
        embed.add_field(name="Reason/Breach", value=reason, inline=False)

        mod_channel = bot.get_channel(MOD_ALERT_CHANNEL_ID)
        if mod_channel: await mod_channel.send(embed=embed)
        await ctx.send(f"✅ Banned {member.mention}. Auto-Eviction Protocol Active.", delete_after=5)

    except Exception as e:
        await ctx.send(f"❌ AURA Error: {e}")


@bot.command(name='mute', help='[STAFF] Applies Temporary Suspension. Usage: !mute @Member reason')
@commands.check(is_moderator)
async def mute_command(ctx, member: discord.Member, *, reason="No reason provided"):
    muted_role = discord.utils.get(ctx.guild.roles, name=MUTED_ROLE_NAME)
    
    if not muted_role:
        await ctx.send(f"❌ Error: The required role '{MUTED_ROLE_NAME}' does not exist.", delete_after=10)
        return
        
    try:
        await member.add_roles(muted_role, reason=reason)
        update_log_and_metrics('MUTE', member.id, ctx.author.id, reason, ctx.guild.members)
        
        embed = discord.Embed(
            title="🔇 TEMPORARY SUSPENSION: MUTE", 
            description=f"Agent {member.mention} data stream has been suspended.", 
            color=discord.Color.dark_grey()
        )
        embed.add_field(name="Reason", value=reason, inline=False)

        mod_channel = bot.get_channel(MOD_ALERT_CHANNEL_ID)
        if mod_channel: await mod_channel.send(embed=embed)
        await ctx.send(f"✅ Suspension applied to {member.mention}.", delete_after=5)

    except Exception as e:
        await ctx.send(f"❌ AURA Error: {e}")


@bot.command(name='unmute', help='[STAFF] Removes Temporary Suspension. Usage: !unmute @Member')
@commands.check(is_moderator)
async def unmute_command(ctx, member: discord.Member):
    muted_role = discord.utils.get(ctx.guild.roles, name=MUTED_ROLE_NAME)
    
    if not muted_role:
        await ctx.send(f"❌ Error: The required role '{MUTED_ROLE_NAME}' does not exist.", delete_after=10)
        return
        
    try:
        await member.remove_roles(muted_role, reason="Suspension lifted by moderator.")
        await ctx.send(f"✅ Suspension lifted for {member.mention}.", delete_after=5)
        
    except Exception as e:
        await ctx.send(f"❌ AURA Error: {e}")


@bot.command(name='report', help='[ALL] Discreetly submits a violation report. Usage: !report @Member reason')
async def report_command(ctx, member: discord.Member, *, reason="No reason provided"):
    try:
        update_log_and_metrics('REPORT', member.id, ctx.author.id, reason)
        
        mod_channel = bot.get_channel(MOD_ALERT_CHANNEL_ID)
        if mod_channel:
            embed = discord.Embed(
                title="🚨 VIOLATION REPORT SUBMITTED",
                description=f"**Reported Agent:** {member.mention} (`{member.id}`)\n**Reported By:** {ctx.author.mention} (`{ctx.author.id}`)\n**Channel:** {ctx.channel.mention}",
                color=discord.Color.light_grey()
            )
            embed.add_field(name="Details", value=reason, inline=False)
            await mod_channel.send(embed=embed)

        await ctx.message.delete()
        await ctx.author.send("✅ Report submitted to Root Access discreetly. Thank you.", delete_after=10)
        
    except Exception as e:
        await ctx.author.send(f"❌ AURA Error while reporting: {e}", delete_after=10)


@bot.command(name='whois', help='[STAFF] Performs a Background Check and displays disciplinary history. Usage: !whois @Member')
@commands.check(is_moderator)
async def whois_command(ctx, member: discord.Member):
    target_id = str(member.id)
    user_logs = [log for log in MOD_LOGS['logs'] if log['target_id'] == target_id]
    
    embed = discord.Embed(
        title=f"👤 Background Check: Agent {member.display_name}",
        description=f"System Profile and Permanent Record Scan.",
        color=discord.Color.blue()
    )
    
    embed.add_field(name="Account Info", value=(
        f"**ID:** `{target_id}`\n"
        f"**Joined Station:** {member.joined_at.strftime('%Y-%m-%d %H:%M')}\n"
        f"**Created Account:** {member.created_at.strftime('%Y-%m-%d %H:%M')}"
    ), inline=False)
    
    if user_logs:
        history_summary = ""
        for log in user_logs[:5]:
            dt_obj = datetime.fromisoformat(log['timestamp'].replace('Z', '')) # Handles timezone format
            time_str = dt_obj.strftime('%m/%d %H:%M')
            
            history_summary += f"**[{log['action']}** on {time_str}] Reason: {log['reason']}\n"
            
        embed.add_field(name=f"Permanent Record History ({len(user_logs)} Total)", value=history_summary, inline=False)
    else:
        embed.add_field(name="Permanent Record History", value="Clean profile. No infractions found.", inline=False)
        
    await ctx.send(embed=embed)


@bot.command(name='verify', help='[ALL] Manually activates system access (grants Member role).')
async def verify_command(ctx):
    member_role = discord.utils.get(ctx.guild.roles, name=MEMBER_ROLE_NAME)
    
    if not member_role:
        await ctx.send(f"❌ AURA Error: The required role '{MEMBER_ROLE_NAME}' does not exist.", delete_after=10)
        return
        
    if member_role in ctx.author.roles:
        await ctx.send("✅ System Access already granted.", delete_after=5)
    else:
        try:
            await ctx.author.add_roles(member_role, reason="Manual verification command.")
            await ctx.send("✅ Access granted. Welcome to the Command Structure.", delete_after=5)
        except Exception as e:
            await ctx.send(f"❌ AURA Error adding role: {e}", delete_after=10)
