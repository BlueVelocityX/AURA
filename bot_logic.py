# bot_logic.py
# Core logic, commands, and events for Aura (The Caretaker).

import os
import json
from datetime import datetime, timedelta
from discord.ext import commands, tasks
import discord
import asyncio
import time 
import collections 
import aiohttp # For making external API calls (Gemini)

# --- CONFIGURATION & SETUP ---

# Fetches the bot token from the environment variable (DISCORD_BOT_TOKEN)
TOKEN = os.environ.get('DISCORD_BOT_TOKEN')
COMMAND_PREFIX = '!'
API_KEY = "" # Leave as-is for canvas environment to provide key

# Filepaths
MOD_LOGS_FILE = 'permanent_record.json'
METRICS_FILE = 'operational_metrics.json'

# Role Names (ADJUST THESE TO MATCH YOUR SERVER'S ROLES)
# Note: Verification is removed, so 'Regular' is the primary role.
MEMBER_ROLE_NAME = 'Regular' # Your primary member role
MUTED_ROLE_NAME = 'Time-Out' # Your mute role
STAFF_ROLE_NAME = 'Co-Host' # Role that should have access to mod commands/flags

# Channel IDs (PLACEHOLDERS - MUST BE UPDATED TO YOUR SERVER'S IDs)
MOD_ALERT_CHANNEL_ID = 123456789012345678 # Your alert channel (where !flag goes)
WELCOME_CHANNEL_ID = 123456789012345679 # Channel where the welcome message is sent

# Gemini API Endpoint
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-05-20:generateContent"

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

# Initialize the bot client (Aura, The Caretaker)
bot = commands.Bot(command_prefix=COMMAND_PREFIX, intents=intents)

# --- HELPER FUNCTIONS ---

def get_active_chatters():
    return ACTIVE_CHATTERS

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
        'members_joined': [],
        'members_left': [],
        'messages_by_channel': {}, 
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

# --- METRICS & DATA MANAGEMENT FUNCTIONS ---

def update_log_and_metrics(action, target_id, moderator_id, reason, guild_members=None):
    """Saves a log entry (The Chalkboard) and updates metrics."""
    timestamp = datetime.now().isoformat()
    
    log_entry = {
        'timestamp': timestamp,
        'action': action,
        'target_id': str(target_id),
        'moderator_id': str(moderator_id),
        'reason': reason,
    }
    
    MOD_LOGS['logs'].insert(0, log_entry) 
    save_json(MOD_LOGS_FILE, MOD_LOGS)
    
    # Update monthly metrics
    if action in ['MUTE', 'BAN', 'KICK']:
        update_monthly_metric(f'total_{action.lower()}s')
    
    if guild_members:
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
    
    SERVER_METRICS['messages_by_channel'] = {str(k): v for k, v in CHANNEL_ACTIVITY.items()}
    
    save_json(METRICS_FILE, SERVER_METRICS)


# --- DISCORD EVENTS ---

@bot.event
async def on_ready():
    """Confirms the bot is connected and starts the metric saver loop."""
    print('---------------------------------')
    print(f'Aura (The Caretaker) is ONLINE. Logged in as: {bot.user.name}')
    print('---------------------------------')
    
    if not metric_saver_loop.is_running():
        metric_saver_loop.start()


@bot.event
async def on_member_join(member):
    """
    Handles ban evasion check and sends a warm welcome message.
    """
    # 1. Ban Evasion Check
    is_banned = any(log['target_id'] == str(member.id) and log['action'] == 'BAN' for log in MOD_LOGS['logs'])
    
    if is_banned:
        try:
            await member.ban(reason="Auto-Barring Protocol: Detected prior BAN record in Guestbook.")
            mod_channel = bot.get_channel(MOD_ALERT_CHANNEL_ID)
            if mod_channel:
                await mod_channel.send(f"🚫 **AUTO-BARRED:** Someone with a permanent record tried to enter: **{member.display_name}** (`{member.id}`). They were instantly barred.", embed=None)
            return

        except Exception as e:
            print(f"ERROR: Failed to auto-ban {member.id}. {e}")

    # 2. Welcome Message
    welcome_channel = bot.get_channel(WELCOME_CHANNEL_ID)
    if welcome_channel:
        try:
            await welcome_channel.send(
                f"🏡 **Welcome to the Hangout, {member.mention}!** I'm Aura, here to keep things cozy. "
                f"The **[Host]** (that's the owner!) will give you the **[Regular]** role soon. "
                "While you wait, check out **#house-rules**!"
            )
        except Exception as e:
            print(f"ERROR: Could not send welcome message: {e}")

    # 3. Metric Logging
    SERVER_METRICS['members_joined'].append(datetime.now().isoformat())
    save_json(METRICS_FILE, SERVER_METRICS)


