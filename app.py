import os
import asyncio # Needed for safe threading
from flask import Flask, render_template_string
import threading
from bot_logic import bot 
from admin_dashboard import admin_bp 

app = Flask(__name__)

# Register the admin blueprint and protect it behind the /admin URL prefix.
app.register_blueprint(admin_bp, url_prefix='/admin')

# --- START BOT IN A SEPARate THREAD (For 24/7 Hosting on Render) ---

def start_discord_bot():
    """
    Function to run the Discord bot's blocking client method safely in a thread.
    """
    print("--- AURA Operational AI: Starting Discord Bot Thread -----")
    try:
        # 1. Create a new event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # 2. Use bot.start() to run the bot and run_until_complete to block the thread
        loop.run_until_complete(bot.start(os.getenv('DISCORD_BOT_TOKEN'), reconnect=True))

    except Exception as e:
        print(f"FATAL ERROR IN DISCORD BOT THREAD: {e}")

print("--- Gunicorn Worker Booted, Initiating AURA Startup ---")
discord_thread = threading.Thread(target=start_discord_bot)
# Make the thread a daemon so it doesn't prevent the web server from closing when Gunicorn shuts down
discord_thread.daemon = True 
discord_thread.start()


# --- FLASK WEB SERVER (AURA Status Landing Page) ---

@app.route('/')
def home():
    """
    The member-facing landing page for the AURA system status.
    """
    
    # NOTE: Update this link to your actual server invite.
    DISCORD_INVITE_LINK = "https://discord.gg/YOURINVITELINK" 
    
    is_online = bot.is_ready()
    status_text = "Operational" if is_online else "Standby Mode"
    status_color = "bg-green-500" if is_online else "bg-yellow-500"
    
    # Placeholder links for community platforms. Update these!
    AURA_LINKS = [
        {"name": "Command Center Website", "url": "https://yourwebsite.com"},
        {"name": "External Platform Alpha", "url": "https://external.com/alpha"},
        {"name": "External Platform Beta", "url": "https://external.com/beta"},
    ]
    
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>AURA Operational AI - Status</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;900&display=swap');
            
            /* Sci-Fi Blue Theme */
            :root {{
                --bg-color: #0d1117;
                --card-bg: #161b22;
                --primary-action: #58a6ff;
                --text-color: #e6edf3;
            }}
            
            body {{ 
                font-family: 'Inter', sans-serif; 
                background-color: var(--bg-color); 
            }}
            
            .btn-primary {{
                background-color: var(--primary-action);
                color: #ffffff;
            }}
            .btn-primary:hover {{
                background-color: #4b88cc;
            }}

            /* Scrolling Marquee CSS */
            .marquee-container {{
                overflow: hidden;
                white-space: nowrap;
                width: 100%;
                margin-bottom: 1rem;
                border-bottom: 2px solid #2d2d2d;
                padding-bottom: 0.5rem;
            }}
            .marquee-text {{
                display: inline-block;
                padding-left: 100%;
                animation: marquee 20s linear infinite;
                font-size: 1.5rem;
                font-weight: 700;
                color: #374151; 
            }}
            @keyframes marquee {{
                0%   {{ transform: translate(0, 0); }}
                100% {{ transform: translate(-100%, 0); }}
            }}
        </style>
    </head>
    <body class="min-h-screen flex items-center justify-center p-4">
        <div class="max-w-xl w-full bg-[var(--card-bg)] text-white p-8 md:p-10 rounded-xl shadow-2xl border-t-8 border-[var(--primary-action)] space-y-8">
            
            <div class="marquee-container">
                <div class="marquee-text">AURA OPERATIONAL AI | SYSTEM STATUS | COMMAND ONLINE |</div>
            </div>

            <div class="text-center space-y-3">
                <h1 class="text-4xl font-extrabold text-[var(--primary-action)] tracking-tight">
                    AURA OPERATIONAL AI
                </h1>
                <p class="text-xl text-gray-300">
                    The core system designated to maintain Command integrity.
                </p>
                <span class="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium {status_color} text-white">
                    <svg class="w-2 h-2 mr-1.5" fill="currentColor" viewBox="0 0 8 8">
                        <circle cx="4" cy="4" r="3" />
                    </svg>
                    System Status: {status_text}
                </span>
            </div>

            <div class="text-center">
                <a href="{DISCORD_INVITE_LINK}" target="_blank"
                   class="inline-block w-full sm:w-auto px-8 py-3 text-lg font-bold rounded-lg transition duration-300 btn-primary shadow-xl">
                    Connect to Server Network 🌐
                </a>
            </div>
            
            <hr class="border-gray-700">

            <div class="space-y-4">
                <h2 class="text-2xl font-semibold text-gray-200">🛡️ Protocol Enforcement</h2>
                <ul class="space-y-3 text-gray-400">
                    <li class="flex items-start">
                        <span class="text-[var(--primary-action)] mr-2 mt-0.5">📜</span>
                        <p><strong>Total Accountability:</strong> All staff actions are logged to the **Permanent Record** for security audits.</p>
                    </li>
                    <li class="flex items-start">
                        <span class="text-[var(--primary-action)] mr-2 mt-0.5">🔨</span>
                        <p><strong>Auto-Eviction Enforcement:</strong> The system automatically blocks attempts to evade permanent blacklisting.</p>
                    </li>
                </ul>
            </div>
            
            <hr class="border-gray-700">
            
            <div class="space-y-4">
                <h2 class="text-2xl font-semibold text-gray-200">🔗 Auxiliary Systems</h2>
                <ul class="space-y-3 text-gray-400">
                    {
                        ''.join([
                            f"""
                            <li class="flex justify-between items-center bg-gray-700/30 p-3 rounded-lg">
                                <span class="font-medium text-white">{link['name']}</span>
                                <a href="{link['url']}" target="_blank" class="text-[var(--primary-action)] hover:underline">
                                    Access System &rarr;
                                </a>
                            </li>
                            """ for link in AURA_LINKS
                        ])
                    }
                </ul>
            </div>

            <hr class="border-gray-700">

            <div class="text-center text-sm text-gray-500 space-y-2">
                <p>
                    <a href="/admin" class="hover:text-[var(--primary-action)] transition text-gray-600 font-medium border-b border-dotted border-gray-600">Root Access Terminal Login</a>
                </p>
            </div>
            
        </div>
    </body>
    </html>
    """
    
    return render_template_string(html_content)

if __name__ == '__main__':
    # For local testing only
    if os.getenv('DISCORD_BOT_TOKEN'):
        print("Running Flask server locally...")
        app.run(host='0.0.0.0', port=os.environ.get('PORT', 5000))
    else:
        print("ERROR: DISCORD_BOT_TOKEN environment variable not set. Please set it for local testing.")