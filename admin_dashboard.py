import os
import json
from datetime import datetime, timedelta
import time
from functools import wraps
from flask import Blueprint, request, render_template_string, jsonify
from flask_httpauth import HTTPBasicAuth
from werkzeug.security import generate_password_hash, check_password_hash
import discord
from bot_logic import MOD_LOGS_FILE, METRICS_FILE, bot, BOT_START_TIME, get_active_chatters 

# --- CONFIGURATION ---
admin_bp = Blueprint('admin', __name__)
auth = HTTPBasicAuth()

# Fetch credentials from environment variables (MANDATORY for security)
ADMIN_USER = os.environ.get('ADMIN_USER')
ADMIN_PASS_HASHED = generate_password_hash(os.environ.get('ADMIN_PASS')) if os.environ.get('ADMIN_PASS') else None

# --- AUTHENTICATION ---

@auth.verify_password
def verify_password(username, password):
    """Verifies the username and password against environment variables."""
    if ADMIN_USER and ADMIN_PASS_HASHED:
        if username == ADMIN_USER and check_password_hash(ADMIN_PASS_HASHED, password):
            return username
    return None

# --- UTILITY FUNCTIONS ---

def load_data(filepath, default_data):
    """Safely loads data from a JSON file."""
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading {filepath}: {e}")
    return default_data

def calculate_kpis(metrics):
    """Calculates key performance indicators for the dashboard."""
    # Note: Bot latency is complex to calculate accurately in this threaded environment, so we skip it.
    
    # Calculate Uptime
    uptime_seconds = time.time() - BOT_START_TIME
    uptime = str(timedelta(seconds=int(uptime_seconds)))
    
    # Calculate Unique Active Chatters
    unique_active_chatters = len(get_active_chatters())
    
    # Total members (Approximation since bot doesn't fetch on startup)
    total_members = sum(1 for guild in bot.guilds for member in guild.members) if bot.is_ready() else "N/A"
    
    # Monthly Summary
    monthly_summary = metrics.get('monthly_summary', {})
    
    # Top 3 Channels (Approximation based on last saved metrics)
    channel_messages = metrics.get('messages_by_channel', {})
    top_channels = sorted(
        [(cid, count) for cid, count in channel_messages.items()],
        key=lambda item: item[1],
        reverse=True
    )[:3]
    
    # Try to resolve channel names
    resolved_channels = []
    if bot.is_ready():
        for cid, count in top_channels:
            channel = bot.get_channel(int(cid))
            name = channel.name if channel else f"ID: {cid}"
            resolved_channels.append((name, count))
    else:
        resolved_channels = [(f"ID: {cid}", count) for cid, count in top_channels]


    kpis = {
        'uptime': uptime,
        'guild_count': len(bot.guilds) if bot.is_ready() else 0,
        'member_count': total_members,
        'unique_active_chatters': unique_active_chatters,
        'monthly_actions': f"Kick: {monthly_summary.get('total_kicks', 0)} | Mute: {monthly_summary.get('total_mutes', 0)} | Ban: {monthly_summary.get('total_bans', 0)}",
        'top_channels': resolved_channels
    }
    return kpis

# --- ROUTES ---