@bot.event
async def on_member_remove(member):
    """
    Logs the leave event for metrics.
    """
    SERVER_METRICS['members_left'].append(datetime.now().isoformat())
    save_json(METRICS_FILE, SERVER_METRICS)


@bot.event
async def on_message(message):
    """Handles content filtering and metric tracking."""
    
    if message.author.bot or not message.content:
        return

    # --- METRIC TRACKING ---
    user_id = str(message.author.id)
    if user_id not in ACTIVE_CHATTERS:
        ACTIVE_CHATTERS.add(user_id)
        
    CHANNEL_ACTIVITY[message.channel.id] += 1

    # --- CONTENT FILTERING (Keeping the Space Clean) ---
    
    # 1. Spam Link Filter (still important even for private servers)
    suspicious_links = ['bit.ly', 'tinyurl.com', '.xyz', '.cc', 'discord.gg']
    if any(link in message.content.lower() for link in suspicious_links) and not message.author.guild_permissions.manage_messages:
        try:
            await message.delete()
            notice_message = await message.channel.send(
                f"**Aura:** {message.author.mention}, that link looks spammy. Removed to keep the space secure."
            )
            await asyncio.sleep(5)
            await notice_message.delete()
            return
        except discord.errors.Forbidden:
            pass # Cannot delete message

    # Process commands after all filters
    await bot.process_commands(message)


# --- INTERACTIVE AND FUN COMMANDS ---

@bot.command(name='vibe', help='[FUN] Aura suggests a vibe, song, or thought based on a topic. Usage: !vibe cozy corner')
async def vibe_command(ctx, *, topic: str):
    """
    Uses the Gemini API to generate a fun, themed, and short response.
    """
    await ctx.send("💫 **Aura is tuning in...** (Please wait, this may take a moment)")
    
    try:
        # 1. Construct the System Prompt
        system_prompt = (
            "You are Aura, a friendly and ambient AI caretaker for a private, cozy, treehouse-themed Discord "
            "server. Your responses should be short (1-3 sentences max), warm, and highly relevant to the user's topic. "
            "Use natural language, casual tone, and themed imagery (trees, warmth, hanging out, juice boxes, gentle light)."
        )
        
        # 2. Construct the User Query
        user_query = f"The user asked for a 'vibe' for the following topic: '{topic}'. Give a friendly, short response about what that vibe feels like or suggests."
        
        # 3. API Payload
        payload = {
            "contents": [{"parts": [{"text": user_query}]}],
            "systemInstruction": {"parts": [{"text": system_prompt}]}
        }
        
        # 4. Exponential Backoff logic for reliable API calls
        max_retries = 3
        delay = 1
        
        for i in range(max_retries):
            async with aiohttp.ClientSession() as session:
                async with session.post(f"{GEMINI_API_URL}?key={API_KEY}", json=payload) as response:
                    if response.status == 200:
                        data = await response.json()
                        text = data.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text', 'Error: No response text found.')
                        
                        # 5. Send the result
                        await ctx.send(f"🌳 **Aura's Vibe Check:** {text}")
                        return
                    
                    elif response.status == 429 and i < max_retries - 1:
                        await asyncio.sleep(delay)
                        delay *= 2
                        continue # Retry
                    
                    else:
                        error_text = await response.text()
                        await ctx.send(f"❌ **Aura Error:** Could not connect to the Vibe stream. Status: {response.status}. Error: {error_text[:100]}...")
                        return
        
        await ctx.send("❌ **Aura Error:** The Vibe stream failed to connect after multiple retries.")
        
    except Exception as e:
        await ctx.send(f"❌ **Aura Internal Error:** Something went wrong in the Vibe system: {e}")

