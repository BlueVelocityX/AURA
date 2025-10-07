import os
import json
from datetime import datetime, timedelta
import time
from flask import Blueprint, request, render_template_string, jsonify
from flask_httpauth import HTTPBasicAuth
from werkzeug.security import generate_password_hash, check_password_hash
from bot_logic import MOD_LOGS_FILE, METRICS_FILE, bot, BOT_START_TIME, get_active_chatters 

# --- CONFIGURATION ---
admin_bp = Blueprint('admin', __name__)
auth = HTTPBasicAuth()

# Fetch credentials from environment variables (MANDATORY for security)
ADMIN_USER = os.environ.get('ADMIN_USER')
# NOTE: ADMIN_PASS environment variable should be set, the hashing is handled below on startup
ADMIN_PASS_HASHED = generate_password_hash(os.environ.get('ADMIN_PASS')) if os.environ.get('ADMIN_PASS') else None

# --- AUTHENTICATION ---

@auth.verify_password
def verify_password(username, password):
    """Verifies the username and password against environment variables."""
    # Ensure both credentials are set in the environment
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
    """Calculates key performance indicators (KPIs) from the server metrics."""
    
    # 1. Net Member Change (Last 30 Days)
    now = datetime.now()
    cutoff_date = now - timedelta(days=30)
    
    members_joined = metrics.get('members_joined', [])
    members_left = metrics.get('members_left', [])
    messages_by_channel = metrics.get('messages_by_channel', {})

    joined_30d = sum(1 for timestamp in members_joined if datetime.fromisoformat(timestamp) > cutoff_date)
    left_30d = sum(1 for timestamp in members_left if datetime.fromisoformat(timestamp) > cutoff_date)
    
    net_change = joined_30d - left_30d

    # 2. Churn Rate (7-Day)
    cutoff_date_7d = now - timedelta(days=7)
    joined_7d = sum(1 for timestamp in members_joined if datetime.fromisoformat(timestamp) > cutoff_date_7d)
    left_7d = sum(1 for timestamp in members_left if datetime.fromisoformat(timestamp) > cutoff_date_7d)
    
    # Avoid division by zero
    churn_rate = (left_7d / joined_7d * 100) if joined_7d > 0 else 0.0

    # 3. Top 5 Active Channels
    channel_list = []
    for channel_id, count in messages_by_channel.items():
        channel_name = f"ID:{channel_id}"
        # Attempt to get channel name (requires bot to be ready)
        if bot.is_ready() and bot.get_channel(int(channel_id)):
            channel_name = bot.get_channel(int(channel_id)).name
        
        channel_list.append({'name': channel_name, 'count': count})
    
    top_channels = sorted(channel_list, key=lambda x: x['count'], reverse=True)[:5]


    return {
        'net_change': net_change,
        'joined_30d': joined_30d,
        'left_30d': left_30d,
        'churn_rate_7d': f"{churn_rate:.1f}%",
        'top_channels': top_channels
    }

def format_timedelta(seconds):
    """Formats seconds into human-readable Uptime string."""
    seconds = int(seconds)
    days = seconds // (24 * 3600)
    seconds %= (24 * 3600)
    hours = seconds // 3600
    seconds %= 3600
    minutes = seconds // 60
    seconds %= 60
    
    parts = []
    if days > 0: parts.append(f"{days}d")
    if hours > 0: parts.append(f"{hours}h")
    if minutes > 0: parts.append(f"{minutes}m")
    parts.append(f"{seconds}s")
    
    return " ".join(parts)

# --- ROUTES (ADAPTED FOR AURA) ---

