import os
from flask import Flask, render_template_string
import threading
from bot_logic import bot 
from admin_dashboard import admin_bp 
import asyncio # Must be imported for thread setup

app = Flask(__name__)

# Register the admin blueprint and protect it behind the /admin URL prefix.
app.register_blueprint(admin_bp, url_prefix='/admin')

# --- START BOT IN A SEPARATE THREAD (For 24/7 Hosting) ---

def start_discord_bot():
    """
    Function to run the Discord bot's blocking client method safely in a thread.
    """
    print("--- Aura Hangout: Starting Discord Bot Thread -----")
    try:
        # 1. Create a new event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # 2. Use bot.start() to run the bot and run_until_complete to block the thread
        loop.run_until_complete(bot.start(os.getenv('DISCORD_BOT_TOKEN'), reconnect=True))

    except Exception as e:
        print(f"FATAL ERROR IN DISCORD BOT THREAD: {e}")


print("--- Gunicorn Worker Booted, Initiating Bot Startup ---")
# The bot runs in a background thread to prevent blocking the Flask web server.
discord_thread = threading.Thread(target=start_discord_bot)
discord_thread.daemon = True 
discord_thread.start()


# --- FLASK WEB SERVER ROUTES ---

# Replace with your actual external links
EXTERNAL_LINKS = [
    {"name": "Guestbook (House Rules)", "url": "#"},
    {"name": "Utility Shed (!commands)", "url": "#"},
    {"name": "Invite a Friend", "url": "#"},
]

def get_discord_invite_link():
    """Dummy function to provide a mock invite link for the template."""
    # In a real app, this would be retrieved dynamically if available, or just a known link
    return "https://discord.gg/your-invite-link"

@app.route('/')
def home():
    """The public landing page for the Hangout."""
    
    # Check if the bot is ready
    if bot.is_ready():
        status_text = "Online and Cozy"
        status_color = "bg-green-500"
    else:
        status_text = "Tuning In..."
        status_color = "bg-yellow-500"
        
    invite_link = get_discord_invite_link()

    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>The Treehouse Hangout</title>
        <!-- Load Tailwind CSS -->
        <script src="https://cdn.tailwindcss.com"></script>
        <style>
            :root {{
                --background-color: #1a1a2e; /* Dark, cozy night sky */
                --text-color: #e0e0f0; /* Soft light text */
                --primary-color: #a8dadc; /* Soft cyan/mint for highlights */
                --primary-action: #457b9d; /* Deeper blue for main buttons */
                --danger-color: #e63946; /* Red for warnings/bans */
                --font-inter: 'Inter', sans-serif;
            }}
            body {{
                font-family: var(--font-inter);
                background-color: var(--background-color);
                color: var(--text-color);
                display: flex;
                justify-content: center;
                align-items: center;
                min-height: 100vh;
                padding: 1rem;
            }}
            .card {{
                background-color: rgba(36, 36, 58, 0.8); /* Darker, transparent base for card */
                backdrop-filter: blur(5px);
                border: 2px solid var(--primary-color);
                box-shadow: 0 4px 6px rgba(0, 0, 0, 0.5);
            }}
            .btn-primary {{
                background-color: var(--primary-action);
                transition: background-color 0.2s;
            }}
            .btn-primary:hover {{
                background-color: #2a5a75;
            }}
        </style>
    </head>
    <body>
        <div class="card p-8 sm:p-10 max-w-lg w-full rounded-xl space-y-8">
            
            <!-- Header & Status -->
            <div class="text-center space-y-3">
                <h1 class="text-4xl font-extrabold text-[var(--primary-action)] tracking-tight">
                    THE TREEHOUSE HANGOUT
                </h1>
                <p class="text-xl text-gray-300">
                    Your personal space to chill and connect.
                </p>
                <span class="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium {status_color} text-white">
                    <svg class="w-2 h-2 mr-1.5" fill="currentColor" viewBox="0 0 8 8">
                        <circle cx="4" cy="4" r="3" />
                    </svg>
                    Aura Status: {status_text}
                </span>
            </div>

            <!-- Join Button -->
            <div class="text-center">
                <a href="{invite_link}" target="_blank" class="btn-primary inline-flex items-center justify-center w-full sm:w-auto px-6 py-3 border border-transparent text-base font-medium rounded-lg shadow-lg text-white hover:shadow-xl transition duration-150 ease-in-out">
                    <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20v-2c0-.656-.126-1.283-.356-1.857M17 20h-2m0 0h-2M4 12v-2a3 3 0 014-3h10a3 3 0 014 3v2m-19 2h2.238l.608 1.127a1 1 0 001.764 0l.608-1.127H20M5 16h14" />
                    </svg>
                    Climb Up to the Treehouse!
                </a>
            </div>

            <!-- Quick Links -->
            <div class="pt-4">
                <h3 class="text-lg font-semibold border-b border-gray-700 pb-2 mb-4 text-gray-200">Quick Links</h3>
                <ul class="space-y-2">
                    {[
                        (link for link in EXTERNAL_LINKS) 
                    ].map(link => `
                        <li>
                            <a href="${link.url}" target="_blank" class="flex items-center text-gray-400 hover:text-[var(--primary-color)] transition">
                                <span class="mr-2 text-[var(--primary-color)]">•</span>
                                ${link.name}
                            </a>
                        </li>
                    `).join('')}
                </ul>
            </div>


            <hr class="border-gray-700">

            <!-- Legal and Important Notice -->
            <div class="text-center text-sm text-gray-500 space-y-2">
                <p class="text-gray-400 font-bold">Aura (The Caretaker) is running the server operations.</p>
                <!-- Admin link is discreetly placed for staff access -->
                <p>Host Access: <a href="/admin" class="hover:text-[var(--primary-action)] transition text-gray-600 font-medium border-b border-dotted border-gray-600">Caretaker Log-in</a></p>
            </div>
            
        </div>
    </body>
    </html>
    """
    
    return render_template_string(html_content)

if __name__ == '__main__':
    # This block is for local testing only
    if os.getenv('DISCORD_BOT_TOKEN'):
        print("Running Flask server locally...")
        app.run(host='0.0.0.0', port=os.environ.get('PORT', 5000))
    else:
        print("ERROR: DISCORD_BOT_TOKEN not set. Cannot start bot thread.")