# --- STAFF AND MODERATION COMMANDS ---

def is_moderator(ctx):
    """Check if the user has Co-Host permissions (manage_messages)."""
    return ctx.author.guild_permissions.manage_messages

@bot.command(name='commands', help='[CO-HOST] Displays available Caretaker commands.')
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
        title="🛠️ Aura: Caretaker Command Console",
        description="Authorized **[Co-Host]** tools:",
        color=discord.Color.brand_green()
    )
    
    embed.add_field(name="HOUSEKEEPING & SECURITY", value="\n".join(command_list), inline=False)
    embed.set_footer(text=f"Aura Protocol | Prefix: {COMMAND_PREFIX}")
    
    await ctx.send(embed=embed)


@bot.command(name='say', help='[CO-HOST] Aura broadcasts a message to a channel. Usage: !say #channel Your message here')
@commands.check(is_moderator)
async def say_command(ctx, channel: discord.TextChannel, *, message):
    try:
        await ctx.message.delete()
        await channel.send(message)
        await ctx.author.send(f"✅ Aura Broadcast sent to **#{channel.name}**:\n>>> {message}", delete_after=5)
    except Exception as e:
        await ctx.author.send(f"❌ Aura Error: {e}", delete_after=10)


@bot.command(name='purge', help='[CO-HOST] Cleans up clutter (deletes messages). Usage: !purge 10')
@commands.check(is_moderator)
async def purge_command(ctx, count: int):
    if count < 1:
        await ctx.send("Please specify a number greater than 0 for cleanup.")
        return
        
    try:
        deleted = await ctx.channel.purge(limit=count + 1)
        notice = await ctx.send(f"🧹 Clutter Removed: Cleared **{len(deleted) - 1}** messages.", delete_after=5)
    except Exception as e:
        await ctx.send(f"❌ Aura Error during cleanup: {e}")


@bot.command(name='kick', help='[CO-HOST] Sends a guest outside (Temporary Time-Out). Usage: !kick @Guest reason')
@commands.check(is_moderator)
async def kick_command(ctx, member: discord.Member, *, reason="No reason provided"):
    try:
        await member.kick(reason=reason)
        update_log_and_metrics('KICK', member.id, ctx.author.id, reason, ctx.guild.members) 
        
        embed = discord.Embed(
            title="🛑 TEMPORARY TIME-OUT: KICK", 
            description=f"Guest {member.mention} was sent outside to cool down.", 
            color=discord.Color.orange()
        )
        embed.add_field(name="Reason/Breach", value=reason, inline=False)
        
        mod_channel = bot.get_channel(MOD_ALERT_CHANNEL_ID)
        if mod_channel: await mod_channel.send(embed=embed)
        await ctx.send(f"✅ Time-Out applied to {member.mention}.", delete_after=5)
        
    except Exception as e:
        await ctx.send(f"❌ Aura Error: {e}")


@bot.command(name='ban', help='[HOST] Bars a guest permanently (Permanent Barring). Usage: !ban @Guest reason')
@commands.check(is_moderator)
async def ban_command(ctx, member: discord.Member, *, reason="No reason provided"):
    # In a private server, only the Host (owner) should typically use this, but we use manage_messages check for simplicity
    try:
        await member.ban(reason=reason)
        update_log_and_metrics('BAN', member.id, ctx.author.id, reason, ctx.guild.members)

        embed = discord.Embed(
            title="⛔ PERMANENT BARRING", 
            description=f"Guest {member.mention} has been permanently barred from the hangout.", 
            color=discord.Color.red()
        )
        embed.add_field(name="Reason/Breach", value=reason, inline=False)

        mod_channel = bot.get_channel(MOD_ALERT_CHANNEL_ID)
        if mod_channel: await mod_channel.send(embed=embed)
        await ctx.send(f"✅ Permanently barred {member.mention}.", delete_after=5)

    except Exception as e:
        await ctx.send(f"❌ Aura Error: {e}")


