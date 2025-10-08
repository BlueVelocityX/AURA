import os
from flask import Flask, render_template_string
import threading
import asyncio # <-- Added missing import
from bot_logic import bot 
from admin_dashboard import admin_bp 

# --- CONFIGURATION ---
# Example social links used in the landing page template
DISCORD_SOCIAL_LINKS = [
    ("Twitter", "https://twitter.com/YourHandle"),
    ("Instagram", "https://instagram.com/YourHandle"),
    ("Patreon", "https://patreon.com/YourPage")
]

app = Flask(__name__)

# Register the admin blueprint and protect it behind the /admin URL prefix.
app.register_blueprint(admin_bp, url_prefix='/admin')

# --- START BOT IN A SEPARATE THREAD (For 24/7 Hosting) ---

def start_discord_bot():
    """
    Function to run the Discord bot's blocking client method safely in a thread.
    
    NOTE: This uses bot.start/loop.run_until_complete to safely run the bot in 
    a separate thread, avoiding the fatal "RuntimeError: can't register atexit after shutdown".
    """
    print("--- Aura Manager: Starting Discord Bot Thread -----")
    try:
        # 1. Create a new event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # 2. Use bot.start() to run the bot and run_until_complete to block the thread
        token = os.getenv('DISCORD_BOT_TOKEN')
        if not token:
            print("ERROR: DISCORD_BOT_TOKEN is missing. Bot will not start.")
            return

        loop.run_until_complete(bot.start(token, reconnect=True))

    except Exception as e:
        print(f"FATAL ERROR IN DISCORD BOT THREAD: {e}")

print("--- Gunicorn Worker Booted, Initiating Bot Startup ---")
# Only start the thread if the bot token is available
if os.getenv('DISCORD_BOT_TOKEN'):
    discord_thread = threading.Thread(target=start_discord_bot)
    discord_thread.daemon = True 
    discord_thread.start()
else:
    print("WARNING: DISCORD_BOT_TOKEN is not set. Discord bot thread skipped.")


# --- FLASK ROUTES ---

@app.route('/')
def index():
    """
    Renders the public-facing landing page for the Aura (Treehouse Hangout) Bot.
    """
    # Using Tailwind-like classes and custom CSS variables for styling
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Aura Bot - Treehouse Hangout</title>
        <!-- Load Tailwind CSS via CDN -->
        <script src="https://cdn.tailwindcss.com"></script>
        <!-- Custom Styling for the "Treehouse Hangout" vibe -->
        <style>
            :root {{
                --primary-color: #6D9C8D; /* Soft Green/Mint */
                --secondary-color: #F7E7CD; /* Cream/Beige */
                --danger-color: #E63946; /* Soft Red */
                --font-family: 'Inter', sans-serif;
            }}
            body {{
                font-family: var(--font-family);
                background-color: #1a202c; /* Dark background */
                color: #e2e8f0; /* Light text */
            }}
            .card {{
                background-color: #2D3748; /* Slightly lighter dark card */
                box-shadow: 0 10px 15px rgba(0, 0, 0, 0.5);
                border: 1px solid #4A5568;
            }}
            .btn {{
                background-color: var(--primary-color);
                color: #1a202c;
                transition: background-color 0.3s;
            }}
            .btn:hover {{
                background-color: #8EB8AD;
            }}
        </style>
    </head>
    <body class="flex items-center justify-center min-h-screen p-4">
        <div class="card w-full max-w-lg p-8 rounded-xl space-y-8">
            
            <!-- Header -->
            <header class="text-center space-y-2">
                <h1 class="text-4xl font-extrabold text-white">🌳 Aura Bot</h1>
                <p class="text-xl font-light text-gray-400">The Caretaker of your Treehouse Hangout</p>
                <div class="inline-block p-2 bg-gray-700 rounded-lg text-sm font-mono text-gray-300">
                    Prefix: <span class="text-var(--primary-color)">!</span>
                </div>
            </header>

            <hr class="border-gray-700">

            <!-- Description -->
            <section class="space-y-4 text-center">
                <h2 class="text-2xl font-semibold text-white">What I Do</h2>
                <p class="text-gray-400">
                    I am here to ensure your cozy, friends-only server remains a safe and chill space. I handle quiet moderation,
                    track essential activity metrics, and help set the atmosphere with the **!vibe** command.
                </p>
                <p class="text-gray-400">
                    Think of me as your gentle Co-Host, keeping the vibes immaculate and the spam out.
                </p>
            </section>

            <!-- Key Commands Highlight -->
            <section class="p-4 bg-gray-800 rounded-lg space-y-3">
                <h3 class="text-xl font-semibold text-center text-white">Quick Access</h3>
                <div class="space-y-2">
                    <p class="font-mono bg-gray-900 p-2 rounded-md text-sm">
                        <span class="text-var(--primary-color)">!vibe</span> [topic] - Set the mood with a fun, AI-generated response.
                    </p>
                    <p class="font-mono bg-gray-900 p-2 rounded-md text-sm">
                        <span class="text-var(--primary-color)">!flag</span> @Guest [reason] - Discreetly report a concern to staff.
                    </p>
                    <a href="/admin" class="block btn text-center py-2 px-4 rounded-lg font-bold">
                        Staff: View Caretaker Log
                    </a>
                </div>
            </section>
            
            <hr class="border-gray-700">

            <!-- Social Links -->
            <div class="space-y-4">
                <p class="text-center text-gray-500 font-medium">Find the Community:</p>
                <ul class="flex justify-center space-x-6 text-xl">
                    <!-- Dynamic Links Block - CORRECTED PYTHON SYNTAX -->
                    {'\n'.join([
                        f"<li><a href='{url}' target='_blank' class='hover:text-[var(--primary-color)] transition'>{name}</a></li>"
                        for name, url in DISCORD_SOCIAL_LINKS
                    ])}
                </ul>
            </div>


            <hr class="border-gray-700">

            <!-- Legal and Important Notice -->
            <div class="text-center text-sm text-gray-500 space-y-2">
                <p class="text-red-400 font-bold">⚠️ AGE RESTRICTION: ALL PLATFORMS ARE STRICTLY 18+</p>
                <p>
                    <a href="#" target="_blank" class="hover:text-[var(--danger-color)] transition">Privacy Policy</a> | 
                    <a href="#" target="_blank" class="hover:text-[var(--danger-color)] transition">Terms of Service</a>
                </p>
                <!-- Admin link is discreetly placed for staff access -->
                <p>Staff: <a href="/admin" class="hover:text-[var(--danger-color)] transition text-gray-600 font-medium border-b border-dotted border-gray-600">Admin Portal Login</a></p>
            </div>
            
        </div>
    </body>
    </html>
    """
    
    return render_template_string(html_content)

if __name__ == '__main__':
    # This block is for local testing only (Gunicorn ignores this in production).
    if os.getenv('DISCORD_BOT_TOKEN'):
        print("Running Flask server locally...")
        app.run(host='0.0.0.0', port=os.environ.get('PORT', 5000))
    else:
        # Run without bot thread if token is missing (for local dev/testing the web part)
        print("Running Flask server locally without Discord bot (DISCORD_BOT_TOKEN missing).")
        app.run(host='0.0.0.0', port=os.environ.get('PORT', 5000))