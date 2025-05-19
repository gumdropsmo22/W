import os
import threading
import logging
from flask import Flask, jsonify

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('wilhelmina.log')
    ]
)
log = logging.getLogger('web')

# Bot thread function
def run_discord_bot():
    import asyncio
    import bot

    # Create a new event loop for the bot thread
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # Start the bot
    bot.run_bot()

# Start bot in a separate thread
bot_thread = None

@app.route('/')
def index():
    """Landing page for the bot's web interface"""
    return jsonify({
        "status": "online",
        "bot_name": "Wilhelmina",
        "description": "A sassy witch Discord bot with magical features"
    })

@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({"status": "healthy"})

# Start the bot when the Flask app is initialized if a token is available
if not os.environ.get("WEB_ONLY", False) and os.environ.get("DISCORD_TOKEN"):
    bot_thread = threading.Thread(target=run_discord_bot, daemon=True)
    bot_thread.start()
    log.info("Discord bot started in background thread")
else:
    log.warning("Discord bot not started - no token provided or web-only mode enabled")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