@admin_bp.route('/', methods=['GET', 'POST'])
@auth.login_required
def dashboard():
    """Main administrative dashboard view."""
    
    # 1. Load Data
    mod_logs = load_data(MOD_LOGS_FILE, {'logs': []})
    server_metrics = load_data(METRICS_FILE, {})
    
    # 2. Bot Health Checks
    uptime_seconds = time.time() - BOT_START_TIME
    uptime_str = format_timedelta(uptime_seconds)
    bot_ready = bot.is_ready()
    
    # 3. Process Moderation Search (POST request)
    search_results = None
    search_query = None
    if request.method == 'POST':
        search_query = request.form.get('user_id_search', '').strip()
        if search_query:
            search_results = [
                log for log in mod_logs.get('logs', []) 
                if search_query.lower() in log.get('target_username', '').lower() 
                or search_query == str(log.get('target_id'))
            ]

    # 4. Calculate KPIs
    kpis = calculate_kpis(server_metrics)

    # 5. Get Live Data
    # Note: get_active_chatters returns the size of the set now.
    active_chatters_count = len(get_active_chatters()) 
    
    # 6. Prepare Template Data
    
    # Simple list of log entries for display (last 10)
    recent_logs = mod_logs.get('logs', [])[:10] # Top 10 entries (reverse chronological)

    # --- HTML Template (Themed Blue/Sci-Fi) ---
    
    CSS_VARS = """
    :root {
        --bg-color: #0d1117; /* Dark Sci-fi background */
        --card-bg: #161b22;
        --text-color: #e6edf3;
        --primary-action: #58a6ff; /* Blue for primary actions/titles */
        --danger-color: #f85149; /* Red for evictions/bans */
        --border-color: #30363d;
    }
    body {
        font-family: 'Inter', sans-serif;
        background-color: var(--bg-color);
        color: var(--text-color);
    }
    .card {
        background-color: var(--card-bg);
        border: 1px solid var(--border-color);
    }
    .text-aura-blue { color: var(--primary-action); }
    .bg-aura-blue { background-color: var(--primary-action); }
    .btn-primary {
        background-color: var(--primary-action);
        color: #ffffff;
        transition: background-color 0.15s;
    }
    .btn-primary:hover {
        background-color: #4b88cc; 
    }

    /* Scrolling Marquee CSS */
    .marquee-container-header {
        overflow: hidden;
        white-space: nowrap;
        width: 100%;
        margin-bottom: 0.5rem;
        padding-bottom: 0.25rem;
    }
    .marquee-text-header {
        display: inline-block;
        padding-left: 100%;
        animation: marquee 20s linear infinite;
        font-size: 1.25rem;
        font-weight: 700;
        color: #374151; /* Subtle contrast */
    }
    @keyframes marquee {
        0%   { transform: translate(0, 0); }
        100% { transform: translate(-100%, 0); }
    }
    """

    # Format recent logs for HTML table
    log_rows = ""
    for log in recent_logs:
        action_class = 'bg-red-800 text-red-300' if log.get('action') in ['BAN', 'KICK'] else 'bg-gray-700 text-gray-300'
        
        # Ensure 'moderator' key is handled if not always present
        moderator_display = bot.get_user(int(log.get('moderator_id'))) if bot.is_ready() and log.get('moderator_id') else 'System'
        moderator_name = moderator_display.name if isinstance(moderator_display, discord.User) else moderator_display

        log_rows += f"""
        <tr class="border-b border-gray-700 hover:bg-gray-700/50">
            <td class="px-4 py-2 text-xs text-gray-400">{log.get('timestamp', 'N/A').split('.')[0].replace('T', ' ')}</td>
            <td class="px-4 py-2 font-medium">
                <span class="px-2 py-0.5 rounded-full text-xs font-semibold {action_class}">
                    {log.get('action', 'N/A')}
                </span>
            </td>
            <td class="px-4 py-2 font-mono text-xs">{log.get('target_username', 'N/A')} ({log.get('target_id', 'N/A')})</td>
            <td class="px-4 py-2 text-sm text-gray-400 max-w-xs truncate">{log.get('reason', 'No reason provided')}</td>
        </tr>
        """
        
    # Format search results
    search_rows = ""
    if search_results is not None:
        if search_results:
            for log in search_results:
                action_class = 'bg-red-800 text-red-300' if log.get('action') in ['BAN', 'KICK'] else 'bg-gray-700 text-gray-300'

                moderator_display = bot.get_user(int(log.get('moderator_id'))) if bot.is_ready() and log.get('moderator_id') else 'System'
                moderator_name = moderator_display.name if isinstance(moderator_display, discord.User) else moderator_display

                search_rows += f"""
                <tr class="border-b border-gray-700 hover:bg-gray-700/50">
                    <td class="px-4 py-3 text-xs text-gray-400">{log.get('timestamp', 'N/A').split('.')[0].replace('T', ' ')}</td>
                    <td class="px-4 py-3 font-medium">
                        <span class="px-2 py-0.5 rounded-full text-xs font-semibold {action_class}">
                            {log.get('action', 'N/A')}
                        </span>
                    </td>
                    <td class="px-4 py-3 font-mono text-xs">{moderator_name}</td>
                    <td class="px-4 py-3 text-sm text-gray-400">{log.get('reason', 'No reason provided')}</td>
                </tr>
                """
        else:
            search_rows = f"""
            <tr><td colspan="4" class="py-4 text-center text-gray-400">No disciplinary records found for '{search_query}'.</td></tr>
            """


    html_template = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>AURA Operational Hub - Root Access</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;900&display=swap');
            {CSS_VARS}
        </style>
    </head>
    <body class="p-4 md:p-8">
        <div class="max-w-7xl mx-auto space-y-8">
            
            <div class="marquee-container-header">
                <div class="marquee-text-header">ROOT ACCESS TERMINAL | AURA OPERATIONAL HUB | PERMANENT RECORD |</div>
            </div>

            <header class="flex flex-col md:flex-row justify-between items-center pb-4 border-b border-aura-blue">
                <h1 class="text-3xl font-extrabold text-aura-blue">
                    AURA Operational Hub
                </h1>
                <p class="text-sm text-gray-400 mt-2 md:mt-0">
                    Secure Dashboard for Command Staff.
                </p>
            </header>
            
            <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
                <div class="card p-5 rounded-lg shadow-lg space-y-2">
                    <h2 class="text-sm font-semibold text-gray-400">System Health</h2>
                    <p class="text-2xl font-bold">
                        <span class="{ 'text-green-500' if bot_ready else 'text-danger-color' }">
                            { 'OPERATIONAL' if bot_ready else 'OFFLINE' }
                        </span>
                    </p>
                    <p class="text-xs text-gray-500">Uptime: {uptime_str}</p>
                </div>

                <div class="card p-5 rounded-lg shadow-lg space-y-2">
                    <h2 class="text-sm font-semibold text-gray-400">Net Agent Change (30D)</h2>
                    <p class="text-2xl font-bold { 'text-green-500' if kpis['net_change'] >= 0 else 'text-danger-color' }">
                        { '+' if kpis['net_change'] >= 0 else '' }{kpis['net_change']}
                    </p>
                    <p class="text-xs text-gray-500">Joined: {kpis['joined_30d']} / Left: {kpis['left_30d']}</p>
                </div>

                <div class="card p-5 rounded-lg shadow-lg space-y-2">
                    <h2 class="text-sm font-semibold text-gray-400">7-Day Churn Rate</h2>
                    <p class="text-2xl font-bold text-danger-color">
                        {kpis['churn_rate_7d']}
                    </p>
                    <p class="text-xs text-gray-500">Protocol Target: < 5%</p>
                </div>
                
                <div class="card p-5 rounded-lg shadow-lg space-y-2">
                    <h2 class="text-sm font-semibold text-gray-400">Active Data Streams</h2>
                    <p class="text-2xl font-bold text-aura-blue">
                        {active_chatters_count}
                    </p>
                    <p class="text-xs text-gray-500">Agents chatting in the last 5 min.</p>
                </div>
            </div>

            <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
                <div class="card p-6 rounded-lg shadow-lg lg:col-span-1">
                    <h2 class="text-xl font-bold mb-4 border-b pb-2 border-gray-700 text-white">Top 5 Operational Channels</h2>
                    <ul class="space-y-3">
                        {''.join(f"""
                        <li class="flex justify-between items-center text-sm">
                            <span class="text-gray-300 font-medium">#{channel['name']}</span>
                            <span class="text-white bg-aura-blue px-2 py-0.5 rounded-full text-xs">
                                {channel['count']}
                            </span>
                        </li>
                        """ for channel in kpis['top_channels'])}
                        {'' if kpis['top_channels'] else '<li class="text-gray-500 text-sm">No message data available yet.</li>'}
                    </ul>
                </div>
                
                <div class="card p-6 rounded-lg shadow-lg lg:col-span-2">
                    <h2 class="text-xl font-bold mb-4 border-b pb-2 border-gray-700 text-danger-color">Recent Permanent Record Entries (Last 10)</h2>
                    <div class="overflow-x-auto">
                        <table class="min-w-full divide-y divide-gray-700">
                            <thead>
                                <tr>
                                    <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Time</th>
                                    <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Action</th>
                                    <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Target User</th>
                                    <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Reason</th>
                                </tr>
                            </thead>
                            <tbody class="divide-y divide-gray-800">
                                {log_rows if recent_logs else '<tr><td colspan="4" class="py-4 text-center text-gray-400">No recent entries in the permanent record.</td></tr>'}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>

            <div class="card p-6 rounded-lg shadow-lg space-y-4">
                <h2 class="text-xl font-bold border-b pb-2 border-gray-700 text-aura-blue">Background Check: Agent Lookup</h2>
                <form method="POST" action="{request.path}" class="flex flex-col sm:flex-row gap-4">
                    <input type="text" name="user_id_search" placeholder="Enter Agent ID or Username (e.g., 12345... or Sentinel)" 
                           value="{search_query if search_query else ''}"
                           class="flex-grow p-3 rounded-lg bg-gray-700 border border-gray-600 focus:ring-aura-blue focus:border-aura-blue text-white placeholder-gray-400" required>
                    <button type="submit" class="btn-primary px-6 py-3 rounded-lg font-bold text-sm shadow-md">
                        Search Permanent Record
                    </button>
                </form>

                {f"""
                <div class="mt-6">
                    <h3 class="text-lg font-semibold mb-3 text-white">Search Results for '{search_query}':</h3>
                    <div class="overflow-x-auto">
                        <table class="min-w-full divide-y divide-gray-700">
                            <thead>
                                <tr>
                                    <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Time</th>
                                    <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Action</th>
                                    <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Moderator</th>
                                    <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Reason</th>
                                </tr>
                            </thead>
                            <tbody class="divide-y divide-gray-800">
                                {search_rows}
                            </tbody>
                        </table>
                    </div>
                </div>
                """ if search_results is not None else ''}
            </div>

            <footer class="text-center pt-8 text-gray-500 text-sm">
                AURA Operational Hub v1.0 | Root Access Secured.
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