@bot.command(name='mute', help='[CO-HOST] Applies chat restriction (Time-Out). Usage: !mute @Guest reason')
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
            title="🔇 CHAT TIME-OUT APPLIED", 
            description=f"Guest {member.mention}'s chat privileges have been suspended.", 
            color=discord.Color.dark_grey()
        )
        embed.add_field(name="Reason", value=reason, inline=False)

        mod_channel = bot.get_channel(MOD_ALERT_CHANNEL_ID)
        if mod_channel: await mod_channel.send(embed=embed)
        await ctx.send(f"✅ Chat Time-Out applied to {member.mention}.", delete_after=5)

    except Exception as e:
        await ctx.send(f"❌ Aura Error: {e}")


@bot.command(name='unmute', help='[CO-HOST] Removes chat restriction. Usage: !unmute @Guest')
@commands.check(is_moderator)
async def unmute_command(ctx, member: discord.Member):
    muted_role = discord.utils.get(ctx.guild.roles, name=MUTED_ROLE_NAME)
    
    if not muted_role:
        await ctx.send(f"❌ Error: The required role '{MUTED_ROLE_NAME}' does not exist.", delete_after=10)
        return
        
    try:
        await member.remove_roles(muted_role, reason="Time-Out lifted by Host/Co-Host.")
        await ctx.send(f"✅ Chat Time-Out lifted for {member.mention}.", delete_after=5)
        
    except Exception as e:
        await ctx.send(f"❌ Aura Error: {e}")


@bot.command(name='flag', help='[ALL] Discreetly flags a concern to the Host/Co-Host. Usage: !flag @Guest reason')
async def report_command(ctx, member: discord.Member, *, reason="No reason provided"):
    """Renamed from !report to !flag for softer tone."""
    try:
        update_log_and_metrics('FLAG', member.id, ctx.author.id, reason)
        
        mod_channel = bot.get_channel(MOD_ALERT_CHANNEL_ID)
        if mod_channel:
            embed = discord.Embed(
                title="⚠️ GUEST CONCERN FLAGGED",
                description=f"**Concern About:** {member.mention} (`{member.id}`)\n**Flagged By:** {ctx.author.mention} (`{ctx.author.id}`)\n**Channel:** {ctx.channel.mention}",
                color=discord.Color.yellow()
            )
            embed.add_field(name="Details", value=reason, inline=False)
            await mod_channel.send(embed=embed)

        await ctx.message.delete()
        await ctx.author.send("✅ Concern flagged privately to the Host/Co-Host. Thank you for keeping our space cozy.", delete_after=10)
        
    except Exception as e:
        await ctx.author.send(f"❌ Aura Error while flagging: {e}", delete_after=10)


@bot.command(name='whois', help='[CO-HOST] Checks a guest’s Sign-in History. Usage: !whois @Guest')
@commands.check(is_moderator)
async def whois_command(ctx, member: discord.Member):
    target_id = str(member.id)
    user_logs = [log for log in MOD_LOGS['logs'] if log['target_id'] == target_id]
    
    embed = discord.Embed(
        title=f"📝 Guestbook Entry: {member.display_name}",
        description=f"A check of their history in the Hangout.",
        color=discord.Color.green()
    )
    
    embed.add_field(name="Account Info", value=(
        f"**ID:** `{target_id}`\n"
        f"**First Visit:** {member.joined_at.strftime('%Y-%m-%d %H:%M')}\n"
        f"**Account Created:** {member.created_at.strftime('%Y-%m-%d %H:%M')}"
    ), inline=False)
    
    if user_logs:
        history_summary = ""
        # Only show MUTE, KICK, BAN for history
        clean_logs = [log for log in user_logs if log['action'] in ['MUTE', 'KICK', 'BAN']]
        
        if clean_logs:
            for log in clean_logs[:5]:
                dt_obj = datetime.fromisoformat(log['timestamp'].replace('Z', ''))
                time_str = dt_obj.strftime('%m/%d %H:%M')
                
                history_summary += f"**[{log['action']}** on {time_str}] Reason: {log['reason']}\n"
            
            embed.add_field(name=f"Sign-in History ({len(clean_logs)} Incidents)", value=history_summary, inline=False)
        else:
             embed.add_field(name="Sign-in History", value="Clean record. No recorded incidents.", inline=False)
        
    else:
        embed.add_field(name="Sign-in History", value="Clean record. No recorded incidents.", inline=False)
        
    await ctx.send(embed=embed)