@admin_bp.route('/', methods=['GET', 'POST'])
@auth.login_required
def dashboard():
    """Main Caretaker Log Dashboard."""
    
    # Load data for dashboard display
    logs = load_data(MOD_LOGS_FILE, {'logs': []}).get('logs', [])
    metrics = load_data(METRICS_FILE, {})
    kpis = calculate_kpis(metrics)
    
    # Handle search functionality
    search_query = request.form.get('search_query', '')
    search_results = None
    
    if request.method == 'POST' and search_query:
        # Search for user ID or part of the reason/action
        search_results = [
            log for log in logs 
            if search_query.lower() in str(log.get('target_id', '')).lower() or
               search_query.lower() in log.get('reason', '').lower() or
               search_query.lower() in log.get('action', '').lower()
        ]

    # Render HTML template
    # --- HTML TEMPLATE START ---
    html_template = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Aura Caretaker Log</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <style>
            :root {{
                --bg-color: #1f2937; /* Dark slate */
                --card-bg: #374151; /* Slightly lighter card */
                --text-color: #f3f4f6; /* Light gray text */
                --accent-color: #10b981; /* Green accent */
                --danger-color: #ef4444; /* Red for bans */
                --warn-color: #f59e0b; /* Yellow for mutes */
                --primary-action: #3b82f6; /* Blue for primary actions */
            }}
            body {{
                font-family: 'Inter', sans-serif;
                background-color: var(--bg-color);
                color: var(--text-color);
            }}
            .card {{
                background-color: var(--card-bg);
                border-radius: 0.5rem;
                box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
            }}
            .text-accent {{ color: var(--accent-color); }}
            .bg-accent-light {{ background-color: #4ade80; }}
            .btn-search {{ background-color: var(--primary-action); }}
            .btn-search:hover {{ background-color: #2563eb; }}
            .action-BAN {{ color: var(--danger-color); font-weight: bold; }}
            .action-MUTE {{ color: var(--warn-color); font-weight: bold; }}
            .action-KICK {{ color: var(--accent-color); font-weight: bold; }}
            .action-FLAG {{ color: #a855f7; font-weight: bold; }}
        </style>
    </head>
    <body>
        <div class="max-w-7xl mx-auto p-4 sm:p-6 lg:p-8">
            <header class="mb-8">
                <h1 class="text-4xl font-extrabold text-white">🌳 Aura Caretaker Log</h1>
                <p class="text-gray-400 mt-1">Hangout operational metrics and Guestbook (Moderation Logs).</p>
            </header>

            <!-- KPI Cards -->
            <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
                <div class="card p-5">
                    <p class="text-sm font-medium text-gray-400">Uptime</p>
                    <p class="text-2xl font-bold mt-1 text-accent">{kpis['uptime']}</p>
                </div>
                <div class="card p-5">
                    <p class="text-sm font-medium text-gray-400">Total Guests</p>
                    <p class="text-2xl font-bold mt-1 text-accent">{kpis['member_count']}</p>
                </div>
                <div class="card p-5">
                    <p class="text-sm font-medium text-gray-400">Active Chatters (Current Session)</p>
                    <p class="text-2xl font-bold mt-1 text-accent">{kpis['unique_active_chatters']}</p>
                </div>
                <div class="card p-5">
                    <p class="text-sm font-medium text-gray-400">Monthly Time-Outs/Barrings</p>
                    <p class="text-lg font-bold mt-1 text-accent">{kpis['monthly_actions']}</p>
                </div>
            </div>

            <!-- Top Channels & Activity -->
            <div class="card p-6 mb-8">
                <h2 class="text-xl font-semibold mb-4 border-b border-gray-700 pb-2">Hangout Activity Summary</h2>
                <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div class="col-span-1">
                        <p class="text-sm font-medium text-gray-400">Top 3 Channels by Message Count (since last reset)</p>
                        <ul class="mt-2 space-y-1">
                            {''.join([f'<li class="text-sm"><span class="text-accent">#{name}:</span> {count} msgs</li>' for name, count in kpis['top_channels']])}
                        </ul>
                    </div>
                </div>
            </div>


            <!-- Guestbook (Logs) Search -->
            <div class="card p-6 mb-8">
                <h2 class="text-xl font-semibold mb-4 border-b border-gray-700 pb-2">Guestbook Search</h2>
                <form method="POST" action="/admin" class="flex space-x-4">
                    <input type="text" name="search_query" placeholder="Search by Guest ID, Action, or Reason" value="{search_query}" 
                           class="flex-grow p-2 rounded bg-gray-600 border border-gray-700 focus:ring-accent focus:border-accent" required>
                    <button type="submit" class="btn-search px-4 py-2 text-white font-medium rounded hover:shadow-md transition">Search</button>
                </form>

                {f"""
                <div class="mt-6">
                    <h3 class="text-lg font-medium mb-3 text-gray-300">Search Results: {len(search_results)} found for "{search_query}"</h3>
                    <div class="overflow-x-auto">
                        <table class="min-w-full divide-y divide-gray-700">
                            <thead class="bg-gray-700">
                                <tr>
                                    <th class="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">Time</th>
                                    <th class="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">Action</th>
                                    <th class="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">Guest ID</th>
                                    <th class="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">Moderator ID</th>
                                    <th class="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">Reason</th>
                                </tr>
                            </thead>
                            <tbody class="divide-y divide-gray-700">
                                {''.join([
                                    f"""
                                    <tr class="hover:bg-gray-600 transition">
                                        <td class="px-4 py-3 whitespace-nowrap text-sm">{log['timestamp'][:16].replace('T', ' ')}</td>
                                        <td class="px-4 py-3 whitespace-nowrap text-sm action-{log['action']}">{log['action']}</td>
                                        <td class="px-4 py-3 whitespace-nowrap text-sm font-mono">{log['target_id']}</td>
                                        <td class="px-4 py-3 whitespace-nowrap text-sm font-mono">{log['moderator_id']}</td>
                                        <td class="px-4 py-3 text-sm max-w-xs overflow-hidden text-ellipsis">{log['reason']}</td>
                                    </tr>
                                    """
                                    for log in search_results
                                ])}
                            </tbody>
                        </table>
                    </div>
                </div>
                """ if search_results is not None else ''}
            </div>

            <!-- Footer Link -->
            <footer class="text-center pt-8 text-gray-500 text-sm">
                Aura Caretaker Log | Dashboard Access secured by HTTP Basic Authentication.
            </footer>

        </div>
    </body>
    </html>
    """
    
    return render_template_string(html_template)

@admin_bp.route('/data/metrics')
@auth.login_required
def metrics_api():
    """API endpoint to get the latest metrics data (for future API calls)."""
    metrics = load_data(METRICS_FILE, {})
    return jsonify(metrics)